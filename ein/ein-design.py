#!/usr/bin/env python3
"""Ein Design Pipeline — SeleniumBase browser automation for design synthesis.

Design pipeline (same conversation per engine throughout):
  Phase 1 (draft)       — upload source files, produce full design document
  Phase 2 (cross_review)— review one other engine's draft with an assigned lens
  Phase 3a (dispute_1)  — first dispute resolution round
  Phase 3b (dispute_2)  — second dispute resolution round (remaining disputes only)
  Phase 4 (assembly)    — facilitator only, no LLM round

Key differences from ein-selenium.py:
  - No new_chat() after Phase 1 — all phases continue in the same conversation
  - Claude Continue watchdog — handles mid-response "Continue" prompts
  - Phase 1.5 replaced with design-specific cross-review lenses
  - --resume flag — navigates to existing conversations by title (skips Phase 1)
  - Source tagging on responses — "inline" vs "file"

Usage:
    python ein-design.py                         # Full run from Phase 1
    python ein-design.py --resume LEDGER_PATH    # Resume from Phase 2 using existing conversations
    python ein-design.py --only chatgpt          # Single-engine test (Phase 1 only)
    python ein-design.py --phase draft           # Single phase
"""

import importlib.util, json, os, sys, time, threading, argparse
from pathlib import Path
from datetime import datetime, timezone

# ── WMI hang bypass ──────────────────────────────────────────────────────────
# platform.machine() → platform.uname() → _wmi_query() can hang for minutes
# when the WMI service is slow (e.g. after killing many processes). Pre-cache
# the uname result using env vars to avoid WMI entirely.
def _patch_platform_wmi_bypass():
    import platform as _p, os as _o
    if getattr(_p, '_uname_cache', None) is None:
        _arch = _o.environ.get('PROCESSOR_ARCHITECTURE', 'AMD64')
        _m = {'AMD64': 'AMD64', 'x86': 'x86', 'ARM64': 'ARM64'}.get(_arch, 'AMD64')
        _p._uname_cache = _p.uname_result(
            'Windows', _o.environ.get('COMPUTERNAME', 'localhost'),
            '10', '10.0', _m,
        )
_patch_platform_wmi_bypass()
del _patch_platform_wmi_bypass

_clipboard_lock = threading.Lock()

# Snapshot of the user's Chrome PIDs taken at import time — before we launch anything.
# Used by kill_automation_chrome() to never touch the user's personal browser.
try:
    import subprocess as _sp, json as _json
    _r = _sp.run(
        ["powershell.exe", "-Command",
         r"Get-WmiObject Win32_Process | Where-Object { $_.Name -eq 'chrome.exe' -and "
         r"(-not $_.CommandLine -or $_.CommandLine -notlike '*chrome-automation-profile*') } | "
         r"Select-Object ProcessId | ConvertTo-Json -Compress"],
        capture_output=True, text=True, timeout=15
    )
    _procs = _json.loads(_r.stdout or "[]")
    if isinstance(_procs, dict):
        _procs = [_procs]
    _INITIAL_USER_CHROME_PIDS: set = {int(p["ProcessId"]) for p in _procs if "ProcessId" in p}
except Exception:
    _INITIAL_USER_CHROME_PIDS: set = set()


def clipboard_copy(text, retries=20, delay=0.3):
    """Thread-safe clipboard copy using ctypes directly.

    pyperclip raises on WinError 0 ("completed successfully") which is a
    spurious failure when Chrome briefly holds the clipboard. We use the raw
    Win32 API with retries to work around it.
    """
    import ctypes
    import ctypes.wintypes

    CF_UNICODETEXT = 13
    GMEM_MOVEABLE = 0x0002

    encoded = (text + '\0').encode('utf-16-le')
    size = len(encoded)

    with _clipboard_lock:
        for attempt in range(retries):
            try:
                if not ctypes.windll.user32.OpenClipboard(0):
                    if attempt < retries - 1:
                        time.sleep(delay)
                        continue
                    raise RuntimeError("OpenClipboard failed after retries")
                try:
                    ctypes.windll.user32.EmptyClipboard()
                    h = ctypes.windll.kernel32.GlobalAlloc(GMEM_MOVEABLE, size)
                    p = ctypes.windll.kernel32.GlobalLock(h)
                    ctypes.memmove(p, encoded, size)
                    ctypes.windll.kernel32.GlobalUnlock(h)
                    ctypes.windll.user32.SetClipboardData(CF_UNICODETEXT, h)
                finally:
                    ctypes.windll.user32.CloseClipboard()
                return  # success
            except RuntimeError:
                raise
            except Exception:
                if attempt < retries - 1:
                    time.sleep(delay)
                else:
                    raise

os.chdir(r"C:\Users\chris\PROJECTS")

from seleniumbase import Driver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains

# ── Import ein-design-ledger ──────────────────────────────────────────────────

_LEDGER_PATH = Path(__file__).parent / "ein-design-ledger.py"
_spec = importlib.util.spec_from_file_location("ein_design_ledger", _LEDGER_PATH)
_ledger_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_ledger_mod)

_create_ledger      = _ledger_mod.create_ledger
_append_phase       = _ledger_mod.append_phase
_save_ledger        = _ledger_mod._save
_set_registry       = _ledger_mod.set_conversation_registry
_get_other_two      = _ledger_mod.get_other_two
_source_phase_for   = _ledger_mod.source_phase_for
_status             = _ledger_mod.status

# ── Config ────────────────────────────────────────────────────────────────────

PROFILES = {
    "chatgpt": r"C:\Users\chris\PROJECTS\chrome-automation-profile",
    "gemini":  r"C:\Users\chris\PROJECTS\chrome-automation-profile-2",
    "claude":  r"C:\Users\chris\PROJECTS\chrome-automation-profile-3",
}
PHASE_TIMEOUT = 900        # 15 min — thinking models are slow on large documents
LOG_PREFIX    = "[ein-d]"
DOWNLOAD_DIR  = r"C:\Users\chris\PROJECTS\downloaded_files"

# ── Helpers ───────────────────────────────────────────────────────────────────

def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"{LOG_PREFIX} {ts} {msg}", flush=True)


def clean_locks(profile_dir):
    crash_files = {"CrashpadMetrics-active.pma", "CrashpadMetrics.pma"}
    for root, dirs, files in os.walk(profile_dir):
        for f in files:
            if f in ["LOCK", "lockfile", "SingletonLock"] or f in crash_files:
                try: os.remove(os.path.join(root, f))
                except: pass


def _get_user_chrome_pids():
    """Return PIDs of Chrome processes NOT using automation profiles.
    Called once at startup to build a protected set.
    """
    import subprocess
    result = subprocess.run([
        "powershell.exe", "-Command",
        r"Get-WmiObject Win32_Process | Where-Object { $_.Name -eq 'chrome.exe' } | "
        r"Select-Object ProcessId, CommandLine | ConvertTo-Json -Compress"
    ], capture_output=True, text=True, timeout=15)
    pids = set()
    try:
        procs = json.loads(result.stdout or "[]")
        if isinstance(procs, dict):
            procs = [procs]
        for p in procs:
            cl = (p.get("CommandLine") or "")
            if "chrome-automation-profile" not in cl:
                pids.add(int(p["ProcessId"]))
    except Exception:
        pass
    return pids

# PIDs of the user's Chrome windows at script start — NEVER kill these.
_PROTECTED_CHROME_PIDS: set = set()

def kill_automation_chrome():
    """Kill only Chrome instances using automation profiles, never touching the user's browser."""
    import subprocess
    protected = _INITIAL_USER_CHROME_PIDS | _PROTECTED_CHROME_PIDS
    # Build a filter that excludes protected PIDs and requires automation profile in command line
    pid_exclusion = " -and ".join(
        f"$_.ProcessId -ne {pid}" for pid in protected
    ) if protected else "$true"
    cmd = (
        r"Get-WmiObject Win32_Process | Where-Object { $_.Name -eq 'chrome.exe' -and "
        r"$_.CommandLine -like '*chrome-automation-profile*' -and "
        + pid_exclusion +
        r" } | ForEach-Object { $_.Terminate() }"
    )
    subprocess.run(["powershell.exe", "-Command", cmd],
                   capture_output=True, timeout=15)
    log("Killed stale automation Chrome instances (user browser protected)")
    time.sleep(2)


