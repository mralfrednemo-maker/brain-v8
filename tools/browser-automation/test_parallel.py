"""
Runs ChatGPT (Thinking), Gemini (Pro), and Claude (Opus + Extended Thinking) in parallel.
After getting responses, opens a new chat on each — then stops.
"""
import os, time, threading
from pathlib import Path
from seleniumbase import Driver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

PROFILE_CHATGPT = r"C:\Users\chris\PROJECTS\chrome-automation-profile"
PROFILE_GEMINI  = r"C:\Users\chris\PROJECTS\chrome-automation-profile-2"
PROFILE_CLAUDE  = r"C:\Users\chris\PROJECTS\chrome-automation-profile-3"
TEST_FILE = Path(r"C:\Users\chris\PROJECTS\test_upload_file.txt").resolve()
PROMPT = "What is the project name and version described in the uploaded file? List all the features mentioned."

results = {}


def clean_locks(profile_dir):
    for root, dirs, files in os.walk(profile_dir):
        for f in files:
            if f in ["LOCK", "lockfile", "SingletonLock"]:
                try: os.remove(os.path.join(root, f))
                except: pass


def wait_for_done(driver, stop_selector, timeout=300):
    """Poll until streaming indicator disappears."""
    for i in range(timeout // 2):
        time.sleep(2)
        if not driver.find_elements(By.CSS_SELECTOR, stop_selector):
            return i * 2
    return timeout


# ── ChatGPT ──────────────────────────────────────────────────────────────────

def run_chatgpt(driver=None):
    tag = "[ChatGPT]"
    try:
        print(f"{tag} Starting")
        time.sleep(2)

        # Select Thinking model
        print(f"{tag} Opening model selector...")
        driver.find_element(By.CSS_SELECTOR, 'button[aria-label="Model selector"]').click()
        time.sleep(1)
        driver.save_screenshot("chatgpt_s1_model_dropdown.png")

        clicked_model = driver.execute_script("""
            const items = Array.from(document.querySelectorAll('[role="option"], [role="menuitem"], [role="menuitemradio"], li, button'));
            const thinking = items.find(el => {
                const t = (el.textContent || '').toLowerCase();
                return (t.includes('think') || t.includes('reason') || t.includes('o3') || t.includes('o1')) && el.offsetParent !== null;
            });
            if (thinking) { thinking.click(); return thinking.textContent.trim(); }
            return null;
        """)
        time.sleep(1)
        driver.save_screenshot("chatgpt_s2_model_selected.png")
        print(f"{tag} Model selected: {(clicked_model or 'not found')[:50]}")

        # Attach file
        driver.execute_script("""
            const textarea = document.querySelector('#prompt-textarea');
            if (!textarea) return;
            const textareaRect = textarea.getBoundingClientRect();
            const buttons = Array.from(document.querySelectorAll('button')).filter(b => b.offsetParent !== null);
            const scored = buttons.map(b => {
                const text = [b.getAttribute('aria-label'),b.getAttribute('title'),b.getAttribute('data-testid'),b.textContent].join(' ').toLowerCase();
                let score = 0;
                if (text.includes('attach')) score += 100;
                if (text.includes('upload')) score += 80;
                if (text.includes('file')) score += 40;
                if (b.textContent.trim() === '+') score += 30;
                const r = b.getBoundingClientRect();
                if (Math.abs(r.bottom-textareaRect.bottom)<160 && Math.abs(r.left-textareaRect.left)<260) score += 20;
                return {b, score};
            }).sort((a,b) => b.score-a.score);
            if (scored.length && scored[0].score > 0) scored[0].b.click();
        """)
        time.sleep(2)

        file_input = driver.execute_script("""
            const inputs = Array.from(document.querySelectorAll('input[type="file"]'));
            const isImageOnly = inp => {
                const a = (inp.getAttribute('accept')||'').toLowerCase();
                if (!a) return false;
                return a.split(',').map(x=>x.trim()).filter(Boolean).every(p => p.startsWith('image/') || ['.png','.jpg','.jpeg','.gif','.webp','.bmp','.svg'].includes(p));
            };
            const inp = inputs.find(i => !isImageOnly(i));
            if (!inp) return null;
            inp.style.cssText = 'display:block;visibility:visible;opacity:1;position:fixed;top:0;left:0;width:1px;height:1px;z-index:999999';
            return inp;
        """)
        if file_input:
            file_input.send_keys(str(TEST_FILE))
            print(f"{tag} File attached")
        else:
            print(f"{tag} ERROR: file input not found")
        time.sleep(3)
        driver.save_screenshot("chatgpt_s3_file_attached.png")

        # Type prompt
        ta = driver.find_element(By.CSS_SELECTOR, "#prompt-textarea")
        ta.click()
        ta.send_keys(PROMPT)
        time.sleep(1)
        driver.save_screenshot("chatgpt_s4_prompt_typed.png")

        # Submit
        submitted = driver.execute_script("""
            const btn = document.querySelector("button[data-testid='send-button']");
            if (btn) { btn.click(); return true; } return false;
        """)
        if not submitted:
            ta.send_keys(Keys.RETURN)
        print(f"{tag} Prompt submitted — waiting for response...")
        driver.save_screenshot("chatgpt_s5_submitted.png")

        secs = wait_for_done(driver, 'button[aria-label="Stop streaming"], button[data-testid="stop-button"]')
        driver.save_screenshot("chatgpt_s6_response.png")
        print(f"{tag} Response received after ~{secs}s")

        resp_els = driver.find_elements(By.CSS_SELECTOR, "[data-message-author-role='assistant']")
        results["chatgpt"] = resp_els[-1].text if resp_els else "ERROR: no response found"

        print(f"{tag} Done")

    except Exception as e:
        results["chatgpt"] = f"ERROR: {e}"
        print(f"{tag} FAILED: {e}")
        try: driver.save_screenshot("chatgpt_ERROR.png")
        except: pass


# ── Gemini ────────────────────────────────────────────────────────────────────

def run_gemini(driver=None):
    tag = "[Gemini] "
    try:
        time.sleep(2)
        print(f"{tag} Starting")

        # Select Pro model
        print(f"{tag} Selecting Pro model...")
        for btn in driver.find_elements(By.TAG_NAME, "button"):
            if btn.text.strip() in ("Pro", "Fast", "Thinking", "Flash") and btn.is_displayed():
                btn.click()
                time.sleep(1)
                break
        driver.save_screenshot("gemini_s1_model_dropdown.png")

        for item in driver.find_elements(By.CSS_SELECTOR, '[role="option"],[role="menuitem"]'):
            if "Pro" in item.text and "Flash" not in item.text and item.is_displayed():
                item.click()
                print(f"{tag} Pro model selected")
                break
        time.sleep(1)
        driver.save_screenshot("gemini_s2_model_selected.png")

        # Suppress file dialog, upload file
        driver.execute_script("""
            HTMLInputElement.prototype._origClick = HTMLInputElement.prototype.click;
            HTMLInputElement.prototype.click = function() {
                if (this.type === 'file') return;
                return this._origClick.apply(this, arguments);
            };
        """)

        for btn in driver.find_elements(By.TAG_NAME, "button"):
            try:
                label = (btn.get_attribute("aria-label") or "").lower()
                if ("add" in label or "attach" in label or "upload" in label or btn.text.strip() == "+") and btn.is_displayed():
                    driver.execute_script("arguments[0].click();", btn)
                    break
            except: pass
        time.sleep(1)

        for item in driver.find_elements(By.XPATH, "//*[contains(text(),'Upload files')]"):
            if item.is_displayed():
                item.click()
                break
        time.sleep(1)

        file_input = driver.execute_script("""
            const inp = document.querySelector('input[type="file"]');
            if (!inp) return null;
            inp.style.cssText = 'display:block;visibility:visible;opacity:1;position:fixed;top:0;left:0;width:1px;height:1px;z-index:999999';
            return inp;
        """)
        if file_input:
            file_input.send_keys(str(TEST_FILE))
            print(f"{tag} File attached")
        else:
            print(f"{tag} ERROR: file input not found")
        time.sleep(4)
        driver.save_screenshot("gemini_s3_file_attached.png")

        # Type prompt
        ta = driver.find_element(By.CSS_SELECTOR, 'div[contenteditable="true"]')
        ta.click()
        ta.send_keys(PROMPT)
        time.sleep(1)
        driver.save_screenshot("gemini_s4_prompt_typed.png")

        # Submit
        submitted = driver.execute_script("""
            const btns = Array.from(document.querySelectorAll('button'));
            const send = btns.find(b => (b.getAttribute('aria-label')||'').toLowerCase().includes('send') && b.offsetParent!==null);
            if (send) { send.click(); return true; } return false;
        """)
        if not submitted:
            ta.send_keys(Keys.RETURN)
        print(f"{tag} Prompt submitted — waiting for response...")
        driver.save_screenshot("gemini_s5_submitted.png")

        secs = wait_for_done(driver, 'button[aria-label="Stop response"]')
        driver.save_screenshot("gemini_s6_response.png")
        print(f"{tag} Response received after ~{secs}s")

        resp_els = driver.find_elements(By.CSS_SELECTOR, '.model-response-text')
        if not resp_els:
            resp_els = driver.find_elements(By.CSS_SELECTOR, 'model-response')
        results["gemini"] = resp_els[-1].text if resp_els else "ERROR: no response found"

        print(f"{tag} Done")

    except Exception as e:
        results["gemini"] = f"ERROR: {e}"
        print(f"{tag} FAILED: {e}")
        try: driver.save_screenshot("gemini_ERROR.png")
        except: pass


# ── Claude ────────────────────────────────────────────────────────────────────

def run_claude(driver=None):
    tag = "[Claude] "
    try:
        time.sleep(2)
        print(f"{tag} Starting")

        def open_model_dropdown():
            for btn in driver.find_elements(By.TAG_NAME, "button"):
                if not btn.is_displayed():
                    continue
                text = btn.text.strip()
                if any(name in text for name in ("Haiku", "Sonnet", "Opus")):
                    driver.execute_script("arguments[0].click();", btn)
                    time.sleep(1.5)
                    return True
            return False

        def select_menu_item(label_contains):
            for item in driver.find_elements(By.CSS_SELECTOR, '[role="menuitem"]'):
                if item.is_displayed() and label_contains.lower() in item.text.lower():
                    driver.execute_script("arguments[0].click();", item)
                    time.sleep(1.5)
                    return True
            return False

        def model_button_text():
            for btn in driver.find_elements(By.TAG_NAME, "button"):
                if btn.is_displayed():
                    text = btn.text.strip()
                    if any(name in text for name in ("Haiku", "Sonnet", "Opus")):
                        return text
            return ""

        # Select Opus 4.6
        print(f"{tag} Selecting Opus 4.6...")
        open_model_dropdown()
        driver.save_screenshot("claude_s1_model_dropdown.png")
        select_menu_item("Opus")
        driver.save_screenshot("claude_s2_opus_selected.png")
        print(f"{tag} Model: {repr(model_button_text())}")

        # Enable Extended Thinking
        print(f"{tag} Enabling Extended Thinking...")
        is_on = "Extended" in model_button_text()
        if not is_on:
            open_model_dropdown()
            driver.save_screenshot("claude_s3_dropdown_for_thinking.png")
            select_menu_item("Extended thinking")
            time.sleep(2)
        driver.save_screenshot("claude_s4_thinking_enabled.png")
        print(f"{tag} Model now: {repr(model_button_text())}")

        # Dismiss any overlay
        driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
        time.sleep(1)

        # Upload file
        print(f"{tag} Uploading file...")
        file_input = driver.execute_script("""
            const inputs = Array.from(document.querySelectorAll('input[type="file"]'));
            if (!inputs.length) return null;
            const inp = inputs[0];
            inp.style.cssText = 'display:block;visibility:visible;opacity:1;position:fixed;top:0;left:0;width:1px;height:1px;z-index:999999';
            return inp;
        """)
        if not file_input:
            driver.execute_script("""
                const btns = Array.from(document.querySelectorAll('button'));
                const attach = btns.find(b => {
                    const label = (b.getAttribute('aria-label')||'').toLowerCase();
                    return label.includes('add') || label.includes('attach') || label.includes('file');
                });
                if (attach) attach.click();
            """)
            time.sleep(1)
            file_input = driver.execute_script("""
                const inputs = Array.from(document.querySelectorAll('input[type="file"]'));
                if (!inputs.length) return null;
                const inp = inputs[0];
                inp.style.cssText = 'display:block;visibility:visible;opacity:1;position:fixed;top:0;left:0;width:1px;height:1px;z-index:999999';
                return inp;
            """)
        if file_input:
            file_input.send_keys(str(TEST_FILE))
            print(f"{tag} File attached")
        else:
            print(f"{tag} ERROR: file input not found")
        time.sleep(3)
        driver.save_screenshot("claude_s5_file_attached.png")

        # Type prompt
        print(f"{tag} Typing prompt...")
        ta = driver.find_element(By.CSS_SELECTOR, 'div[contenteditable="true"]')
        driver.execute_script("arguments[0].focus();", ta)
        time.sleep(0.5)
        ta.send_keys(PROMPT)
        time.sleep(1)
        driver.save_screenshot("claude_s6_prompt_typed.png")

        # Submit
        submitted = driver.execute_script("""
            const btns = Array.from(document.querySelectorAll('button'));
            const send = btns.find(b => (b.getAttribute('aria-label')||'').toLowerCase().includes('send') && b.offsetParent !== null);
            if (send) { send.click(); return send.getAttribute('aria-label'); }
            return null;
        """)
        if not submitted:
            ta.send_keys(Keys.RETURN)
        print(f"{tag} Prompt submitted — waiting for response...")
        driver.save_screenshot("claude_s7_submitted.png")

        secs = wait_for_done(driver, 'button[aria-label="Stop response"]')
        driver.save_screenshot("claude_s8_response.png")
        print(f"{tag} Response received after ~{secs}s")

        response_text = driver.execute_script("""
            const byTestId = Array.from(document.querySelectorAll('[data-testid="assistant-message"]'));
            if (byTestId.length) return byTestId[byTestId.length - 1].innerText;
            const byClass = Array.from(document.querySelectorAll('.font-claude-message'));
            if (byClass.length) return byClass[byClass.length - 1].innerText;
            const divs = Array.from(document.querySelectorAll('div[class]')).filter(d => {
                const t = (d.innerText || '').trim();
                return t.length > 100 && !d.querySelector('div[contenteditable]');
            });
            if (divs.length) return divs[divs.length - 1].innerText;
            return null;
        """)
        results["claude"] = response_text or "ERROR: no response found"

        print(f"{tag} Done")

    except Exception as e:
        results["claude"] = f"ERROR: {e}"
        print(f"{tag} FAILED: {e}")
        try: driver.save_screenshot("claude_ERROR.png")
        except: pass


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Launch browsers sequentially to avoid uc_driver conflict
    clean_locks(PROFILE_CHATGPT)
    driver_chatgpt = Driver(uc=True, headless=False, user_data_dir=PROFILE_CHATGPT)
    time.sleep(3)
    clean_locks(PROFILE_GEMINI)
    driver_gemini = Driver(uc=True, headless=False, user_data_dir=PROFILE_GEMINI)
    time.sleep(3)
    clean_locks(PROFILE_CLAUDE)
    driver_claude = Driver(uc=True, headless=False, user_data_dir=PROFILE_CLAUDE)
    time.sleep(2)

    # Navigate all to their sites
    driver_chatgpt.get("https://chatgpt.com")
    driver_gemini.get("https://gemini.google.com")
    driver_claude.get("https://claude.ai")

    # Check login
    time.sleep(5)
    chatgpt_ready = bool(driver_chatgpt.find_elements(By.CSS_SELECTOR, "#prompt-textarea"))
    gemini_ready  = bool(driver_gemini.find_elements(By.CSS_SELECTOR, 'div[contenteditable="true"]'))
    claude_ready  = bool(driver_claude.find_elements(By.CSS_SELECTOR, 'div[contenteditable="true"]'))

    if not chatgpt_ready or not gemini_ready or not claude_ready:
        print("\n" + "=" * 50)
        if not chatgpt_ready: print("→ Log in to ChatGPT in browser 1")
        if not gemini_ready:  print("→ Log in to Gemini in browser 2")
        if not claude_ready:  print("→ Log in to Claude in browser 3")
        print("You have 120 seconds...")
        print("=" * 50)
        for i in range(12):
            time.sleep(10)
            chatgpt_ready = bool(driver_chatgpt.find_elements(By.CSS_SELECTOR, "#prompt-textarea"))
            gemini_ready  = bool(driver_gemini.find_elements(By.CSS_SELECTOR, 'div[contenteditable="true"]'))
            claude_ready  = bool(driver_claude.find_elements(By.CSS_SELECTOR, 'div[contenteditable="true"]'))
            remaining = 120 - (i + 1) * 10
            status = f"  ChatGPT={'✓' if chatgpt_ready else '…'}  Gemini={'✓' if gemini_ready else '…'}  Claude={'✓' if claude_ready else '…'}  ({remaining}s left)"
            print(status)
            if chatgpt_ready and gemini_ready and claude_ready:
                break

    print("\nAll ready — starting parallel run...")

    t1 = threading.Thread(target=run_chatgpt, args=(driver_chatgpt,))
    t2 = threading.Thread(target=run_gemini,  args=(driver_gemini,))
    t3 = threading.Thread(target=run_claude,  args=(driver_claude,))

    t1.start()
    t2.start()
    t3.start()

    t1.join()
    t2.join()
    t3.join()

    print("\n" + "=" * 60)
    print("ChatGPT response:")
    print("=" * 60)
    print(results.get("chatgpt", "no result"))

    print("\n" + "=" * 60)
    print("Gemini response:")
    print("=" * 60)
    print(results.get("gemini", "no result"))

    print("\n" + "=" * 60)
    print("Claude response:")
    print("=" * 60)
    print(results.get("claude", "no result"))
