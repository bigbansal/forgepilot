from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_prefix="MANCH_",
    )

    env: str = "dev"
    host: str = "0.0.0.0"
    port: int = 8080
    log_level: str = "INFO"
    api_prefix: str = "/api/v1"
    database_url: str = "postgresql+psycopg://manch:manch_secret@localhost:5432/manch"

    opensandbox_base_url: str = "http://localhost:3000"
    # Public URL shown to the user in task output — should always be the externally reachable host.
    # In Docker the backend env overrides opensandbox_base_url to the internal hostname,
    # so this separate field keeps the user-facing URL correct.
    opensandbox_public_url: str = "http://localhost:3000"
    public_base_url: str = "http://localhost:8212"
    opensandbox_api_key: str = ""
    opensandbox_image_uri: str = "manch/sandbox-runtime:local"
    opensandbox_timeout_seconds: int = 1800
    opensandbox_ready_timeout_seconds: int = 120
    opensandbox_request_timeout_seconds: int = 30
    opensandbox_use_server_proxy: bool = True

    gemini_api_key: str = ""
    openai_api_key: str = ""
    anthropic_api_key: str = ""

    max_steps_per_task: int = 30
    allow_high_risk_commands: bool = False

    # CORS (comma-separated origins for production; * for dev)
    cors_origins: str = "*"

    # Auth
    secret_key: str = "change-me-in-production-use-openssl-rand-hex-32"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7

    # Telegram bot integration
    telegram_bot_token: str = ""  # MANCH_TELEGRAM_BOT_TOKEN

    # WhatsApp Cloud API integration
    whatsapp_token: str = ""          # MANCH_WHATSAPP_TOKEN (permanent access token)
    whatsapp_verify_token: str = "manch-verify"  # MANCH_WHATSAPP_VERIFY_TOKEN
    whatsapp_phone_number_id: str = ""  # MANCH_WHATSAPP_PHONE_NUMBER_ID


settings = Settings()
