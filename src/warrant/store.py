"""SQLite persistence for missions, warrants, runs and events. One file, WAL mode, no ORM."""

from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any

from .models import Mission, Warrant, new_id, now

SCHEMA = """
CREATE TABLE IF NOT EXISTS missions (id TEXT PRIMARY KEY, body TEXT NOT NULL, created_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS warrants (
  id TEXT PRIMARY KEY, mission_id TEXT NOT NULL, status TEXT NOT NULL, body TEXT NOT NULL, created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS runs (
  id TEXT PRIMARY KEY, mission_id TEXT NOT NULL, warrant_id TEXT, setup TEXT NOT NULL, status TEXT NOT NULL,
  started_at REAL NOT NULL, finished_at REAL, result TEXT, usage TEXT, owner TEXT
);
CREATE TABLE IF NOT EXISTS events (
  seq INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL, t REAL NOT NULL, kind TEXT NOT NULL, body TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS events_run ON events(run_id, seq);
CREATE INDEX IF NOT EXISTS warrants_mission ON warrants(mission_id, created_at);
CREATE TABLE IF NOT EXISTS memory (
  id TEXT PRIMARY KEY, kind TEXT NOT NULL, key TEXT NOT NULL, text TEXT NOT NULL, created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS skills (
  name TEXT PRIMARY KEY, mission_id TEXT NOT NULL, warrant_id TEXT NOT NULL, created_at REAL NOT NULL
);
"""