# ── Download resolution ───────────────────────────────────────────────────────

def resolve_downloads(driver, engine_name, last_message_selector=None, wait=25):
    """Scan ONLY THE LAST ASSISTANT MESSAGE for download links, click them, read files.

    Scoped to the last message to avoid re-downloading artifacts from prior phases.
    Called ONCE per phase after stability is confirmed — NOT on every poll.

    Returns (file_contents: str, source: str).
    """
    import glob as _glob

    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    before = set(_glob.glob(os.path.join(DOWNLOAD_DIR, "*")))

    clicked = driver.execute_script(r"""
        const FILE_EXT = /\.(docx?|xlsx?|pdf|md|txt|csv|json|zip)(\s|$|\))/i;
        const sel = arguments[0];

        // Find the last assistant message container to scope the search
        let scope = document;
        if (sel) {
            const els = document.querySelectorAll(sel);
            if (els.length) scope = els[els.length - 1];
        }

        const candidates = new Set();
        scope.querySelectorAll(
            'a[download], a[href*="blob:"], a[href*="/files/"], a[href*="oaiusercontent"]'
        ).forEach(el => { if (el.offsetParent !== null) candidates.add(el); });

        scope.querySelectorAll('button, a, [role="button"]').forEach(el => {
            if (el.offsetParent === null) return;
            const label = (el.getAttribute('aria-label') || el.getAttribute('title') || el.innerText || '').toLowerCase();
            if (label.includes('download') || label.includes('télécharger')) candidates.add(el);
        });

        scope.querySelectorAll('button, [role="button"]').forEach(el => {
            if (el.offsetParent === null) return;
            if (FILE_EXT.test((el.innerText || '').trim())) candidates.add(el);
        });

        const clicked = [];
        candidates.forEach(el => {
            try { el.click(); clicked.push(el.innerText.trim().slice(0, 60)); } catch(e) {}
        });
        return clicked;
    """, last_message_selector)

    if not clicked:
        return "", "inline"

    log(f"  [{engine_name}] {len(clicked)} download element(s) clicked")

    contents = []
    deadline = time.time() + wait
    while time.time() < deadline:
        time.sleep(1)
        import glob as _glob
        after     = set(_glob.glob(os.path.join(DOWNLOAD_DIR, "*")))
        new_files = [f for f in (after - before) if not f.endswith(".crdownload")]
        if new_files:
            for fpath in sorted(new_files):
                try:
                    text = Path(fpath).read_text(encoding="utf-8", errors="replace")
                    log(f"  [{engine_name}] downloaded: {Path(fpath).name} ({len(text)} chars)")
                    contents.append(text)
                except Exception as e:
                    log(f"  [{engine_name}] could not read {fpath}: {e}")
            break

    return "\n\n".join(contents), "file"


# ── Prompt-file helper ───────────────────────────────────────────────────────

def write_prompt_file(text, phase_label="prompt"):
    """Write prompt text to a clearly-labelled temp file for upload.

    The file starts with a header so it cannot be confused with source/design
    files that are also attached in the same conversation.
    """
    import tempfile
    header = (
        f"=== PROMPT ===\n"
        f"This file contains your next task. Read it carefully and respond as instructed inside.\n"
        f"{'=' * 60}\n\n"
    )
    tmp = tempfile.NamedTemporaryFile(
        mode='w', suffix='.txt', delete=False,
        prefix=f'ein_prompt_{phase_label}_',
        encoding='utf-8', dir=DOWNLOAD_DIR
    )
    tmp.write(header + text)
    tmp.close()
    return tmp.name


# ── Streaming helpers ─────────────────────────────────────────────────────────

def wait_for_streaming(driver, stop_selector, timeout=PHASE_TIMEOUT, stable_secs=6):
    """Wait for streaming to start then finish.

    stable_secs: how many consecutive seconds the stop button must be absent
    before we declare done. This handles tool-use pauses where the stop button
    disappears briefly between tool calls.
    """
    for _ in range(30):
        time.sleep(1)
        if driver.find_elements(By.CSS_SELECTOR, stop_selector):
            break
    absent_for = 0
    for i in range(timeout):
        time.sleep(1)
        if driver.find_elements(By.CSS_SELECTOR, stop_selector):
            absent_for = 0  # stop button visible — still streaming
        else:
            absent_for += 1
            if absent_for >= stable_secs:
                return i + 1
    return timeout


# ── Global session watchdog ───────────────────────────────────────────────────

def start_session_watchdog(engines_ref, stop_event, interval=12):
    """Global watchdog that runs for the entire pipeline lifetime.

    Checks every `interval` seconds:
    - Claude: clicks the 'Continue' button if it appears mid-response
    - All engines: pings the browser session and logs a warning if it has gone dead

    Args:
        engines_ref: a list that is mutated in-place as engines come and go.
                     The watchdog always reads the current contents.
        stop_event:  threading.Event — set this to stop the watchdog at pipeline end.
        interval:    poll interval in seconds (default 12)
    """
    import datetime as _dt

    def _watchdog():
        while not stop_event.is_set():
            ts = _dt.datetime.now().strftime("%H:%M:%S")
            for engine in list(engines_ref):
                try:
                    if engine.name == "claude":
                        clicked = engine.driver.execute_script("""
                            const btn = Array.from(document.querySelectorAll('button'))
                                .find(el =>
                                    el.offsetParent !== null &&
                                    el.innerText.trim().toLowerCase() === 'continue'
                                );
                            if (btn) { btn.click(); return true; }
                            return false;
                        """)
                        if clicked:
                            print(f"{LOG_PREFIX} {ts}   [watchdog] clicked Continue on claude",
                                  flush=True)
                    else:
                        # Lightweight ping — just read the current URL
                        _ = engine.driver.current_url
                except Exception as e:
                    print(f"{LOG_PREFIX} {ts}   [watchdog] WARNING: {engine.name} browser "
                          f"may be unresponsive — {type(e).__name__}", flush=True)
            stop_event.wait(interval)

    t = threading.Thread(target=_watchdog, daemon=True)
    t.start()
    return t


# ── Engine classes ────────────────────────────────────────────────────────────

