import argparse
from seleniumbase import Driver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
import time
import os
from pathlib import Path


AUTOMATION_PROFILE_DIR = r"C:\Users\chris\PROJECTS\chrome-automation-profile"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--prompt', required=True, help='Prompt text to send')
    parser.add_argument('--file', default=None, help='Optional file path to attach')
    parser.add_argument('--new', action='store_true', help='Start a fresh conversation thread')
    args = parser.parse_args()

    THREAD_FILE = Path(AUTOMATION_PROFILE_DIR) / ".kk_thread_url"

    file_path = Path(args.file).resolve() if args.file else None

    # Remove any stale lock files from the automation profile (no global taskkill)
    for lock_file in ["LOCK", "lockfile", "SingletonLock", "SingletonCookie", "SingletonSocket"]:
        for root, dirs, files in os.walk(AUTOMATION_PROFILE_DIR):
            for f in files:
                if f == lock_file:
                    try:
                        os.remove(os.path.join(root, f))
                    except Exception:
                        pass

    driver = Driver(uc=True, headless=False, user_data_dir=AUTOMATION_PROFILE_DIR)

    try:
        # Navigate to existing thread or start fresh
        if not args.new and THREAD_FILE.exists():
            saved_url = THREAD_FILE.read_text().strip()
            driver.get(saved_url)
        else:
            if args.new and THREAD_FILE.exists():
                THREAD_FILE.unlink()
            driver.get("https://chatgpt.com")
        time.sleep(6)

        login_buttons = [el for el in driver.find_elements(By.CSS_SELECTOR, "button, a")
                         if el.text.strip() in ("Log in", "Sign up for free") and el.is_displayed()]
        if login_buttons:
            print("Not logged in — LOG IN NOW. You have 90 seconds.")
            time.sleep(90)
        else:
            print("Already logged in — session persisted!")
        time.sleep(3)

        textarea_elements = []
        for _ in range(20):
            textarea_elements = driver.find_elements(By.CSS_SELECTOR, "#prompt-textarea")
            if textarea_elements:
                break
            time.sleep(1)

        if not textarea_elements:
            print("ERROR: #prompt-textarea not found")
            driver.quit()
            return

        # Select the thinking model
        driver.find_element(By.CSS_SELECTOR, 'button[aria-label="Model selector"]').click()
        time.sleep(0.5)
        clicked_model = driver.execute_script("""
            const items = Array.from(document.querySelectorAll('[role="option"], [role="menuitem"], [role="menuitemradio"], li, button'));
            const thinking = items.find(el => {
                const t = (el.textContent || '').toLowerCase();
                return (t.includes('think') || t.includes('reason') || t.includes('o3') || t.includes('o1')) && el.offsetParent !== null;
            });
            if (thinking) { thinking.click(); return thinking.textContent.trim(); }
            return null;
        """)
        print(f"Selected model: {clicked_model[:60] if clicked_model else 'WARNING: not found, using current'}")
        time.sleep(1)

        # File upload (optional)
        if file_path:
            clicked = driver.execute_script("""
                const textarea = document.querySelector('#prompt-textarea');
                if (!textarea) return false;

                const isVisible = (el) => {
                    if (!el) return false;
                    const style = window.getComputedStyle(el);
                    const rect = el.getBoundingClientRect();
                    return style.display !== 'none' &&
                           style.visibility !== 'hidden' &&
                           rect.width > 0 &&
                           rect.height > 0;
                };

                const textOf = (el) => [
                    el.getAttribute('aria-label') || '',
                    el.getAttribute('title') || '',
                    el.getAttribute('data-testid') || '',
                    el.textContent || ''
                ].join(' ').toLowerCase();

                const textareaRect = textarea.getBoundingClientRect();
                const buttons = Array.from(document.querySelectorAll('button')).filter(isVisible);

                let best = null;
                let bestScore = -1;

                for (const button of buttons) {
                    const text = textOf(button);
                    const rect = button.getBoundingClientRect();
                    let score = 0;

                    if (text.includes('attach')) score += 100;
                    if (text.includes('upload')) score += 80;
                    if (text.includes('file')) score += 40;
                    if (text.includes('plus')) score += 30;
                    if ((button.textContent || '').trim() === '+') score += 30;

                    const nearTextarea =
                        Math.abs(rect.bottom - textareaRect.bottom) < 160 &&
                        Math.abs(rect.left - textareaRect.left) < 260;
                    if (nearTextarea) score += 20;

                    if (score > bestScore) {
                        best = button;
                        bestScore = score;
                    }
                }

                if (!best || bestScore <= 0) return false;
                best.click();
                return true;
            """)

            if not clicked:
                print("ERROR: could not click attach/+ button")
                driver.quit()
                return

            time.sleep(2)

            input_element = driver.execute_script("""
                const inputs = Array.from(document.querySelectorAll('input[type="file"]'));

                const isImageOnly = (input) => {
                    const accept = (input.getAttribute('accept') || '').toLowerCase().trim();
                    if (!accept) return false;
                    const parts = accept.split(',').map(x => x.trim()).filter(Boolean);
                    if (!parts.length) return false;
                    return parts.every(part =>
                        part.startsWith('image/') ||
                        ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp', '.svg'].includes(part)
                    );
                };

                for (const input of inputs) {
                    if (isImageOnly(input)) continue;

                    input.style.display = 'block';
                    input.style.visibility = 'visible';
                    input.style.opacity = '1';
                    input.style.position = 'fixed';
                    input.style.left = '0';
                    input.style.top = '0';
                    input.style.width = '1px';
                    input.style.height = '1px';
                    input.style.zIndex = '2147483647';
                    return input;
                }

                return null;
            """)

            if input_element is None:
                print("ERROR: could not find non-image file input")
                driver.quit()
                return

            input_element.send_keys(str(file_path))
            time.sleep(3)

        # Type the prompt
        driver.find_element(By.CSS_SELECTOR, "#prompt-textarea").send_keys(args.prompt)
        time.sleep(1)

        # Submit
        submitted = driver.execute_script("""
            const btn = document.querySelector("button[data-testid='send-button']");
            if (!btn) return false;
            btn.click();
            return true;
        """)

        if not submitted:
            driver.find_element(By.CSS_SELECTOR, "#prompt-textarea").send_keys(Keys.RETURN)

        # Poll until streaming finishes (up to 3 minutes)
        for _ in range(90):
            time.sleep(2)
            stop = driver.find_elements(By.CSS_SELECTOR,
                'button[aria-label="Stop streaming"], button[data-testid="stop-button"]')
            if not stop:
                break

        responses = driver.find_elements(By.CSS_SELECTOR, "[data-message-author-role='assistant']")
        if responses:
            print(responses[-1].text)  # full text, no truncation
        else:
            print("ERROR: no assistant response found")

        # Save current conversation URL for thread continuity
        current_url = driver.current_url
        if "/c/" in current_url:
            THREAD_FILE.write_text(current_url)

        driver.quit()

    except Exception:
        try:
            driver.quit()
        except Exception:
            pass
        raise


if __name__ == "__main__":
    main()
