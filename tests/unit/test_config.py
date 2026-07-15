from needradar.core.config import Settings


def test_default_settings():
    s = Settings()
    assert str(s.database_url).startswith("sqlite")
    assert s.vault_path == "./vault"
    assert s.llm_default_model == "gpt-4o"
    assert s.rerank_mode == "none"
    assert s.rerank_recall_k == 20
    assert s.rerank_top_k == 3
    assert s.debug is False


def test_settings_from_env(monkeypatch):
    monkeypatch.setenv("NR_DEBUG", "true")
    monkeypatch.setenv("NR_LLM_DEFAULT_MODEL", "claude-sonnet-4-20250514")
    s = Settings()
    assert s.debug is True
    assert s.llm_default_model == "claude-sonnet-4-20250514"


def test_reranker_settings_accept_unprefixed_provider_key(monkeypatch):
    monkeypatch.setenv("SILICONFLOW_API_KEY", "secret-for-test")
    monkeypatch.setenv("NR_RERANK_MODE", "qwen3")

    s = Settings()

    assert s.siliconflow_api_key == "secret-for-test"
    assert s.rerank_mode == "qwen3"
