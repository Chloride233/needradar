import json
from pathlib import Path

import pytest

from needradar.llm.config_store import load_config, save_config, save_active_model, save_preset_config
from needradar.llm.model_presets import PRESETS, ModelPreset


def test_deepseek_presets():
    assert len(PRESETS) == 2
    assert "deepseek-v4-pro" in PRESETS
    assert "deepseek-v4-flash" in PRESETS


def test_preset_fields():
    p = PRESETS["deepseek-v4-pro"]
    assert p.provider == "deepseek"
    assert p.base_url == "https://api.deepseek.com"
    assert p.litellm_model == "openai/deepseek-v4-pro"
    assert p.max_tokens == 4096


def test_preset_mask_key():
    p = ModelPreset(
        id="test", name="Test", provider="test",
        litellm_model="openai/test", base_url="http://test",
        api_key="sk-1234567890abcdef",
    )
    assert p.mask_key() == "sk-1***********cdef"

    p2 = ModelPreset(
        id="t", name="T", provider="t",
        litellm_model="openai/t", base_url="http://t",
        api_key="",
    )
    assert p2.mask_key() == ""

    p3 = ModelPreset(
        id="s", name="S", provider="s",
        litellm_model="openai/s", base_url="http://s",
        api_key="short",
    )
    assert p3.mask_key() == "****"


def test_preset_to_dict():
    p = ModelPreset(
        id="test", name="Test", provider="test",
        litellm_model="openai/test", base_url="http://test",
    )
    d = p.to_dict()
    assert d["id"] == "test"
    assert "api_key" not in d
    assert d["has_api_key"] is False

    d2 = p.to_dict(include_key=True)
    assert "api_key" in d2


def test_update_preset(tmp_path, monkeypatch):
    import needradar.llm.config_store as cs
    config_file = tmp_path / "llm_config.json"
    monkeypatch.setattr(cs, "_CONFIG_PATH", config_file)
    PRESETS["deepseek-v4-pro"].api_key = ""
    from needradar.llm.provider import LLMProvider
    provider = LLMProvider()
    p = provider.update_preset("deepseek-v4-pro", api_key="test-key", temperature=0.7, max_tokens=2048)
    assert p.api_key == "test-key"
    assert p.temperature == 0.7
    assert p.max_tokens == 2048


def test_update_preset_auto_activates(tmp_path, monkeypatch):
    import needradar.llm.config_store as cs
    config_file = tmp_path / "llm_config.json"
    monkeypatch.setattr(cs, "_CONFIG_PATH", config_file)
    PRESETS["deepseek-v4-pro"].api_key = ""
    from needradar.llm.provider import LLMProvider
    provider = LLMProvider()
    assert provider.active_preset_id is None
    provider.update_preset("deepseek-v4-pro", api_key="sk-test")
    assert provider.active_preset_id == "deepseek-v4-pro"


def test_update_unknown_preset():
    from needradar.llm.provider import LLMProvider
    provider = LLMProvider()
    with pytest.raises(ValueError, match="Unknown preset"):
        provider.update_preset("nonexistent", api_key="key")


def test_get_health_default():
    from needradar.llm.provider import LLMProvider
    provider = LLMProvider()
    assert provider.get_health("deepseek-v4-pro") == {}


def test_config_store_save_load(tmp_path, monkeypatch):
    import needradar.llm.config_store as cs
    config_file = tmp_path / "llm_config.json"
    monkeypatch.setattr(cs, "_CONFIG_PATH", config_file)

    save_config({"active_model": "deepseek-v4-pro", "presets": {}})
    loaded = load_config()
    assert loaded["active_model"] == "deepseek-v4-pro"


def test_config_store_save_preset(tmp_path, monkeypatch):
    import needradar.llm.config_store as cs
    config_file = tmp_path / "llm_config.json"
    monkeypatch.setattr(cs, "_CONFIG_PATH", config_file)

    save_preset_config("deepseek-v4-pro", api_key="sk-abc", temperature=0.5, max_tokens=4096)
    loaded = load_config()
    assert loaded["presets"]["deepseek-v4-pro"]["api_key"] == "sk-abc"
    assert loaded["presets"]["deepseek-v4-pro"]["temperature"] == 0.5


def test_config_store_save_active(tmp_path, monkeypatch):
    import needradar.llm.config_store as cs
    config_file = tmp_path / "llm_config.json"
    monkeypatch.setattr(cs, "_CONFIG_PATH", config_file)

    save_active_model("deepseek-v4-pro")
    loaded = load_config()
    assert loaded["active_model"] == "deepseek-v4-pro"


def test_config_store_corrupt(tmp_path, monkeypatch):
    import needradar.llm.config_store as cs
    config_file = tmp_path / "llm_config.json"
    monkeypatch.setattr(cs, "_CONFIG_PATH", config_file)

    config_file.write_text("{invalid json}")
    loaded = load_config()
    assert loaded == {"active_model": "", "presets": {}}
