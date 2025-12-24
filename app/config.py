"""Application configuration using Pydantic Settings."""
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    env: str = "development"
    log_level: str = "INFO"
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # Database
    database_url: str

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Redpanda (Phase 2)
    redpanda_brokers: str = "localhost:9092"

    # External Services (Phase 2)
    onboarding_service_url: str = "http://localhost:8000"

    # OpenAI (supports OpenRouter via base URL)
    openai_api_key: str
    openai_model: str = "gpt-4-turbo-preview"
    openai_api_base: Optional[str] = None
    openai_model_name: Optional[str] = None

    # AWS SES
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    aws_region: str = "us-east-1"
    ses_sender_email: Optional[str] = None

    # Twilio
    twilio_account_sid: Optional[str] = None
    twilio_auth_token: Optional[str] = None
    twilio_whatsapp_from: Optional[str] = None

    # SuprSend
    suprsend_workspace_key: Optional[str] = None
    suprsend_workspace_secret: Optional[str] = None
    is_staging_env: bool = False

    # Security
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


# Global settings instance
settings = Settings()
