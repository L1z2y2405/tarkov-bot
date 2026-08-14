from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip().lstrip("\ufeff")
        value = value.strip().strip('"').strip("'")
        current_value = os.environ.get(key)
        if key and (current_value is None or not current_value.strip()):
            os.environ[key] = value


def _parse_bool(value: str | None, default: bool = True) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _parse_int(value: str | None, default: int) -> int:
    if value is None or not value.strip():
        return default
    try:
        return int(value)
    except ValueError:
        return default


@dataclass(frozen=True, slots=True)
class Settings:
    discord_webhook_url: str
    check_interval_seconds: int
    twitter_username: str
    headless: bool
    retry_attempts: int
    run_once: bool
    data_dir: Path

    @classmethod
    def from_env(cls) -> "Settings":
        root_dir = Path(__file__).resolve().parent
        _load_dotenv(root_dir / ".env")
        return cls(
            discord_webhook_url=os.getenv("DISCORD_WEBHOOK_URL", "").strip(),
            check_interval_seconds=_parse_int(
                os.getenv("CHECK_INTERVAL_SECONDS"), 300
            ),
            twitter_username=os.getenv("TWITTER_USERNAME", "tarkov").strip(),
            headless=_parse_bool(os.getenv("HEADLESS"), True),
            retry_attempts=_parse_int(os.getenv("RETRY_ATTEMPTS"), 3),
            run_once=_parse_bool(os.getenv("RUN_ONCE"), False),
            data_dir=root_dir / "data",
        )
