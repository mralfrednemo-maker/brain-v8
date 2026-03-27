"""Async LLM client supporting OpenRouter and Anthropic direct API."""
from __future__ import annotations

import time

import anthropic
import httpx

from thinker.config import BrainConfig, ModelConfig
from thinker.types import ModelResponse


class LLMClient:
    """Unified async client for all LLM calls.

    Routes to OpenRouter or Anthropic based on ModelConfig.provider.
    """

    def __init__(self, config: BrainConfig):
        self._http = httpx.AsyncClient(
            base_url="https://openrouter.ai/api/v1",
            headers={
                "Authorization": f"Bearer {config.openrouter_api_key}",
                "Content-Type": "application/json",
            },
        )
        self._anthropic = anthropic.AsyncAnthropic(api_key=config.anthropic_api_key)

    async def call(self, model_cfg: ModelConfig, prompt: str,
                   system: str = "") -> ModelResponse:
        if model_cfg.provider == "openrouter":
            return await self._call_openrouter(
                model_cfg.model_id, prompt, model_cfg.max_tokens, model_cfg.timeout_s,
            )
        else:
            return await self._call_anthropic(
                prompt, model_cfg.max_tokens, system,
            )

    async def _call_openrouter(self, model_id: str, prompt: str,
                                max_tokens: int, timeout_s: int) -> ModelResponse:
        start = time.monotonic()
        try:
            resp = await self._http.post(
                "/chat/completions",
                json={
                    "model": model_id,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": max_tokens,
                },
                timeout=timeout_s,
            )
            resp.raise_for_status()
            data = resp.json()
            text = data["choices"][0]["message"]["content"]
            return ModelResponse(
                model=model_id, ok=True, text=text,
                elapsed_s=time.monotonic() - start,
            )
        except Exception as e:
            return ModelResponse(
                model=model_id, ok=False, text="",
                elapsed_s=time.monotonic() - start, error=str(e),
            )

    async def _call_anthropic(self, prompt: str, max_tokens: int,
                               system: str = "") -> ModelResponse:
        start = time.monotonic()
        try:
            kwargs = {
                "model": "claude-sonnet-4-6",
                "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": prompt}],
            }
            if system:
                kwargs["system"] = system
            msg = await self._anthropic.messages.create(**kwargs)
            text = msg.content[0].text
            return ModelResponse(
                model="claude-sonnet-4-6", ok=True, text=text,
                elapsed_s=time.monotonic() - start,
            )
        except Exception as e:
            return ModelResponse(
                model="claude-sonnet-4-6", ok=False, text="",
                elapsed_s=time.monotonic() - start, error=str(e),
            )

    async def close(self):
        await self._http.aclose()