class ChatGPTEngine:
    # Extended thinking uses both "Stop" and "Stop streaming" variants
    STOP_SEL = (
        'button[aria-label="Stop streaming"], button[data-testid="stop-button"], '
        'button[aria-label="Stop"], button[aria-label="Stop generating"]'
    )

    def __init__(self, driver, model_target="thinking"):
        self.driver       = driver
        self.name         = "chatgpt"
        self._model_target = model_target
        self._model_name  = model_target

    def screenshot(self, label):
        path = f"ein_d_chatgpt_{label}.png"
        self.driver.save_screenshot(path)
        log(f"  [chatgpt] screenshot: {path}")

    def new_chat(self):
        self.driver.get("https://chatgpt.com")
        time.sleep(4)

    def navigate_to(self, title: str):
        """Navigate to an existing conversation by sidebar title."""
        found = self.driver.execute_script("""
            const links = Array.from(document.querySelectorAll('a'));
            const match = links.find(el =>
                el.textContent.trim().toLowerCase().includes(arguments[0].toLowerCase())
            );
            if (match) { match.click(); return match.textContent.trim().slice(0,80); }
            return null;
        """, title)
        time.sleep(5)
        log(f"  [chatgpt] navigated to: {found}")
        return found

    def get_conversation_url(self) -> str:
        return self.driver.current_url

    def select_model(self, target=None):
        d = self.driver
        target = (target or self._model_target).lower()
        try:
            d.find_element(By.CSS_SELECTOR, 'button[aria-label="Model selector"]').click()
            time.sleep(1)
            clicked = d.execute_script("""
                const target = arguments[0];
                const items  = Array.from(document.querySelectorAll(
                    '[role="option"],[role="menuitem"],[role="menuitemradio"],li,button'));
                const match  = items.find(el => {
                    const t = (el.textContent || '').toLowerCase();
                    return t.includes(target) && el.offsetParent !== null;
                });
                if (match) { match.click(); return match.textContent.trim(); }
                return null;
            """, target)
            time.sleep(1)
            log(f"  [chatgpt] model: {(clicked or 'not found')[:60]}")
            self._model_name = clicked or target
        except Exception as e:
            log(f"  [chatgpt] model select failed: {e}")

    def upload_files(self, *filepaths):
        d = self.driver
        abs_paths = "\n".join(
            str(Path(p).resolve()) for p in filepaths if Path(p).exists()
        )
        if not abs_paths:
            log(f"  [chatgpt] WARNING: no valid files to upload")
            return False

        d.execute_script("""
            const ta = document.querySelector('#prompt-textarea');
            if (!ta) return;
            const attach = ta.closest('form')?.querySelector('input[type="file"]')
                        || document.querySelector('input[type="file"]');
            if (attach) attach.style.display = 'block';
        """)
        time.sleep(0.5)
        try:
            inp = d.find_element(By.CSS_SELECTOR, 'input[type="file"]')
            inp.send_keys(abs_paths)
            time.sleep(3)
            names = ", ".join(Path(p).name for p in filepaths if Path(p).exists())
            log(f"  [chatgpt] uploaded: {names}")
            return True
        except Exception as e:
            log(f"  [chatgpt] upload failed: {e}")
            return False

    def send_file_and_wait(self, text, phase_label="prompt", timeout=PHASE_TIMEOUT):
        """Always upload prompt as a file instead of pasting into chat."""
        import os as _os
        tmp_path = write_prompt_file(text, phase_label)
        log(f"  [chatgpt] uploading prompt as file: {_os.path.basename(tmp_path)}")
        d = self.driver
        d.execute_script("""
            const ta = document.querySelector('#prompt-textarea');
            if (!ta) return;
            const attach = ta.closest('form')?.querySelector('input[type="file"]')
                        || document.querySelector('input[type="file"]');
            if (attach) attach.style.display = 'block';
        """)
        time.sleep(0.5)
        try:
            inp = d.find_element(By.CSS_SELECTOR, 'input[type="file"]')
            inp.send_keys(tmp_path)
            time.sleep(4)
        except Exception as e:
            log(f"  [chatgpt] file upload failed: {e} — falling back to send_and_wait")
            _os.unlink(tmp_path)
            return self.send_and_wait(text, timeout)
        fname = _os.path.basename(tmp_path)
        trigger = f"Your prompt for this round is in the attached file: {fname}"
        ta = d.find_element(By.CSS_SELECTOR, "#prompt-textarea")
        ta.click()
        time.sleep(0.3)
        d.execute_script("arguments[0].focus(); document.execCommand('insertText',false,arguments[1]);", ta, trigger)
        time.sleep(0.5)
        submitted = d.execute_script("""
            const btn = document.querySelector("button[data-testid='send-button']");
            if (btn && !btn.disabled) { btn.click(); return true; } return false;
        """)
        if not submitted:
            ta.send_keys(Keys.RETURN)
        result = wait_for_streaming(d, self.STOP_SEL, timeout)
        try: _os.unlink(tmp_path)
        except Exception: pass
        return result

    def send_and_wait(self, text, timeout=PHASE_TIMEOUT):
        """Send text and wait for response.

        For large prompts (>20k chars) on conversations with deep history,
        execCommand insertText times out because ProseMirror re-renders the
        entire conversation DOM on each JS call. We work around this by
        writing the prompt to a temp file and uploading it, then sending a
        short trigger message asking ChatGPT to process the attachment.
        """
        import tempfile, os as _os

        d = self.driver
        FILE_THRESHOLD = 20000  # chars — use file upload above this

        if len(text) >= FILE_THRESHOLD:
            # ── Large prompt: write to temp .txt and upload ───────────────────
            tmp = tempfile.NamedTemporaryFile(
                mode='w', suffix='.txt', delete=False,
                prefix='ein_prompt_', encoding='utf-8',
                dir=DOWNLOAD_DIR
            )
            tmp.write(text)
            tmp.close()
            log(f"  [chatgpt] large prompt ({len(text)} chars) → uploading as file: {tmp.name}")

            # Upload the file
            d.execute_script("""
                const ta = document.querySelector('#prompt-textarea');
                if (!ta) return;
                const attach = ta.closest('form')?.querySelector('input[type="file"]')
                            || document.querySelector('input[type="file"]');
                if (attach) attach.style.display = 'block';
            """)
            time.sleep(0.5)
            try:
                inp = d.find_element(By.CSS_SELECTOR, 'input[type="file"]')
                inp.send_keys(tmp.name)
                time.sleep(4)
                log(f"  [chatgpt] file uploaded: {_os.path.basename(tmp.name)}")
            except Exception as e:
                log(f"  [chatgpt] file upload failed: {e} — falling back to chunked paste")
                _os.unlink(tmp.name)
                # Fall through to chunked paste below
                text_to_paste = text
            else:
                # Send a short trigger message referencing the file
                trigger = "Process the attached file. Respond with your full revised document as specified inside it."
                ta = d.find_element(By.CSS_SELECTOR, "#prompt-textarea")
                ta.click()
                time.sleep(0.3)
                d.execute_script("""
                    const el = arguments[0], msg = arguments[1];
                    el.focus();
                    document.execCommand('insertText', false, msg);
                """, ta, trigger)
                time.sleep(0.5)
                submitted = d.execute_script("""
                    const btn = document.querySelector("button[data-testid='send-button']");
                    if (btn && !btn.disabled) { btn.click(); return true; }
                    return false;
                """)
                if not submitted:
                    ta.send_keys(Keys.RETURN)
                result = wait_for_streaming(d, self.STOP_SEL, timeout)
                try:
                    _os.unlink(tmp.name)
                except Exception:
                    pass
                return result

            # If upload failed, fall through with text_to_paste
        else:
            text_to_paste = text

        # ── Small/fallback prompt: chunked execCommand insert ─────────────────
        ta = d.find_element(By.CSS_SELECTOR, "#prompt-textarea")
        ta.click()
        time.sleep(0.3)
        d.set_script_timeout(90)
        CHUNK = 5000
        for chunk in [text_to_paste[i:i+CHUNK] for i in range(0, len(text_to_paste), CHUNK)]:
            d.execute_script("""
                const el = arguments[0], chunk = arguments[1];
                el.focus();
                document.execCommand('insertText', false, chunk);
            """, ta, chunk)
            time.sleep(0.15)
        time.sleep(1.0)
        actual_len = d.execute_script(
            "return (document.querySelector('#prompt-textarea') || {}).innerText?.length || 0;"
        )
        if actual_len < len(text_to_paste) * 0.8:
            log(f"  [chatgpt] WARNING: paste landed {actual_len}/{len(text_to_paste)} chars")

        submitted = d.execute_script("""
            const btn = document.querySelector("button[data-testid='send-button']");
            if (btn && !btn.disabled) { btn.click(); return true; }
            return false;
        """)
        if not submitted:
            ta.send_keys(Keys.RETURN)

        return wait_for_streaming(d, self.STOP_SEL, timeout)

    # Selector for scoping downloads to the last message only
    LAST_MSG_SEL = "[data-message-author-role='assistant']"

    def get_latest_response(self):
        """Returns (inline_text, 'inline') — no downloads. Used by stability loop."""
        els = self.driver.find_elements(By.CSS_SELECTOR, "[data-message-author-role='assistant']")
        return (els[-1].text if els else ""), "inline"

    def get_final_response(self):
        """Called once after stability confirmed. Checks for downloads in last message."""
        inline, _ = self.get_latest_response()
        downloaded, src = resolve_downloads(self.driver, self.name, self.LAST_MSG_SEL)
        if downloaded:
            return downloaded, "file"
        return inline, "inline"

    def model_name(self):
        return self._model_name or "Thinking"


