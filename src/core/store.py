"""SQLite persistence (spec §8). Stdlib sqlite3; one writer process."""
from __future__ import annotations

import json
import sqlite3
from datetime import date
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS contacts(
  id INTEGER PRIMARY KEY, name TEXT NOT NULL, phone TEXT UNIQUE NOT NULL,
  relationship TEXT, consented_to_ai_calls INTEGER NOT NULL DEFAULT 0,
  notes TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS sessions(
  id TEXT PRIMARY KEY, channel TEXT, peer TEXT, role TEXT, persona TEXT,
  state TEXT, updated_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS messages(
  id INTEGER PRIMARY KEY, session_id TEXT, direction TEXT, content TEXT,
  ts TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS calls(
  id INTEGER PRIMARY KEY, sid TEXT UNIQUE, direction TEXT, peer TEXT,
  answered_by TEXT, started_at TEXT, ended_at TEXT, outcome TEXT,
  transcript TEXT);
CREATE TABLE IF NOT EXISTS reminders(
  id INTEGER PRIMARY KEY, when_ts TEXT NOT NULL, text TEXT NOT NULL,
  urgency TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'PENDING',
  attempts INTEGER NOT NULL DEFAULT 0, escalation_json TEXT);
CREATE TABLE IF NOT EXISTS counters(
  day TEXT NOT NULL, name TEXT NOT NULL, value REAL NOT NULL DEFAULT 0,
  PRIMARY KEY(day, name));
"""


class Store:
    def __init__(self, path: str | Path = ":memory:") -> None:
        self.db = sqlite3.connect(str(path))
        self.db.row_factory = sqlite3.Row
        self.db.executescript(_SCHEMA)

    # -- counters (S5, operations §2) ----------------------------------------
    def counter(self, name: str, day: str | None = None) -> float:
        day = day or date.today().isoformat()
        row = self.db.execute(
            "SELECT value FROM counters WHERE day=? AND name=?", (day, name)
        ).fetchone()
        return row["value"] if row else 0.0

    def incr(self, name: str, day: str | None = None) -> float:
        day = day or date.today().isoformat()
        self.db.execute(
            "INSERT INTO counters(day,name,value) VALUES(?,?,1) "
            "ON CONFLICT(day,name) DO UPDATE SET value=value+1", (day, name))
        self.db.commit()
        return self.counter(name, day)

    def add(self, name: str, amount: float, day: str | None = None) -> float:
        """Accumulate a fractional bucket (e.g. spend_usd_llm)."""
        day = day or date.today().isoformat()
        self.db.execute(
            "INSERT INTO counters(day,name,value) VALUES(?,?,?) "
            "ON CONFLICT(day,name) DO UPDATE SET value=value+excluded.value",
            (day, name, amount))
        self.db.commit()
        return self.counter(name, day)

    # -- contacts (consent registry) ------------------------------------------
    def add_contact(self, name: str, phone: str, relationship: str = "",
                    consented: bool = False, notes: str = "") -> int:
        cur = self.db.execute(
            "INSERT INTO contacts(name,phone,relationship,consented_to_ai_calls,notes) "
            "VALUES(?,?,?,?,?)", (name, phone, relationship, int(consented), notes))
        self.db.commit()
        return int(cur.lastrowid)

    def contact_by_phone(self, phone: str) -> sqlite3.Row | None:
        return self.db.execute(
            "SELECT * FROM contacts WHERE phone=?", (phone,)).fetchone()

    # -- reminders / escalation persistence ------------------------------------
    def add_reminder(self, when_ts: str, text: str, urgency: str) -> int:
        cur = self.db.execute(
            "INSERT INTO reminders(when_ts,text,urgency) VALUES(?,?,?)",
            (when_ts, text, urgency))
        self.db.commit()
        return int(cur.lastrowid)

    def save_escalation(self, reminder_id: int, esc_dict: dict) -> None:
        self.db.execute(
            "UPDATE reminders SET escalation_json=?, state=?, attempts=? WHERE id=?",
            (json.dumps(esc_dict), esc_dict["state"], esc_dict["call_attempts"],
             reminder_id))
        self.db.commit()

    def load_escalation(self, reminder_id: int) -> dict | None:
        row = self.db.execute(
            "SELECT escalation_json FROM reminders WHERE id=?", (reminder_id,)
        ).fetchone()
        return json.loads(row["escalation_json"]) if row and row["escalation_json"] else None
