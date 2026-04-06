from __future__ import annotations

from pathlib import Path
from typing import Optional

from seleniumbase import Driver


class NaturalHumanLikeBrowser:
    """Thin SeleniumBase wrapper for visible, compatibility-focused browser control."""

    def __init__(self) -> None:
        self.driver = Driver(uc=True, headless=False)

    def navigate(self, url: str, reconnect_time: float = 2.5) -> None:
        self.driver.uc_open_with_reconnect(url, reconnect_time)

    def type_text(self, selector: str, text: str, timeout: float = 20) -> None:
        self.driver.wait_for_element_visible(selector, timeout=timeout)
        self.driver.uc_click(selector, timeout=timeout)
        self.driver.type(selector, text)

    def read_text(self, selector: str, timeout: float = 20) -> str:
        self.driver.wait_for_element_visible(selector, timeout=timeout)
        return self.driver.get_text(selector)

    def upload_file(self, selector: str, file_path: str | Path, timeout: float = 20) -> None:
        path = str(Path(file_path).expanduser().resolve())
        self.driver.wait_for_element_present(selector, timeout=timeout)
        self.driver.choose_file(selector, path)

    def take_screenshot(self, file_name: str | Path) -> str:
        path = str(Path(file_name).expanduser().resolve())
        self.driver.save_screenshot(path)
        return path

    def handle_any_verification_if_present(self) -> None:
        try:
            self.driver.uc_gui_click_captcha()
        except Exception:
            pass

    def close(self) -> None:
        self.driver.quit()


def _quick_test() -> None:
    browser: Optional[NaturalHumanLikeBrowser] = None
    try:
        browser = NaturalHumanLikeBrowser()
        browser.navigate("https://gitlab.com/users/sign_in")
        browser.handle_any_verification_if_present()
        body_text = browser.read_text("body")
        screenshot_path = browser.take_screenshot("natural_browser_gitlab_sign_in.png")
        print("Page text preview:")
        print(body_text[:1000])
        print(f"Screenshot saved to: {screenshot_path}")
    finally:
        if browser is not None:
            browser.close()


if __name__ == "__main__":
    _quick_test()