class GeminiEngine:
    STOP_SEL = 'button[aria-label="Stop response"], button[aria-label="Stop generating"]'

    def __init__(self, driver, model_target="Pro"):
        self.driver        = driver
        self.name          = "gemini"
        self._model_target = model_target
        self._model_name   = model_target

    def screenshot(self, label):
        path = f"ein_d_gemini_{label}.png"
        self.driver.save_screenshot(path)
        log(f"  [gemini] screenshot: {path}")

    def new_chat(self):
        self.driver.get("https://gemini.google.com")
        time.sleep(4)

    def navigate_to(self, title: str):
        found = self.driver.execute_script("""
            const items = Array.from(document.querySelectorAll('a, li, nav *'));
            const match = items.find(el =>
                el.textContent.trim().toLowerCase().includes(arguments[0].toLowerCase())
            );
            if (match) { match.click(); return match.textContent.trim().slice(0,80); }
            return null;
        """, title)
        time.sleep(5)
        log(f"  [gemini] navigated to: {found}")
        return found

    def get_conversation_url(self) -> str:
        return self.driver.current_url

    def select_model(self, target=None):
        d      = self.driver
        target = target or self._model_target
        try:
            for btn in d.find_elements(By.TAG_NAME, "button"):
                if btn.is_displayed() and btn.text.strip() in (
                        "Pro", "Fast", "Thinking", "Flash", "Gemini 3", "Gemini"):
                    btn.click()
                    time.sleep(1.5)
                    break
            clicked = d.execute_script("""
                const target = arguments[0].toLowerCase();
                const items  = Array.from(document.querySelectorAll('[role="option"],[role="menuitem"],li'));
                const match  = items.find(el => {
                    if (!el.offsetParent) return false;
                    const first_line = (el.textContent || '').split('\\n')[0].trim();
                    // Match on first word only (e.g. "Pro" matches "Pro  Advanced math..."
                    // but NOT "Pro Thinking" or "2.0 Pro Thinking").
                    const first_word = first_line.split(/\\s+/)[0].toLowerCase();
                    return first_word === target;
                });
                if (match) { match.click(); return match.textContent.trim(); }
                return null;
            """, target)
            time.sleep(1)
            log(f"  [gemini] model: {(clicked or 'not found')[:60]}")
            self._model_name = clicked or target
        except Exception as e:
            log(f"  [gemini] model select failed: {e}")

    def upload_files(self, *filepaths):
        d = self.driver
        for filepath in filepaths:
            abs_path = str(Path(filepath).resolve())
            if not Path(filepath).exists():
                log(f"  [gemini] file not found: {filepath}")
                continue
            try:
                # Step 1: open the "+" input area menu (new-chat flow requires this)
                plus_btn = d.execute_script("""
                    const btns = Array.from(document.querySelectorAll('button, [role="button"]'));
                    return btns.find(b => {
                        const label = (b.getAttribute('aria-label') || '').toLowerCase();
                        return label.includes('input area menu') && b.offsetParent !== null;
                    }) || null;
                """)
                if plus_btn:
                    d.execute_script("arguments[0].click();", plus_btn)
                    time.sleep(1.5)

                # Step 2: click "Upload files" menu item via text-walk + ActionChains
                upload_el = d.execute_script("""
                    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
                    let node;
                    while (node = walker.nextNode()) {
                        if (node.textContent.trim() === 'Upload files') {
                            let el = node.parentElement;
                            for (let i = 0; i < 5; i++) {
                                if (!el) break;
                                const tag = el.tagName.toLowerCase();
                                const role = el.getAttribute('role') || '';
                                if (tag === 'button' || tag === 'a' || tag === 'li'
                                        || role === 'menuitem' || role === 'option'
                                        || role === 'button') {
                                    return el;
                                }
                                el = el.parentElement;
                            }
                            return node.parentElement;
                        }
                    }
                    return null;
                """)
                if upload_el:
                    ActionChains(d).move_to_element(upload_el).click().perform()
                    time.sleep(1.5)

                # Step 3: find and use input[type="file"]
                d.execute_script("""
                    document.querySelectorAll('input[type="file"]').forEach(i => {
                        i.style.display = 'block';
                        i.style.visibility = 'visible';
                        i.removeAttribute('hidden');
                    });
                """)
                inp = d.find_elements(By.CSS_SELECTOR, 'input[type="file"]')
                if inp:
                    inp[-1].send_keys(abs_path)
                    time.sleep(3)
                    log(f"  [gemini] uploaded: {Path(filepath).name}")
                else:
                    log(f"  [gemini] upload failed for {Path(filepath).name}: no file input found after menu click")
            except Exception as e:
                log(f"  [gemini] upload failed for {filepath}: {e}")

    def send_and_wait(self, text, timeout=PHASE_TIMEOUT):
        d = self.driver
        try:
            ta = d.find_element(By.CSS_SELECTOR, 'div[contenteditable="true"]')
        except Exception:
            log("  [gemini] ERROR: no input area found")
            return 0

        ta.click()
        time.sleep(0.3)
        d.execute_script("""
            const el = arguments[0], text = arguments[1];
            el.focus();
            document.execCommand('insertText', false, text);
        """, ta, text)
        time.sleep(0.5)

        submitted = d.execute_script("""
            const btns = Array.from(document.querySelectorAll('button'));
            const send = btns.find(b => {
                const l = (b.getAttribute('aria-label') || b.innerText || '').toLowerCase();
                return l.includes('send') && b.offsetParent !== null;
            });
            if (send) { send.click(); return true; }
            return false;
        """)
        if not submitted:
            ta.send_keys(Keys.RETURN)

        return wait_for_streaming(d, self.STOP_SEL, timeout)

    def send_file_and_wait(self, text, phase_label="prompt", timeout=PHASE_TIMEOUT):
        """Always upload prompt as a file instead of pasting into chat."""
        import os as _os
        tmp_path = write_prompt_file(text, phase_label)
        fname = _os.path.basename(tmp_path)
        log(f"  [gemini] uploading prompt as file: {fname}")
        self.upload_files(tmp_path)
        try: _os.unlink(tmp_path)
        except Exception: pass
        d = self.driver
        try:
            ta = d.find_element(By.CSS_SELECTOR, 'div[contenteditable="true"]')
        except Exception:
            log("  [gemini] ERROR: no input area for trigger message")
            return 0
        trigger = f"Your prompt for this round is in the attached file: {fname}"
        ta.click()
        time.sleep(0.3)
        d.execute_script("document.execCommand('insertText', false, arguments[0]);", trigger)
        time.sleep(0.5)
        submitted = d.execute_script("""
            const btns = Array.from(document.querySelectorAll('button'));
            const send = btns.find(b => (b.getAttribute('aria-label')||b.innerText||'').toLowerCase().includes('send') && b.offsetParent !== null);
            if (send) { send.click(); return true; } return false;
        """)
        if not submitted:
            ta.send_keys(Keys.RETURN)
        return wait_for_streaming(d, self.STOP_SEL, timeout)

    LAST_MSG_SEL = "model-response, .model-response-text, [data-response-index]"

    def get_latest_response(self):
        """Returns (inline_text, 'inline') — no downloads. Used by stability loop."""
        inline = self.driver.execute_script("""
            const msgs = Array.from(document.querySelectorAll(
                'model-response, .model-response-text, [data-response-index]'));
            if (msgs.length) return msgs[msgs.length - 1].innerText;
            const divs = Array.from(document.querySelectorAll('div')).filter(d => {
                const t = (d.innerText || '').trim();
                return t.length > 200 && !d.querySelector('div[contenteditable]');
            });
            return divs.length ? divs[divs.length - 1].innerText : '';
        """) or ""
        return inline, "inline"

    def get_final_response(self):
        """Called once after stability confirmed. Checks for downloads in last message."""
        inline, _ = self.get_latest_response()
        downloaded, src = resolve_downloads(self.driver, self.name, self.LAST_MSG_SEL)
        if downloaded:
            return downloaded, "file"
        return inline, "inline"

    def model_name(self):
        return self._model_name or "Pro"


