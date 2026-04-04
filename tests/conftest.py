"""Shared fixtures and MockLLMClient for all tests."""
from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path
from typing import Optional

import pytest

from thinker.types import ModelResponse

FIXTURES_DIR = Path(__file__).parent / "fixtures"
TMP_ROOT = Path("C:/Users/chris/.codex/memories/thinker-v8-test-tmp")


class MockLLMClient:
    """Mock LLM client that returns pre-programmed responses."""

    def __init__(self):
        self._responses: dict[str, list[str]] = {}
        self._call_log: list[dict] = []

    def add_response(self, model: str, text: str):
        self._responses.setdefault(model, []).append(text)

    def add_responses_from_fixtures(self, round_num: int, models: list[str]):
        for model in models:
            path = FIXTURES_DIR / "model_outputs" / f"r{round_num}_{model}.txt"
            if path.exists():
                self.add_response(model, path.read_text(encoding="utf-8"))

    async def call(self, model_name: str, prompt: str,
                   max_tokens: int = 4096, timeout_s: int = 120) -> ModelResponse:
        self._call_log.append({"model": model_name, "prompt": prompt})
        queue = self._responses.get(model_name, [])
        if not queue:
            return ModelResponse(
                model=model_name, ok=False, text="",
                elapsed_s=0.0, error=f"No mock response for {model_name}",
            )
        text = queue.pop(0)
        return ModelResponse(model=model_name, ok=True, text=text, elapsed_s=0.1)

    @property
    def call_count(self) -> int:
        return len(self._call_log)

    def calls_for(self, model: str) -> list[dict]:
        return [c for c in self._call_log if c["model"] == model]

    def last_prompt_for(self, model: str) -> Optional[str]:
        calls = self.calls_for(model)
        return calls[-1]["prompt"] if calls else None


@pytest.fixture
def mock_llm():
    return MockLLMClient()


@pytest.fixture
def tmp_path():
    """Workspace-local tmp_path override for sandboxed test runs."""
    TMP_ROOT.mkdir(exist_ok=True)
    path = TMP_ROOT / f"tmp-{uuid.uuid4().hex}"
    path.mkdir()
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


@pytest.fixture
def brief_b1() -> str:
    return (FIXTURES_DIR / "briefs" / "b1.md").read_text(encoding="utf-8")


@pytest.fixture
def brief_b4() -> str:
    return (FIXTURES_DIR / "briefs" / "b4.md").read_text(encoding="utf-8")


@pytest.fixture
def proof_complete() -> dict:
    return json.loads(
        (FIXTURES_DIR / "proofs" / "proof_complete.json").read_text(encoding="utf-8")
    )


@pytest.fixture
def evidence_r1_to_r2() -> str:
    return (FIXTURES_DIR / "evidence" / "evidence_r1_to_r2.txt").read_text(encoding="utf-8")


def load_model_output(round_num: int, model: str) -> str:
    path = FIXTURES_DIR / "model_outputs" / f"r{round_num}_{model}.txt"
    return path.read_text(encoding="utf-8")
