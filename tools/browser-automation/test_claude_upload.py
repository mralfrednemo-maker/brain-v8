import os, time
from pathlib import Path
from seleniumbase import Driver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

PROFILE_CLAUDE = r"C:\Users\chris\PROJECTS\chrome-automation-profile-3"
TEST_FILE = Path(r"C:\Users\chris\PROJECTS\test_upload_file.txt").resolve()
PROMPT = "What is the project name and version described in the uploaded file? List all the features mentioned."

for root, dirs, files in os.walk(PROFILE_CLAUDE):
    for f in files:
        if f in ["LOCK", "lockfile", "SingletonLock"]:
            try: os.remove(os.path.join(root, f))
            except: pass

driver = Driver(uc=True, headless=False, user_data_dir=PROFILE_CLAUDE)
driver.get("https://claude.ai")
time.sleep(6)

assert driver.find_elements(By.CSS_SELECTOR, 'div[contenteditable="true"]'), "Not logged in"
print("Logged in OK")
driver.save_screenshot("s01_logged_in.png")
print("Screenshot: s01_logged_in.png")


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
            print(f"  Clicking menu item: {repr(item.text.strip()[:60])}")
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


# ── Step 1: Open dropdown, select Haiku ──────────────────────────────────────
print("\n[Step 1] Opening model dropdown...")
open_model_dropdown()
driver.save_screenshot("s02_dropdown_open.png")
print("Screenshot: s02_dropdown_open.png")

print("[Step 1] Clicking Haiku 4.5...")
select_menu_item("Haiku")
driver.save_screenshot("s03_haiku_selected.png")
print(f"Screenshot: s03_haiku_selected.png — model: {repr(model_button_text())}")

# ── Step 2: Check & disable Extended Thinking ─────────────────────────────────
time.sleep(1)
is_on = "Extended" in model_button_text()
print(f"\n[Step 2] Extended thinking is: {'ON' if is_on else 'OFF'}")

if is_on:
    print("[Step 2] Opening dropdown to disable Extended Thinking...")
    open_model_dropdown()
    driver.save_screenshot("s04_dropdown_for_thinking.png")
    print("Screenshot: s04_dropdown_for_thinking.png")

    print("[Step 2] Clicking Extended thinking toggle...")
    select_menu_item("Extended thinking")
    time.sleep(2)
    driver.save_screenshot("s05_thinking_toggled.png")
    print(f"Screenshot: s05_thinking_toggled.png — model: {repr(model_button_text())}")
else:
    print("[Step 2] Already OFF — pressing Escape to close any overlay")
    driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
    time.sleep(0.5)

# Dismiss any remaining overlay
driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
time.sleep(1)
driver.save_screenshot("s06_ready_to_upload.png")
print(f"\nScreenshot: s06_ready_to_upload.png — model: {repr(model_button_text())}")

# ── Step 3: Upload file ───────────────────────────────────────────────────────
print("\n[Step 3] Uploading file...")
file_input = driver.execute_script("""
    const inputs = Array.from(document.querySelectorAll('input[type="file"]'));
    if (!inputs.length) return null;
    const inp = inputs[0];
    inp.style.cssText = 'display:block;visibility:visible;opacity:1;position:fixed;top:0;left:0;width:1px;height:1px;z-index:999999';
    return inp;
""")

if not file_input:
    print("[Step 3] No file input found directly — clicking attach button...")
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

if not file_input:
    print("[Step 3] ERROR: no file input found")
    driver.save_screenshot("s_error_no_input.png")
    driver.quit()
    exit(1)

file_input.send_keys(str(TEST_FILE))
time.sleep(3)
driver.save_screenshot("s07_file_attached.png")
print("Screenshot: s07_file_attached.png")

# ── Step 4: Type prompt ───────────────────────────────────────────────────────
print("\n[Step 4] Typing prompt...")
ta = driver.find_element(By.CSS_SELECTOR, 'div[contenteditable="true"]')
driver.execute_script("arguments[0].focus();", ta)
time.sleep(0.5)
ta.send_keys(PROMPT)
time.sleep(1)
driver.save_screenshot("s08_prompt_typed.png")
print("Screenshot: s08_prompt_typed.png")

# ── Step 5: Click send button ─────────────────────────────────────────────────
print("\n[Step 5] Clicking Send...")
submitted = driver.execute_script("""
    const btns = Array.from(document.querySelectorAll('button'));
    const send = btns.find(b => (b.getAttribute('aria-label')||'').toLowerCase().includes('send') && b.offsetParent !== null);
    if (send) { send.click(); return send.getAttribute('aria-label'); }
    return null;
""")
if not submitted:
    print("[Step 5] Send button not found — using Enter key")
    ta.send_keys(Keys.RETURN)
else:
    print(f"[Step 5] Clicked: {submitted}")

time.sleep(2)
driver.save_screenshot("s09_submitted.png")
print("Screenshot: s09_submitted.png")

# ── Step 6: Wait for response ─────────────────────────────────────────────────
print("\n[Step 6] Waiting for response to complete...")
for i in range(90):
    time.sleep(2)
    stop = driver.find_elements(By.CSS_SELECTOR, 'button[aria-label="Stop response"]')
    if not stop:
        print(f"  Done after ~{(i+1)*2}s")
        break

time.sleep(2)
driver.save_screenshot("s10_response.png")
print("Screenshot: s10_response.png")

# ── Step 7: Read response ─────────────────────────────────────────────────────
print("\n[Step 7] Reading response...")
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

if response_text:
    print("\n=== Claude Response ===")
    print(response_text)
else:
    print("Could not extract response — check s10_response.png")

time.sleep(10)
driver.quit()