class Store:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self._db.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._lock:
            self._db.execute("PRAGMA journal_mode=WAL")
            self._db.executescript(SCHEMA)

    def _q(self, sql: str, args: tuple = ()) -> list[sqlite3.Row]:
        with self._lock:
            return self._db.execute(sql, args).fetchall()

    # memory: a keyed entry replaces the earlier one with that key
    def remember(self, kind: str, text: str, key: str = "") -> dict[str, Any]:
        if key:
            self._q("DELETE FROM memory WHERE kind=? AND key=?", (kind, key))
        entry = {"id": new_id("mem"), "kind": kind, "key": key, "text": text, "created_at": now()}
        self._q("INSERT INTO memory VALUES (:id,:kind,:key,:text,:created_at)", entry)  # type: ignore[arg-type]
        return entry

    def memories(self, kind: str | None = None) -> list[dict[str, Any]]:
        if kind:
            rows = self._q("SELECT * FROM memory WHERE kind=? ORDER BY created_at", (kind,))
        else:
            rows = self._q("SELECT * FROM memory ORDER BY created_at")
        return [dict(r) for r in rows]

    def forget(self, memory_id: str) -> None:
        self._q("DELETE FROM memory WHERE id=?", (memory_id,))

    # skills: a named job with the warrant you approved for it
    def save_skill(self, name: str, mission_id: str, warrant_id: str) -> dict[str, Any]:
        self._q("INSERT OR REPLACE INTO skills VALUES (?,?,?,?)", (name, mission_id, warrant_id, now()))
        return self.skill(name)

    def skill(self, name: str) -> dict[str, Any]:
        rows = self._q("SELECT * FROM skills WHERE name=?", (name,))
        if not rows:
            raise KeyError(name)
        return dict(rows[0])

    def skills(self) -> list[dict[str, Any]]:
        return [dict(r) for r in self._q("SELECT * FROM skills ORDER BY created_at")]

    def delete_skill(self, name: str) -> None:
        self._q("DELETE FROM skills WHERE name=?", (name,))

    def close_interrupted_runs(self) -> None:
        """Runs live in this process, so any still marked running after a restart will never finish."""
        for row in self._q("SELECT id FROM runs WHERE status='running'"):
            self.finish_run(row["id"], "failed", {"error": "Stopped when the server restarted."}, {})
            self.add_event(row["id"], "done", {"status": "failed"})

    # missions
    def save_mission(self, m: Mission) -> Mission:
        self._q("INSERT OR REPLACE INTO missions VALUES (?,?,?)", (m.id, m.model_dump_json(), m.created_at))
        return m

    def mission(self, mid: str) -> Mission:
        rows = self._q("SELECT body FROM missions WHERE id=?", (mid,))
        if not rows:
            raise KeyError(mid)
        return Mission.model_validate_json(rows[0]["body"])

    def missions(self) -> list[Mission]:
        return [
            Mission.model_validate_json(r["body"]) for r in self._q("SELECT body FROM missions ORDER BY created_at")
        ]

    # warrants
    def save_warrant(self, w: Warrant) -> Warrant:
        self._q(
            "INSERT OR REPLACE INTO warrants VALUES (?,?,?,?,?)",
            (w.id, w.mission_id, w.status, w.model_dump_json(), w.created_at),
        )
        return w

    def warrant(self, wid: str) -> Warrant:
        rows = self._q("SELECT body FROM warrants WHERE id=?", (wid,))
        if not rows:
            raise KeyError(wid)
        return Warrant.model_validate_json(rows[0]["body"])

    def latest_warrant(self, mission_id: str) -> Warrant | None:
        rows = self._q("SELECT body FROM warrants WHERE mission_id=? ORDER BY created_at DESC LIMIT 1", (mission_id,))
        return Warrant.model_validate_json(rows[0]["body"]) if rows else None

    # runs
    def start_run(self, mission_id: str, warrant_id: str | None, setup: str, owner: str = "owner") -> str:
        rid = new_id("run")
        self._q(
            "INSERT INTO runs (id, mission_id, warrant_id, setup, status, started_at, owner) VALUES (?,?,?,?,?,?,?)",
            (rid, mission_id, warrant_id, setup, "running", now(), owner),
        )
        return rid

    def finish_run(self, rid: str, status: str, result: dict[str, Any], usage: dict[str, Any]) -> None:
        self._q(
            "UPDATE runs SET status=?, finished_at=?, result=?, usage=? WHERE id=?",
            (status, now(), json.dumps(result), json.dumps(usage), rid),
        )

    def run(self, rid: str) -> dict[str, Any]:
        rows = self._q("SELECT * FROM runs WHERE id=?", (rid,))
        if not rows:
            raise KeyError(rid)
        return self._run_row(rows[0])

    def runs(self, limit: int = 50, mission_id: str | None = None) -> list[dict[str, Any]]:
        if mission_id:
            rows = self._q(
                "SELECT * FROM runs WHERE mission_id=? ORDER BY started_at DESC LIMIT ?", (mission_id, limit)
            )
        else:
            rows = self._q("SELECT * FROM runs ORDER BY started_at DESC LIMIT ?", (limit,))
        return [self._run_row(r) for r in rows]

    def count_since(self, table: str, since: float) -> int:
        column = {"runs": "started_at", "warrants": "created_at"}[table]
        return int(self._q(f"SELECT COUNT(*) AS n FROM {table} WHERE {column}>=?", (since,))[0]["n"])

    def spend_since(self, since: float, owner: str | None = None) -> float:
        sql = "SELECT usage FROM runs WHERE started_at>=? AND usage IS NOT NULL"
        args: tuple = (since,)
        if owner:
            sql += " AND owner=?"
            args += (owner,)
        total = 0.0
        for r in self._q(sql, args):
            total += (json.loads(r["usage"]) or {}).get("cost_usd") or 0.0
        return total

    @staticmethod
    def _run_row(r: sqlite3.Row) -> dict[str, Any]:
        d = dict(r)
        d["result"] = json.loads(d["result"]) if d["result"] else None
        d["usage"] = json.loads(d["usage"]) if d["usage"] else None
        return d

    # events
    def add_event(self, run_id: str, kind: str, body: dict[str, Any]) -> int:
        with self._lock:
            cur = self._db.execute(
                "INSERT INTO events (run_id, t, kind, body) VALUES (?,?,?,?)", (run_id, now(), kind, json.dumps(body))
            )
            return int(cur.lastrowid or 0)

    def events(self, run_id: str, after: int = 0) -> list[dict[str, Any]]:
        rows = self._q("SELECT * FROM events WHERE run_id=? AND seq>? ORDER BY seq", (run_id, after))
        return [{"seq": r["seq"], "t": r["t"], "kind": r["kind"], **json.loads(r["body"])} for r in rows]
