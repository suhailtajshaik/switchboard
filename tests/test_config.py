"""Fail-fast configuration (spec §1; §11 unit: config validation, S2)."""
from __future__ import annotations

import pytest

from core.config import ConfigError, from_env


def test_happy_path_defaults(base_env) -> None:
    cfg = from_env(base_env)
    assert cfg.quiet_hours_start == 21 and cfg.quiet_hours_end == 9
    assert cfg.max_call_minutes == 10
    assert cfg.daily_max_outbound_calls == 15 and cfg.daily_max_sms == 30
    assert cfg.approval_timeout_minutes == 5
    assert cfg.sms_enabled is False and cfg.dry_run is False
    assert cfg.daily_max_spend_usd == 5.0
    assert cfg.transcript_retention_days == 90
    assert cfg.persona_lang == "en" and cfg.default_region == "US"


def test_owner_phone_is_normalized(base_env) -> None:
    base_env["OWNER_PHONE"] = "555-000-0001"
    assert from_env(base_env).owner_phone == "+15550000001"


def test_missing_required_keys_are_all_reported(base_env) -> None:
    del base_env["ANTHROPIC_API_KEY"]
    del base_env["TWILIO_AUTH_TOKEN"]
    with pytest.raises(ConfigError) as exc:
        from_env(base_env)
    assert "ANTHROPIC_API_KEY" in str(exc.value)
    assert "TWILIO_AUTH_TOKEN" in str(exc.value)


def test_placeholder_value_rejected(base_env) -> None:
    base_env["ANTHROPIC_API_KEY"] = "sk-ant-REPLACE"
    with pytest.raises(ConfigError):
        from_env(base_env)


@pytest.mark.parametrize("flag", ["DISABLE_WEBHOOK_VALIDATION", "SKIP_TWILIO_SIGNATURE"])
@pytest.mark.parametrize("value", ["1", "true", "yes", "on"])
def test_s2_signature_validation_cannot_be_disabled(base_env, flag, value) -> None:
    base_env[flag] = value
    with pytest.raises(ConfigError) as exc:
        from_env(base_env)
    assert "S2" in str(exc.value)


def test_s2_flag_falsy_value_boots(base_env) -> None:
    base_env["DISABLE_WEBHOOK_VALIDATION"] = "false"
    from_env(base_env)  # must not raise


def test_chat_id_must_be_numeric(base_env) -> None:
    base_env["TELEGRAM_OWNER_CHAT_ID"] = "not-a-number"
    with pytest.raises(ConfigError):
        from_env(base_env)


def test_negative_chat_id_allowed(base_env) -> None:
    base_env["TELEGRAM_OWNER_CHAT_ID"] = "-100123"
    assert from_env(base_env).telegram_owner_chat_id == -100123


def test_unknown_timezone_rejected(base_env) -> None:
    base_env["OWNER_TIMEZONE"] = "Mars/Olympus_Mons"
    with pytest.raises(ConfigError):
        from_env(base_env)


def test_dtmf_pin_validation(base_env) -> None:
    base_env["DTMF_PIN"] = "12"
    with pytest.raises(ConfigError):
        from_env(base_env)
    base_env["DTMF_PIN"] = "123456"
    assert from_env(base_env).dtmf_pin == "123456"


def test_whitelist_parsing_and_normalization(base_env) -> None:
    base_env["WHITELIST_PHONES"] = " 555-000-0002 , +15550000003 ,"
    cfg = from_env(base_env)
    assert cfg.whitelist_phones == ("+15550000002", "+15550000003")


def test_whitelist_bad_entry_reported(base_env) -> None:
    base_env["WHITELIST_PHONES"] = "+15550000002,garbage"
    with pytest.raises(ConfigError) as exc:
        from_env(base_env)
    assert "WHITELIST_PHONES" in str(exc.value)


def test_quiet_hours_out_of_range(base_env) -> None:
    base_env["QUIET_HOURS_START"] = "25"
    with pytest.raises(ConfigError):
        from_env(base_env)


def test_blocked_prefixes_parsed(base_env) -> None:
    base_env["BLOCKED_PREFIXES"] = "+1809, +1900"
    assert from_env(base_env).blocked_extra == ("+1809", "+1900")
