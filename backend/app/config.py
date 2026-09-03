from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database (Postgres only — no Redis)
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "pulse"
    POSTGRES_USER: str = "pulse"
    POSTGRES_PASSWORD: str = "pulse_dev_password"

    # Auth — signs session cookies + CSRF tokens + widget JWTs
    SECRET_KEY: str = "dev-secret-key-change-in-production"
    SESSION_EXPIRY_DAYS: int = 7

    # JWT (only for public widget API — sessions handle dashboard auth)
    JWT_SECRET_KEY: str = "dev-jwt-secret-change-in-production"
    JWT_SECRET_KEY_PREVIOUS: str = ""
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Google OAuth (sign-in)
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/auth/google/callback"

    # Google Drive OAuth (knowledge base integration)
    GOOGLE_DRIVE_CLIENT_ID: str = ""
    GOOGLE_DRIVE_CLIENT_SECRET: str = ""

    # Notion OAuth
    NOTION_CLIENT_ID: str = ""
    NOTION_CLIENT_SECRET: str = ""
    NOTION_REDIRECT_URI: str = "http://localhost:8000/oauth/notion/callback"

    # Slack Bot OAuth
    SLACK_CLIENT_ID: str = ""
    SLACK_CLIENT_SECRET: str = ""
    SLACK_SIGNING_SECRET: str = ""
    SLACK_BOT_SCOPE: str = "app_mentions:read,channels:history,chat:write,im:history,im:write"

    # Meta (WhatsApp / Messenger / Instagram)
    META_WHATSAPP_VERIFY_TOKEN: str = ""
    META_WHATSAPP_TOKEN: str = ""
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

    # Base URL
    BASE_URL: str = "http://localhost:8000"

    # AI Keys
    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    GOOGLE_AI_API_KEY: str = ""
    OPENROUTER_API_KEY: str = ""

    # Global AI proxy overrides
    AI_BASE_URL: str = ""
    AI_API_KEY: str = ""
    DEFAULT_CHATBOT_MODEL: str = ""
    INTERNAL_MODEL: str = ""

    # Bootstrap admin account
    ADMIN_EMAIL: str = ""
    ADMIN_PASSWORD: str = ""

    # Encryption
    FERNET_KEY: str = ""

    # Stripe
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""

    # Database connection pool
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 1800

    # Crawl
    CRAWL_FETCH_CONCURRENCY: int = 30
    CRAWL_MAX_PAGES: int = 10000
    CRAWL_EMBED_BATCH_SIZE: int = 256

    # Deployment mode
    CLOUD_MODE: bool = False

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    WORKERS: int = 4

    # CORS (for widget script on external sites)
    CORS_ORIGINS: list[str] = ["*"]

    @property
    def database_url(self) -> str:
        return f"postgresql+psycopg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    @property
    def database_url_sync(self) -> str:
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
