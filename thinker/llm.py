"""Async LLM client supporting OpenRouter, Anthropic, DeepSeek, and Z.AI."""
from __future__ import annotations

import time

import anthropic
import httpx

from thinker.config import BrainConfig, ModelConfig
from thinker.types import ModelResponse


class LLMClient:
    """Unified async client for all LLM calls.

    Routes to the correct provider based on ModelConfig.provider:
    - "openrouter" -> OpenRouter (R1, Kimi K2, Sonar Pro)
    - "anthropic"  -> Anthropic direct (Sonnet)
    - "deepseek"   -> DeepSeek direct (Reasoner)
    - "zai"        -> Z.AI direct (GLM-5)
    """

    def __init__(self, config: BrainConfig):
        self._http_openrouter = httpx.AsyncClient(
            base_url="https://openrouter.ai/api/v1",
            headers={
                "Authorization": f"Bearer {config.openrouter_api_key}",
                "Content-Type": "application/json",
            },
        )
        self._http_deepseek = httpx.AsyncClient(
            base_url="https://api.deepseek.com",
            headers={
                "Authorization": f"Bearer {config.deepseek_api_key}",
                "Content-Type": "application/json",
            },
        )
        self._http_zai = httpx.AsyncClient(
            base_url="https://api.z.ai/api/coding/paas/v4",
            headers={
                "Authorization": f"Bearer {config.zai_api_key}",
                "Content-Type": "application/json",
            },
        )
        self._anthropic = anthropic.AsyncAnthropic(api_key=config.anthropic_api_key)

    async def call(self, model_cfg: ModelConfig, prompt: str,
                   system: str = "") -> ModelResponse:
        """Call a model. Routes based on model_cfg.provider."""
        if model_cfg.provider == "openrouter":
            return await self._call_openai_compat(
                self._http_openrouter, model_cfg.model_id, prompt,
                model_cfg.max_tokens, model_cfg.timeout_s,
            )
        elif model_cfg.provider == "deepseek":
            return await self._call_openai_compat(
                self._http_deepseek, model_cfg.model_id, prompt,
                model_cfg.max_tokens, model_cfg.timeout_s,
            )
        elif model_cfg.provider == "zai":
            return await self._call_openai_compat(
                self._http_zai, model_cfg.model_id, prompt,
                model_cfg.max_tokens, model_cfg.timeout_s,
            )
        else:
            return await self._call_anthropic(
                prompt, model_cfg.max_tokens, system,
            )

    async def _call_openai_compat(self, client: httpx.AsyncClient, model_id: str,
                                   prompt: str, max_tokens: int,
                                   timeout_s: int) -> ModelResponse:
        """Call any OpenAI-compatible API (OpenRouter, DeepSeek, Z.AI)."""
        start = time.monotonic()
        try:
            resp = await client.post(
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
        await self._http_openrouter.aclose()
        await self._http_deepseek.aclose()
        await self._http_zai.aclose()
