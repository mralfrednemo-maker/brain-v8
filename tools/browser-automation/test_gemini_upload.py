import argparse, os, time
from pathlib import Path
from seleniumbase import Driver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys


AUTOMATION_PROFILE_DIR = r"C:\Users\chris\PROJECTS\chrome-automation-profile-2"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--prompt', required=True, help='Prompt text to send')
    parser.add_argument('--file', default=None, help='Optional file path to attach')
    parser.add_argument('--new', action='store_true', help='Start a fresh conversation thread')
    args = parser.parse_args()

    file_path = Path(args.file).resolve() if args.file else None
    THREAD_FILE = Path(AUTOMATION_PROFILE_DIR) / ".jj_thread_url"

    # Remove stale lock files (no global taskkill)
    for root, dirs, files in os.walk(AUTOMATION_PROFILE_DIR):
        for f in files:
            if f in ["LOCK", "lockfile", "SingletonLock"]:
                try: os.remove(os.path.join(root, f))
                except: pass

    driver = Driver(uc=True, headless=False, user_data_dir=AUTOMATION_PROFILE_DIR)

    # Navigate to existing thread or start fresh
    if not args.new and THREAD_FILE.exists():
        saved_url = THREAD_FILE.read_text().strip()
        driver.get(saved_url)
    else:
        if args.new and THREAD_FILE.exists():
            THREAD_FILE.unlink()
        driver.get("https://gemini.google.com")
    time.sleep(6)

    # Ensure Pro model is selected
    btn_texts = [b.text.strip() for b in driver.find_elements(By.TAG_NAME, "button") if b.is_displayed()]
    if "Pro" not in btn_texts:
        for btn in driver.find_elements(By.TAG_NAME, "button"):
            if btn.is_displayed() and btn.text.strip() in ("Fast", "Thinking"):
                btn.click()
                time.sleep(0.5)
                items = driver.find_elements(By.CSS_SELECTOR, '[role="option"], [role="menuitem"]')
                for item in items:
                    if "Pro" in item.text and item.is_displayed():
                        item.click()
                        print("Pro model selected")
                        break
                break
    else:
        print("Pro model already active")
    time.sleep(1)

    # File upload (optional)
    if file_path:
        plus_btn = None
        for btn in driver.find_elements(By.TAG_NAME, "button"):
            try:
                label = btn.get_attribute("aria-label") or ""
                if "add" in label.lower() or "attach" in label.lower() or "upload" in label.lower():
                    if btn.is_displayed():
                        plus_btn = btn
                        break
            except:
                pass

        if not plus_btn:
            plus_btn = driver.execute_script("""
                const btns = Array.from(document.querySelectorAll('button'));
                return btns.find(b => b.textContent.trim() === '+' && b.offsetParent !== null) || null;
            """)

        if plus_btn:
            driver.execute_script("arguments[0].click();", plus_btn)
        else:
            print("WARNING: + button not found, trying direct file input")

        time.sleep(1)

        for item in driver.find_elements(By.XPATH, "//*[contains(text(),'Upload files')]"):
            if item.is_displayed():
                item.click()
                break
        time.sleep(1)

        file_input = driver.execute_script("""
            const inputs = Array.from(document.querySelectorAll('input[type="file"]'));
            if (!inputs.length) return null;
            const input = inputs[0];
            input.style.display = 'block';
            input.style.visibility = 'visible';
            input.style.opacity = '1';
            input.style.position = 'fixed';
            input.style.top = '0'; input.style.left = '0';
            input.style.width = '1px'; input.style.height = '1px';
            input.style.zIndex = '999999';
            return input;
        """)

        if file_input:
            file_input.send_keys(str(file_path))
        else:
            print("ERROR: no file input found")
            driver.quit()
            return

        time.sleep(4)

    # Type the prompt
    textarea = driver.find_element(By.CSS_SELECTOR, 'div[contenteditable="true"], textarea[aria-label*="Gemini" i], p[data-placeholder*="Ask" i]')
    textarea.click()
    textarea.send_keys(args.prompt)
    time.sleep(1)

    # Submit
    submitted = driver.execute_script("""
        const btns = Array.from(document.querySelectorAll('button'));
        const send = btns.find(b => {
            const label = (b.getAttribute('aria-label') || '').toLowerCase();
            return (label.includes('send') || label.includes('submit')) && b.offsetParent !== null;
        });
        if (send) { send.click(); return true; }
        return false;
    """)
    if not submitted:
        textarea.send_keys(Keys.RETURN)

    # Poll until streaming finishes (up to 3 minutes)
    for _ in range(90):
        time.sleep(2)
        stop = driver.find_elements(By.CSS_SELECTOR,
            'button[aria-label="Stop generating"], [aria-label*="stop" i]')
        generating = driver.find_elements(By.CSS_SELECTOR,
            '.loading, [data-is-streaming="true"], mat-progress-bar')
        if not stop and not generating:
            break

    # Read response — full text, no truncation
    responses = driver.find_elements(By.CSS_SELECTOR, 'model-response, .model-response-text, [data-response-index]')
    if not responses:
        responses = driver.find_elements(By.CSS_SELECTOR, 'message-content, .message-content')
    if responses:
        print(responses[-1].text)
    else:
        print("ERROR: could not extract response text")

    # Save current conversation URL for thread continuity
    current_url = driver.current_url
    if "/app/" in current_url or "?conversation" in current_url:
        THREAD_FILE.write_text(current_url)
    elif current_url != "https://gemini.google.com/" and "gemini.google.com" in current_url:
        THREAD_FILE.write_text(current_url)

    driver.quit()


if __name__ == "__main__":
    main()
