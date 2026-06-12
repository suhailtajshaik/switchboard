"""SQLite store (spec §8): schema constraints, counters incl. fractional
spend buckets, consent registry, escalation persistence, WAL mode (spec §1)."""
from __future__ import annotations

import sqlite3

import pytest

from core.store import Store


@pytest.fixture
def store() -> Store:
    return Store()  # :memory:


def test_incr_and_counter(store: Store) -> None:
    assert store.counter("calls_out") == 0.0
    assert store.incr("calls_out") == 1
    assert store.incr("calls_out") == 2
    assert store.counter("calls_out") == 2


def test_add_accumulates_fractional_spend(store: Store) -> None:
    assert store.add("spend_usd_llm", 0.37) == pytest.approx(0.37)
    assert store.add("spend_usd_llm", 0.13) == pytest.approx(0.50)


def test_counters_are_per_day(store: Store) -> None:
    store.incr("calls_out", day="2026-06-11")
    store.incr("calls_out", day="2026-06-12")
    assert store.counter("calls_out", day="2026-06-11") == 1
    assert store.counter("calls_out", day="2026-06-12") == 1


def test_call_sid_unique(store: Store) -> None:
    store.db.execute("INSERT INTO calls(sid) VALUES('CA1')")
    with pytest.raises(sqlite3.IntegrityError):
        store.db.execute("INSERT INTO calls(sid) VALUES('CA1')")


def test_contact_roundtrip_and_unique_phone(store: Store) -> None:
    store.add_contact("Tony", "+15551234567", relationship="pizzeria",
                      consented=True, notes="pickup orders")
    row = store.contact_by_phone("+15551234567")
    assert row is not None
    assert row["name"] == "Tony"
    assert row["consented_to_ai_calls"] == 1
    assert store.contact_by_phone("+15559999999") is None
    with pytest.raises(sqlite3.IntegrityError):
        store.add_contact("Tony again", "+15551234567")


def test_escalation_persistence_roundtrip(store: Store) -> None:
    rid = store.add_reminder("2026-06-13T08:00:00", "wake up", "high")
    assert store.load_escalation(rid) is None
    store.save_escalation(rid, {"state": "RETRY_WAIT", "call_attempts": 2})
    loaded = store.load_escalation(rid)
    assert loaded == {"state": "RETRY_WAIT", "call_attempts": 2}


def test_file_database_uses_wal(tmp_path) -> None:
    store = Store(tmp_path / "switchboard.db")
    mode = store.db.execute("PRAGMA journal_mode").fetchone()[0]
    assert mode == "wal"
