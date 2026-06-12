"""Reminder escalation state machine (spec §6).

Pure FSM: callers provide events; we return the actions to perform
("notify", "sms", "call") and the next timer to arm. Serializable so
schedules survive restarts (restart-recovery conformance test).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Urgency(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"


class EscState(str, Enum):
    PENDING = "PENDING"
    NOTIFIED = "NOTIFIED"
    WAITING = "WAITING"
    CALLING = "CALLING"
    RETRY_WAIT = "RETRY_WAIT"
    ACKED = "ACKED"
    ABANDONED = "ABANDONED"


MAX_RETRIES = 4          # initial call + 4 retries (spec §6)
RETRY_MINUTES = 5


@dataclass
class Escalation:
    reminder_id: int
    urgency: Urgency
    wait_minutes: int = 5
    sms_enabled: bool = False
    state: EscState = EscState.PENDING
    call_attempts: int = 0
    history: list[str] = field(default_factory=list)

    # -- events ------------------------------------------------------------
    def on_fire(self) -> tuple[list[str], int | None]:
        """Reminder fired. Returns (actions, next_timer_minutes|None)."""
        self._require(EscState.PENDING)
        if self.urgency is Urgency.LOW:
            self._go(EscState.NOTIFIED)
            return ["notify"], None
        if self.urgency is Urgency.NORMAL:
            self._go(EscState.WAITING)
            acts = ["notify"] + (["sms"] if self.sms_enabled else [])
            return acts, self.wait_minutes
        # HIGH: call immediately, message on every attempt
        self.call_attempts = 1
        self._go(EscState.CALLING)
        return ["call", "notify"] + (["sms"] if self.sms_enabled else []), None

    def on_timeout(self) -> tuple[list[str], int | None]:
        """Armed timer elapsed without an ack."""
        if self.state is EscState.WAITING:
            self.call_attempts = 1
            self._go(EscState.CALLING)
            return ["call"], None
        if self.state is EscState.RETRY_WAIT:
            self.call_attempts += 1
            self._go(EscState.CALLING)
            acts = ["call"]
            if self.urgency is Urgency.HIGH:
                acts += ["notify"] + (["sms"] if self.sms_enabled else [])
            return acts, None
        return [], None

    def on_call_unanswered(self) -> tuple[list[str], int | None]:
        self._require(EscState.CALLING)
        if self.call_attempts > MAX_RETRIES:   # initial + 4 retries exhausted
            self._go(EscState.ABANDONED)
            return ["notify_failed"], None
        self._go(EscState.RETRY_WAIT)
        return [], RETRY_MINUTES

    def on_ack(self) -> tuple[list[str], int | None]:
        """An ack on ANY channel cancels the chain (spec §6)."""
        if self.state in (EscState.ACKED, EscState.ABANDONED):
            return [], None
        self._go(EscState.ACKED)
        return [], None

    # -- persistence (restart recovery) -------------------------------------
    def to_dict(self) -> dict:
        return {
            "reminder_id": self.reminder_id,
            "urgency": self.urgency.value,
            "wait_minutes": self.wait_minutes,
            "sms_enabled": self.sms_enabled,
            "state": self.state.value,
            "call_attempts": self.call_attempts,
            "history": list(self.history),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Escalation":
        esc = cls(
            reminder_id=d["reminder_id"],
            urgency=Urgency(d["urgency"]),
            wait_minutes=d["wait_minutes"],
            sms_enabled=d["sms_enabled"],
        )
        esc.state = EscState(d["state"])
        esc.call_attempts = d["call_attempts"]
        esc.history = list(d.get("history", []))
        return esc

    # -- helpers -------------------------------------------------------------
    def _go(self, new: EscState) -> None:
        self.history.append(f"{self.state.value}->{new.value}")
        self.state = new

    def _require(self, expected: EscState) -> None:
        if self.state is not expected:
            raise ValueError(f"event invalid in state {self.state} (expected {expected})")
