"""Async LLM client supporting OpenRouter, Anthropic (OAuth), DeepSeek, and Z.AI."""
from __future__ import annotations

import time

import httpx

from thinker.config import BrainConfig, ModelConfig, MODEL_REGISTRY
from thinker.types import ModelResponse

# Required for Anthropic Max subscription OAuth
_CC_IDENTITY = "You are Claude Code, Anthropic's official CLI for Claude."


class LLMClient:
    """Unified async client for all LLM calls.

    Routes to the correct provider based on ModelConfig.provider:
    - "openrouter" -> OpenRouter (R1, Kimi K2, Sonar Pro)
    - "anthropic"  -> Anthropic OAuth/Max subscription (Sonnet)
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
        # Anthropic OAuth requires raw HTTP with specific identity headers
        self._http_anthropic = httpx.AsyncClient(
            base_url="https://api.anthropic.com/v1",
            headers={
                "Authorization": f"Bearer {config.anthropic_oauth_token}",
                "Content-Type": "application/json",
                "User-Agent": "claude-cli/2.1.62",
                "x-app": "cli",
                "anthropic-version": "2023-06-01",
                "anthropic-dangerous-direct-browser-access": "true",
                "anthropic-beta": "claude-code-20250219,oauth-2025-04-20",
            },
        ) if config.anthropic_oauth_token else None

    async def call(self, model_cfg: ModelConfig | str, prompt: str,
                   system: str = "") -> ModelResponse:
        """Call a model. Accepts ModelConfig or model name string."""
        if isinstance(model_cfg, str):
            model_cfg = MODEL_REGISTRY[model_cfg]
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
        """Call Anthropic via OAuth (Max subscription).

        System prompt MUST be array format with Claude Code identity first.
        Uses raw HTTP — the SDK's auth_token path doesn't handle OAuth correctly.
        """
        if not self._http_anthropic:
            return ModelResponse(
                model="claude-sonnet-4-6", ok=False, text="",
                elapsed_s=0.0, error="No Anthropic OAuth token configured",
            )
        start = time.monotonic()
        try:
            # Array format: CC identity first (required), then custom instructions
            system_blocks = [
                {"type": "text", "text": _CC_IDENTITY},
            ]
            if system:
                system_blocks.append({"type": "text", "text": system})

            resp = await self._http_anthropic.post(
                "/messages",
                json={
                    "model": "claude-sonnet-4-6",
                    "max_tokens": max_tokens,
                    "system": system_blocks,
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=120,
            )
            resp.raise_for_status()
            data = resp.json()
            text = data["content"][0]["text"]
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
        if self._http_anthropic:
            await self._http_anthropic.aclose()
