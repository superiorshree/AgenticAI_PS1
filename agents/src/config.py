from enum import Enum
from functools import lru_cache
from typing import Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(str, Enum):
    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"


class SeverityLevel(str, Enum):
    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Core App
    APP_NAME: str = "YuktiOps Agent Service"
    APP_VERSION: str = "0.2.0"
    ENVIRONMENT: Environment = Environment.DEVELOPMENT
    DEBUG: bool = False
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    LOG_LEVEL: str = "INFO"

    # CORS
    CORS_ORIGINS: str = Field(
        default="http://localhost:3000,http://localhost:5173",
        description="Comma-separated allowed origins for CORS",
    )

    # Database — PostgreSQL (Supabase) preferred; SQLite fallback for local dev
    DATABASE_URL: str = Field(
        default="sqlite+aiosqlite:///./yuktiops.db",
        description="Async database connection string (PostgreSQL or SQLite)",
    )

    # Redis / Workers
    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL for async queues",
    )

    # Firebase Admin SDK
    FIREBASE_PROJECT_ID: Optional[str] = None
    FIREBASE_SERVICE_ACCOUNT_JSON: Optional[str] = Field(
        default=None,
        description="JSON string of Firebase service account credentials",
    )

    # GitHub App
    GITHUB_APP_ID: Optional[str] = None
    GITHUB_APP_PRIVATE_KEY: Optional[str] = None
    GITHUB_WEBHOOK_SECRET: str = Field(
        default="mock_webhook_secret_for_local_testing",
        description="Webhook secret to verify HMAC SHA256 signatures",
    )

    # Telegram Bot
    TELEGRAM_BOT_TOKEN: Optional[str] = None
    TELEGRAM_ALERT_CHAT_ID: Optional[str] = None
    TELEGRAM_WEBHOOK_SECRET: Optional[str] = Field(
        default=None,
        description="Secret token for verifying Telegram webhook updates",
    )
    # PUBLIC_BASE_URL used for registering Telegram webhook endpoint
    PUBLIC_BASE_URL: Optional[str] = Field(
        default=None,
        description="Public HTTPS base URL (e.g. from ngrok) for Telegram webhook registration",
    )

    # LLM Provider (Google Gemini)
    GEMINI_API_KEY: Optional[str] = None
    GOOGLE_API_KEY: Optional[str] = None
    GEMINI_MODEL_NAME: str = "gemini-1.5-flash"
    MOCK_LLM_MODE: bool = Field(
        default=False,
        description="When True, LLMService runs in offline deterministic mock mode for CI/evals",
    )

    @property
    def gemini_key(self) -> Optional[str]:
        """Return GEMINI_API_KEY or GOOGLE_API_KEY, whichever is configured."""
        return self.GEMINI_API_KEY or self.GOOGLE_API_KEY

    # Reddit API (PRAW / OAuth2)
    REDDIT_CLIENT_ID: Optional[str] = None
    REDDIT_CLIENT_SECRET: Optional[str] = None
    REDDIT_USER_AGENT: str = "YuktiOpsAI/0.2 (hackathon research bot)"

    # LinkedIn API
    LINKEDIN_CLIENT_ID: Optional[str] = None
    LINKEDIN_CLIENT_SECRET: Optional[str] = None
    LINKEDIN_ACCESS_TOKEN: Optional[str] = Field(
        default=None,
        description="Long-lived LinkedIn OAuth2 access token for API calls",
    )

    # Rewarded Ads
    REWARDED_ADS_TEST_MODE: bool = Field(
        default=True,
        description="When True, skip real ad provider verification (dev/test only)",
    )
    ADMOB_SERVER_SIDE_VERIFICATION_SECRET: Optional[str] = Field(
        default=None,
        description="AdMob SSV HMAC secret for verifying rewarded ad completions",
    )

    # Credits & Referrals (configurable — no hardcoded business values)
    CREDIT_COST_FULL_SOLUTION: int = Field(
        default=10,
        description="Credit cost to generate a full AI solution (product decision required)",
    )
    CREDIT_COST_SOCIAL_RESEARCH: int = Field(
        default=5,
        description="Credit cost for Reddit/LinkedIn research (product decision required)",
    )
    CREDIT_REFERRAL_REWARD: int = Field(
        default=20,
        description="Credits awarded to referrer on qualifying activation (product decision required)",
    )
    CREDIT_REFERRAL_REFEREE_REWARD: int = Field(
        default=10,
        description="Credits awarded to new user who used a referral code (product decision required)",
    )
    CREDIT_NEW_USER_GRANT: int = Field(
        default=50,
        description="Free credits granted to new users on first sign-in (product decision required)",
    )
    REWARDED_AD_UNLOCK_DURATION_SECONDS: int = Field(
        default=3600,
        description="Seconds a feature unlock granted by rewarded ad remains active",
    )
    REWARDED_AD_ELIGIBLE_FEATURES: str = Field(
        default="full_solution,social_research",
        description="Comma-separated feature keys that can be unlocked via rewarded ad",
    )

    # Context & Cost Boundaries
    MAX_DIFF_LINES: int = 1200
    MAX_DIFF_BYTES: int = 60000
    SEVERITY_NOTIFICATION_THRESHOLD: SeverityLevel = SeverityLevel.HIGH

    # CORS — comma-separated list of allowed frontend origins.
    # In .env use:  ALLOWED_ORIGINS=http://localhost:3000,https://app.example.com
    # Stored as a plain string; split to list at the CORS middleware call site.
    ALLOWED_ORIGINS: str = Field(
        default="http://localhost:3000",
        description="Comma-separated trusted frontend origins for CORS",
    )

    @property
    def allowed_origins_list(self) -> list[str]:
        """Return ALLOWED_ORIGINS or CORS_ORIGINS as a split, stripped list of origin strings."""
        origins = self.ALLOWED_ORIGINS or self.CORS_ORIGINS
        return [o.strip() for o in origins.split(",") if o.strip()]

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def rewarded_ad_features_list(self) -> list[str]:
        return [f.strip() for f in self.REWARDED_AD_ELIGIBLE_FEATURES.split(",") if f.strip()]

    @field_validator("GITHUB_WEBHOOK_SECRET")
    @classmethod
    def validate_webhook_secret_in_production(cls, v: str, info) -> str:
        """Prevent startup in production if the webhook secret is the known public default."""
        env = info.data.get("ENVIRONMENT", Environment.DEVELOPMENT)
        if env == Environment.PRODUCTION and v == "mock_webhook_secret_for_local_testing":
            raise ValueError(
                "GITHUB_WEBHOOK_SECRET must be overridden in production. "
                "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
            )
        return v


@lru_cache()
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()
