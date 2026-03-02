"""Application configuration."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Application
    app_name: str = "Vectriva"
    debug: bool = False
    environment: str = "development"

    # Database
    database_url: str = "postgresql+asyncpg://user:pass@localhost/vectriva"
    database_pool_size: int = 10
    database_max_overflow: int = 20

    # Redis
    redis_url: str = "redis://localhost:6379/0"
    redis_context_ttl_seconds: int = 86400  # 24 hours

    # LLM Provider (default)
    default_llm_provider: str = "gemini"  # "openai" or "gemini"
    default_llm_model: str = "gemini-1.5-pro"
    default_embedding_provider: str = "gemini"  # "openai" or "gemini"
    default_embedding_model: str = "models/text-embedding-004"

    # OpenAI
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    openai_embedding_model: str = "text-embedding-3-small"

    # Gemini (Google AI)
    gemini_api_key: str = ""
    gemini_model: str = "gemini-1.5-pro"
    gemini_embedding_model: str = "models/text-embedding-004"

    # Google Calendar
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/api/integrations/google/callback"
    google_oauth_scopes: list[str] = [
        "https://www.googleapis.com/auth/calendar",
        "https://www.googleapis.com/auth/calendar.events",
    ]

    # JWT
    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7

    # Encryption
    encryption_master_key: str = "change-me-in-production-32-bytes!"

    # File Storage
    file_storage_path: str = "./storage/documents"
    max_file_size_mb: int = 50

    # Agent
    max_booking_days_ahead: int = 30
    slot_duration_minutes: int = 30
    sentiment_threshold: float = 0.4

    # Rate Limiting
    rate_limit_per_minute: int = 60


settings = Settings()
