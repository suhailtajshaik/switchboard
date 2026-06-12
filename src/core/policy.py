"""Policy engine — the only path to side-effecting tools (spec §2, §3, §5, v0.2).

Pure decision logic: time, counters and approval state are injected so
everything is testable. The model is never the security boundary.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

from .config import Config
from .identity import Role
from .phones import digits_only, normalize

# Emergency / crisis short codes (S4): never auto-dialed; a detected emergency
# is escalated to the owner instead. Extend via BLOCKED_PREFIXES config.
EMERGENCY_SHORT_CODES = {"911", "112", "999", "000", "110", "119", "988"}
PREMIUM_PREFIXES = ("+1900", "+44090", "+44091", "+44098")


class Deny(str, Enum):
    EMERGENCY_NUMBER = "emergency_number"
    PREMIUM_NUMBER = "premium_number"
    QUIET_HOURS = "quiet_hours"
    DAILY_CAP = "daily_cap"
    NO_CONSENT = "no_consent"
    ROLE_FORBIDDEN = "role_forbidden"
    APPROVAL_REQUIRED = "approval_required"            # S3 (was pin_required)
    UNKNOWN_NUMBER_UNCONFIRMED = "unknown_number_unconfirmed"  # S3
    BLOCKED_NUMBER = "blocked_number"
    DAILY_SPEND_BUDGET = "daily_spend_budget"          # operations §2
    HALTED = "halted"                                  # S14 kill switch


@dataclass(frozen=True)
class Decision:
    allowed: bool
    reason: Deny | None = None

    def __bool__(self) -> bool:  # pragma: no cover - convenience
        return self.allowed


ALLOW = Decision(True)


# --- Tool capability table (spec §3, S1) -----------------------------------
_STRANGER_TOOLS = frozenset({"take_message"})
_TRUSTED_DENIED = frozenset({"add_contact", "config_mutation"})

# Actions that are SENSITIVE when requested over an untrusted channel
# (phone/SMS): they require out-of-band approval on the root-of-trust channel
# before executing (spec §2.1, S3).
SENSITIVE_TOOLS = frozenset({
    "config_mutation", "whitelist_mutation", "add_contact",
    "disclose_owner_private_data",
    # make_call is sensitive only when the target is not a known contact;
    # handled in check_outbound_call, not here.
})


def tool_allowed(role: Role, tool: str) -> Decision:
    """S1: STRANGER reaches take_message and nothing else, ever."""
    if role is Role.STRANGER:
        return ALLOW if tool in _STRANGER_TOOLS else Decision(False, Deny.ROLE_FORBIDDEN)
    if role is Role.TRUSTED and tool in _TRUSTED_DENIED:
        return Decision(False, Deny.ROLE_FORBIDDEN)
    return ALLOW


def requires_approval(tool: str, *, channel: str, approved: bool) -> Decision:
    """Sensitive action over phone/SMS must be approved out-of-band (S3).
    `channel` is the request channel ('telegram' is root of trust and exempt;
    'voice'/'sms' are untrusted). Telegram-owner requests never need approval.
    """
    if channel == "telegram":
        return ALLOW
    if tool in SENSITIVE_TOOLS and not approved:
        return Decision(False, Deny.APPROVAL_REQUIRED)
    return ALLOW


# --- Quiet hours (spec §5) -------------------------------------------------
def in_quiet_hours(now_local: datetime, start: int, end: int) -> bool:
    """start == end disables quiet hours; window may wrap midnight."""
    if start == end:
        return False
    h = now_local.hour
    if start < end:
        return start <= h < end
    return h >= start or h < end


# --- Number safety (S4) ----------------------------------------------------
def number_block_reason(target: str, cfg: Config) -> Deny | None:
    digits = digits_only(target)
    if digits in EMERGENCY_SHORT_CODES:
        return Deny.EMERGENCY_NUMBER
    try:
        e164 = normalize(target, cfg.default_region)
    except ValueError:
        return Deny.BLOCKED_NUMBER
    if any(e164.startswith(p) for p in PREMIUM_PREFIXES):
        return Deny.PREMIUM_NUMBER
    if any(e164.startswith(p) for p in cfg.blocked_extra):
        return Deny.BLOCKED_NUMBER
    if e164[1:] in EMERGENCY_SHORT_CODES:
        return Deny.EMERGENCY_NUMBER
    return None


# --- Outbound-call pre-flight (spec §5) ------------------------------------
def check_outbound_call(
    *,
    target: str,
    cfg: Config,
    role: Role,
    channel: str,
    now_local: datetime,
    calls_made_today: int,
    contact_is_person: bool,
    contact_consented: bool,
    is_known_contact: bool,
    approved: bool = False,
) -> Decision:
    gate = tool_allowed(role, "make_call")
    if not gate.allowed:
        return gate
    blocked = number_block_reason(target, cfg)
    if blocked:
        return Decision(False, blocked)
    target_e164 = normalize(target, cfg.default_region)
    is_owner_target = target_e164 == cfg.owner_phone
    # Calling a number that is not a saved contact is sensitive over untrusted
    # channels → needs out-of-band approval first (S3).
    if channel != "telegram" and not is_known_contact and not is_owner_target and not approved:
        return Decision(False, Deny.UNKNOWN_NUMBER_UNCONFIRMED)
    if not is_owner_target and in_quiet_hours(
        now_local, cfg.quiet_hours_start, cfg.quiet_hours_end
    ):
        return Decision(False, Deny.QUIET_HOURS)
    if calls_made_today >= cfg.daily_max_outbound_calls:
        return Decision(False, Deny.DAILY_CAP)
    if contact_is_person and not contact_consented and not is_owner_target:
        return Decision(False, Deny.NO_CONSENT)
    return ALLOW


# --- Daily caps with warn threshold (S5) -----------------------------------
@dataclass
class CapStatus:
    allowed: bool
    warn: bool          # crossed >=80% on this increment — notify owner once
    used: int
    cap: int


def cap_check(used_before: int, cap: int) -> CapStatus:
    used_after = used_before + 1
    if used_after > cap:
        return CapStatus(False, False, used_before, cap)
    warn = used_after >= int(cap * 0.8) and used_before < int(cap * 0.8)
    return CapStatus(True, warn, used_after, cap)


# --- Inbound rate limiting / financial-DoS protection (S11) -----------------
def inbound_allowed(
    *,
    now: datetime,
    last_seen: datetime | None,
    active_calls: int,
    inbound_minutes_today: float,
    cfg: Config,
) -> Decision:
    if active_calls >= cfg.max_concurrent_calls:
        return Decision(False, Deny.DAILY_CAP)
    if inbound_minutes_today >= cfg.daily_inbound_minutes:
        return Decision(False, Deny.DAILY_CAP)
    if last_seen is not None and (now - last_seen) < timedelta(
        seconds=cfg.inbound_per_number_cooldown_seconds
    ):
        return Decision(False, Deny.DAILY_CAP)
    return ALLOW


# --- Out-of-band approval store (S3) ---------------------------------------
# Replaces the v0.1 spoken-PIN gate. A sensitive action requested over an
# untrusted channel is parked here, an approval prompt is sent to the owner's
# root-of-trust channel, and the action runs only when the owner approves
# before expiry. No secret is ever spoken or transcribed.
class ApprovalState(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    EXPIRED = "expired"


@dataclass
class PendingApproval:
    approval_id: str
    action: str            # opaque tool/action identifier
    summary: str           # human-readable, shown to the owner
    requested_at: datetime
    state: ApprovalState = ApprovalState.PENDING


class ApprovalGate:
    """Pure, testable approval bookkeeping. The Telegram adapter sends the
    prompt and feeds back approve/deny; expiry is evaluated against `now`."""

    def __init__(self, timeout_minutes: int) -> None:
        self._timeout = timedelta(minutes=timeout_minutes)
        self._pending: dict[str, PendingApproval] = {}

    def request(self, approval_id: str, action: str, summary: str,
                now: datetime) -> PendingApproval:
        pa = PendingApproval(approval_id, action, summary, now)
        self._pending[approval_id] = pa
        return pa

    def _expire_if_due(self, pa: PendingApproval, now: datetime) -> None:
        if pa.state is ApprovalState.PENDING and now - pa.requested_at >= self._timeout:
            pa.state = ApprovalState.EXPIRED

    def resolve(self, approval_id: str, approve: bool, now: datetime) -> ApprovalState:
        pa = self._pending.get(approval_id)
        if pa is None:
            return ApprovalState.EXPIRED
        self._expire_if_due(pa, now)
        if pa.state is ApprovalState.PENDING:
            pa.state = ApprovalState.APPROVED if approve else ApprovalState.DENIED
        return pa.state

    def is_approved(self, approval_id: str, now: datetime) -> bool:
        pa = self._pending.get(approval_id)
        if pa is None:
            return False
        self._expire_if_due(pa, now)
        return pa.state is ApprovalState.APPROVED


# --- Spend budget (operations §2; soft, dollar-denominated) -----------------
@dataclass
class SpendStatus:
    allowed: bool
    warn: bool            # crossed >=80% on this increment — notify owner once
    spent_after: float
    budget: float


def spend_check(spent_usd_today: float, est_cost_usd: float, budget_usd: float,
                *, urgent: bool = False, owner_override: bool = False) -> SpendStatus:
    """Soft daily dollar budget. Urgent escalations to the owner and explicit
    owner overrides are exempt from the block (never from the accounting)."""
    after = spent_usd_today + max(est_cost_usd, 0.0)
    if budget_usd <= 0:                      # 0 disables the budget
        return SpendStatus(True, False, after, budget_usd)
    blocked = after > budget_usd and not (urgent or owner_override)
    warn = after >= budget_usd * 0.8 and spent_usd_today < budget_usd * 0.8
    return SpendStatus(not blocked, warn, after, budget_usd)


# --- Break-glass kill switch (S14) ------------------------------------------
class KillSwitch:
    """Halts all outbound activity. Toggled ONLY from the root-of-trust
    channel (caller enforces by passing channel); state is persisted by the
    store (`runtime_flags`) and rehydrated at boot via `restore()`."""

    def __init__(self) -> None:
        self._engaged = False
        self._reason = ""
        self._since: datetime | None = None

    # -- state --
    @property
    def engaged(self) -> bool:
        return self._engaged

    def status_line(self) -> str:
        if not self._engaged:
            return "active"
        return f"⛔ HALTED ({self._reason or 'no reason'}, since {self._since:%Y-%m-%d %H:%M})"

    # -- transitions (only the owner control channel may call these) --
    def halt(self, reason: str, now: datetime, *, channel: str) -> bool:
        if channel != "telegram":
            return False
        self._engaged, self._reason, self._since = True, reason, now
        return True

    def resume(self, *, channel: str) -> bool:
        if channel != "telegram":
            return False
        self._engaged, self._reason, self._since = False, "", None
        return True

    def restore(self, engaged: bool, reason: str, since: datetime | None) -> None:
        self._engaged, self._reason, self._since = engaged, reason, since

    # -- gate --
    def check_outbound(self) -> Decision:
        return Decision(False, Deny.HALTED) if self._engaged else ALLOW


# --- Outbound idempotency key (S13) ------------------------------------------
def make_action_key(tool: str, target: str, task_id: str) -> str:
    """Deterministic key for an outbound side effect: same task + tool +
    target collapses to one execution (store dedupes via processed_actions)."""
    import hashlib
    raw = f"{tool}|{target}|{task_id}".encode()
    return hashlib.sha256(raw).hexdigest()[:32]
