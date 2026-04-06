#!/usr/bin/env python3
"""Ein Phase 1-4 parallel runner using SeleniumBase browser automation.

Full Ein deliberation pipeline with ledger integration.
Three engines run in parallel threads per phase.

Usage:
    python ein-selenium.py                           # Full run (smart models)
    python ein-selenium.py --kill-stale              # Kill stale Chrome first
    python ein-selenium.py --phase 1                 # Single phase
    python ein-selenium.py --model-chatgpt thinking  # Override model
"""

import importlib.util
import json, os, sys, time, threading, argparse
from pathlib import Path
from datetime import datetime, timezone

os.chdir(r"C:\Users\chris\PROJECTS")

from seleniumbase import Driver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

# ── Import ein-selenium-ledger (hyphen in filename requires importlib) ────────

_spec = importlib.util.spec_from_file_location("ein_ledger", Path("ein-selenium-ledger.py").resolve())
_ledger_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_ledger_mod)
_create_ledger   = _ledger_mod.create_ledger
_append_phase    = _ledger_mod.append_phase
_extract_prompt  = _ledger_mod.extract_for_prompt
_save_ledger     = _ledger_mod._save

# ── Config ────────────────────────────────────────────────────────────────────

PROFILES = {
    "chatgpt": r"C:\Users\chris\PROJECTS\chrome-automation-profile",
    "gemini":  r"C:\Users\chris\PROJECTS\chrome-automation-profile-2",
    "claude":  r"C:\Users\chris\PROJECTS\chrome-automation-profile-3",
}
PHASE_TIMEOUT = 900  # 15 min — thinking models can be slow
LOG_PREFIX = "[ein]"
DOWNLOAD_DIR = r"C:\Users\chris\PROJECTS\downloaded_files"

DELIBERATION_QUESTION = (
    "Given four source documents (DESIGN-V3.0, DESIGN-V3.0B, DOD-V3.0, DOD-V3.0B) "
    "for the Thinker deliberation platform: produce a unified Master Design & DOD "
    "document by selecting the strongest mechanism at each decision point and merging "
    "complementary features."
)
DELIBERATION_CONTEXT = (
    "Merging two parallel design/DOD versions of the Thinker platform into one "
    "authoritative Master document. Participants read all four source files in full."
)
DELIBERATION_BRIEF = {
    "decision_type": "synthesis",
    "success_criteria": "A self-contained Master document where every design element "
        "has a corresponding DOD requirement, conflicts are resolved by selection with "
        "rationale, and no design feature is invented.",
    "constraints": "Select only from the four source documents. Do not invent new "
        "features. Flag irreconcilable conflicts explicitly.",
    "out_of_scope": "Any mechanism not present in the four source documents.",
}
UPLOAD_FILES = [
    r"_audit_thinker\thinker-v8\output\design-session\DESIGN-V3.md",
    r"_audit_thinker\thinker-v8\output\design-session\DESIGN-V3.0B.md",
    r"_audit_thinker\thinker-v8\output\design-session\DOD-V3.md",
    r"_audit_thinker\thinker-v8\output\design-session\DOD-V3.0B.md",
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"{LOG_PREFIX} {ts} {msg}", flush=True)


def clean_locks(profile_dir):
    for root, dirs, files in os.walk(profile_dir):
        for f in files:
            if f in ["LOCK", "lockfile", "SingletonLock"]:
                try: os.remove(os.path.join(root, f))
                except: pass


def resolve_downloads(driver, engine_name, wait=15):
    """Scan the DOM for download links, click any found, read downloaded files.

    Always called after get_latest_response() — regardless of response length.
    Returns file contents concatenated as a string, or "" if no downloads found.
    """
    import glob as _glob

    # Snapshot files already in download dir before clicking
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    before = set(_glob.glob(os.path.join(DOWNLOAD_DIR, "*")))

    # Find all visible download-style links/buttons in the page
    clicked = driver.execute_script(r"""
        const FILE_EXT = /\.(docx?|xlsx?|pdf|md|txt|csv|json|zip)(\s|$|\))/i;
        const candidates = new Set();

        // 1. <a> tags: download attr, blob href, /files/ href, oaiusercontent
        document.querySelectorAll('a[download], a[href*="blob:"], a[href*="/files/"], a[href*="oaiusercontent"]').forEach(el => {
            if (el.offsetParent !== null) candidates.add(el);
        });

        // 2. Any element with "download" in aria-label/title/text
        document.querySelectorAll('button, a, [role="button"]').forEach(el => {
            if (el.offsetParent === null) return;
            const label = (el.getAttribute('aria-label') || el.getAttribute('title') || el.innerText || '').toLowerCase();
            if (label.includes('download') || label.includes('télécharger')) candidates.add(el);
        });

        // 3. Buttons whose visible text matches a file extension pattern
        // (ChatGPT renders downloadable files as plain buttons with filename text)
        document.querySelectorAll('button, [role="button"]').forEach(el => {
            if (el.offsetParent === null) return;
            const text = (el.innerText || '').trim();
            if (FILE_EXT.test(text)) candidates.add(el);
        });

        const clicked = [];
        candidates.forEach(el => {
            try { el.click(); clicked.push(el.outerHTML.slice(0, 120)); } catch(e) {}
        });
        return clicked;
    """)

    if not clicked:
        return ""

    log(f"  [{engine_name}] {len(clicked)} download link(s) clicked, waiting for files...")

    # Wait for new files to appear
    contents = []
    deadline = time.time() + wait
    while time.time() < deadline:
        time.sleep(1)
        after = set(_glob.glob(os.path.join(DOWNLOAD_DIR, "*")))
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

    return "\n\n".join(contents)


