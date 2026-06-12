"""Escalation state machine (spec §6; §11 unit: transitions incl. restart
recovery). notify → wait → call → retry(≤4) → acked/abandoned."""
from __future__ import annotations

import pytest

from core.escalation import EscState, Escalation, Urgency


def test_low_urgency_notifies_only() -> None:
    esc = Escalation(1, Urgency.LOW)
    actions, timer = esc.on_fire()
    assert actions == ["notify"] and timer is None
    assert esc.state is EscState.NOTIFIED


def test_normal_notifies_then_waits() -> None:
    esc = Escalation(1, Urgency.NORMAL, wait_minutes=5)
    actions, timer = esc.on_fire()
    assert actions == ["notify"] and timer == 5
    assert esc.state is EscState.WAITING


def test_normal_with_sms_enabled() -> None:
    esc = Escalation(1, Urgency.NORMAL, sms_enabled=True)
    actions, _ = esc.on_fire()
    assert actions == ["notify", "sms"]


def test_high_calls_immediately() -> None:
    esc = Escalation(1, Urgency.HIGH, sms_enabled=True)
    actions, timer = esc.on_fire()
    assert actions == ["call", "notify", "sms"] and timer is None
    assert esc.state is EscState.CALLING and esc.call_attempts == 1


def test_ack_on_any_channel_cancels_chain() -> None:
    esc = Escalation(1, Urgency.NORMAL)
    esc.on_fire()
    esc.on_ack()
    assert esc.state is EscState.ACKED
    assert esc.on_timeout() == ([], None)      # late timer is a no-op
    assert esc.on_ack() == ([], None)          # ack is idempotent


def test_full_retry_chain_then_abandoned() -> None:
    esc = Escalation(1, Urgency.NORMAL)
    esc.on_fire()                              # WAITING
    dials = 0
    actions, _ = esc.on_timeout()              # first call
    while "call" in actions:
        dials += 1
        _, timer = esc.on_call_unanswered()
        if esc.state is EscState.ABANDONED:
            break
        assert timer == 5                      # retry interval
        actions, _ = esc.on_timeout()
    assert esc.state is EscState.ABANDONED
    assert dials == 5                          # initial + 4 retries (spec §6)


def test_restart_recovery_mid_chain() -> None:
    esc = Escalation(7, Urgency.NORMAL)
    esc.on_fire()
    esc.on_timeout()
    esc.on_call_unanswered()                   # RETRY_WAIT, attempts=1
    snapshot = esc.to_dict()

    revived = Escalation.from_dict(snapshot)   # process restart
    assert revived.state is EscState.RETRY_WAIT
    assert revived.call_attempts == 1
    assert revived.history == esc.history

    actions, _ = revived.on_timeout()
    assert "call" in actions and revived.call_attempts == 2

    revived.on_ack()
    assert revived.state is EscState.ACKED


def test_invalid_event_for_state_raises() -> None:
    esc = Escalation(1, Urgency.LOW)
    esc.on_fire()
    with pytest.raises(ValueError):
        esc.on_fire()                          # fire requires PENDING
    with pytest.raises(ValueError):
        esc.on_call_unanswered()               # requires CALLING
