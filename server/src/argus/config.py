"""Configuration management using Pydantic Settings."""

import json
import secrets
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


ARGUS_DIR = Path.home() / ".argus"
CONFIG_FILE = ARGUS_DIR / "config.json"


def _load_or_create_token() -> str:
    """Load existing token from ~/.argus/config.json or create a new one."""
    ARGUS_DIR.mkdir(parents=True, exist_ok=True)

    if CONFIG_FILE.exists():
        try:
            data = json.loads(CONFIG_FILE.read_text())
            if token := data.get("auth_token"):
                return token
        except (json.JSONDecodeError, OSError):
            pass

    token = secrets.token_urlsafe(32)
    try:
        existing = {}
        if CONFIG_FILE.exists():
            try:
                existing = json.loads(CONFIG_FILE.read_text())
            except (json.JSONDecodeError, OSError):
                pass
        existing["auth_token"] = token
        CONFIG_FILE.write_text(json.dumps(existing, indent=2))
    except OSError:
        pass

    return token


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ARGUS_")

    host: str = "127.0.0.1"
    port: int = 42777
    auth_token: str = ""
    transport: str = "stdio"  # "stdio", "sse", or "all"
    max_errors: int = 100
    max_console: int = 200
    max_network: int = 200
    max_screenshots: int = 15
    max_payload_size: int = 5 * 1024 * 1024  # 5MB
    rate_limit: int = 120  # requests per minute
    log_level: str = "INFO"
    max_body_length: int = 2000

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.auth_token:
            self.auth_token = _load_or_create_token()


settings = Settings()

