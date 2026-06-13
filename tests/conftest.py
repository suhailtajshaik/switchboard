"""Shared fixtures. Makes src/ importable so the conformance suite runs
without an install step (core is stdlib-only by design)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import pytest

from core.config import from_env

BASE_ENV = {
    "ANTHROPIC_API_KEY": "sk-ant-test",
    "TELEGRAM_BOT_TOKEN": "tg-token",
    "TELEGRAM_OWNER_CHAT_ID": "12345",
    "TWILIO_ACCOUNT_SID": "ACtest",
    "TWILIO_AUTH_TOKEN": "twilio-secret",
    "TWILIO_NUMBER": "+15550000000",
    "OWNER_NAME": "Alex",
    "OWNER_PHONE": "+15550000001",
    "PUBLIC_DOMAIN": "assistant.example.com",
    "OWNER_TIMEZONE": "America/New_York",
}


@pytest.fixture
def base_env() -> dict[str, str]:
    return dict(BASE_ENV)


@pytest.fixture
def cfg():
    env = dict(BASE_ENV)
    env["WHITELIST_PHONES"] = "+15550000002, +15550000003"
    return from_env(env)
