"""Fail-fast configuration loading (spec §1, v0.2)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Mapping
from zoneinfo import ZoneInfo

from .phones import normalize


class ConfigError(Exception):
    """Raised at boot when configuration is missing or invalid."""


# NOTE (v0.2): VOICE_PIN removed. Sensitive actions use out-of-band approval
# on the root-of-trust channel (spec §2.1, S3), not a spoken secret.
_REQUIRED = [
    "ANTHROPIC_API_KEY", "TELEGRAM_BOT_TOKEN", "TELEGRAM_OWNER_CHAT_ID",
    "TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_NUMBER",
    "OWNER_NAME", "OWNER_PHONE", "PUBLIC_DOMAIN", "OWNER_TIMEZONE",
]

# Settings that disable webhook signature validation are forbidden (S2): if any
# appears truthy in the environment, boot fails.
_FORBIDDEN_TRUTHY = ["DISABLE_WEBHOOK_VALIDATION", "SKIP_TWILIO_SIGNATURE"]


@dataclass(frozen=True)
class Config:
    anthropic_api_key: str
    telegram_bot_token: str
    telegram_owner_chat_id: int
    twilio_account_sid: str
    twilio_auth_token: str
    twilio_number: str
    owner_name: str
    owner_phone: str
    whitelist_phones: tuple[str, ...]
    public_domain: str
    owner_timezone: str
    # brain
    brain_base_url: str = ""
    brain_model: str = ""
    # policy / safety
    quiet_hours_start: int = 21
    quiet_hours_end: int = 9
    max_call_minutes: int = 10
    daily_max_outbound_calls: int = 15
    daily_max_sms: int = 30
    escalation_wait_minutes: int = 5
    approval_timeout_minutes: int = 5         # S3 out-of-band approval expiry
    sms_enabled: bool = False
    dtmf_pin: str = ""                        # optional 2nd factor only (S3)
    # inbound abuse limits (S11) + reliability (§7)
    max_concurrent_calls: int = 2
    inbound_per_number_cooldown_seconds: int = 60
    daily_inbound_minutes: int = 120
    brain_response_timeout_seconds: int = 12
    relay_nonce_ttl_seconds: int = 120
    # operations (v0.3)
    daily_max_spend_usd: float = 5.0
    transcript_retention_days: int = 90
    dry_run: bool = False
    # voice / locale
    persona_lang: str = "en"
    tts_provider: str = ""                    # e.g. "ElevenLabs"; empty=default
    tts_voice: str = ""
    default_region: str = "US"
    blocked_extra: tuple[str, ...] = field(default_factory=tuple)


def _float(env: Mapping[str, str], key: str, default: float, errs: list[str],
           lo: float = 0.0, hi: float = 10.0**6) -> float:
    raw = env.get(key, str(default))
    try:
        val = float(raw)
    except ValueError:
        errs.append(f"{key}: not a number ({raw!r})")
        return default
    if not lo <= val <= hi:
        errs.append(f"{key}: out of range [{lo},{hi}] ({val})")
    return val


def _int(env: Mapping[str, str], key: str, default: int, errs: list[str],
         lo: int = 0, hi: int = 10**6) -> int:
    raw = env.get(key, str(default))
    try:
        val = int(raw)
    except ValueError:
        errs.append(f"{key}: not an integer ({raw!r})")
        return default
    if not lo <= val <= hi:
        errs.append(f"{key}: out of range [{lo},{hi}] ({val})")
    return val


def from_env(env: Mapping[str, str]) -> Config:
    """Build Config from an environment mapping; raise ConfigError listing
    *all* problems (spec §1: fail fast at boot)."""
    errs: list[str] = []
    for key in _REQUIRED:
        if not env.get(key) or "REPLACE" in env.get(key, ""):
            errs.append(f"{key}: missing or placeholder")

    for key in _FORBIDDEN_TRUTHY:
        if env.get(key, "").lower() in ("1", "true", "yes", "on"):
            errs.append(f"{key}: webhook signature validation cannot be disabled (S2)")

    region = env.get("DEFAULT_REGION", "US")

    def phone(key: str) -> str:
        try:
            return normalize(env.get(key, ""), region)
        except ValueError as exc:
            errs.append(f"{key}: {exc}")
            return ""

    owner_phone = phone("OWNER_PHONE")
    twilio_number = phone("TWILIO_NUMBER")
    whitelist: list[str] = []
    for item in filter(None, (s.strip() for s in env.get("WHITELIST_PHONES", "").split(","))):
        try:
            whitelist.append(normalize(item, region))
        except ValueError as exc:
            errs.append(f"WHITELIST_PHONES[{item}]: {exc}")

    chat_id_raw = env.get("TELEGRAM_OWNER_CHAT_ID", "")
    chat_id = 0
    if not re.fullmatch(r"-?\d+", chat_id_raw or ""):
        errs.append("TELEGRAM_OWNER_CHAT_ID: must be numeric")
    else:
        chat_id = int(chat_id_raw)

    # Optional DTMF second factor: if set, must be 4-8 digits. Never the sole
    # gate; never logged (S3).
    dtmf = env.get("DTMF_PIN", "")
    if dtmf and not re.fullmatch(r"\d{4,8}", dtmf):
        errs.append("DTMF_PIN: if set, must be 4-8 digits")

    tz = env.get("OWNER_TIMEZONE", "")
    try:
        ZoneInfo(tz)
    except Exception:
        errs.append(f"OWNER_TIMEZONE: unknown timezone ({tz!r})")

    qs = _int(env, "QUIET_HOURS_START", 21, errs, 0, 23)
    qe = _int(env, "QUIET_HOURS_END", 9, errs, 0, 23)
    cfg = Config(
        anthropic_api_key=env.get("ANTHROPIC_API_KEY", ""),
        telegram_bot_token=env.get("TELEGRAM_BOT_TOKEN", ""),
        telegram_owner_chat_id=chat_id,
        twilio_account_sid=env.get("TWILIO_ACCOUNT_SID", ""),
        twilio_auth_token=env.get("TWILIO_AUTH_TOKEN", ""),
        twilio_number=twilio_number,
        owner_name=env.get("OWNER_NAME", ""),
        owner_phone=owner_phone,
        whitelist_phones=tuple(whitelist),
        public_domain=env.get("PUBLIC_DOMAIN", ""),
        owner_timezone=tz,
        brain_base_url=env.get("BRAIN_BASE_URL", ""),
        brain_model=env.get("BRAIN_MODEL", ""),
        quiet_hours_start=qs,
        quiet_hours_end=qe,
        max_call_minutes=_int(env, "MAX_CALL_MINUTES", 10, errs, 1, 120),
        daily_max_outbound_calls=_int(env, "DAILY_MAX_OUTBOUND_CALLS", 15, errs, 1),
        daily_max_sms=_int(env, "DAILY_MAX_SMS", 30, errs, 1),
        escalation_wait_minutes=_int(env, "ESCALATION_WAIT_MINUTES", 5, errs, 1, 240),
        approval_timeout_minutes=_int(env, "APPROVAL_TIMEOUT_MINUTES", 5, errs, 1, 60),
        sms_enabled=env.get("SMS_ENABLED", "false").lower() == "true",
        dtmf_pin=dtmf,
        max_concurrent_calls=_int(env, "MAX_CONCURRENT_CALLS", 2, errs, 1, 50),
        inbound_per_number_cooldown_seconds=_int(env, "INBOUND_PER_NUMBER_COOLDOWN_SECONDS", 60, errs, 0, 3600),
        daily_inbound_minutes=_int(env, "DAILY_INBOUND_MINUTES", 120, errs, 1, 10000),
        brain_response_timeout_seconds=_int(env, "BRAIN_RESPONSE_TIMEOUT_SECONDS", 12, errs, 3, 120),
        relay_nonce_ttl_seconds=_int(env, "RELAY_NONCE_TTL_SECONDS", 120, errs, 10, 600),
        daily_max_spend_usd=_float(env, "DAILY_MAX_SPEND_USD", 5.0, errs, 0.0, 1000.0),
        transcript_retention_days=_int(env, "TRANSCRIPT_RETENTION_DAYS", 90, errs, 0, 3650),
        dry_run=env.get("DRY_RUN", "false").lower() == "true",
        persona_lang=env.get("PERSONA_LANG", "en"),
        tts_provider=env.get("TTS_PROVIDER", ""),
        tts_voice=env.get("TTS_VOICE", ""),
        default_region=region,
        blocked_extra=tuple(filter(None, (s.strip() for s in env.get("BLOCKED_PREFIXES", env.get("BLOCKED_NUMBERS", "")).split(",")))),
    )
    if errs:
        raise ConfigError("Invalid configuration:\n  - " + "\n  - ".join(errs))
    return cfg
