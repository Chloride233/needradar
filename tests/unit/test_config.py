from needradar.core.config import Settings


def test_default_settings():
    s = Settings()
    assert str(s.database_url).startswith("sqlite")
    assert s.vault_path == "./vault"
    assert s.llm_default_model == "gpt-4o"
    assert s.debug is False


def test_settings_from_env(monkeypatch):
    monkeypatch.setenv("NR_DEBUG", "true")
    monkeypatch.setenv("NR_LLM_DEFAULT_MODEL", "claude-sonnet-4-20250514")
    s = Settings()
    assert s.debug is True
    assert s.llm_default_model == "claude-sonnet-4-20250514"
