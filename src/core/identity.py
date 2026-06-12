"""Caller-identity resolution (spec §2). Caller ID is a routing hint, not
authentication — sensitive actions over phone/SMS require out-of-band
approval on the root-of-trust channel (policy.ApprovalGate, S3)."""
from __future__ import annotations

from enum import Enum

from .config import Config
from .phones import normalize


class Role(str, Enum):
    MASTER = "MASTER"
    TRUSTED = "TRUSTED"
    STRANGER = "STRANGER"


def resolve_phone_role(raw_phone: str, cfg: Config) -> Role:
    try:
        e164 = normalize(raw_phone, cfg.default_region)
    except ValueError:
        return Role.STRANGER
    if e164 == cfg.owner_phone:
        return Role.MASTER
    if e164 in cfg.whitelist_phones:
        return Role.TRUSTED
    return Role.STRANGER


def resolve_telegram_role(chat_id: int, cfg: Config) -> Role:
    """Owner chat is the root of trust; every other chat is dropped upstream,
    but resolution stays defensive."""
    return Role.MASTER if chat_id == cfg.telegram_owner_chat_id else Role.STRANGER
