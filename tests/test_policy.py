"""Policy engine conformance (spec §2, §3, §5; §11 unit: S1 corpus,
sensitive-action gate, quiet hours, caps 79/80/100%, S11 inbound limits,
spend edges, S13 idempotency keys, S14 kill switch)."""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from core.identity import Role
from core.policy import (
    ApprovalGate,
    ApprovalState,
    Deny,
    KillSwitch,
    cap_check,
    check_outbound_call,
    in_quiet_hours,
    inbound_allowed,
    make_action_key,
    number_block_reason,
    requires_approval,
    spend_check,
    tool_allowed,
)

NOON = datetime(2026, 6, 12, 12, 0)
NIGHT = datetime(2026, 6, 12, 22, 30)

ALL_TOOLS = [
    "make_call", "send_sms", "notify_owner", "add_reminder",
    "list_reminders", "cancel_reminder", "add_contact", "lookup_contact",
    "web_search", "web_fetch", "config_mutation", "whitelist_mutation",
    "disclose_owner_private_data", "shell", "exec", "file_write",
]


# --- S1: stranger isolation --------------------------------------------------
@pytest.mark.parametrize("tool", ALL_TOOLS)
def test_s1_stranger_denied_every_tool(tool: str) -> None:
    decision = tool_allowed(Role.STRANGER, tool)
    assert not decision.allowed
    assert decision.reason is Deny.ROLE_FORBIDDEN


def test_s1_stranger_only_take_message() -> None:
    assert tool_allowed(Role.STRANGER, "take_message").allowed


def test_trusted_denied_contact_and_config_mutation() -> None:
    assert not tool_allowed(Role.TRUSTED, "add_contact").allowed
    assert not tool_allowed(Role.TRUSTED, "config_mutation").allowed
    assert tool_allowed(Role.TRUSTED, "make_call").allowed


def test_master_allowed_at_capability_layer() -> None:
    for tool in ALL_TOOLS:
        assert tool_allowed(Role.MASTER, tool).allowed


# --- S3: sensitive-action gate (out-of-band approval) ------------------------
@pytest.mark.parametrize("channel", ["voice", "sms"])
def test_sensitive_over_untrusted_channel_needs_approval(channel: str) -> None:
    decision = requires_approval("add_contact", channel=channel, approved=False)
    assert not decision.allowed
    assert decision.reason is Deny.APPROVAL_REQUIRED


def test_sensitive_over_telegram_exempt() -> None:
    assert requires_approval("add_contact", channel="telegram", approved=False).allowed


def test_sensitive_approved_passes() -> None:
    assert requires_approval("add_contact", channel="voice", approved=True).allowed


def test_non_sensitive_tool_needs_no_approval() -> None:
    assert requires_approval("add_reminder", channel="voice", approved=False).allowed


def test_approval_gate_flow_and_expiry() -> None:
    gate = ApprovalGate(timeout_minutes=5)
    t0 = NOON
    gate.request("a1", "add_contact", "Add +1555…?", t0)
    assert not gate.is_approved("a1", t0)
    assert gate.resolve("a1", True, t0 + timedelta(minutes=1)) is ApprovalState.APPROVED
    assert gate.is_approved("a1", t0 + timedelta(minutes=2))

    gate.request("a2", "add_contact", "…", t0)
    assert gate.resolve("a2", True, t0 + timedelta(minutes=5)) is ApprovalState.EXPIRED
    assert not gate.is_approved("a2", t0 + timedelta(minutes=6))

    gate.request("a3", "add_contact", "…", t0)
    assert gate.resolve("a3", False, t0 + timedelta(minutes=1)) is ApprovalState.DENIED
    assert gate.resolve("missing", True, t0) is ApprovalState.EXPIRED


# --- Quiet hours (wraps midnight; start == end disables) ----------------------
@pytest.mark.parametrize(
    ("hour", "quiet"),
    [(20, False), (21, True), (23, True), (0, True), (8, True), (9, False), (12, False)],
)
def test_quiet_hours_wrapping_midnight(hour: int, quiet: bool) -> None:
    now = datetime(2026, 6, 12, hour, 0)
    assert in_quiet_hours(now, 21, 9) is quiet