class ClaudeEngine:
    STOP_SEL = 'button[aria-label="Stop Response"], button[aria-label="Stop"]'

    def __init__(self, driver, model_target="Opus", extended_thinking=True):
        self.driver             = driver
        self.name               = "claude"
        self._model_target      = model_target
        self._model_name        = model_target
        self._extended_thinking = extended_thinking
        # Watchdog state — managed per phase
        self._watchdog_stop : threading.Event | None = None
        self._watchdog_thread: threading.Thread | None = None

    def screenshot(self, label):
        path = f"ein_d_claude_{label}.png"
        self.driver.save_screenshot(path)
        log(f"  [claude] screenshot: {path}")

    def new_chat(self):
        self.driver.get("https://claude.ai")
        time.sleep(4)

    def navigate_to(self, title: str):
        found = self.driver.execute_script("""
            const links = Array.from(document.querySelectorAll('a[href*="/chat/"]'));
            const match = links.find(el =>
                el.textContent.trim().toLowerCase().includes(arguments[0].toLowerCase())
            );
            if (match) { match.click(); return match.textContent.trim().slice(0,80); }
            const all = Array.from(document.querySelectorAll('nav a, aside a, a'));
            const m2  = all.find(el =>
                el.textContent.trim().toLowerCase().includes(arguments[0].toLowerCase())
            );
            if (m2) { m2.click(); return 'fallback: ' + m2.textContent.trim().slice(0,80); }
            return null;
        """, title)
        time.sleep(6)
        log(f"  [claude] navigated to: {found}")
        return found

    def get_conversation_url(self) -> str:
        return self.driver.current_url

    def select_model(self, target=None):
        d      = self.driver
        target = target or self._model_target
        try:
            d.find_element(By.CSS_SELECTOR,
                'button[data-testid="model-selector-button"], '
                'button[aria-label*="model"], button[aria-label*="Model"]'
            ).click()
            time.sleep(1)
            clicked = d.execute_script("""
                const target = arguments[0].toLowerCase();
                const items  = Array.from(document.querySelectorAll(
                    '[role="option"],[role="menuitem"],li,button'));
                const match  = items.find(el => {
                    const t = (el.textContent || '').toLowerCase();
                    return t.includes(target) && el.offsetParent !== null;
                });
                if (match) { match.click(); return match.textContent.trim(); }
                return null;
            """, target)
            time.sleep(1)
            log(f"  [claude] model: {(clicked or 'not found')[:60]}")
            self._model_name = clicked or target
        except Exception as e:
            log(f"  [claude] model select failed: {e}")

    def upload_files(self, *filepaths):
        d = self.driver
        for filepath in filepaths:
            abs_path = str(Path(filepath).resolve())
            if not Path(filepath).exists():
                log(f"  [claude] file not found: {filepath}")
                continue
            try:
                d.execute_script("""
                    const inps = Array.from(document.querySelectorAll('input[type="file"]'));
                    if (inps.length) inps[inps.length - 1].style.display = 'block';
                """)
                time.sleep(0.5)
                inp = d.find_elements(By.CSS_SELECTOR, 'input[type="file"]')[-1]
                inp.send_keys(abs_path)
                time.sleep(3)
                log(f"  [claude] uploaded: {Path(filepath).name}")
            except Exception as e:
                log(f"  [claude] upload failed for {filepath}: {e}")

    def send_and_wait(self, text, timeout=PHASE_TIMEOUT):
        d = self.driver
        try:
            ta = d.find_element(By.CSS_SELECTOR, 'div[contenteditable="true"]')
        except Exception:
            log("  [claude] ERROR: no input area found")
            return 0

        ta.click()
        time.sleep(0.3)

        CHUNK = 3000
        if len(text) <= CHUNK:
            ta.send_keys(text)
        else:
            d.execute_script("arguments[0].focus();", ta)
            for i in range(0, len(text), CHUNK):
                chunk = text[i:i + CHUNK]
                d.execute_script(
                    "arguments[0].focus(); document.execCommand('insertText', false, arguments[1]);",
                    ta, chunk)
                time.sleep(0.2)
            time.sleep(0.5)

        submitted = d.execute_script("""
            const btn = document.querySelector('button[aria-label="Send message"]');
            if (btn && !btn.disabled) { btn.click(); return true; }
            return false;
        """)
        if not submitted:
            try:
                ta.send_keys(Keys.RETURN)
            except Exception:
                pass

        return wait_for_streaming(d, self.STOP_SEL, timeout)

    def send_file_and_wait(self, text, phase_label="prompt", timeout=PHASE_TIMEOUT):
        """Always upload prompt as a file instead of pasting into chat."""
        import os as _os
        tmp_path = write_prompt_file(text, phase_label)
        fname = _os.path.basename(tmp_path)
        log(f"  [claude] uploading prompt as file: {fname}")
        self.upload_files(tmp_path)
        try: _os.unlink(tmp_path)
        except Exception: pass
        d = self.driver
        try:
            ta = d.find_element(By.CSS_SELECTOR, 'div[contenteditable="true"]')
        except Exception:
            log("  [claude] ERROR: no input area for trigger message")
            return 0
        trigger = f"Your prompt for this round is in the attached file: {fname}"
        ta.click()
        time.sleep(0.3)
        d.execute_script("arguments[0].focus(); document.execCommand('insertText', false, arguments[1]);", ta, trigger)
        time.sleep(0.5)
        submitted = d.execute_script("""
            const btn = document.querySelector('button[aria-label="Send message"]');
            if (btn && !btn.disabled) { btn.click(); return true; } return false;
        """)
        if not submitted:
            try: ta.send_keys(Keys.RETURN)
            except Exception: pass
        return wait_for_streaming(d, self.STOP_SEL, timeout)

    def start_watchdog(self, interval=12):
        """No-op — Continue-button watching is now handled by the global session watchdog."""
        pass

    def stop_watchdog(self):
        """No-op — global session watchdog is stopped at pipeline end."""
        pass

    LAST_MSG_SEL = '.row-start-2'

    def get_latest_response(self):
        """Returns (inline_text, 'inline') — no downloads. Used by stability loop."""
        inline = self.driver.execute_script("""
            // Primary: .row-start-2 — Claude's grid layout final-answer cell.
            // Confirmed working via isolated selector test 2026-04-05.
            // Returns empty string when Claude opened the document editor (content in artifact).
            const byRow = Array.from(document.querySelectorAll('.row-start-2'));
            if (byRow.length) return byRow[byRow.length - 1].innerText;

            // Fallback 1: data-testid (may not exist in current Claude DOM)
            const byTestId = Array.from(document.querySelectorAll(
                '[data-testid="assistant-message"]'));
            if (byTestId.length) return byTestId[byTestId.length - 1].innerText;

            // Fallback 2: font-claude-message class
            const byClass = Array.from(document.querySelectorAll('.font-claude-message'));
            if (byClass.length) return byClass[byClass.length - 1].innerText;

            return '';
        """) or ""
        return inline, "inline"

    def get_final_response(self):
        """Called once after stability confirmed. Checks for downloads in last message."""
        inline, _ = self.get_latest_response()
        downloaded, src = resolve_downloads(self.driver, self.name, self.LAST_MSG_SEL)
        if downloaded:
            return downloaded, "file"
        return inline, "inline"

    def model_name(self):
        return self._model_name or "Opus"


# ── Parallel execution ────────────────────────────────────────────────────────

def run_parallel(engines, func, desc):
    """Run func(engine) in parallel threads. Hard-fails if any engine fails."""
    log(f"PHASE: {desc}")
    results = {}
    errors  = {}

    def worker(engine):
        try:
            results[engine.name] = func(engine)
        except Exception as e:
            import traceback
            errors[engine.name] = str(e)
            log(f"  [{engine.name}] FAILED: {e}")
            traceback.print_exc()

    threads = [threading.Thread(target=worker, args=(e,)) for e in engines]
    for t in threads: t.start()
    for t in threads: t.join()

    if errors:
        log(f"FATAL: {desc} failed for: {list(errors.keys())}")
        sys.exit(1)

    return results


