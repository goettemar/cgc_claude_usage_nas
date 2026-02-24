"""Application configuration with dual-source: JSON file + environment variables."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

DATA_DIR = Path(os.environ.get("DATA_DIR", "/app/data"))
CONFIG_FILE = DATA_DIR / "config.json"


@dataclass
class AppConfig:
    session_key: str = ""
    org_uuid: str = ""
    admin_api_key: str = ""
    openrouter_api_key: str = ""
    deepl_api_key: str = ""
    auto_refresh_minutes: int = 15
    retention_days: int = 90

    def save(self) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_FILE.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")

    @classmethod
    def load(cls) -> AppConfig:
        """Load config: JSON first, then fill missing fields from env vars."""
        data: dict = {}
        if CONFIG_FILE.exists():
            try:
                data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            except Exception:
                logger.warning("Config load failed, using defaults", exc_info=True)

        # Filter to known fields only
        data = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}

        # Fill missing fields from environment variables
        env_map = {
            "session_key": "SESSION_KEY",
            "org_uuid": "ORG_UUID",
            "admin_api_key": "ADMIN_API_KEY",
            "openrouter_api_key": "OPENROUTER_API_KEY",
            "deepl_api_key": "DEEPL_API_KEY",
            "auto_refresh_minutes": "AUTO_REFRESH_MINUTES",
            "retention_days": "RETENTION_DAYS",
        }
        for field_name, env_var in env_map.items():
            if field_name not in data or not data[field_name]:
                env_val = os.environ.get(env_var, "")
                if env_val:
                    field_type = cls.__dataclass_fields__[field_name].type
                    if field_type == "int":
                        data[field_name] = int(env_val)
                    else:
                        data[field_name] = env_val

        return cls(**data)