def wait_for_streaming(driver, stop_selector, timeout=PHASE_TIMEOUT):
    """Wait for streaming to start, then wait for it to finish."""
    # Phase 1: wait for stop button to appear (streaming started)
    for _ in range(30):
        time.sleep(1)
        if driver.find_elements(By.CSS_SELECTOR, stop_selector):
            break
    # Phase 2: wait for stop button to disappear (streaming done)
    for i in range(timeout // 2):
        time.sleep(2)
        if not driver.find_elements(By.CSS_SELECTOR, stop_selector):
            return (i + 1) * 2
    return timeout


# ── ChatGPT Engine ────────────────────────────────────────────────────────────

class ChatGPTEngine:
    # Extended thinking uses "Stop" (no "streaming" suffix) — include both variants
    STOP_SEL = ('button[aria-label="Stop streaming"], button[data-testid="stop-button"], '
                'button[aria-label="Stop"], button[aria-label="Stop generating"]')

    def __init__(self, driver, model_target="thinking"):
        self.driver = driver
        self.name = "chatgpt"
        self._model_target = model_target
        self._model_name = model_target

    def screenshot(self, label):
        path = f"ein_chatgpt_{label}.png"
        self.driver.save_screenshot(path)
        log(f"  [chatgpt] screenshot: {path}")

    def new_chat(self):
        self.driver.get("https://chatgpt.com")
        time.sleep(4)

    def select_model(self, target=None):
        d = self.driver
        target = (target or self._model_target).lower()
        try:
            d.find_element(By.CSS_SELECTOR, 'button[aria-label="Model selector"]').click()
            time.sleep(1)
            clicked = d.execute_script("""
                const target = arguments[0];
                const items = Array.from(document.querySelectorAll(
                    '[role="option"],[role="menuitem"],[role="menuitemradio"],li,button'));
                const match = items.find(el => {
                    const t = (el.textContent || '').toLowerCase();
                    return t.includes(target) && el.offsetParent !== null;
                });
                if (match) { match.click(); return match.textContent.trim(); }
                return null;
            """, target)
            time.sleep(1)
            log(f"  [chatgpt] model: {(clicked or 'not found')[:60]}")
            self._model_name = clicked or target
            return clicked
        except Exception as e:
            log(f"  [chatgpt] model select failed: {e}")
            return None

    def upload_file(self, filepath):
        """Upload a single file."""
        return self.upload_files(filepath)

    def upload_files(self, *filepaths):
        """Upload one or more files. ChatGPT supports newline-separated paths."""
        d = self.driver
        # Click attach button (scored approach)
        d.execute_script("""
            const ta = document.querySelector('#prompt-textarea');
            if (!ta) return;
            const taRect = ta.getBoundingClientRect();
            const buttons = Array.from(document.querySelectorAll('button')).filter(b => b.offsetParent !== null);
            const scored = buttons.map(b => {
                const text = [b.getAttribute('aria-label'),b.getAttribute('title'),
                              b.getAttribute('data-testid'),b.textContent].join(' ').toLowerCase();
                let score = 0;
                if (text.includes('attach')) score += 100;
                if (text.includes('upload')) score += 80;
                if (text.includes('file')) score += 40;
                if ((b.textContent||'').trim() === '+') score += 30;
                const r = b.getBoundingClientRect();
                if (Math.abs(r.bottom-taRect.bottom)<160 && Math.abs(r.left-taRect.left)<260) score += 20;
                return {b, score};
            }).sort((a,b) => b.score-a.score);
            if (scored.length && scored[0].score > 0) scored[0].b.click();
        """)
        time.sleep(2)
        file_input = d.execute_script("""
            const inputs = Array.from(document.querySelectorAll('input[type="file"]'));
            const isImageOnly = inp => {
                const a = (inp.getAttribute('accept')||'').toLowerCase();
                if (!a) return false;
                return a.split(',').map(x=>x.trim()).filter(Boolean).every(p =>
                    p.startsWith('image/') || ['.png','.jpg','.jpeg','.gif','.webp','.bmp','.svg'].includes(p));
            };
            const inp = inputs.find(i => !isImageOnly(i));
            if (!inp) return null;
            inp.style.cssText = 'display:block;visibility:visible;opacity:1;position:fixed;top:0;left:0;width:1px;height:1px;z-index:999999';
            return inp;
        """)
        if file_input:
            all_paths = "\n".join(str(Path(f).resolve()) for f in filepaths)
            file_input.send_keys(all_paths)
            time.sleep(4)
            log(f"  [chatgpt] uploaded: {', '.join(Path(f).name for f in filepaths)}")
            return True
        log(f"  [chatgpt] ERROR: file input not found")
        return False

    def send_and_wait(self, text, timeout=PHASE_TIMEOUT):
        d = self.driver
        ta = d.find_element(By.CSS_SELECTOR, "#prompt-textarea")
        ta.click()
        time.sleep(0.3)

        if len(text) <= 3000:
            ta.send_keys(text)
        else:
            d.execute_script("""
                const el = arguments[0], text = arguments[1];
                el.focus();
                const dt = new DataTransfer();
                dt.setData('text/plain', text);
                el.dispatchEvent(new ClipboardEvent('paste', {clipboardData: dt, bubbles: true, cancelable: true}));
            """, ta, text)
            time.sleep(1)

        # Verify content
        content = d.execute_script("return arguments[0].innerText || ''", ta)
        if len(content) < 10:
            log(f"  [chatgpt] WARN: textarea appears empty ({len(content)} chars)")

        submitted = d.execute_script("""
            const btn = document.querySelector("button[data-testid='send-button']");
            if (btn && !btn.disabled) { btn.click(); return true; } return false;
        """)
        if not submitted:
            ta.send_keys(Keys.RETURN)

        return wait_for_streaming(d, self.STOP_SEL, timeout)

    def get_latest_response(self):
        els = self.driver.find_elements(By.CSS_SELECTOR, "[data-message-author-role='assistant']")
        inline = els[-1].text if els else ""
        downloaded = resolve_downloads(self.driver, self.name)
        return (inline + "\n\n" + downloaded).strip() if downloaded else inline

    def model_name(self):
        return self._model_name or "Thinking"


# ── Gemini Engine ─────────────────────────────────────────────────────────────

class GeminiEngine:
    STOP_SEL = 'button[aria-label="Stop response"], button[aria-label="Stop generating"]'

    def __init__(self, driver, model_target="Pro"):
        self.driver = driver
        self.name = "gemini"
        self._model_target = model_target
        self._model_name = model_target

    def screenshot(self, label):
        path = f"ein_gemini_{label}.png"
        self.driver.save_screenshot(path)
        log(f"  [gemini] screenshot: {path}")

    def new_chat(self):
        self.driver.get("https://gemini.google.com")
        time.sleep(4)

    def select_model(self, target=None):
        d = self.driver
        target = target or self._model_target
        try:
            # Open model dropdown
            for btn in d.find_elements(By.TAG_NAME, "button"):
                if btn.is_displayed() and btn.text.strip() in (
                        "Pro", "Fast", "Thinking", "Flash", "Gemini 3", "Gemini"):
                    btn.click()
                    time.sleep(1.5)
                    break
            # Select target model — match FIRST LINE only (avoid matching description text like "problems")
            for item in d.find_elements(By.CSS_SELECTOR, '[role="option"],[role="menuitem"]'):
                first_line = item.text.split('\n')[0].strip()
                if target.lower() in first_line.lower() and item.is_displayed():
                    d.execute_script("arguments[0].click();", item)
                    self._model_name = first_line  # store just the model name, not description
                    log(f"  [gemini] model: {self._model_name[:60]}")
                    time.sleep(2)  # wait for CDK overlay to fully dismiss
                    # Dismiss any remaining overlay
                    try:
                        d.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
                        time.sleep(0.5)
                    except Exception:
                        pass
                    return self._model_name
        except Exception as e:
            log(f"  [gemini] model select failed: {e}")
        return "unknown"

    def upload_file(self, filepath):
        """Upload a single file to Gemini."""
        d = self.driver
        # Suppress OS file dialog
        d.execute_script("""
            HTMLInputElement.prototype._origClick = HTMLInputElement.prototype.click;
            HTMLInputElement.prototype.click = function() {
                if (this.type === 'file') return;
                return this._origClick.apply(this, arguments);
            };
        """)
        # Click + / attach button
        for btn in d.find_elements(By.TAG_NAME, "button"):
            try:
                label = (btn.get_attribute("aria-label") or "").lower()
                if ("add" in label or "attach" in label or "upload" in label
                        or btn.text.strip() == "+") and btn.is_displayed():
                    d.execute_script("arguments[0].click();", btn)
                    break
            except: pass
        time.sleep(1)
        # Click "Upload files" from menu
        for item in d.find_elements(By.XPATH, "//*[contains(text(),'Upload files')]"):
            if item.is_displayed():
                item.click()
                break
        time.sleep(1)
        # Find and use the file input
        file_input = d.execute_script("""
            const inp = document.querySelector('input[type="file"]');
            if (!inp) return null;
            inp.style.cssText = 'display:block;visibility:visible;opacity:1;position:fixed;top:0;left:0;width:1px;height:1px;z-index:999999';
            return inp;
        """)
        if not file_input:
            # Retry once: dismiss overlays, click + again, try "Upload files" again
            log(f"  [gemini] file input not found, retrying upload for {Path(filepath).name}...")
            time.sleep(2)
            d.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
            time.sleep(1)
            # Re-suppress and try again
            d.execute_script("""
                HTMLInputElement.prototype._origClick = HTMLInputElement.prototype._origClick || HTMLInputElement.prototype.click;
                HTMLInputElement.prototype.click = function() {
                    if (this.type === 'file') return;
                    return this._origClick.apply(this, arguments);
                };
            """)
            for btn in d.find_elements(By.TAG_NAME, "button"):
                try:
                    label = (btn.get_attribute("aria-label") or "").lower()
                    if ("add" in label or "attach" in label or "upload" in label
                            or btn.text.strip() == "+") and btn.is_displayed():
                        d.execute_script("arguments[0].click();", btn)
                        break
                except: pass
            time.sleep(1)
            for item in d.find_elements(By.XPATH, "//*[contains(text(),'Upload files')]"):
                if item.is_displayed():
                    item.click()
                    break
            time.sleep(1)
            file_input = d.execute_script("""
                const inp = document.querySelector('input[type="file"]');
                if (!inp) return null;
                inp.style.cssText = 'display:block;visibility:visible;opacity:1;position:fixed;top:0;left:0;width:1px;height:1px;z-index:999999';
                return inp;
            """)

        if file_input:
            file_input.send_keys(str(Path(filepath).resolve()))
            time.sleep(4)
            log(f"  [gemini] uploaded: {Path(filepath).name}")
            return True
        log(f"  [gemini] ERROR: file input not found for {filepath}")
        return False

    def upload_files(self, *filepaths):
        """Upload multiple files sequentially."""
        for f in filepaths:
            if not self.upload_file(f):
                return False
        return True

    def send_and_wait(self, text, timeout=PHASE_TIMEOUT):
        d = self.driver
        # Dismiss any lingering overlays
        d.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
        time.sleep(0.5)

        # Strip non-BMP chars (emoji etc. crash ChromeDriver send_keys)
        safe_text = ''.join(c for c in text if ord(c) <= 0xFFFF)

        # Gemini uses Quill editor — execCommand is the only reliable way to type
        d.execute_script("""
            const el = document.querySelector('div.ql-editor[aria-label="Enter a prompt for Gemini"]')
                     || document.querySelector('div[contenteditable="true"]');
            if (!el) return;
            el.focus();
            document.execCommand('insertText', false, arguments[0]);
        """, safe_text)
        time.sleep(0.3)

        # Verify content
        content = d.execute_script("""
            const el = document.querySelector('div.ql-editor') || document.querySelector('div[contenteditable="true"]');
            return el ? (el.innerText || '') : '';
        """)
        if len(content) < 10:
            log(f"  [gemini] WARN: textarea appears empty ({len(content)} chars)")

        submitted = d.execute_script("""
            const btns = Array.from(document.querySelectorAll('button'));
            const send = btns.find(b => {
                const label = (b.getAttribute('aria-label') || '').toLowerCase();
                return (label.includes('send') || label.includes('submit'))
                       && b.offsetParent !== null && !b.disabled;
            });
            if (send) { send.click(); return true; }
            return false;
        """)
        if not submitted:
            ta = d.find_element(By.CSS_SELECTOR,
                'div.ql-editor[aria-label="Enter a prompt for Gemini"], div[contenteditable="true"]')
            ta.send_keys(Keys.RETURN)

        return wait_for_streaming(d, self.STOP_SEL, timeout)

    def get_latest_response(self):
        d = self.driver
        for sel in ["model-response", ".model-response-text", "[data-response-index]",
                    "message-content", ".message-content"]:
            els = d.find_elements(By.CSS_SELECTOR, sel)
            if els:
                text = els[-1].text.strip()
                if len(text) > 50:
                    return text
        # JS fallback: text-density scan, skip nav/sidebar content
        return d.execute_script("""
            const candidates = [];
            const skipTexts = ['Conversation with Gemini', 'Where should we start',
                               'Create image', 'Boost my day'];
            document.querySelectorAll('p, [class*="response"], [class*="message"], [class*="markdown"]')
                .forEach(el => {
                    if (!el.offsetParent) return;
                    const t = (el.textContent || '').trim();
                    if (t.length < 100) return;
                    if (skipTexts.some(s => t.includes(s))) return;
                    candidates.push({el, len: t.length});
                });
            candidates.sort((a, b) => b.len - a.len);
            return candidates.length ? candidates[0].el.textContent.trim().substring(0, 10000) : '';
        """) or ""

    def model_name(self):
        return self._model_name or "Pro"


# ── Claude Engine ─────────────────────────────────────────────────────────────

class ClaudeEngine:
    STOP_SEL = 'button[aria-label="Stop response"]'

    def __init__(self, driver, model_target="Opus", extended_thinking=True):
        self.driver = driver
        self.name = "claude"
        self._model_target = model_target
        self._extended_thinking = extended_thinking
        self._model_name = model_target

    def screenshot(self, label):
        path = f"ein_claude_{label}.png"
        self.driver.save_screenshot(path)
        log(f"  [claude] screenshot: {path}")

    def new_chat(self):
        self.driver.get("https://claude.ai")
        time.sleep(4)

    def select_model(self, target=None, extended_thinking=None):
        d = self.driver
        target = target or self._model_target
        want_extended = extended_thinking if extended_thinking is not None else self._extended_thinking

        def open_dropdown():
            for btn in d.find_elements(By.TAG_NAME, "button"):
                if not btn.is_displayed(): continue
                if any(n in btn.text.strip() for n in ("Haiku", "Sonnet", "Opus")):
                    d.execute_script("arguments[0].click();", btn)
                    time.sleep(1.5)
                    return True
            return False

        def select_item(label):
            for item in d.find_elements(By.CSS_SELECTOR, '[role="menuitem"]'):
                if item.is_displayed() and label.lower() in item.text.lower():
                    d.execute_script("arguments[0].click();", item)
                    time.sleep(1.5)
                    return True
            return False

        def button_text():
            for btn in d.find_elements(By.TAG_NAME, "button"):
                if btn.is_displayed() and any(n in btn.text.strip() for n in ("Haiku", "Sonnet", "Opus")):
                    return btn.text.strip()
            return ""

        try:
            open_dropdown()
            select_item(target)

            has_extended = "Extended" in button_text()
            if want_extended and not has_extended:
                open_dropdown()
                select_item("Extended thinking")
                time.sleep(2)
            elif not want_extended and has_extended:
                open_dropdown()
                select_item("Extended thinking")  # toggle off
                time.sleep(2)

            d.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
            time.sleep(1)
            model = button_text()
            self._model_name = model
            log(f"  [claude] model: {model!r}")
            return model
        except Exception as e:
            log(f"  [claude] model select failed: {e}")
            return "unknown"

    def upload_file(self, filepath):
        """Upload a single file to Claude."""
        d = self.driver
        file_input = d.execute_script("""
            const inputs = Array.from(document.querySelectorAll('input[type="file"]'));
            if (!inputs.length) return null;
            const inp = inputs[0];
            inp.style.cssText = 'display:block;visibility:visible;opacity:1;position:fixed;top:0;left:0;width:1px;height:1px;z-index:999999';
            return inp;
        """)
        if not file_input:
            # Fallback: click attach button first
            d.execute_script("""
                const btns = Array.from(document.querySelectorAll('button'));
                const attach = btns.find(b => {
                    const label = (b.getAttribute('aria-label')||'').toLowerCase();
                    return label.includes('add') || label.includes('attach') || label.includes('file');
                });
                if (attach) attach.click();
            """)
            time.sleep(1)
            file_input = d.execute_script("""
                const inputs = Array.from(document.querySelectorAll('input[type="file"]'));
                if (!inputs.length) return null;
                const inp = inputs[0];
                inp.style.cssText = 'display:block;visibility:visible;opacity:1;position:fixed;top:0;left:0;width:1px;height:1px;z-index:999999';
                return inp;
            """)
        if file_input:
            file_input.send_keys(str(Path(filepath).resolve()))
            time.sleep(3)
            log(f"  [claude] uploaded: {Path(filepath).name}")
            return True
        log(f"  [claude] ERROR: file input not found for {filepath}")
        return False

    def upload_files(self, *filepaths):
        """Upload multiple files sequentially."""
        for f in filepaths:
            if not self.upload_file(f):
                return False
        return True

    def send_and_wait(self, text, timeout=PHASE_TIMEOUT):
        d = self.driver
        time.sleep(2)  # let DOM settle after upload / previous response

        # Claude uses ProseMirror/TipTap — execCommand is reliable
        d.execute_script("""
            const el = document.querySelector('div[contenteditable="true"]');
            if (!el) return;
            el.focus();
            document.execCommand('insertText', false, arguments[0]);
        """, text)
        time.sleep(0.3)

        # Verify content (use querySelector — avoids stale reference issue)
        content = d.execute_script(
            'return (document.querySelector(\'div[contenteditable="true"]\') || {innerText:""}).innerText || ""'
        )
        if len(content) < 10:
            log(f"  [claude] WARN: textarea appears empty ({len(content)} chars)")

        submitted = d.execute_script("""
            const btns = Array.from(document.querySelectorAll('button'));
            const send = btns.find(b =>
                (b.getAttribute('aria-label')||'').toLowerCase().includes('send')
                && b.offsetParent !== null && !b.disabled);
            if (send) { send.click(); return true; }
            return false;
        """)
        if not submitted:
            try:
                ta = d.find_element(By.CSS_SELECTOR, 'div[contenteditable="true"]')
                ta.send_keys(Keys.RETURN)
            except Exception:
                pass

        return wait_for_streaming(d, self.STOP_SEL, timeout)

    def get_latest_response(self):
        inline = self.driver.execute_script("""
            const byTestId = Array.from(document.querySelectorAll('[data-testid="assistant-message"]'));
            if (byTestId.length) return byTestId[byTestId.length - 1].innerText;
            const byClass = Array.from(document.querySelectorAll('.font-claude-message'));
            if (byClass.length) return byClass[byClass.length - 1].innerText;
            const divs = Array.from(document.querySelectorAll('div[class]')).filter(d => {
                const t = (d.innerText || '').trim();
                return t.length > 100 && !d.querySelector('div[contenteditable]');
            });
            if (divs.length) return divs[divs.length - 1].innerText;
            return '';
        """) or ""
        downloaded = resolve_downloads(self.driver, self.name)
        return (inline + "\n\n" + downloaded).strip() if downloaded else inline

    def model_name(self):
        return self._model_name or "Opus 4.6 Extended"


# ── Orchestration ─────────────────────────────────────────────────────────────

def run_parallel(engines, func, desc):
    """Run func(engine) in parallel threads. Hard-fails if any engine fails."""
    log(f"PHASE: {desc}")
    results = {}
    errors = {}

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
        for name, err in errors.items():
            log(f"  [{name}] error: {err}")
        sys.exit(1)

    return results


def build_phase_output(engines, elapsed_map, action="ask",
                       min_chars=200, retry_wait=180):
    """Build ein-ledger compatible output from current engine responses.

    If any engine has a short response (< min_chars), retries every 10s
    for up to retry_wait seconds — handles extended thinking models that
    finish after wait_for_streaming returns.
    """
    results = {}
    for engine in engines:
        resp = engine.get_latest_response()
        name = engine.name
        results[name] = {
            "success": len(resp) >= min_chars,
            "response": resp,
            "model_used": engine.model_name(),
            "llm": name,
            "elapsed_seconds": elapsed_map.get(name, 0),
        }

    # Retry loop: monitors all engines until each has >= min_chars AND has stopped growing.
    # An engine is considered "done" when its response length hasn't changed for 2 checks (20s).
    # This handles extended thinking models that stream slowly after wait_for_streaming returns.
    monitored = list(engines)
    prev_lens = {e.name: len(results[e.name]["response"]) for e in engines}
    stable_counts = {e.name: 0 for e in engines}
    needs_wait = any(len(results[e.name]["response"]) < min_chars for e in engines)
    if needs_wait:
        names = [e.name for e in monitored]
        log(f"Short responses from {[e.name for e in monitored if len(results[e.name]['response']) < min_chars]}, "
            f"waiting up to {retry_wait}s (stability check)...")

    for i in range(retry_wait // 10):
        if not monitored:
            break
        time.sleep(10)
        still_monitoring = []
        for engine in monitored:
            resp = engine.get_latest_response()
            cur_len = len(resp)
            # Always keep the longest captured version
            if cur_len > len(results[engine.name]["response"]):
                results[engine.name]["response"] = resp
            # Stability check
            if cur_len < min_chars:
                # Still too short — keep monitoring, reset stability
                stable_counts[engine.name] = 0
                still_monitoring.append(engine)
            elif cur_len == prev_lens[engine.name]:
                # Same length as last check — might be stable
                stable_counts[engine.name] += 1
                if stable_counts[engine.name] < 2:
                    still_monitoring.append(engine)  # need 2 consecutive stable reads
                else:
                    # Stable — mark done
                    results[engine.name]["success"] = True
                    log(f"  [{engine.name}] stable: {cur_len} chars "
                        f"(after {(i+1)*10}s extra wait)")
            else:
                # Still growing — reset stability counter
                stable_counts[engine.name] = 0
                results[engine.name]["success"] = False
                still_monitoring.append(engine)
            prev_lens[engine.name] = cur_len
        monitored = still_monitoring

    for name, r in results.items():
        if not r["success"]:
            r["error"] = f"Response too short ({len(r['response'])} chars)"

    return {
        "action": action,
        "results": results,
        "total_elapsed_seconds": round(max(elapsed_map.values()) if elapsed_map else 0, 1),
    }


def save_results(data, filename):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    log(f"Saved: {filename}")


def take_screenshots(engines, label):
    """Take screenshots from all engines (main thread, called after phase completes)."""
    for engine in engines:
        try:
            engine.screenshot(label)
        except Exception as e:
            log(f"  [{engine.name}] screenshot failed: {e}")


def check_failures(data, phase_name, min_chars=200):
    """Hard-fail if any engine has a short/missing response."""
    failures = []
    for name, r in data["results"].items():
        if not r.get("success") or len(r.get("response", "")) < min_chars:
            failures.append(f"{name}: {len(r.get('response', ''))} chars")
    if failures:
        log(f"FATAL: {phase_name} failed — short/missing responses: {failures}")
        sys.exit(1)


# ── Phase 1.5 config ──────────────────────────────────────────────────────────

P15_TEMPLATE = """You are on a fresh thread. You have NOT seen this material before.

Here are three opening positions on "{question}":

PERSPECTIVE A (ChatGPT):
{resp_chatgpt}

PERSPECTIVE B (Claude):
{resp_claude}

PERSPECTIVE C (Gemini):
{resp_gemini}

YOUR CONTRARIAN TASK — {lens}, targeted at PERSPECTIVE {target_label}:

{task}

Focus your critique SPECIFICALLY on Perspective {target_label}'s argument. You may reference the other perspectives for contrast, but your primary target is Perspective {target_label}.

Do NOT just disagree for the sake of it. Instead: what is the strongest, most inconvenient truth that undermines this position? What would a smart skeptic say that would make this participant uncomfortable?

Be specific. Take a clear stance. 4-6 paragraphs.

IMPORTANT: Do you have enough context from the provided documents and briefing to give a well-informed response? If not, tell me what additional information you need before proceeding."""

P15_TASKS = {
    # chatgpt critiques Claude (B) — Opposite Conclusion
    "chatgpt": {
        "lens": "Opposite Conclusion",
        "target_label": "B",
        "target": "Perspective B (Claude)",
        "task": (
            "What is the strongest case that Perspective B's core position is wrong? "
            "Why would following their recommendations actually make Ein WORSE? "
            "What would a principled critic say is fundamentally misguided about this direction?"
        ),
    },
    # claude critiques Gemini (C) — Missing Stakeholder/Risk
    "claude": {
        "lens": "Missing Stakeholder/Risk",
        "target_label": "C",
        "target": "Perspective C (Gemini)",
        "task": (
            "What critical stakeholder, risk, or second-order effect did Perspective C's position ignore? "
            "What blind spot would a smart skeptic expose?"
        ),
    },
    # gemini critiques ChatGPT (A) — Pre-Mortem
    "gemini": {
        "lens": "Pre-Mortem",
        "target_label": "A",
        "target": "Perspective A (ChatGPT)",
        "task": (
            "Imagine Perspective A's changes are implemented and Ein is WORSE six months later. "
            "What went wrong? What did Perspective A fail to anticipate?"
        ),
    },
}

P3_TEMPLATE = """Here are the other two participants' analyses:

PARTICIPANT {label1}:
{resp1}

PARTICIPANT {label2}:
{resp2}

Respond directly:

1. Where do you AGREE with their analysis? Be specific — which of their judgments do you share?
2. Where do you DISAGREE? What did they get wrong?
3. They identified fault lines and gaps. Are those the RIGHT fault lines? Or did they miss the real ones?
4. Has your position shifted after seeing their analysis? If yes, what moved you? If no, why not?

IMPORTANT: Do you have enough context from the provided documents and briefing to give a well-informed response? If not, tell me what additional information you need before proceeding."""

P4_TEMPLATE = """Here are the other two participants' Phase 3 responses:

PARTICIPANT {label1} (Phase 3):
{resp1}

PARTICIPANT {label2} (Phase 3):
{resp2}

This is your FINAL POSITION. Respond directly:

1. After seeing all arguments across both rounds, what is your FINAL ranked list of optimizations? Justify each ranking.
2. Where has your position CHANGED from your Phase 2 analysis? What specifically changed your mind?
3. Where has your position NOT changed despite pressure? Why do you hold firm?
4. What is the single strongest point made by either participant that you had NOT previously considered?
5. State your CLOSING POSITION clearly: your top 3 recommendations, in order, with one sentence each on why.

IMPORTANT: Do you have enough context from the provided documents and briefing to give a well-informed response? If not, tell me what additional information you need before proceeding."""


# ── Phase implementations ─────────────────────────────────────────────────────

def run_phase1(engines):
    """Phase 1: Opening positions. Fresh chats + upload all files + same prompt."""
    phase1_prompt = Path("phase1-prompt.txt").read_text(encoding="utf-8")

    def step(engine):
        t0 = time.time()
        engine.new_chat()
        engine.select_model()
        engine.screenshot("p1_01_model_selected")
        engine.upload_files(*UPLOAD_FILES)
        engine.screenshot("p1_02_uploaded")
        engine.send_and_wait(phase1_prompt, timeout=PHASE_TIMEOUT)
        elapsed = round(time.time() - t0, 1)
        resp = engine.get_latest_response()
        log(f"  [{engine.name}] phase1: {len(resp)} chars in {elapsed}s")
        engine.screenshot("p1_03_response")
        return elapsed

    elapsed_map = run_parallel(engines, step, "Phase 1: Opening Positions")
    data = build_phase_output(engines, elapsed_map, "phase1", min_chars=500, retry_wait=300)
    check_failures(data, "Phase 1", min_chars=500)
    save_results(data, "ein-phase1-results.json")
    log(f"Phase 1 COMPLETE: " + " | ".join(
        f"{n}={len(r['response'])}c" for n, r in data["results"].items()))
    return data


def run_phase15(engines, phase1_data):
    """Phase 1.5: Contrarian challenges. Fresh chats + upload protocol + per-engine prompts."""
    resp_chatgpt = phase1_data["results"]["chatgpt"]["response"]
    resp_claude  = phase1_data["results"]["claude"]["response"]
    resp_gemini  = phase1_data["results"]["gemini"]["response"]

    prompts = {}
    for name, task_info in P15_TASKS.items():
        prompts[name] = P15_TEMPLATE.format(
            question=DELIBERATION_QUESTION,
            resp_chatgpt=resp_chatgpt,
            resp_claude=resp_claude,
            resp_gemini=resp_gemini,
            lens=task_info["lens"],
            target_label=task_info["target_label"],
            task=task_info["task"],
        )
        log(f"  [{name}] Phase 1.5 prompt: {len(prompts[name])} chars")

    def step(engine):
        t0 = time.time()
        engine.new_chat()
        engine.select_model()
        engine.screenshot("p15_01_model_selected")
        engine.upload_files(*UPLOAD_FILES)
        engine.screenshot("p15_02_uploaded")
        engine.send_and_wait(prompts[engine.name], timeout=PHASE_TIMEOUT)
        elapsed = round(time.time() - t0, 1)
        resp = engine.get_latest_response()
        log(f"  [{engine.name}] phase1.5: {len(resp)} chars in {elapsed}s")
        engine.screenshot("p15_03_response")
        return elapsed

    elapsed_map = run_parallel(engines, step, "Phase 1.5: Contrarian Challenges")
    data = build_phase_output(engines, elapsed_map, "phase1_5")
    check_failures(data, "Phase 1.5", min_chars=200)
    save_results(data, "ein-phase15-results.json")
    log(f"Phase 1.5 COMPLETE: " + " | ".join(
        f"{n}={len(r['response'])}c" for n, r in data["results"].items()))
    return data


def run_phase2(engines, ledger, ledger_path):
    """Phase 2: Cross-examination R1. Fresh chats + upload BOTH files + real prompt.

    Uses dynamically generated context from ledger (Phase 1 + 1.5 responses).
    No priming step — both files uploaded together, real prompt sent immediately.
    """
    # Generate phase2-context.md from ledger
    log("Generating phase2-context.md from ledger...")
    ctx = _extract_prompt(ledger, "phase2")
    context_doc = ctx.get("document", "")
    if not context_doc:
        log("FATAL: extract_for_prompt returned empty document for phase2")
        sys.exit(1)
    Path("phase2-context.md").write_text(context_doc, encoding="utf-8")
    log(f"  phase2-context.md written: {len(context_doc)} chars")

    phase2_prompt = Path("phase2-prompt.txt").read_text(encoding="utf-8")

    def step(engine):
        t0 = time.time()
        engine.new_chat()
        engine.select_model()
        engine.screenshot("p2_01_model_selected")
        # Upload phase2 context + protocol spec only (code already in phase2-context via P1 responses)
        engine.upload_files("phase2-context.md", "three-way-deliberation.md")
        engine.screenshot("p2_02_files_uploaded")
        engine.send_and_wait(phase2_prompt, timeout=PHASE_TIMEOUT)
        elapsed = round(time.time() - t0, 1)
        resp = engine.get_latest_response()
        log(f"  [{engine.name}] phase2: {len(resp)} chars in {elapsed}s")
        engine.screenshot("p2_03_response")
        return elapsed

    elapsed_map = run_parallel(engines, step, "Phase 2: Cross-examination R1")
    data = build_phase_output(engines, elapsed_map, "phase2")
    check_failures(data, "Phase 2", min_chars=500)
    save_results(data, "ein-phase2-results.json")
    log(f"Phase 2 COMPLETE: " + " | ".join(
        f"{n}={len(r['response'])}c" for n, r in data["results"].items()))
    return data


def run_phase3(engines, phase2_data):
    """Phase 3: Cross-examination R2. Continue on Phase 2 thread. Each sees other two's P2."""
    chatgpt_resp = phase2_data["results"]["chatgpt"]["response"]
    claude_resp  = phase2_data["results"]["claude"]["response"]
    gemini_resp  = phase2_data["results"]["gemini"]["response"]

    prompts = {
        "claude":  P3_TEMPLATE.format(label1="A (ChatGPT)", resp1=chatgpt_resp,
                                       label2="B (Gemini)",  resp2=gemini_resp),
        "chatgpt": P3_TEMPLATE.format(label1="A (Claude)",  resp1=claude_resp,
                                       label2="B (Gemini)",  resp2=gemini_resp),
        "gemini":  P3_TEMPLATE.format(label1="A (Claude)",  resp1=claude_resp,
                                       label2="B (ChatGPT)", resp2=chatgpt_resp),
    }
    for name, p in prompts.items():
        log(f"  [{name}] Phase 3 prompt: {len(p)} chars")

    def step(engine):
        t0 = time.time()
        engine.send_and_wait(prompts[engine.name], timeout=PHASE_TIMEOUT)
        elapsed = round(time.time() - t0, 1)
        resp = engine.get_latest_response()
        log(f"  [{engine.name}] phase3: {len(resp)} chars in {elapsed}s")
        engine.screenshot("p3_01_response")
        return elapsed

    elapsed_map = run_parallel(engines, step, "Phase 3: Cross-examination R2")
    data = build_phase_output(engines, elapsed_map, "phase3")
    check_failures(data, "Phase 3", min_chars=200)
    save_results(data, "ein-phase3-results.json")
    log(f"Phase 3 COMPLETE: " + " | ".join(
        f"{n}={len(r['response'])}c" for n, r in data["results"].items()))
    return data


def run_phase4(engines, phase3_data):
    """Phase 4: Final positions. Continue on Phase 2 thread. Each sees other two's P3."""
    chatgpt_resp = phase3_data["results"]["chatgpt"]["response"]
    claude_resp  = phase3_data["results"]["claude"]["response"]
    gemini_resp  = phase3_data["results"]["gemini"]["response"]

    prompts = {
        "claude":  P4_TEMPLATE.format(label1="A (ChatGPT)", resp1=chatgpt_resp,
                                       label2="B (Gemini)",  resp2=gemini_resp),
        "chatgpt": P4_TEMPLATE.format(label1="A (Claude)",  resp1=claude_resp,
                                       label2="B (Gemini)",  resp2=gemini_resp),
        "gemini":  P4_TEMPLATE.format(label1="A (Claude)",  resp1=claude_resp,
                                       label2="B (ChatGPT)", resp2=chatgpt_resp),
    }
    for name, p in prompts.items():
        log(f"  [{name}] Phase 4 prompt: {len(p)} chars")

    def step(engine):
        t0 = time.time()
        engine.send_and_wait(prompts[engine.name], timeout=PHASE_TIMEOUT)
        elapsed = round(time.time() - t0, 1)
        resp = engine.get_latest_response()
        log(f"  [{engine.name}] phase4: {len(resp)} chars in {elapsed}s")
        engine.screenshot("p4_01_response")
        return elapsed

    elapsed_map = run_parallel(engines, step, "Phase 4: Final Positions")
    data = build_phase_output(engines, elapsed_map, "phase4")
    check_failures(data, "Phase 4", min_chars=200)
    save_results(data, "ein-phase4-results.json")
    log(f"Phase 4 COMPLETE: " + " | ".join(
        f"{n}={len(r['response'])}c" for n, r in data["results"].items()))
    return data


# ── Ledger operations ─────────────────────────────────────────────────────────

def ledger_append(ledger, ledger_path, phase_name, phase_data, assignments=None):
    """Append a phase to the ledger and save."""
    try:
        _append_phase(ledger, phase_name, phase_data, assignments)
        _save_ledger(ledger, ledger_path)
        log(f"Ledger: {phase_name} appended → {ledger_path}")
    except SystemExit:
        log(f"FATAL: Ledger append failed for {phase_name}")
        raise
    except Exception as e:
        log(f"FATAL: Ledger error for {phase_name}: {e}")
        sys.exit(1)


def audit_ledger(ledger, ledger_path):
    """Post-run audit: verify all phases present, all engines succeeded, models correct."""
    log("\n" + "="*60)
    log("LEDGER AUDIT")
    log("="*60)

    errors = []
    expected_phases = ["phase1", "phase1_5", "phase2", "phase3", "phase4"]
    expected_engines = {"chatgpt", "claude", "gemini"}

    for phase in expected_phases:
        if phase not in ledger.get("phases", {}):
            errors.append(f"MISSING phase: {phase}")
            continue

        entry = ledger["phases"][phase]
        log(f"\n  {phase}:")

        for engine in expected_engines:
            resp = entry.get("responses", {}).get(engine, {})
            success = resp.get("success", False)
            chars = len(resp.get("response", ""))
            model = resp.get("model_used", "unknown")
            status = "OK" if success else "FAIL"
            log(f"    [{engine}] {status} | {chars} chars | model={model}")
            if not success:
                errors.append(f"{phase}/{engine}: marked as failed")
            if chars < 100:
                errors.append(f"{phase}/{engine}: response too short ({chars} chars)")

    # Model verification
    log("\n  Model verification:")
    p1 = ledger["phases"].get("phase1", {})
    for engine in expected_engines:
        model = p1.get("responses", {}).get(engine, {}).get("model_used", "?")
        log(f"    [{engine}] model used: {model}")

    if errors:
        log(f"\n  AUDIT FAILED: {len(errors)} error(s):")
        for e in errors:
            log(f"    - {e}")
        return False
    else:
        log("\n  AUDIT PASSED: All phases complete, all engines succeeded.")
        return True


# ── Browser launch ────────────────────────────────────────────────────────────

def launch_browsers(profiles_subset=None):
    """Launch Chrome instances sequentially (avoids driver conflicts).

    profiles_subset: optional dict of {name: profile_path} to launch a subset.
    Defaults to the global PROFILES dict (all 3 engines).
    """
    profiles = profiles_subset if profiles_subset is not None else PROFILES
    URLS = {"chatgpt": "https://chatgpt.com", "gemini": "https://gemini.google.com", "claude": "https://claude.ai"}
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    drivers = {}
    for name, profile in profiles.items():
        log(f"Launching {name} browser...")
        clean_locks(profile)
        d = Driver(uc=True, headless=False, user_data_dir=profile)
        # Set download directory via CDP (works with uc=True)
        d.execute_cdp_cmd("Page.setDownloadBehavior", {
            "behavior": "allow",
            "downloadPath": DOWNLOAD_DIR,
        })
        drivers[name] = d
        time.sleep(3)

    for name in drivers:
        drivers[name].get(URLS[name])
    time.sleep(5)

    def check_ready(drivers):
        result = {}
        if "chatgpt" in drivers:
            result["chatgpt"] = bool(drivers["chatgpt"].find_elements(By.CSS_SELECTOR, "#prompt-textarea"))
        if "claude" in drivers:
            result["claude"] = bool(drivers["claude"].find_elements(By.CSS_SELECTOR, 'div[contenteditable="true"]'))
        if "gemini" in drivers:
            # Gemini: contenteditable EXISTS on logged-out page too — check absence of "Sign in" button
            gm_has_input = bool(drivers["gemini"].find_elements(By.CSS_SELECTOR, 'div[contenteditable="true"]'))
            gm_signed_out = drivers["gemini"].execute_script("""
                return Array.from(document.querySelectorAll('a, button')).some(
                    el => el.textContent.trim() === 'Sign in' && el.offsetParent !== null
                );
            """)
            result["gemini"] = gm_has_input and not gm_signed_out
        return result

    ready = check_ready(drivers)
    not_ready = [n for n, r in ready.items() if not r]
    if not_ready:
        log(f"NOT LOGGED IN: {not_ready}. Waiting up to 300s for manual login...")
        for i in range(30):
            time.sleep(10)
            ready = check_ready(drivers)
            remaining = 300 - (i + 1) * 10
            status = " | ".join(f"{n}={'OK' if ready[n] else 'WAIT'}" for n in ready)
            log(f"  {status}  ({remaining}s left)")
            if all(ready.values()):
                break

    if not all(ready.values()):
        log(f"FATAL: Not all engines logged in: {ready}")
        sys.exit(1)

    log(f"{len(drivers)} browser(s) ready: {list(drivers)}")
    return drivers


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Ein deliberation runner (SeleniumBase)")
    parser.add_argument("--phase", type=str,
        help="Run specific phase: 1, 1.5, 2, 3, 4, or 'all' (default: all)")
    parser.add_argument("--kill-stale", action="store_true",
        help="Kill stale automation Chrome processes first")
    parser.add_argument("--model-chatgpt", type=str, default="thinking",
        help="ChatGPT model keyword (default: thinking)")
    parser.add_argument("--model-gemini", type=str, default="Pro",
        help="Gemini model keyword (default: Pro)")
    parser.add_argument("--model-claude", type=str, default="Opus",
        help="Claude model keyword (default: Opus)")
    parser.add_argument("--no-extended-thinking", action="store_true",
        help="Disable Claude extended thinking")
    parser.add_argument("--only", type=str, default=None,
        help="Comma-separated engines to run (e.g. chatgpt, chatgpt,claude). "
             "Skips ledger audit — for testing only.")
    parser.add_argument("--skip-check", action="store_true",
        help="Skip brief suitability check")
    args = parser.parse_args()

    phase = args.phase or "all"
    extended = not args.no_extended_thinking

    only_engines = [x.strip().lower() for x in args.only.split(",")] if args.only else None

    # ── Brief suitability check ──────────────────────────────────────────────
    # The adversarial deliberation pipeline works well for specific topic types.
    if not args.skip_check:
        brief_text = (DELIBERATION_QUESTION + " " + DELIBERATION_CONTEXT + " " +
                      DELIBERATION_BRIEF.get("success_criteria", "")).lower()

        SUITABLE_CATEGORIES = [
            ("truth-seeking / factual",
             ["true", "false", "fact", "evidence", "verify", "claim", "cause",
              "prove", "investigate", "determine"]),
            ("decision-making",
             ["should", "decision", "choose", "option", "recommend", "trade-off",
              "risk", "versus", " vs ", "pros and cons", "approve"]),
            ("risk assessment",
             ["risk", "threat", "vulnerability", "failure", "worst case",
              "what could go wrong", "danger", "mitigation", "impact"]),
            ("ethical / governance",
             ["ethical", "governance", "responsible", "fair", "bias",
              "accountability", "compliance", "moral", "principle"]),
            ("adversarial review",
             ["review", "critique", "challenge", "weak", "flaw", "assumption",
              "sound", "robust", "stress test", "audit"]),
        ]

        matched = []
        for category, signals in SUITABLE_CATEGORIES:
            hits = sum(1 for s in signals if s in brief_text)
            if hits >= 2:
                matched.append(category)

        if not matched:
            log("")
            log("=" * 70)
            log("BRIEF SUITABILITY CHECK — FAILED")
            log("=" * 70)
            log("")
            log("This pipeline uses adversarial multi-model deliberation with")
            log("contrarian lenses and cross-examination. It works well for:")
            log("")
            log("  • Truth-seeking / factual     — testing claims under pressure")
            log("  • Decision-making              — adversarial evaluation of options")
            log("  • Risk assessment              — surfacing what could go wrong")
            log("  • Ethical / governance          — exploring competing principles")
            log("  • Adversarial review            — stress-testing assumptions")
            log("")
            log("Your brief did not match any of these categories.")
            log("")
            log("If your brief is about MERGING DOCUMENTS or SYNTHESIZING")
            log("multiple sources into a unified output, use the Ein Design")
            log("cross-pollination pipeline instead:")
            log("  → python ein-design.py --prompt <your-brief> --upload-files <files>")
            log("  (collaborative convergence with cross-pollination rounds)")
            log("")
            log("If you believe this brief IS suitable, re-run with --skip-check")
            log("=" * 70)
            sys.exit(1)
        else:
            log(f"Brief suitability: PASS — matched categories: {', '.join(matched)}")

    if args.kill_stale:
        import subprocess
        subprocess.run([
            "powershell.exe", "-Command",
            r'Get-WmiObject Win32_Process | Where-Object { $_.Name -eq "chrome.exe" -and $_.CommandLine -like "*chrome-automation-profile*" } | ForEach-Object { $_.Terminate() }'
        ], capture_output=True)
        log("Killed stale Chrome processes")
        time.sleep(2)

    # Create ledger
    ledger_path = Path(f"deliberation-ledger-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json")
    log(f"Creating ledger: {ledger_path}")
    ledger = _create_ledger(DELIBERATION_QUESTION, DELIBERATION_CONTEXT, ledger_path,
                            brief=DELIBERATION_BRIEF)

    # Launch browsers (subset if --only specified)
    active_profiles = {k: v for k, v in PROFILES.items()
                       if only_engines is None or k in only_engines}
    if only_engines:
        log(f"--only mode: launching {list(active_profiles)} only")
    drivers = launch_browsers(active_profiles)

    all_engines = [
        ChatGPTEngine(drivers["chatgpt"], model_target=args.model_chatgpt)
            if "chatgpt" in drivers else None,
        GeminiEngine(drivers["gemini"],   model_target=args.model_gemini)
            if "gemini" in drivers else None,
        ClaudeEngine(drivers["claude"],   model_target=args.model_claude,
                     extended_thinking=extended)
            if "claude" in drivers else None,
    ]
    engines = [e for e in all_engines if e is not None]

    start_total = time.time()
    p1_data = p15_data = p2_data = p3_data = None

    def maybe_append(phase_name, data, assignments=None):
        """Append to ledger only in full-run mode (--only skips ledger write)."""
        if not only_engines:
            ledger_append(ledger, ledger_path, phase_name, data, assignments)

    if phase in ("1", "all"):
        p1_data = run_phase1(engines)
        maybe_append("phase1", p1_data)

    if phase in ("1.5", "all"):
        if p1_data is None:
            p1_data = json.loads(Path("ein-phase1-results.json").read_text(encoding="utf-8"))
        p15_data = run_phase15(engines, p1_data)
        maybe_append("phase1_5", p15_data, assignments=P15_TASKS)

    if phase in ("2", "all"):
        if p15_data is None:
            # Rebuild ledger from saved results if resuming mid-run
            p1_saved  = json.loads(Path("ein-phase1-results.json").read_text(encoding="utf-8"))
            p15_saved = json.loads(Path("ein-phase15-results.json").read_text(encoding="utf-8"))
            if "phase1" not in ledger.get("phases", {}):
                _append_phase(ledger, "phase1", p1_saved)
            if "phase1_5" not in ledger.get("phases", {}):
                _append_phase(ledger, "phase1_5", p15_saved, P15_TASKS)
        p2_data = run_phase2(engines, ledger, ledger_path)
        maybe_append("phase2", p2_data)

    if phase in ("3", "all"):
        if p2_data is None:
            p2_data = json.loads(Path("ein-phase2-results.json").read_text(encoding="utf-8"))
        p3_data = run_phase3(engines, p2_data)
        maybe_append("phase3", p3_data)

    if phase in ("4", "all"):
        if p3_data is None:
            p3_data = json.loads(Path("ein-phase3-results.json").read_text(encoding="utf-8"))
        p4_data = run_phase4(engines, p3_data)
        maybe_append("phase4", p4_data)

    total = round(time.time() - start_total, 1)
    log(f"\nAll phases complete in {total}s")

    if only_engines:
        # --only mode: print responses for review, skip full audit
        log(f"\n{'='*60}")
        log("--only mode: RESPONSE PREVIEW (no audit)")
        log(f"{'='*60}")
        # Print from result data variables (not ledger, since we didn't append)
        p4_data_maybe = locals().get("p4_data")
        for phase_name, data in [
            ("phase1", p1_data), ("phase1_5", p15_data),
            ("phase2", p2_data), ("phase3", p3_data), ("phase4", p4_data_maybe),
        ]:
            if data:
                for name, r in data.get("results", {}).items():
                    resp = r.get("response", "")
                    log(f"\n[{phase_name}][{name}] {len(resp)} chars:")
                    log(resp[:800] + ("..." if len(resp) > 800 else ""))
        log(f"\nResults saved to ein-phase1-results.json (and other phase files)")
    else:
        # Audit
        passed = audit_ledger(ledger, ledger_path)
        if not passed:
            log("\nFATAL: Audit failed. Results are incomplete or incorrect.")
            sys.exit(1)
        log(f"\nLedger saved: {ledger_path}")
    log("Browsers left open (sessions preserved). Close manually when done.")


if __name__ == "__main__":
    main()
