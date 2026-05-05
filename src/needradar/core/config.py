from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="NR_",
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
    )

    # Database (SQLite for MVP)
    database_url: str = "sqlite+aiosqlite:///./data/needradar.db"

    # Obsidian vault path
    vault_path: str = "./vault"

    # LLM
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    llm_default_model: str = "gpt-4o"
    llm_default_max_tokens: int = 4096
    llm_default_temperature: float = 0.3
    llm_embedding_model: str = "text-embedding-3-small"
    llm_fallback_model: str = "claude-sonnet-4-20250514"

    # DeepSeek
    deepseek_api_key: str = ""

    # ChromaDB
    chroma_persist_dir: str = "./data/chroma"

    # GitHub
    github_token: str = ""

    # Stack Exchange
    stackexchange_key: str = ""

    # Analysis
    similarity_threshold: float = 0.85
    analysis_batch_size: int = 50

    # Report
    report_top_n: int = 20

    # Budget alerts (CNY)
    budget_daily_limit: float = 0.0  # 0 = disabled
    budget_monthly_limit: float = 0.0  # 0 = disabled

    # App
    debug: bool = False
    log_level: str = "INFO"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])


settings = Settings()