def test_quiet_hours_non_wrapping_window() -> None:
    assert in_quiet_hours(datetime(2026, 6, 12, 10, 0), 9, 17)
    assert not in_quiet_hours(datetime(2026, 6, 12, 18, 0), 9, 17)


def test_quiet_hours_disabled_when_start_equals_end() -> None:
    for hour in range(24):
        assert not in_quiet_hours(datetime(2026, 6, 12, hour, 0), 9, 9)


# --- S4: emergency / premium / blocked numbers --------------------------------
def test_emergency_short_codes_blocked(cfg) -> None:
    for number in ("911", "112", "999", "988"):
        assert number_block_reason(number, cfg) is Deny.EMERGENCY_NUMBER


def test_premium_prefix_blocked(cfg) -> None:
    assert number_block_reason("+19005551234", cfg) is Deny.PREMIUM_NUMBER


def test_unparseable_number_blocked(cfg) -> None:
    assert number_block_reason("notaphone", cfg) is Deny.BLOCKED_NUMBER


def test_blocked_extra_prefix(base_env) -> None:
    from core.config import from_env

    base_env["BLOCKED_PREFIXES"] = "+1809"
    cfg = from_env(base_env)
    assert number_block_reason("+18095551234", cfg) is Deny.BLOCKED_NUMBER


def test_normal_number_not_blocked(cfg) -> None:
    assert number_block_reason("+15551234567", cfg) is None


# --- §5: outbound-call pre-flight ---------------------------------------------
def preflight(cfg, **overrides):
    kwargs = dict(
        target="+15551234567",
        cfg=cfg,
        role=Role.MASTER,
        channel="telegram",
        now_local=NOON,
        calls_made_today=0,
        contact_is_person=False,
        contact_consented=False,
        is_known_contact=True,
        approved=False,
    )
    kwargs.update(overrides)
    return check_outbound_call(**kwargs)


def test_preflight_happy_path(cfg) -> None:
    assert preflight(cfg).allowed


def test_preflight_stranger_role_forbidden(cfg) -> None:
    assert preflight(cfg, role=Role.STRANGER).reason is Deny.ROLE_FORBIDDEN


def test_preflight_emergency_blocked(cfg) -> None:
    assert preflight(cfg, target="911").reason is Deny.EMERGENCY_NUMBER


def test_preflight_unknown_number_needs_oob_approval(cfg) -> None:
    decision = preflight(cfg, channel="voice", is_known_contact=False)
    assert decision.reason is Deny.UNKNOWN_NUMBER_UNCONFIRMED
    assert preflight(cfg, channel="voice", is_known_contact=False, approved=True).allowed


def test_preflight_unknown_number_fine_from_telegram(cfg) -> None:
    assert preflight(cfg, channel="telegram", is_known_contact=False).allowed


def test_preflight_quiet_hours_blocks_non_owner(cfg) -> None:
    assert preflight(cfg, now_local=NIGHT).reason is Deny.QUIET_HOURS


def test_preflight_owner_exempt_from_quiet_hours(cfg) -> None:
    assert preflight(
        cfg, target=cfg.owner_phone, now_local=NIGHT, is_known_contact=False
    ).allowed


def test_preflight_daily_cap(cfg) -> None:
    assert preflight(cfg, calls_made_today=15).reason is Deny.DAILY_CAP


def test_preflight_person_without_consent(cfg) -> None:
    decision = preflight(cfg, contact_is_person=True, contact_consented=False)
    assert decision.reason is Deny.NO_CONSENT
    assert preflight(cfg, contact_is_person=True, contact_consented=True).allowed


