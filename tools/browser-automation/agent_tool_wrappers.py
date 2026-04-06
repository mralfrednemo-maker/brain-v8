from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional

from natural_browser import NaturalHumanLikeBrowser


@dataclass
class BrowserToolResult:
    action: str
    ok: bool
    data: Any = None
    error: Optional[str] = None


class NaturalBrowserAgentTools:
    """Reusable wrappers that agent frameworks can call."""

    def __init__(self, browser: Optional[NaturalHumanLikeBrowser] = None) -> None:
        self.browser = browser or NaturalHumanLikeBrowser()

    def navigate(self, url: str) -> BrowserToolResult:
        try:
            self.browser.navigate(url)
            return BrowserToolResult(action="navigate", ok=True, data=url)
        except Exception as exc:
            return BrowserToolResult(action="navigate", ok=False, error=str(exc))

    def type_text(self, selector: str, text: str) -> BrowserToolResult:
        try:
            self.browser.type_text(selector, text)
            return BrowserToolResult(action="type_text", ok=True, data={"selector": selector})
        except Exception as exc:
            return BrowserToolResult(action="type_text", ok=False, error=str(exc))

    def read_text(self, selector: str) -> BrowserToolResult:
        try:
            text = self.browser.read_text(selector)
            return BrowserToolResult(action="read_text", ok=True, data=text)
        except Exception as exc:
            return BrowserToolResult(action="read_text", ok=False, error=str(exc))

    def upload_file(self, selector: str, file_path: str) -> BrowserToolResult:
        try:
            self.browser.upload_file(selector, file_path)
            return BrowserToolResult(action="upload_file", ok=True, data=file_path)
        except Exception as exc:
            return BrowserToolResult(action="upload_file", ok=False, error=str(exc))

    def screenshot(self, file_name: str) -> BrowserToolResult:
        try:
            path = self.browser.take_screenshot(file_name)
            return BrowserToolResult(action="screenshot", ok=True, data=path)
        except Exception as exc:
            return BrowserToolResult(action="screenshot", ok=False, error=str(exc))

    def verify(self) -> BrowserToolResult:
        try:
            self.browser.handle_any_verification_if_present()
            return BrowserToolResult(action="verify", ok=True)
        except Exception as exc:
            return BrowserToolResult(action="verify", ok=False, error=str(exc))

    def close(self) -> BrowserToolResult:
        try:
            self.browser.close()
            return BrowserToolResult(action="close", ok=True)
        except Exception as exc:
            return BrowserToolResult(action="close", ok=False, error=str(exc))


def build_langchain_tools() -> list[Any]:
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field

    tools = NaturalBrowserAgentTools()

    class NavigateInput(BaseModel):
        url: str = Field(..., description="The URL to open in the visible browser.")

    class TypeInput(BaseModel):
        selector: str = Field(..., description="CSS selector for the target element.")
        text: str = Field(..., description="Text to type into the target element.")

    class ReadInput(BaseModel):
        selector: str = Field(..., description="CSS selector for the element to read.")

    return [
        StructuredTool.from_function(
            func=lambda url: tools.navigate(url).__dict__,
            name="browser_navigate",
            description="Open a URL with SeleniumBase UC reconnect mode.",
            args_schema=NavigateInput,
        ),
        StructuredTool.from_function(
            func=lambda selector, text: tools.type_text(selector, text).__dict__,
            name="browser_type_text",
            description="Click and type into a page element.",
            args_schema=TypeInput,
        ),
        StructuredTool.from_function(
            func=lambda selector: tools.read_text(selector).__dict__,
            name="browser_read_text",
            description="Read text from a page element.",
            args_schema=ReadInput,
        ),
    ]


def build_crewai_tools() -> list[type]:
    from crewai.tools import BaseTool
    from pydantic import BaseModel, Field

    shared = NaturalBrowserAgentTools()

    class NavigateInput(BaseModel):
        url: str = Field(..., description="The URL to open.")

    class ReadInput(BaseModel):
        selector: str = Field(..., description="CSS selector to read.")

    class CrewNavigateTool(BaseTool):
        name: str = "browser_navigate"
        description: str = "Open a URL in a visible SeleniumBase browser."
        args_schema: type[BaseModel] = NavigateInput

        def _run(self, url: str) -> str:
            return str(shared.navigate(url).__dict__)

    class CrewReadTool(BaseTool):
        name: str = "browser_read_text"
        description: str = "Read text from the current page."
        args_schema: type[BaseModel] = ReadInput

        def _run(self, selector: str) -> str:
            return str(shared.read_text(selector).__dict__)

    return [CrewNavigateTool, CrewReadTool]


def autogen_function_map() -> dict[str, Callable[..., dict[str, Any]]]:
    tools = NaturalBrowserAgentTools()

    return {
        "browser_navigate": lambda url: tools.navigate(url).__dict__,
        "browser_type_text": lambda selector, text: tools.type_text(selector, text).__dict__,
        "browser_read_text": lambda selector: tools.read_text(selector).__dict__,
        "browser_upload_file": lambda selector, file_path: tools.upload_file(selector, file_path).__dict__,
        "browser_screenshot": lambda file_name: tools.screenshot(file_name).__dict__,
        "browser_verify": lambda: tools.verify().__dict__,
        "browser_close": lambda: tools.close().__dict__,
    }


if __name__ == "__main__":
    print("LangChain tools:", build_langchain_tools())
    print("CrewAI tools:", build_crewai_tools())
    print("AutoGen function map keys:", list(autogen_function_map().keys()))
