import os, time
from seleniumbase import Driver
from selenium.webdriver.common.by import By

PROFILE_CLAUDE = r"C:\Users\chris\PROJECTS\chrome-automation-profile-3"

for root, dirs, files in os.walk(PROFILE_CLAUDE):
    for f in files:
        if f in ["LOCK", "lockfile", "SingletonLock"]:
            try: os.remove(os.path.join(root, f))
            except: pass

driver = Driver(uc=True, headless=False, user_data_dir=PROFILE_CLAUDE)
driver.get("https://claude.ai")
time.sleep(6)

# Confirm logged in
assert driver.find_elements(By.CSS_SELECTOR, 'div[contenteditable="true"]'), "Not logged in"
print("Logged in OK")


def open_model_dropdown():
    for btn in driver.find_elements(By.TAG_NAME, "button"):
        if not btn.is_displayed():
            continue
        text = btn.text.strip()
        if any(name in text for name in ("Haiku", "Sonnet", "Opus", "Claude")):
            driver.execute_script("arguments[0].click();", btn)
            time.sleep(1)
            return True
    return False


def select_menu_item(label_contains):
    for item in driver.find_elements(By.CSS_SELECTOR, '[role="menuitem"]'):
        if item.is_displayed() and label_contains.lower() in item.text.lower():
            print(f"  Clicking: {repr(item.text.strip()[:60])}")
            driver.execute_script("arguments[0].click();", item)
            time.sleep(1)
            return True
    return False


def current_model():
    for btn in driver.find_elements(By.TAG_NAME, "button"):
        if not btn.is_displayed():
            continue
        text = btn.text.strip()
        if any(name in text for name in ("Haiku", "Sonnet", "Opus")):
            return text
    return "unknown"


# ── Step 1: Switch to Opus 4.6 ───────────────────────────────────────────────
print("\n--- Switch to Opus 4.6 ---")
open_model_dropdown()
select_menu_item("Opus")
driver.save_screenshot("claude_model_opus.png")
print(f"Current model: {current_model()}")

# ── Step 2: Enable Extended Thinking on Opus ─────────────────────────────────
print("\n--- Enable Extended Thinking ---")
open_model_dropdown()
select_menu_item("Extended thinking")
driver.save_screenshot("claude_model_opus_thinking_on.png")
print(f"Current model button: {current_model()}")

# ── Step 3: Disable Extended Thinking ────────────────────────────────────────
print("\n--- Disable Extended Thinking ---")
open_model_dropdown()
select_menu_item("Extended thinking")
driver.save_screenshot("claude_model_opus_thinking_off.png")
print(f"Current model button: {current_model()}")

# ── Step 4: Switch to Sonnet 4.6 ─────────────────────────────────────────────
print("\n--- Switch to Sonnet 4.6 ---")
open_model_dropdown()
select_menu_item("Sonnet")
driver.save_screenshot("claude_model_sonnet.png")
print(f"Current model: {current_model()}")

# ── Step 5: Switch to Haiku 4.5 ──────────────────────────────────────────────
print("\n--- Switch to Haiku 4.5 ---")
open_model_dropdown()
select_menu_item("Haiku")
driver.save_screenshot("claude_model_haiku.png")
print(f"Current model: {current_model()}")

print("\nAll model switches done. Check screenshots.")
time.sleep(8)
driver.quit()
