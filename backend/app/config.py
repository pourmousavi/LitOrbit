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
    gemini_api_key: str = ""

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
    gemini_model_fast: str = "gemini-2.5-flash"

    # App
    secret_key: str = ""
    environment: str = "development"
    frontend_url: str = "http://localhost:5173"

    # Database (constructed from supabase_url)
    database_url: str = ""

    # Shared secret used by external schedulers (GitHub Actions cron)
    # to authenticate scheduled pipeline runs without a user JWT.
    pipeline_trigger_secret: str = ""

    # Optional base URL for the Gemini API. When set, all google-genai
    # client calls are routed through this URL instead of
    # https://generativelanguage.googleapis.com. Used to proxy through a
    # Cloudflare Worker so calls originate from a CF edge POP rather than
    # Render's egress IP (which Google's geo-restriction list still blocks
    # even on paid tier). The path-prefix secret is embedded directly in
    # this URL, e.g. https://litorbit-gemini-proxy.foo.workers.dev/<secret>
    gemini_api_base: str = ""

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
