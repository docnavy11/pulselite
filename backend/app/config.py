from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "pulse"
    POSTGRES_USER: str = "pulse"
    POSTGRES_PASSWORD: str = "pulse_dev_password"

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str = ""

    # JWT
    SECRET_KEY: str
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Google OAuth (sign-in)
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/api/v1/auth/google/callback"

    # Google Drive OAuth (knowledge base integration)
    GOOGLE_DRIVE_CLIENT_ID: str = ""
    GOOGLE_DRIVE_CLIENT_SECRET: str = ""

    # Notion OAuth
    NOTION_CLIENT_ID: str = ""
    NOTION_CLIENT_SECRET: str = ""
    NOTION_REDIRECT_URI: str = "http://localhost:8000/api/v1/oauth/notion/callback"

    # Slack Bot OAuth
    SLACK_CLIENT_ID: str = ""
    SLACK_CLIENT_SECRET: str = ""
    SLACK_SIGNING_SECRET: str = ""
    SLACK_BOT_SCOPE: str = "app_mentions:read,channels:history,chat:write,im:history,im:write"

    # Meta (WhatsApp / Messenger / Instagram)
    META_WHATSAPP_VERIFY_TOKEN: str = ""
    META_WHATSAPP_TOKEN: str = ""  # fallback system token
    META_MESSENGER_VERIFY_TOKEN: str = ""
    META_INSTAGRAM_VERIFY_TOKEN: str = ""

    # Shopify
    SHOPIFY_CLIENT_ID: str = ""
    SHOPIFY_CLIENT_SECRET: str = ""

    # Zendesk
    ZENDESK_CLIENT_ID: str = ""
    ZENDESK_CLIENT_SECRET: str = ""

    # Dropbox
    DROPBOX_CLIENT_ID: str = ""
    DROPBOX_CLIENT_SECRET: str = ""

    # Salesforce
    SALESFORCE_CLIENT_ID: str = ""
    SALESFORCE_CLIENT_SECRET: str = ""

    # Base URL (used for OAuth redirect URIs)
    BASE_URL: str = "http://localhost:8000"
    FRONTEND_URL: str = "http://localhost:3001"

    # AI Keys
    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    GOOGLE_AI_API_KEY: str = ""
    OPENROUTER_API_KEY: str = ""

    # Global AI proxy overrides (used as defaults when no workspace-level config is set)
    AI_BASE_URL: str = ""
    AI_API_KEY: str = ""

    # Encryption
    FERNET_KEY: str = ""

    # Stripe
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""

    # Deployment mode
    CLOUD_MODE: bool = False

    # CORS
    BACKEND_CORS_ORIGINS: list[str] = ["http://localhost:3000"]

    @property
    def database_url(self) -> str:
        return f"postgresql+psycopg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    @property
    def database_url_sync(self) -> str:
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    @property
    def REDIS_URL(self) -> str:
        auth = f":{self.REDIS_PASSWORD}@" if self.REDIS_PASSWORD else ""
        return f"redis://{auth}{self.REDIS_HOST}:{self.REDIS_PORT}/0"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()

PLAN_CHAR_LIMITS: dict[str, int | None] = {
    "free":         500_000,
    "starter":    2_000_000,
    "growth":    10_000_000,
    "enterprise": None,         # unlimited
}