def build_phase_output(engines, elapsed_map, action="ask",
                       min_chars=500, retry_wait=300, phase1_sizes=None):
    """Build ledger-compatible output from current engine responses.

    Stability check: an engine is done when its response length hasn't
    changed for 2 consecutive reads (20s gap). Retries for up to retry_wait.
    Source tag ("inline" or "file") is preserved per engine.
    """
    results   = {}
    src_map   = {}

    for engine in engines:
        text, src = engine.get_latest_response()
        results[engine.name] = {
            "success":         len(text) >= min_chars,
            "response":        text,
            "source":          src,
            "model_used":      engine.model_name(),
            "llm":             engine.name,
            "elapsed_seconds": elapsed_map.get(engine.name, 0),
        }
        src_map[engine.name] = src

    # Stability check loop
    monitored     = list(engines)
    prev_lens     = {e.name: len(results[e.name]["response"]) for e in engines}
    stable_counts = {e.name: 0 for e in engines}
    needs_wait    = any(len(results[e.name]["response"]) < min_chars for e in engines)

    if needs_wait:
        short_names = [e.name for e in monitored
                       if len(results[e.name]["response"]) < min_chars]
        log(f"Short responses from {short_names}, waiting up to {retry_wait}s (stability)...")

    for i in range(retry_wait // 10):
        if not monitored:
            break
        time.sleep(10)
        still = []
        for engine in monitored:
            text, src = engine.get_latest_response()
            cur_len   = len(text)

            if cur_len > len(results[engine.name]["response"]):
                results[engine.name]["response"] = text
                results[engine.name]["source"]   = src

            if cur_len < min_chars:
                stable_counts[engine.name] = 0
                still.append(engine)
            elif cur_len == prev_lens[engine.name]:
                stable_counts[engine.name] += 1
                if stable_counts[engine.name] < 2:
                    still.append(engine)
                else:
                    results[engine.name]["success"] = True
                    log(f"  [{engine.name}] stable: {cur_len} chars "
                        f"(after {(i+1)*10}s extra wait)")
            else:
                stable_counts[engine.name] = 0
                results[engine.name]["success"] = False
                still.append(engine)
            prev_lens[engine.name] = cur_len
        monitored = still

    for name, r in results.items():
        if not r["success"]:
            r["error"] = f"Response too short or unstable ({len(r['response'])} chars)"

    # Final download check — called ONCE after stability, scoped to last message only
    log("Checking for downloadable files in final responses...")
    _p1_sizes = set(phase1_sizes.values()) if phase1_sizes else set()
    for engine in engines:
        final_text, final_src = engine.get_final_response()
        if final_src == "file":
            if _p1_sizes and len(final_text) in _p1_sizes:
                log(f"  [{engine.name}] download matches Phase 1 size "
                    f"({len(final_text)} chars) — discarding, keeping inline")
            elif len(final_text) > len(results[engine.name]["response"]):
                log(f"  [{engine.name}] file download resolved: {len(final_text)} chars")
                results[engine.name]["response"] = final_text
                results[engine.name]["source"]   = "file"
                results[engine.name]["success"]  = len(final_text) >= min_chars

    return {
        "action":                action,
        "results":               results,
        "total_elapsed_seconds": round(
            max(elapsed_map.values()) if elapsed_map else 0, 1
        ),
    }


def check_failures(data, phase_name, min_chars=500):
    failures = []
    for name, r in data["results"].items():
        if not r.get("success") or len(r.get("response", "")) < min_chars:
            failures.append(f"{name}: {len(r.get('response', ''))} chars")
    if failures:
        log(f"FATAL: {phase_name} — short/missing: {failures}")
        sys.exit(1)


def save_results(data, filename):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    log(f"Saved: {filename}")


# ── Phase implementations ─────────────────────────────────────────────────────

def run_phase_draft(engines, upload_files, prompt_path):
    """Phase 1: Each engine gets source files + brief, produces full draft."""
    prompt = Path(prompt_path).read_text(encoding="utf-8")

    def step(engine):
        t0 = time.time()
        engine.new_chat()
        engine.select_model()
        engine.screenshot("draft_01_model")

        # Claude: start watchdog for long generation
        if isinstance(engine, ClaudeEngine):
            engine.start_watchdog()

        engine.upload_files(*upload_files)
        engine.screenshot("draft_02_uploaded")
        engine.send_and_wait(prompt, timeout=PHASE_TIMEOUT)
        # Capture conversation URL immediately after sending (URL settles once chat is created)
        conv_url = engine.get_conversation_url()
        log(f"  [{engine.name}] conversation URL: {conv_url}")
        elapsed = round(time.time() - t0, 1)

        if isinstance(engine, ClaudeEngine):
            engine.stop_watchdog()

        text, src = engine.get_latest_response()
        log(f"  [{engine.name}] draft: {len(text)} chars ({src}) in {elapsed}s")
        engine.screenshot("draft_03_response")
        return elapsed

    elapsed_map = run_parallel(engines, step, "Phase 1: Draft")
    data = build_phase_output(engines, elapsed_map, "draft", min_chars=500, retry_wait=300)
    check_failures(data, "Draft", min_chars=500)
    save_results(data, "ein-design-draft-results.json")
    log("Phase DRAFT COMPLETE: " + " | ".join(
        f"{n}={len(r['response'])}c/{r['source']}"
        for n, r in data["results"].items()))
    return data


def run_phase_cross_pollination(engines, ledger, phase_name, round_number,
                                quality_criterion="more thorough, better reasoned, and more actionable"):
    """Cross-pollination: each engine receives the other two's documents and revises.

    Continues in the SAME conversation (no new_chat).
    Injects the other two engines' full responses from the previous phase.
    Each engine produces a REVISED complete document + rejection appendix.
    """
    CROSS_POLLINATION_TEMPLATE = """\
⚠ RESPOND IN THIS CHAT ONLY. Do NOT open the document editor. Do NOT create an artifact or \
downloadable file. Your entire response must be typed here as chat text.

You are now in cross-pollination round {round_number}.

Here are the other two participants' complete documents:

--- PARTICIPANT: {name_a} ---

{draft_a}

--- PARTICIPANT: {name_b} ---

{draft_b}

---

When compared to your draft, you need to state where they are stronger and adopt their approach. \
Where you are stronger, keep yours. "Stronger" means: {quality_criterion}. \
Produce your REVISED complete document.

Add as an appendix the points you reject and explain why and what is your proposal.
"""

    source = _source_phase_for(phase_name, ledger)
    log(f"  Reading other engines' responses from phase: {source}")

    def step(engine):
        t0 = time.time()
        others = _get_other_two(ledger, source, engine.name)
        if len(others) < 2:
            log(f"  [{engine.name}] FATAL: need 2 other drafts, got {len(others)}")
            return 0

        prompt = CROSS_POLLINATION_TEMPLATE.format(
            round_number      = round_number,
            quality_criterion = quality_criterion,
            name_a            = others[0][0].upper(),
            draft_a           = others[0][1],
            name_b            = others[1][0].upper(),
            draft_b           = others[1][1],
        )

        if isinstance(engine, ClaudeEngine):
            engine.start_watchdog()

        engine.send_file_and_wait(prompt, phase_label=phase_name, timeout=PHASE_TIMEOUT)
        elapsed = round(time.time() - t0, 1)

        if isinstance(engine, ClaudeEngine):
            engine.stop_watchdog()

        text, src = engine.get_latest_response()
        log(f"  [{engine.name}] {phase_name}: {len(text)} chars ({src}) in {elapsed}s")
        engine.screenshot(f"{phase_name}_response")
        return elapsed

    elapsed_map = run_parallel(engines, step, f"Cross-Pollination Round {round_number}")
    data = build_phase_output(engines, elapsed_map, phase_name,
                              min_chars=500, retry_wait=300)
    check_failures(data, f"Cross-Pollination {round_number}", min_chars=500)
    save_results(data, f"ein-design-{phase_name}-results.json")
    log(f"Phase {phase_name.upper()} COMPLETE: " + " | ".join(
        f"{n}={len(r['response'])}c/{r['source']}"
        for n, r in data["results"].items()))
    return data


def run_phase_final(chatgpt_engine, ledger):
    """Final convergence: ChatGPT acts as facilitator, produces the master document.

    Sent ONLY to ChatGPT. Receives the other two engines' latest revised documents.
    ChatGPT applies 2/3 majority on remaining disagreements and produces the final output.
    """
    FINAL_TEMPLATE = """\
⚠ RESPOND IN THIS CHAT ONLY. Do NOT open the document editor. Do NOT create an artifact or \
downloadable file. Your entire response must be typed here as chat text.

Here are the other two participants' revised documents:

--- GEMINI ---

{draft_gemini}

--- CLAUDE ---

{draft_claude}

---

Most points have converged. For remaining disagreements, make your final call by picking \
the solutions that 2/3 of LLMs voted for.

Before the final document, list each remaining disagreement, which position had 2/3 support, \
and your resolution.

Then produce the FINAL COMPLETE MASTER DOCUMENT.
"""

    source = _source_phase_for("final", ledger)
    log(f"  Reading other engines' responses from phase: {source}")
    others = _get_other_two(ledger, source, "chatgpt")

    gemini_text = ""
    claude_text = ""
    for name, text in others:
        if name == "gemini":
            gemini_text = text
        elif name == "claude":
            claude_text = text

    prompt = FINAL_TEMPLATE.format(
        draft_gemini = gemini_text,
        draft_claude = claude_text,
    )

    t0 = time.time()
    chatgpt_engine.send_file_and_wait(prompt, phase_label="final", timeout=PHASE_TIMEOUT)
    elapsed = round(time.time() - t0, 1)

    text, src = chatgpt_engine.get_latest_response()
    log(f"  [chatgpt] final: {len(text)} chars ({src}) in {elapsed}s")
    chatgpt_engine.screenshot("final_response")

    # Build phase data with only ChatGPT's response
    data = {
        "action": "final",
        "results": {
            "chatgpt": {
                "response": text,
                "model_used": chatgpt_engine._model_name,
                "elapsed_seconds": elapsed,
                "source": src,
                "success": len(text) >= 500,
            }
        },
        "total_elapsed_seconds": elapsed,
    }
    check_failures(data, "Final Convergence", min_chars=500)
    save_results(data, "ein-design-final-results.json")
    log(f"Phase FINAL COMPLETE: chatgpt={len(text)}c/{src}")
    return data


# ── Browser launch ────────────────────────────────────────────────────────────

def launch_browsers(profiles_subset=None):
    """Launch Chrome instances with CDP download dir configured."""
    profiles = profiles_subset if profiles_subset is not None else PROFILES
    URLS     = {
        "chatgpt": "https://chatgpt.com",
        "gemini":  "https://gemini.google.com",
        "claude":  "https://claude.ai",
    }
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    drivers = {}
    for name, profile in profiles.items():
        log(f"Launching {name} browser...")
        clean_locks(profile)
        for attempt in range(3):
            try:
                d = Driver(uc=True, headless=False, user_data_dir=profile)
                d.execute_cdp_cmd("Page.setDownloadBehavior",
                                  {"behavior": "allow", "downloadPath": DOWNLOAD_DIR})
                time.sleep(3)
                d.get(URLS[name])
                drivers[name] = d
                break
            except Exception as e:
                log(f"  {name} launch attempt {attempt+1} failed: {e}")
                try: d.quit()
                except: pass
                if attempt == 2:
                    raise
                clean_locks(profile)
                time.sleep(5)
    time.sleep(5)

    def check_ready(drivers):
        result = {}
        if "chatgpt" in drivers:
            result["chatgpt"] = bool(
                drivers["chatgpt"].find_elements(By.CSS_SELECTOR, "#prompt-textarea"))
        if "claude" in drivers:
            result["claude"] = bool(
                drivers["claude"].find_elements(By.CSS_SELECTOR, 'div[contenteditable="true"]'))
        if "gemini" in drivers:
            has_input   = bool(drivers["gemini"].find_elements(
                By.CSS_SELECTOR, 'div[contenteditable="true"]'))
            signed_out  = drivers["gemini"].execute_script("""
                return Array.from(document.querySelectorAll('a, button')).some(
                    el => el.textContent.trim() === 'Sign in' && el.offsetParent !== null
                );
            """)
            result["gemini"] = has_input and not signed_out
        return result

    ready     = check_ready(drivers)
    not_ready = [n for n, r in ready.items() if not r]
    if not_ready:
        log(f"NOT LOGGED IN: {not_ready}. Waiting up to 300s...")
        for i in range(30):
            time.sleep(10)
            ready     = check_ready(drivers)
            remaining = 300 - (i + 1) * 10
            status    = " | ".join(f"{n}={'OK' if ready[n] else 'WAIT'}" for n in ready)
            log(f"  {status}  ({remaining}s left)")
            if all(ready.values()):
                break

    if not all(ready.values()):
        log(f"FATAL: Not all engines logged in: {ready}")
        sys.exit(1)

    log(f"{len(drivers)} browser(s) ready: {list(drivers)}")
    return drivers


# ── Ledger append helper ──────────────────────────────────────────────────────

def ledger_append(ledger, ledger_path, phase_name, data, assignments=None):
    try:
        _append_phase(ledger, phase_name, data, assignments)
        _save_ledger(ledger, ledger_path)
        log(f"Ledger: {phase_name} appended → {ledger_path}")
    except SystemExit:
        log(f"FATAL: Ledger append failed for {phase_name}")
        raise
    except Exception as e:
        log(f"FATAL: Ledger error for {phase_name}: {e}")
        sys.exit(1)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Ein Design Pipeline V2 (Cross-Pollination)")
    parser.add_argument("--phase", type=str, default=None,
        help="Run specific phase: draft, cross_1, cross_2, cross_3, final")
    parser.add_argument("--resume", type=str, default=None,
        metavar="LEDGER_PATH",
        help="Resume from existing conversations. Skips Phase 1 (draft). "
             "Loads conversation registry from ledger to navigate back to existing threads.")
    parser.add_argument("--only", type=str, default=None,
        help="Comma-separated engines to run (e.g. chatgpt). Skips ledger. For testing.")
    parser.add_argument("--kill-stale", action="store_true",
        help="Kill stale automation Chrome processes before launching")
    parser.add_argument("--skip-check", action="store_true",
        help="Skip brief suitability check (use if you know the topic is suitable)")
    parser.add_argument("--model-chatgpt", type=str, default="thinking")
    parser.add_argument("--model-gemini",  type=str, default="Pro")
    parser.add_argument("--model-claude",  type=str, default="Opus")
    parser.add_argument("--upload-files",  type=str, default=None,
        help="Comma-separated source files to upload in Phase 1")
    parser.add_argument("--prompt",        type=str, default="phase1-v5-prompt.txt",
        help="Path to Phase 1 prompt file (default: phase1-v5-prompt.txt)")
    parser.add_argument("--quality-criterion", type=str,
        default="more thorough, better reasoned, and more actionable",
        help="Defines what 'stronger' means during cross-pollination rounds")
    parser.add_argument("--question",      type=str,
        default="Produce a unified Master Design & DOD document by merging the source files.")
    parser.add_argument("--context",       type=str,
        default="Design synthesis run.")
    args = parser.parse_args()

    only_engines = [x.strip().lower() for x in args.only.split(",")] \
                   if args.only else None

    if args.kill_stale:
        kill_automation_chrome()

    # ── Brief suitability check ──────────────────────────────────────────────
    # The cross-pollination pipeline works well for specific topic types.
    # On a fresh run (no --resume), validate the brief before launching browsers.
    if not args.resume and not args.skip_check and phase_arg in ("draft", "all"):
        prompt_path = Path(args.prompt)
        if prompt_path.exists():
            brief_text = prompt_path.read_text(encoding="utf-8")
        else:
            brief_text = args.question

        SUITABLE_CATEGORIES = [
            ("policy analysis",
             "Multiple perspectives genuinely improve coverage"),
            ("strategic decision",
             "Models catch each other's blind spots"),
            ("research synthesis",
             "Cross-pollination surfaces contradictions in evidence"),
            ("comparative evaluation",
             "Rejection appendix forces explicit trade-off reasoning"),
            ("document merge",
             "Combining two or more source documents into a unified output"),
            ("architecture or design",
             "Technical design benefits from adversarial review and convergence"),
        ]

        brief_lower = brief_text.lower()
        # Heuristic signals for each category
        _signals = {
            "policy analysis":       ["policy", "regulation", "compliance", "governance",
                                       "framework", "stakeholder", "impact assessment"],
            "strategic decision":    ["strategy", "decision", "trade-off", "option",
                                       "recommend", "evaluate", "choose", "select",
                                       "pros and cons", "versus", " vs "],
            "research synthesis":    ["research", "findings", "evidence", "literature",
                                       "study", "analysis", "investigate", "survey"],
            "comparative evaluation": ["compare", "contrast", "evaluate", "benchmark",
                                        "assess", "rank", "score", "criteria"],
            "document merge":        ["merge", "unif", "consolidat", "reconcil",
                                       "combine", "integrat", "master document",
                                       "two versions", "two documents"],
            "architecture or design": ["design", "architecture", "schema", "pipeline",
                                        "module", "component", "interface", "system",
                                        "implementation", "specification", "dod",
                                        "definition of done"],
        }

        matched = []
        for category, reason in SUITABLE_CATEGORIES:
            signals = _signals[category]
            hits = sum(1 for s in signals if s in brief_lower)
            if hits >= 2:
                matched.append((category, reason, hits))

        if not matched:
            log("")
            log("=" * 70)
            log("BRIEF SUITABILITY CHECK — FAILED")
            log("=" * 70)
            log("")
            log("This pipeline uses multi-model cross-pollination with convergence")
            log("rounds. It works well for these topic types:")
            log("")
            for cat, reason in SUITABLE_CATEGORIES:
                log(f"  • {cat:<30} — {reason}")
            log("")
            log("Your brief did not match any of these categories.")
            log("")
            log("If your brief is a QUESTION or DECISION that needs adversarial")
            log("debate (truth-seeking, risk assessment, 'should we do X?'),")
            log("use the Ein Deliberation platform instead:")
            log("  → python ein-parallel.py --prompt <your-brief>")
            log("  (three-way adversarial debate with contrarian lenses)")
            log("")
            log("Topics that do NOT benefit from EITHER pipeline:")
            log("  • Creative writing (voice can't be cross-pollinated)")
            log("  • Simple factual questions (overkill)")
            log("  • Code generation (output isn't document-shaped)")
            log("  • Highly subjective / taste-based topics (no quality axis)")
            log("")
            log("If you believe this brief IS suitable, re-run with --skip-check")
            log("=" * 70)
            sys.exit(1)
        else:
            cats = ", ".join(c for c, _, _ in matched)
            log(f"Brief suitability: PASS — matched categories: {cats}")

    # ── Ledger setup ──────────────────────────────────────────────────────────
    if args.resume:
        ledger_path = Path(args.resume)
        ledger      = json.loads(ledger_path.read_text(encoding="utf-8"))
        log(f"Resuming from ledger: {ledger_path}")
        st = _status(ledger)
        log(f"  Completed: {st['completed_phases']} | Next: {st['next_phase']}")
    else:
        ledger_path = Path(
            f"design-ledger-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
        )
        log(f"Creating ledger: {ledger_path}")
        ledger = _create_ledger(args.question, args.context, ledger_path)

    # ── Source files ──────────────────────────────────────────────────────────
    upload_files = []
    if args.upload_files:
        upload_files = [f.strip() for f in args.upload_files.split(",")]

    phase_arg = args.phase or "all"

    # ── Launch browsers ───────────────────────────────────────────────────────
    # Final phase only needs ChatGPT — never launch all 3 browsers for it.
    if phase_arg == "final":
        active_profiles = {"chatgpt": PROFILES["chatgpt"]}
        log("final phase: ChatGPT browser only")
    else:
        active_profiles = {k: v for k, v in PROFILES.items()
                           if only_engines is None or k in only_engines}
    if only_engines and phase_arg != "final":
        log(f"--only mode: {list(active_profiles)}")
    drivers = launch_browsers(active_profiles)

    all_engine_objs = [
        ChatGPTEngine(drivers["chatgpt"], model_target=args.model_chatgpt)
            if "chatgpt" in drivers else None,
        GeminiEngine(drivers["gemini"],   model_target=args.model_gemini)
            if "gemini" in drivers else None,
        ClaudeEngine(drivers["claude"],   model_target=args.model_claude)
            if "claude" in drivers else None,
    ]
    engines = [e for e in all_engine_objs if e is not None]

    # ── Global session watchdog ───────────────────────────────────────────────
    _watchdog_stop = threading.Event()
    _watchdog_thread = start_session_watchdog(engines, _watchdog_stop, interval=12)
    log("Session watchdog started (12s interval)")

    # ── Resume: navigate to existing conversations + capture real URLs ─────────
    if args.resume:
        registry = ledger.get("conversation_registry", {})
        if registry:
            log("Navigating to existing conversations...")
            for engine in engines:
                info = registry.get(engine.name, {})
                url   = info.get("url", "")
                title = info.get("title", "")
                if url and len(url) > 30 and url not in (
                    "https://chatgpt.com", "https://claude.ai",
                    "https://gemini.google.com", "https://gemini.google.com/app"
                ):
                    engine.driver.get(url)
                    time.sleep(5)
                    log(f"  [{engine.name}] navigated via URL: {url}")
                elif title:
                    engine.navigate_to(title)
                else:
                    log(f"  [{engine.name}] no saved title — going to home")
                    engine.new_chat()

            updated_registry = {}
            for engine in engines:
                real_url = engine.get_conversation_url()
                updated_registry[engine.name] = {
                    "title": registry.get(engine.name, {}).get("title", ""),
                    "url":   real_url,
                }
                log(f"  [{engine.name}] URL: {real_url}")
            _set_registry(ledger, updated_registry)
            if not only_engines:
                _save_ledger(ledger, ledger_path)
            log("Conversation registry updated with real URLs")

    start_total = time.time()

    def maybe_append(phase_name, data):
        if not only_engines:
            ledger_append(ledger, ledger_path, phase_name, data)

    # ── Phase: draft ──────────────────────────────────────────────────────────
    if phase_arg in ("draft", "all") and "draft" not in ledger.get("phases", {}):
        if not upload_files:
            log("WARNING: no --upload-files specified for draft phase")
        p1_data = run_phase_draft(engines, upload_files, args.prompt)
        maybe_append("draft", p1_data)

        registry = {}
        for engine in engines:
            url   = engine.get_conversation_url()
            title = engine.driver.title or url
            registry[engine.name] = {"title": title, "url": url}
        _set_registry(ledger, registry)
        if not only_engines:
            _save_ledger(ledger, ledger_path)
        log(f"Conversation registry saved: {registry}")

    # ── Phase: cross_1 ───────────────────────────────────────────────────────
    if phase_arg in ("cross_1", "all") \
            and "cross_1" not in ledger.get("phases", {}):
        qc = args.quality_criterion
        data = run_phase_cross_pollination(engines, ledger, "cross_1", 1, quality_criterion=qc)
        maybe_append("cross_1", data)

    # ── Phase: cross_2 ───────────────────────────────────────────────────────
    if phase_arg in ("cross_2", "all") \
            and "cross_2" not in ledger.get("phases", {}):
        qc = args.quality_criterion
        data = run_phase_cross_pollination(engines, ledger, "cross_2", 2, quality_criterion=qc)
        maybe_append("cross_2", data)

    # ── Phase: cross_3 (optional — run only if explicitly requested) ─────────
    if phase_arg == "cross_3" \
            and "cross_3" not in ledger.get("phases", {}):
        qc = args.quality_criterion
        data = run_phase_cross_pollination(engines, ledger, "cross_3", 3, quality_criterion=qc)
        maybe_append("cross_3", data)

    # ── Phase: final (ChatGPT only) ──────────────────────────────────────────
    if phase_arg in ("final", "all") \
            and "final" not in ledger.get("phases", {}):
        chatgpt = next((e for e in engines if e.name == "chatgpt"), None)
        if not chatgpt:
            log("FATAL: ChatGPT engine required for final phase")
            sys.exit(1)
        data = run_phase_final(chatgpt, ledger)
        maybe_append("final", data)

    total = round(time.time() - start_total, 1)
    log(f"\nAll phases complete in {total}s")

    if only_engines:
        log("\n--only mode: no ledger audit. Review screenshots and results files.")
    else:
        st = _status(ledger)
        log(f"\nLedger: {ledger_path}")
        log(f"Status: {st['completed_phases']} complete | next: {st['next_phase']}")

    _watchdog_stop.set()
    _watchdog_thread.join(timeout=5)
    log("Session watchdog stopped.")
    log("Browsers left open. Close manually when done.")


if __name__ == "__main__":
    main()
