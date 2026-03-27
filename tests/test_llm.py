"""Tests for the LLM client abstraction."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from thinker.llm import LLMClient
from thinker.config import BrainConfig, R1_MODEL, REASONER_MODEL, GLM5_MODEL, SONNET_MODEL


@pytest.fixture
def config():
    return BrainConfig(
        openrouter_api_key="test-or-key",
        anthropic_api_key="test-anth-key",
        deepseek_api_key="test-ds-key",
        zai_api_key="test-zai-key",
    )


class TestLLMClientRouting:
    async def test_openrouter_model_uses_openrouter(self, config):
        client = LLMClient(config)
        with patch.object(client, "_call_openai_compat", new_callable=AsyncMock) as mock_compat:
            mock_compat.return_value = MagicMock(ok=True, text="response")
            await client.call(R1_MODEL, "test prompt")
            mock_compat.assert_called_once()
            # First arg should be the openrouter http client
            assert mock_compat.call_args[0][0] is client._http_openrouter

    async def test_deepseek_model_uses_deepseek(self, config):
        client = LLMClient(config)
        with patch.object(client, "_call_openai_compat", new_callable=AsyncMock) as mock_compat:
            mock_compat.return_value = MagicMock(ok=True, text="response")
            await client.call(REASONER_MODEL, "test prompt")
            mock_compat.assert_called_once()
            assert mock_compat.call_args[0][0] is client._http_deepseek

    async def test_zai_model_uses_zai(self, config):
        client = LLMClient(config)
        with patch.object(client, "_call_openai_compat", new_callable=AsyncMock) as mock_compat:
            mock_compat.return_value = MagicMock(ok=True, text="response")
            await client.call(GLM5_MODEL, "test prompt")
            mock_compat.assert_called_once()
            assert mock_compat.call_args[0][0] is client._http_zai

    async def test_anthropic_model_uses_anthropic(self, config):
        client = LLMClient(config)
        with patch.object(client, "_call_anthropic", new_callable=AsyncMock) as mock_anth:
            mock_anth.return_value = MagicMock(ok=True, text="response")
            await client.call(SONNET_MODEL, "test prompt")
            mock_anth.assert_called_once()


class TestLLMClientOpenAICompat:
    async def test_successful_call(self, config):
        client = LLMClient(config)
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "model output"}}]
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(client._http_openrouter, "post", new_callable=AsyncMock, return_value=mock_response):
            result = await client._call_openai_compat(
                client._http_openrouter, "deepseek/deepseek-r1-0528", "prompt", 16000, 480,
            )
            assert result.ok is True
            assert result.text == "model output"
            assert result.model == "deepseek/deepseek-r1-0528"

    async def test_timeout_returns_error(self, config):
        client = LLMClient(config)
        import httpx
        with patch.object(client._http_openrouter, "post", new_callable=AsyncMock,
                         side_effect=httpx.ReadTimeout("timed out")):
            result = await client._call_openai_compat(
                client._http_openrouter, "deepseek/deepseek-r1-0528", "prompt", 16000, 480,
            )
            assert result.ok is False
            assert "timed out" in result.error


class TestLLMClientAnthropic:
    async def test_successful_call(self, config):
        client = LLMClient(config)
        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text="sonnet response")]

        with patch.object(client._anthropic, "messages", create=True) as mock_messages:
            mock_messages.create = AsyncMock(return_value=mock_msg)
            result = await client._call_anthropic("test prompt", 4096)
            assert result.ok is True
            assert result.text == "sonnet response"
