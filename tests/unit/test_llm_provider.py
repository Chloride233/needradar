"""Tests for LLMProvider with mocked litellm."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from needradar.llm.provider import SHARED_SYSTEM_PREFIX, LLMProvider


@pytest.fixture
def provider():
    """Create a provider without triggering env/config loading."""
    with patch("needradar.llm.provider.settings") as mock_settings:
        mock_settings.openai_api_key = ""
        mock_settings.anthropic_api_key = ""
        mock_settings.deepseek_api_key = ""
        mock_settings.llm_default_model = "openai/gpt-4o"
        mock_settings.llm_default_max_tokens = 4096
        mock_settings.llm_default_temperature = 0.3
        mock_settings.llm_fallback_model = ""
        with patch("needradar.llm.provider.load_config") as mock_load:
            mock_load.return_value = {"active_model": "", "presets": {}}
            yield LLMProvider()


class TestProviderInit:
    def test_no_active_preset_without_config(self, provider):
        assert provider.active_preset is None
        assert provider.active_preset_id is None

    def test_get_health_default_empty(self, provider):
        assert provider.get_health("deepseek-v4-pro") == {}


class TestActivatePreset:
    def test_activate_valid_preset(self, provider):
        provider.activate_preset("deepseek-v4-pro")
        assert provider.active_preset_id == "deepseek-v4-pro"
        assert provider.active_preset.id == "deepseek-v4-pro"

    def test_activate_unknown_preset_raises(self, provider):
        with pytest.raises(ValueError, match="Unknown preset"):
            provider.activate_preset("nonexistent")

    def test_activate_switches_preset(self, provider):
        provider.activate_preset("deepseek-v4-pro")
        provider.activate_preset("deepseek-v4-flash")
        assert provider.active_preset_id == "deepseek-v4-flash"


class TestPopLastUsage:
    def test_none_initially(self, provider):
        assert provider.pop_last_usage() is None

    def test_returns_then_none(self, provider):
        provider._last_usage = {"test": True}
        assert provider.pop_last_usage() == {"test": True}
        assert provider.pop_last_usage() is None


class TestComplete:
    @pytest.mark.asyncio
    async def test_complete_with_preset(self, provider):
        provider.activate_preset("deepseek-v4-pro")
        from needradar.llm.model_presets import PRESETS
        PRESETS["deepseek-v4-pro"].api_key = "sk-test"

        mock_resp = MagicMock()
        mock_resp.choices = [MagicMock()]
        mock_resp.choices[0].message.content = "hello world"
        mock_resp.usage = MagicMock()
        mock_resp.usage.prompt_tokens = 10
        mock_resp.usage.completion_tokens = 5
        mock_resp.usage.total_tokens = 15
        mock_resp.usage.prompt_tokens_details = None

        with patch("needradar.llm.provider.litellm.acompletion", new_callable=AsyncMock) as m:
            m.return_value = mock_resp
            result = await provider.complete([{"role": "user", "content": "hi"}])
            assert result == "hello world"
            m.assert_called_once()

        PRESETS["deepseek-v4-pro"].api_key = ""

    @pytest.mark.asyncio
    async def test_complete_injects_prefix_to_system_message(self, provider):
        provider.activate_preset("deepseek-v4-pro")
        from needradar.llm.model_presets import PRESETS
        PRESETS["deepseek-v4-pro"].api_key = "sk-test"

        mock_resp = MagicMock()
        mock_resp.choices = [MagicMock()]
        mock_resp.choices[0].message.content = "ok"
        mock_resp.usage = MagicMock()
        mock_resp.usage.prompt_tokens = 5
        mock_resp.usage.completion_tokens = 2
        mock_resp.usage.total_tokens = 7
        mock_resp.usage.prompt_tokens_details = None

        with patch("needradar.llm.provider.litellm.acompletion", new_callable=AsyncMock) as m:
            m.return_value = mock_resp
            await provider.complete([{"role": "system", "content": "custom"}])
            sent = m.call_args[1]["messages"]
            assert SHARED_SYSTEM_PREFIX in sent[0]["content"]

        PRESETS["deepseek-v4-pro"].api_key = ""

    @pytest.mark.asyncio
    async def test_complete_no_prefix_when_disabled(self, provider):
        provider.activate_preset("deepseek-v4-pro")
        from needradar.llm.model_presets import PRESETS
        PRESETS["deepseek-v4-pro"].api_key = "sk-test"

        mock_resp = MagicMock()
        mock_resp.choices = [MagicMock()]
        mock_resp.choices[0].message.content = "ok"
        mock_resp.usage = None

        with patch("needradar.llm.provider.litellm.acompletion", new_callable=AsyncMock) as m:
            m.return_value = mock_resp
            await provider.complete(
                [{"role": "system", "content": "custom"}], cache_prefix=False
            )
            assert m.call_args[1]["messages"][0]["content"] == "custom"

        PRESETS["deepseek-v4-pro"].api_key = ""

    @pytest.mark.asyncio
    async def test_complete_tracks_usage_in_last_usage(self, provider):
        provider.activate_preset("deepseek-v4-flash")
        from needradar.llm.model_presets import PRESETS
        PRESETS["deepseek-v4-flash"].api_key = "sk-test"

        mu = MagicMock()
        mu.prompt_tokens = 100
        mu.completion_tokens = 50
        mu.total_tokens = 150
        mu.prompt_tokens_details = None

        mock_resp = MagicMock()
        mock_resp.choices = [MagicMock()]
        mock_resp.choices[0].message.content = "done"
        mock_resp.usage = mu

        with patch("needradar.llm.provider.litellm.acompletion", new_callable=AsyncMock) as m:
            m.return_value = mock_resp
            await provider.complete([{"role": "user", "content": "test"}])

        u = provider.pop_last_usage()
        assert u["preset_id"] == "deepseek-v4-flash"
        assert u["input_tokens"] == 100
        assert u["output_tokens"] == 50

        PRESETS["deepseek-v4-flash"].api_key = ""

    @pytest.mark.asyncio
    async def test_complete_falls_back_to_default_without_preset(self, provider):
        with patch("needradar.llm.provider.litellm.acompletion", new_callable=AsyncMock) as m:
            mock_resp = MagicMock()
            mock_resp.choices = [MagicMock()]
            mock_resp.choices[0].message.content = "default response"
            mock_resp.usage = MagicMock()
            mock_resp.usage.prompt_tokens = 3
            mock_resp.usage.completion_tokens = 2
            mock_resp.usage.total_tokens = 5
            m.return_value = mock_resp

            result = await provider.complete([{"role": "user", "content": "hi"}])
            assert result == "default response"


class TestUpdatePreset:
    def test_unknown_preset_raises(self, provider):
        with pytest.raises(ValueError, match="Unknown preset"):
            provider.update_preset("nonexistent", api_key="sk-x")

    def test_updates_api_key_and_activates(self, provider):
        with patch("needradar.llm.provider.save_preset_config"):
            result = provider.update_preset("deepseek-v4-pro", api_key="sk-abc")
            assert result.api_key == "sk-abc"
            assert provider.active_preset_id == "deepseek-v4-pro"

    def test_updates_temperature_only(self, provider):
        with patch("needradar.llm.provider.save_preset_config"):
            result = provider.update_preset("deepseek-v4-pro", temperature=0.7)
            assert result.temperature == 0.7

    def test_updates_max_tokens_only(self, provider):
        with patch("needradar.llm.provider.save_preset_config"):
            result = provider.update_preset("deepseek-v4-pro", max_tokens=2048)
            assert result.max_tokens == 2048


class TestExtractStructured:
    @pytest.mark.asyncio
    async def test_extract_valid_json(self, provider):
        from needradar.schemas.schemas import ExtractedRequirement

        provider.activate_preset("deepseek-v4-pro")
        from needradar.llm.model_presets import PRESETS
        PRESETS["deepseek-v4-pro"].api_key = "sk-test"

        mock_resp = MagicMock()
        mock_resp.choices = [MagicMock()]
        mock_resp.choices[0].message.content = (
            '{"title": "AI Tool", "description": "Need AI features"}'
        )
        mock_resp.usage = MagicMock()
        mock_resp.usage.prompt_tokens = 5
        mock_resp.usage.completion_tokens = 3
        mock_resp.usage.total_tokens = 8
        mock_resp.usage.prompt_tokens_details = None

        with patch("needradar.llm.provider.litellm.acompletion", new_callable=AsyncMock) as m:
            m.return_value = mock_resp
            result = await provider.extract_structured(
                "Extract requirements", "User wants AI", ExtractedRequirement
            )
            assert result.title == "AI Tool"

        PRESETS["deepseek-v4-pro"].api_key = ""

    @pytest.mark.asyncio
    async def test_extract_invalid_json_raises(self, provider):
        from needradar.schemas.schemas import ExtractedRequirement

        provider.activate_preset("deepseek-v4-pro")
        from needradar.llm.model_presets import PRESETS
        PRESETS["deepseek-v4-pro"].api_key = "sk-test"

        mock_resp = MagicMock()
        mock_resp.choices = [MagicMock()]
        mock_resp.choices[0].message.content = "not valid json at all"
        mock_resp.usage = MagicMock()
        mock_resp.usage.prompt_tokens = 3
        mock_resp.usage.completion_tokens = 2
        mock_resp.usage.total_tokens = 5
        mock_resp.usage.prompt_tokens_details = None

        with patch("needradar.llm.provider.litellm.acompletion", new_callable=AsyncMock) as m:
            m.return_value = mock_resp
            with pytest.raises(ValueError, match="Failed to parse"):
                await provider.extract_structured("p", "t", ExtractedRequirement)

        PRESETS["deepseek-v4-pro"].api_key = ""


class TestTestConnection:
    @pytest.mark.asyncio
    async def test_no_api_key_configured(self, provider):
        from needradar.llm.model_presets import PRESETS
        PRESETS["deepseek-v4-pro"].api_key = ""
        result = await provider.test_connection("deepseek-v4-pro")
        assert result["success"] is False
        assert "API key not configured" in result["error"]

    @pytest.mark.asyncio
    async def test_unknown_preset_raises(self, provider):
        with pytest.raises(ValueError, match="Unknown preset"):
            await provider.test_connection("nonexistent")

    @pytest.mark.asyncio
    async def test_successful_connection(self, provider):
        from needradar.llm.model_presets import PRESETS
        PRESETS["deepseek-v4-pro"].api_key = "sk-test"

        mock_resp = MagicMock()
        mock_resp.choices = [MagicMock()]
        mock_resp.choices[0].message.content = "OK"
        mock_resp.usage = None

        with patch("needradar.llm.provider.litellm.acompletion", new_callable=AsyncMock) as m:
            m.return_value = mock_resp
            result = await provider.test_connection("deepseek-v4-pro")
            assert result["success"] is True
            assert result["latency_ms"] is not None

        PRESETS["deepseek-v4-pro"].api_key = ""

    @pytest.mark.asyncio
    async def test_connection_error_handling(self, provider):
        from needradar.llm.model_presets import PRESETS
        PRESETS["deepseek-v4-pro"].api_key = "sk-test"

        with patch("needradar.llm.provider.litellm.acompletion", new_callable=AsyncMock) as m:
            m.side_effect = Exception("Connection refused")
            result = await provider.test_connection("deepseek-v4-pro")
            assert result["success"] is False
            assert "Connection refused" in result["error"]

        PRESETS["deepseek-v4-pro"].api_key = ""


def test_shared_prefix_contains_needradar():
    assert "NeedRadar" in SHARED_SYSTEM_PREFIX
    assert "Markdown" in SHARED_SYSTEM_PREFIX
