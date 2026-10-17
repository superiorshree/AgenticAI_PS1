from enum import Enum
from functools import lru_cache
from typing import Optional
from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(str, Enum):
    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Core ────────────────────────────────────────────────────────────────
    APP_NAME: str = "YuktiOps Backend"
    APP_VERSION: str = "0.2.0"
    ENVIRONMENT: Environment = Environment.DEVELOPMENT
    DEBUG: bool = False
    HOST: str = "0.0.0.0"
    PORT: int = 8001
    LOG_LEVEL: str = "INFO"

    # ── CORS ────────────────────────────────────────────────────────────────
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:5173"

    # ── Database ────────────────────────────────────────────────────────────
    DATABASE_URL: str = Field(
        default="sqlite+aiosqlite:///./yuktiops_backend.db",
        description="Async DB URL — use postgresql+asyncpg for Supabase",
    )

    # ── Firebase ────────────────────────────────────────────────────────────
    FIREBASE_PROJECT_ID: Optional[str] = "yuktiopsai-d1f6f"
    FIREBASE_SERVICE_ACCOUNT_FILE: Optional[str] = "firebase-service-account.json"
    FIREBASE_SERVICE_ACCOUNT_JSON: Optional[str] = None

    # ── Telegram ────────────────────────────────────────────────────────────
    TELEGRAM_BOT_TOKEN: Optional[str] = None
    TELEGRAM_ALERT_CHAT_ID: Optional[str] = None
    TELEGRAM_WEBHOOK_SECRET: Optional[str] = None
    PUBLIC_BASE_URL: Optional[str] = None

    # ── GitHub ──────────────────────────────────────────────────────────────
    GITHUB_WEBHOOK_SECRET: str = "mock_webhook_secret_for_local_testing"
    GITHUB_APP_ID: Optional[str] = None
    GITHUB_APP_PRIVATE_KEY: Optional[str] = None

    # ── LLM ─────────────────────────────────────────────────────────────────
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL_NAME: str = "gpt-4o-mini"
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"

    # ── Reddit ──────────────────────────────────────────────────────────────
    REDDIT_CLIENT_ID: Optional[str] = None
    REDDIT_CLIENT_SECRET: Optional[str] = None
    REDDIT_USER_AGENT: str = "YuktiOpsAI/0.2 (hackathon research bot)"

    # ── LinkedIn ────────────────────────────────────────────────────────────
    LINKEDIN_CLIENT_ID: Optional[str] = None
    LINKEDIN_CLIENT_SECRET: Optional[str] = None
    LINKEDIN_ACCESS_TOKEN: Optional[str] = None

    # ── Rewarded Ads ────────────────────────────────────────────────────────
    REWARDED_ADS_TEST_MODE: bool = True
    ADMOB_SERVER_SIDE_VERIFICATION_SECRET: Optional[str] = None

    # ── Credits / Referrals (configurable — product decision required) ───────
    CREDIT_COST_FULL_SOLUTION: int = 10
    CREDIT_COST_SOCIAL_RESEARCH: int = 5
    CREDIT_REFERRAL_REWARD: int = 20
    CREDIT_REFERRAL_REFEREE_REWARD: int = 10
    CREDIT_NEW_USER_GRANT: int = 50
    REWARDED_AD_UNLOCK_DURATION_SECONDS: int = 3600
    REWARDED_AD_ELIGIBLE_FEATURES: str = "full_solution,social_research"

    # ── Agents service ──────────────────────────────────────────────────────
    AGENTS_BASE_URL: str = Field(
        default="http://localhost:8000",
        validation_alias=AliasChoices("AGENTS_URL", "AGENTS_BASE_URL"),
        description="Internal base URL for the agents service (injected via Vercel service binding or local .env)",
    )

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def rewarded_ad_features_list(self) -> list[str]:
        return [f.strip() for f in self.REWARDED_AD_ELIGIBLE_FEATURES.split(",") if f.strip()]


@lru_cache()
def get_settings() -> Settings:
    return Settings()
