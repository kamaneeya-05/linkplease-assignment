"""Application configuration."""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    database_url: str = "sqlite:///./linkplease.db"
    pseudogram_api_key: str = "test-api-key"
    pseudogram_base_url: str = "https://pseudogram-api.onrender.com"

    webhook_secret: Optional[str] = "test-webhook-secret"
    verify_webhook_signature: bool = False

    environment: str = "development"
    debug: bool = True

    cors_origins: str = "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173"

    rate_limit_requests: int = 10
    rate_limit_seconds: int = 60

    max_delivery_attempts: int = 5
    initial_retry_delay_seconds: int = 5
    max_retry_delay_seconds: int = 300
    retry_backoff_multiplier: float = 2.0

    reconciliation_enabled: bool = True
    reconciliation_interval_seconds: int = 30
    reconciliation_max_batch_size: int = 10

    class Config:
        env_file = None
        case_sensitive = False
        extra = "ignore"


settings = Settings()