# --- S5: cap edges (79 / 80 / 100%) -------------------------------------------
def test_cap_edges_percentages() -> None:
    assert cap_check(78, 100).allowed and not cap_check(78, 100).warn   # 79%
    status_80 = cap_check(79, 100)
    assert status_80.allowed and status_80.warn                          # 80% warn once
    assert cap_check(80, 100).allowed and not cap_check(80, 100).warn   # warned already
    assert cap_check(99, 100).allowed                                    # reaches 100%
    assert not cap_check(100, 100).allowed                               # hard stop


def test_cap_edges_default_call_cap() -> None:
    assert cap_check(11, 15).warn          # crosses 12 == 80% of 15
    assert cap_check(14, 15).allowed
    assert not cap_check(15, 15).allowed


# --- S11: inbound limits --------------------------------------------------------
def test_inbound_concurrency_cap(cfg) -> None:
    assert not inbound_allowed(
        now=NOON, last_seen=None, active_calls=2, inbound_minutes_today=0, cfg=cfg
    ).allowed


def test_inbound_daily_minutes_budget(cfg) -> None:
    assert not inbound_allowed(
        now=NOON, last_seen=None, active_calls=0, inbound_minutes_today=120, cfg=cfg
    ).allowed


def test_inbound_per_number_cooldown(cfg) -> None:
    recent = NOON - timedelta(seconds=30)
    old = NOON - timedelta(seconds=61)
    assert not inbound_allowed(
        now=NOON, last_seen=recent, active_calls=0, inbound_minutes_today=0, cfg=cfg
    ).allowed
    assert inbound_allowed(
        now=NOON, last_seen=old, active_calls=0, inbound_minutes_today=0, cfg=cfg
    ).allowed


def test_inbound_first_contact_allowed(cfg) -> None:
    assert inbound_allowed(
        now=NOON, last_seen=None, active_calls=0, inbound_minutes_today=0, cfg=cfg
    ).allowed


# --- Spend budget (operations §2): under / at / over, exemptions ---------------
def test_spend_under_at_over_budget() -> None:
    assert spend_check(0.0, 1.0, 5.0).allowed                  # under
    assert spend_check(4.0, 1.0, 5.0).allowed                  # exactly at budget
    assert not spend_check(4.5, 1.0, 5.0).allowed              # over


def test_spend_urgent_and_override_exempt() -> None:
    assert spend_check(4.5, 1.0, 5.0, urgent=True).allowed
    assert spend_check(4.5, 1.0, 5.0, owner_override=True).allowed


def test_spend_warn_crosses_80_percent_once() -> None:
    assert spend_check(3.5, 0.6, 5.0).warn          # crosses 4.0
    assert not spend_check(4.2, 0.2, 5.0).warn      # already past 80%


def test_spend_zero_budget_disables() -> None:
    assert spend_check(1000.0, 50.0, 0.0).allowed


# --- S14: break-glass kill switch ----------------------------------------------
def test_kill_switch_owner_channel_only() -> None:
    ks = KillSwitch()
    assert not ks.halt("test", NOON, channel="voice")
    assert not ks.engaged
    assert ks.halt("test", NOON, channel="telegram")
    assert ks.engaged
    assert ks.check_outbound().reason is Deny.HALTED
    assert "HALTED" in ks.status_line() and "test" in ks.status_line()
    assert not ks.resume(channel="sms")
    assert ks.engaged
    assert ks.resume(channel="telegram")
    assert ks.check_outbound().allowed
    assert ks.status_line() == "active"


def test_kill_switch_restores_after_restart() -> None:
    ks = KillSwitch()
    ks.restore(True, "incident", NOON)   # rehydrated from runtime_flags
    assert ks.engaged
    assert ks.check_outbound().reason is Deny.HALTED


# --- S13: outbound idempotency keys ----------------------------------------------
def test_action_key_deterministic_and_distinct() -> None:
    key = make_action_key("make_call", "+15551234567", "task-1")
    assert key == make_action_key("make_call", "+15551234567", "task-1")
    assert len(key) == 32
    assert key != make_action_key("send_sms", "+15551234567", "task-1")
    assert key != make_action_key("make_call", "+15559999999", "task-1")
    assert key != make_action_key("make_call", "+15551234567", "task-2")
