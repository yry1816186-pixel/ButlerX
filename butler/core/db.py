import json
import sqlite3
import threading
from typing import Any, Dict, List, Optional
from contextlib import contextmanager
from pathlib import Path

from .db_pool import get_connection_pool


class Database:
    def __init__(self, db_path: str, pool_size: int = 5) -> None:
        self.db_path = db_path
        self.lock = threading.Lock()
        self._pool = get_connection_pool(db_path, pool_size=pool_size)
        self._init_db()

    def _init_db(self) -> None:
        with self.lock:
            with self._pool.get_connection() as conn:
                conn.executescript(
                    """
                    PRAGMA journal_mode=WAL;
                    CREATE TABLE IF NOT EXISTS events (
                        event_id TEXT PRIMARY KEY,
                        ts INTEGER NOT NULL,
                        source TEXT NOT NULL,
                        type TEXT NOT NULL,
                        payload TEXT NOT NULL,
                        severity INTEGER NOT NULL,
                        correlation_id TEXT
                    );
                    CREATE TABLE IF NOT EXISTS plans (
                        plan_id TEXT PRIMARY KEY,
                        triggered_by_event_id TEXT NOT NULL,
                        actions TEXT NOT NULL,
                        policy TEXT NOT NULL,
                        reason TEXT NOT NULL,
                        created_ts INTEGER NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS results (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        plan_id TEXT NOT NULL,
                        action_type TEXT NOT NULL,
                        status TEXT NOT NULL,
                        output TEXT NOT NULL,
                        ts INTEGER NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS state (
                        key TEXT PRIMARY KEY,
                        value TEXT NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS schedules (
                        schedule_id TEXT PRIMARY KEY,
                        run_at INTEGER NOT NULL,
                        actions TEXT NOT NULL,
                        status TEXT NOT NULL,
                        created_ts INTEGER NOT NULL,
                        note TEXT
                    );
                    CREATE TABLE IF NOT EXISTS voiceprints (
                        voiceprint_id TEXT PRIMARY KEY,
                        label TEXT NOT NULL,
                        fingerprint TEXT NOT NULL,
                        created_ts INTEGER NOT NULL,
                        meta TEXT
                    );
                    CREATE TABLE IF NOT EXISTS faceprints (
                        faceprint_id TEXT PRIMARY KEY,
                        label TEXT NOT NULL,
                        embedding TEXT NOT NULL,
                        created_ts INTEGER NOT NULL,
                        meta TEXT
                    );
                    """
                )
                self._ensure_column(conn, "plans", "reason", "TEXT NOT NULL DEFAULT ''")

    def _ensure_column(self, conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
        columns = conn.execute(f"PRAGMA table_info({table})").fetchall()
        if any(row["name"] == column for row in columns):
            return
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
        conn.commit()

    @contextmanager
    def _get_connection(self):
        with self._pool.get_connection() as conn:
            yield conn

    def insert_event(self, event: Dict[str, Any]) -> None:
        with self.lock:
            with self._get_connection() as conn:
                try:
                    conn.execute(
                        """
                        INSERT INTO events (event_id, ts, source, type, payload, severity, correlation_id)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            event["event_id"],
                            event["ts"],
                            event["source"],
                            event["type"],
                            json.dumps(event.get("payload") or {}),
                            int(event.get("severity", 0)),
                            event.get("correlation_id"),
                        ),
                    )
                    conn.commit()
                except Exception as e:
                    conn.rollback()
                    raise

    def insert_plan(self, plan: Dict[str, Any]) -> None:
        with self.lock:
            with self._get_connection() as conn:
                try:
                    conn.execute(
                        """
                        INSERT INTO plans (plan_id, triggered_by_event_id, actions, policy, reason, created_ts)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            plan["plan_id"],
                            plan["triggered_by_event_id"],
                            json.dumps(plan.get("actions") or []),
                            plan["policy"],
                            plan.get("reason", ""),
                            plan["created_ts"],
                        ),
                    )
                    conn.commit()
                except Exception as e:
                    conn.rollback()
                    raise

    def insert_result(self, result: Dict[str, Any]) -> None:
        with self.lock:
            with self._get_connection() as conn:
                try:
                    conn.execute(
                        """
                        INSERT INTO results (plan_id, action_type, status, output, ts)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (
                            result["plan_id"],
                            result["action_type"],
                            result["status"],
                            json.dumps(result.get("output") or {}),
                            result["ts"],
                        ),
                    )
                    conn.commit()
                except Exception as e:
                    conn.rollback()
                    raise

    def get_recent_events(self, limit: int = 10) -> List[Dict[str, Any]]:
        with self.lock:
            with self._get_connection() as conn:
                rows = conn.execute(
                    """
                    SELECT * FROM events
                    ORDER BY ts DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
        return [self._row_to_event(row) for row in rows]

    def get_recent_plans(self, limit: int = 10) -> List[Dict[str, Any]]:
        with self.lock:
            with self._get_connection() as conn:
                rows = conn.execute(
                    """
                    SELECT * FROM plans
                    ORDER BY created_ts DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
        return [self._row_to_plan(row) for row in rows]

    def get_recent_results(self, limit: int = 10) -> List[Dict[str, Any]]:
        with self.lock:
            with self._get_connection() as conn:
                rows = conn.execute(
                    """
                    SELECT plan_id, action_type, status, output, ts
                    FROM results
                    ORDER BY ts DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
        return [self._row_to_result(row) for row in rows]

    def insert_schedule(self, schedule: Dict[str, Any]) -> None:
        with self.lock:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO schedules (schedule_id, run_at, actions, status, created_ts, note)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        schedule["schedule_id"],
                        int(schedule["run_at"]),
                        json.dumps(schedule.get("actions") or []),
                        schedule.get("status", "pending"),
                        int(schedule["created_ts"]),
                        schedule.get("note"),
                    ),
                )
                conn.commit()

    def get_due_schedules(self, now_ts: int, limit: int = 10) -> List[Dict[str, Any]]:
        with self.lock:
            with self._get_connection() as conn:
                rows = conn.execute(
                    """
                    SELECT * FROM schedules
                    WHERE status = 'pending' AND run_at <= ?
                    ORDER BY run_at ASC
                    LIMIT ?
                    """,
                    (int(now_ts), int(limit)),
                ).fetchall()
        return [self._row_to_schedule(row) for row in rows]

    def mark_schedule_done(self, schedule_id: str) -> None:
        with self.lock:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    UPDATE schedules SET status = 'done'
                    WHERE schedule_id = ?
                    """,
                    (schedule_id,),
                )
                conn.commit()

    def insert_voiceprint(self, record: Dict[str, Any]) -> None:
        with self.lock:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO voiceprints (voiceprint_id, label, fingerprint, created_ts, meta)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        record["voiceprint_id"],
                        record["label"],
                        record["fingerprint"],
                        int(record["created_ts"]),
                        json.dumps(record.get("meta") or {}),
                    ),
                )
                conn.commit()

    def insert_faceprint(self, record: Dict[str, Any]) -> None:
        with self.lock:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO faceprints (faceprint_id, label, embedding, created_ts, meta)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        record["faceprint_id"],
                        record["label"],
                        json.dumps(record.get("embedding") or []),
                        int(record["created_ts"]),
                        json.dumps(record.get("meta") or {}),
                    ),
                )
                conn.commit()

    def list_voiceprints(self) -> List[Dict[str, Any]]:
        with self.lock:
            with self._get_connection() as conn:
                rows = conn.execute(
                    """
                    SELECT voiceprint_id, label, fingerprint, created_ts, meta
                    FROM voiceprints
                    ORDER BY created_ts DESC
                    """
                ).fetchall()
        return [self._row_to_voiceprint(row) for row in rows]

    def list_faceprints(self) -> List[Dict[str, Any]]:
        with self.lock:
            with self._get_connection() as conn:
                rows = conn.execute(
                    """
                    SELECT faceprint_id, label, embedding, created_ts, meta
                    FROM faceprints
                    ORDER BY created_ts DESC
                    """
                ).fetchall()
        return [self._row_to_faceprint(row) for row in rows]

    def find_voiceprint(
        self, voiceprint_id: Optional[str] = None, label: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        if not voiceprint_id and not label:
            return None
        with self.lock:
            with self._get_connection() as conn:
                if voiceprint_id:
                    row = conn.execute(
                        """
                        SELECT voiceprint_id, label, fingerprint, created_ts, meta
                        FROM voiceprints
                        WHERE voiceprint_id = ?
                        """,
                        (voiceprint_id,),
                    ).fetchone()
                else:
                    row = conn.execute(
                        """
                        SELECT voiceprint_id, label, fingerprint, created_ts, meta
                        FROM voiceprints
                        WHERE label = ?
                        ORDER BY created_ts DESC
                        LIMIT 1
                        """,
                        (label,),
                    ).fetchone()
        if not row:
            return None
        return self._row_to_voiceprint(row)

    def find_faceprint(
        self, faceprint_id: Optional[str] = None, label: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        if not faceprint_id and not label:
            return None
        with self.lock:
            with self._get_connection() as conn:
                if faceprint_id:
                    row = conn.execute(
                        """
                        SELECT faceprint_id, label, embedding, created_ts, meta
                        FROM faceprints
                        WHERE faceprint_id = ?
                        """,
                        (faceprint_id,),
                    ).fetchone()
                else:
                    row = conn.execute(
                        """
                        SELECT faceprint_id, label, embedding, created_ts, meta
                        FROM faceprints
                        WHERE label = ?
                        ORDER BY created_ts DESC
                        LIMIT 1
                        """,
                        (label,),
                    ).fetchone()
        if not row:
            return None
        return self._row_to_faceprint(row)

    def delete_voiceprint(self, voiceprint_id: str) -> None:
        with self.lock:
            with self._get_connection() as conn:
                conn.execute(
                    "DELETE FROM voiceprints WHERE voiceprint_id = ?",
                    (voiceprint_id,),
                )
                conn.commit()

    def delete_faceprint(self, faceprint_id: str) -> None:
        with self.lock:
            with self._get_connection() as conn:
                conn.execute(
                    "DELETE FROM faceprints WHERE faceprint_id = ?",
                    (faceprint_id,),
                )
                conn.commit()

    def get_last_plan_ts(self, policy: str) -> Optional[int]:
        with self.lock:
            with self._get_connection() as conn:
                row = conn.execute(
                    """
                    SELECT created_ts FROM plans
                    WHERE policy = ?
                    ORDER BY created_ts DESC
                    LIMIT 1
                    """,
                    (policy,),
                ).fetchone()
        if not row:
            return None
        return int(row["created_ts"])

    def get_state(self, key: str, default: Any = None) -> Any:
        with self.lock:
            with self._get_connection() as conn:
                row = conn.execute(
                    "SELECT value FROM state WHERE key = ?",
                    (key,),
                ).fetchone()
        if not row:
            return default
        try:
            return json.loads(row["value"])
        except json.JSONDecodeError:
            return row["value"]

    def set_state(self, key: str, value: Any) -> None:
        payload = json.dumps(value)
        with self.lock:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO state (key, value)
                    VALUES (?, ?)
                    ON CONFLICT(key) DO UPDATE SET value = excluded.value
                    """,
                    (key, payload),
                )
                conn.commit()

    def _row_to_event(self, row: sqlite3.Row) -> Dict[str, Any]:
        return {
            "event_id": row["event_id"],
            "ts": row["ts"],
            "source": row["source"],
            "type": row["type"],
            "payload": json.loads(row["payload"]),
            "severity": row["severity"],
            "correlation_id": row["correlation_id"],
        }

    def _row_to_plan(self, row: sqlite3.Row) -> Dict[str, Any]:
        reason = ""
        if "reason" in row.keys():
            reason = row["reason"]
        return {
            "plan_id": row["plan_id"],
            "triggered_by_event_id": row["triggered_by_event_id"],
            "actions": json.loads(row["actions"]),
            "policy": row["policy"],
            "reason": reason,
            "created_ts": row["created_ts"],
        }

    def count_events(
        self, event_type: str, since_ts: int, payload_filter: Optional[Dict[str, Any]] = None
    ) -> int:
        payload_filter = payload_filter or {}
        with self.lock:
            with self._get_connection() as conn:
                rows = conn.execute(
                    """
                    SELECT payload FROM events
                    WHERE type = ? AND ts >= ?
                    """,
                    (event_type, since_ts),
                ).fetchall()
        count = 0
        for row in rows:
            payload = json.loads(row["payload"])
            if all(payload.get(key) == value for key, value in payload_filter.items()):
                count += 1
        return count

    def _row_to_result(self, row: sqlite3.Row) -> Dict[str, Any]:
        return {
            "plan_id": row["plan_id"],
            "action_type": row["action_type"],
            "status": row["status"],
            "output": json.loads(row["output"]),
            "ts": row["ts"],
        }

    def _row_to_schedule(self, row: sqlite3.Row) -> Dict[str, Any]:
        return {
            "schedule_id": row["schedule_id"],
            "run_at": row["run_at"],
            "actions": json.loads(row["actions"]),
            "status": row["status"],
            "created_ts": row["created_ts"],
            "note": row["note"],
        }

    def _row_to_voiceprint(self, row: sqlite3.Row) -> Dict[str, Any]:
        return {
            "voiceprint_id": row["voiceprint_id"],
            "label": row["label"],
            "fingerprint": row["fingerprint"],
            "created_ts": row["created_ts"],
            "meta": json.loads(row["meta"] or "{}"),
        }

    def _row_to_faceprint(self, row: sqlite3.Row) -> Dict[str, Any]:
        return {
            "faceprint_id": row["faceprint_id"],
            "label": row["label"],
            "embedding": json.loads(row["embedding"] or "[]"),
            "created_ts": row["created_ts"],
            "meta": json.loads(row["meta"] or "{}"),
        }
