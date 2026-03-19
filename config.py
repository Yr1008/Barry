"""Barry configuration management."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings

load_dotenv()


class BarryConfig(BaseSettings):
    # Core
    anthropic_api_key: str = Field(..., env="ANTHROPIC_API_KEY")
    barry_name: str = Field("Barry", env="BARRY_NAME")
    owner_name: str = Field("User", env="BARRY_OWNER_NAME")
    timezone: str = Field("America/New_York", env="BARRY_TIMEZONE")
    poll_interval_minutes: int = Field(5, env="BARRY_POLL_INTERVAL_MINUTES")
    briefing_time: str = Field("07:30", env="BARRY_BRIEFING_TIME")
    data_dir: Path = Field(Path("./data"), env="BARRY_DATA_DIR")

    # Google
    google_client_id: str = Field("", env="GOOGLE_CLIENT_ID")
    google_client_secret: str = Field("", env="GOOGLE_CLIENT_SECRET")
    google_redirect_uri: str = Field("http://localhost:8000/auth/google/callback", env="GOOGLE_REDIRECT_URI")

    # iCloud / Apple Calendar
    icloud_email: str = Field("", env="ICLOUD_EMAIL")
    icloud_password: str = Field("", env="ICLOUD_PASSWORD")

    # Email
    email_address: str = Field("", env="EMAIL_ADDRESS")
    email_password: str = Field("", env="EMAIL_PASSWORD")
    imap_server: str = Field("imap.gmail.com", env="IMAP_SERVER")
    imap_port: int = Field(993, env="IMAP_PORT")
    smtp_server: str = Field("smtp.gmail.com", env="SMTP_SERVER")
    smtp_port: int = Field(587, env="SMTP_PORT")
    email_scan_count: int = Field(50, env="EMAIL_SCAN_COUNT")

    # WhatsApp / Twilio
    twilio_account_sid: str = Field("", env="TWILIO_ACCOUNT_SID")
    twilio_auth_token: str = Field("", env="TWILIO_AUTH_TOKEN")
    twilio_whatsapp_number: str = Field("", env="TWILIO_WHATSAPP_NUMBER")
    my_whatsapp_number: str = Field("", env="MY_WHATSAPP_NUMBER")

    # iPhone Shortcuts Webhook
    shortcuts_webhook_secret: str = Field("", env="SHORTCUTS_WEBHOOK_SECRET")
    shortcuts_webhook_port: int = Field(8001, env="SHORTCUTS_WEBHOOK_PORT")

    # API Server
    api_host: str = Field("0.0.0.0", env="API_HOST")
    api_port: int = Field(8000, env="API_PORT")
    api_secret_key: str = Field("barry-secret-key", env="API_SECRET_KEY")

    # Notifications
    pushover_user_key: str = Field("", env="PUSHOVER_USER_KEY")
    pushover_api_token: str = Field("", env="PUSHOVER_API_TOKEN")

    # External services
    calendly_api_key: str = Field("", env="CALENDLY_API_KEY")
    fireflies_api_key: str = Field("", env="FIREFLIES_API_KEY")

    # Debug
    debug: bool = Field(False, env="DEBUG")
    log_level: str = Field("INFO", env="LOG_LEVEL")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

    def ensure_data_dir(self) -> None:
        """Create data directory and subdirectories."""
        dirs = [
            self.data_dir,
            self.data_dir / "memory",
            self.data_dir / "tokens",
            self.data_dir / "cache",
            self.data_dir / "logs",
        ]
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)

    @property
    def db_path(self) -> Path:
        return self.data_dir / "memory" / "barry.db"

    @property
    def google_token_path(self) -> Path:
        return self.data_dir / "tokens" / "google_token.json"

    @property
    def has_google(self) -> bool:
        return bool(self.google_client_id and self.google_client_secret)

    @property
    def has_icloud(self) -> bool:
        return bool(self.icloud_email and self.icloud_password)

    @property
    def has_email(self) -> bool:
        return bool(self.email_address and self.email_password)

    @property
    def has_whatsapp(self) -> bool:
        return bool(self.twilio_account_sid and self.twilio_auth_token)

    @property
    def has_pushover(self) -> bool:
        return bool(self.pushover_user_key and self.pushover_api_token)


# Singleton
_config: BarryConfig | None = None


def get_config() -> BarryConfig:
    global _config
    if _config is None:
        _config = BarryConfig()
        _config.ensure_data_dir()
    return _config
