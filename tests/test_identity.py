"""Role resolution (spec §2; §11 unit: role resolution). Caller ID is a
routing hint; the owner Telegram chat is the root of trust."""
from __future__ import annotations

from core.identity import Role, resolve_phone_role, resolve_telegram_role


def test_owner_phone_is_master(cfg) -> None:
    assert resolve_phone_role("+15550000001", cfg) is Role.MASTER


def test_owner_phone_matches_any_formatting(cfg) -> None:
    assert resolve_phone_role("1 (555) 000-0001", cfg) is Role.MASTER


def test_whitelisted_phone_is_trusted(cfg) -> None:
    assert resolve_phone_role("+15550000002", cfg) is Role.TRUSTED
    assert resolve_phone_role("+15550000003", cfg) is Role.TRUSTED


def test_unknown_phone_is_stranger(cfg) -> None:
    assert resolve_phone_role("+15559999999", cfg) is Role.STRANGER


def test_unparseable_caller_id_is_stranger_not_crash(cfg) -> None:
    assert resolve_phone_role("anonymous", cfg) is Role.STRANGER
    assert resolve_phone_role("", cfg) is Role.STRANGER


def test_owner_telegram_chat_is_master(cfg) -> None:
    assert resolve_telegram_role(12345, cfg) is Role.MASTER


def test_other_telegram_chat_is_stranger(cfg) -> None:
    assert resolve_telegram_role(99999, cfg) is Role.STRANGER
    assert resolve_telegram_role(-12345, cfg) is Role.STRANGER
