from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_prefix="FORGEPILOT_",
    )

    env: str = "dev"
    host: str = "0.0.0.0"
    port: int = 8080
    log_level: str = "INFO"
    api_prefix: str = "/api/v1"
    database_url: str = "postgresql+psycopg://forgepilot:forgepilot_secret@localhost:5432/forgepilot"

    opensandbox_base_url: str = "http://localhost:3000"
    opensandbox_api_key: str = ""
    opensandbox_image_uri: str = "forgepilot/sandbox-runtime:local"
    opensandbox_timeout_seconds: int = 1800
    opensandbox_ready_timeout_seconds: int = 120
    opensandbox_request_timeout_seconds: int = 30
    opensandbox_use_server_proxy: bool = True

    gemini_api_key: str = ""
    openai_api_key: str = ""

    max_steps_per_task: int = 30
    allow_high_risk_commands: bool = False

    # Auth
    secret_key: str = "change-me-in-production-use-openssl-rand-hex-32"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7


settings = Settings()
