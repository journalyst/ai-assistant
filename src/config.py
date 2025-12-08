from __future__ import annotations
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import computed_field
import os

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Core
    environment: str = "dev"
    debug: bool = False
    log_level: str = "INFO"
    log_file: str = "logs/app.log"

    # Postgres - individual settings (for local dev)
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "journalyst_test"
    postgres_user: str = "postgres"
    postgres_password: str = ""  # MUST be set in .env
    postgres_readonly_user: str = "readonly_user"
    postgres_readonly_password: str = ""  # MUST be set in .env
    
    # Postgres - direct DSN override (for Docker)
    postgres_rw_dsn_override: str | None = None
    postgres_ro_dsn_override: str | None = None

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # QDrant
    qdrant_url: str = "http://localhost:6333"

    # Providers / Keys
    openai_api_key: str | None = None
    openrouter_api_key: str | None = None

    # Models
    embedding_model: str = "all-MiniLM-L6-v2"  # Local transformer model
    embedding_provider: str = "local"  # "local" for transformers, "openai" for API
    analysis_llm_context_window: int = 128000
    model_provider: str = "openrouter"  # "openai" or "openrouter"
    router_model: str = ""
    analysis_model: str = ""
    reasoning_model: str | None = None

    # Embedding config
    embedding_dimension: int = 384  # 384 for MiniLM, 768 for MPNet, 1536 for OpenAI
    embedding_device: str = "cpu"  # "cpu" or "cuda" for GPU acceleration

    # Rate limiting (simple config only; actual limiter integrated later)
    rate_limit_requests_per_minute: int = 60

    @computed_field
    @property
    def postgres_rw_dsn(self) -> str:
        # Use override if provided (for Docker), otherwise build from components
        if self.postgres_rw_dsn_override:
            return self.postgres_rw_dsn_override
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"\
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @computed_field
    @property
    def postgres_ro_dsn(self) -> str:
        # Use override if provided (for Docker), otherwise build from components
        if self.postgres_ro_dsn_override:
            return self.postgres_ro_dsn_override
        return (
            f"postgresql://{self.postgres_readonly_user}:{self.postgres_readonly_password}"\
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @computed_field
    @property
    def is_prod(self) -> bool:
        return self.environment.lower() == "prod"

@lru_cache(maxsize=1)
def get_settings() -> Settings:
    # Allow overriding .env via explicit environment variables
    return Settings()  # pydantic-settings handles precedence

settings = get_settings()

__all__ = ["Settings", "get_settings", "settings"]
