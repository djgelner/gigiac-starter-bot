"""Configuration loader — reads from environment / .env file."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal

BotMode = Literal["worker", "commissioner", "both"]


@dataclass(frozen=True)
class Config:
    api_url: str
    api_key: str
    anthropic_api_key: str
    bot_mode: BotMode
    poll_interval_seconds: int


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _parse_bot_mode(value: str | None) -> BotMode:
    mode = (value or "both").lower()
    if mode in ("worker", "commissioner", "both"):
        return mode  # type: ignore[return-value]
    raise ValueError(f'Invalid BOT_MODE: "{value}". Must be worker, commissioner, or both.')


def load_config() -> Config:
    return Config(
        api_url=(os.environ.get("GIGIAC_API_URL") or "https://gigiac.com").rstrip("/"),
        api_key=_require_env("GIGIAC_API_KEY"),
        anthropic_api_key=_require_env("ANTHROPIC_API_KEY"),
        bot_mode=_parse_bot_mode(os.environ.get("BOT_MODE")),
        poll_interval_seconds=int(os.environ.get("POLL_INTERVAL_SECONDS", "60")),
    )
