from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Supabase
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""

    # API Keys
    ieee_api_key: str = ""
    scopus_api_key: str = ""
    anthropic_api_key: str = ""

    # Email — Resend (preferred) or SMTP fallback
    resend_api_key: str = ""
    resend_from: str = "LitOrbit <noreply@litorbit.app>"
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""

    # Claude models (update these when new versions release)
    claude_model_fast: str = "claude-haiku-4-5"
    claude_model_smart: str = "claude-sonnet-4-6"

    # App
    secret_key: str = ""
    environment: str = "development"
    frontend_url: str = "http://localhost:5173"

    # Database (constructed from supabase_url)
    database_url: str = ""

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
