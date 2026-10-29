"""
carewatcher/memory/store.py
SQLite-backed local per-resident memory store.

All data stays on-device in a single SQLite file — zero cloud, zero network.
Stores health events, sensor readings, conversation history, and mood labels
to power the trend engine's baseline calculations.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from dataclasses import asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID

from carewatcher.interfaces import EventCategory, HealthEvent, SensorReading


class ResidentMemoryStore:
    """Thread-safe, local SQLite memory store for a single resident.

    Parameters
    ----------
    db_path:
        Filesystem path for the SQLite database file.
        Parent directories are created automatically.
    resident_id:
        Default resident identifier for queries.
    """

    def __init__(
        self,
        db_path: str | Path = "data/resident.db",
        resident_id: str = "Aaron",
    ) -> None:
        self.db_path = Path(db_path)
        self.resident_id = resident_id
        self._lock = threading.Lock()
        self._conn: sqlite3.Connection | None = None

    # ── lifecycle ──────────────────────────────────────────────────────

    def open(self) -> None:
        """Create the database and tables if they don't exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._create_tables()

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    def _create_tables(self) -> None:
        assert self._conn is not None
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS health_events (
                id            TEXT PRIMARY KEY,
                category      TEXT NOT NULL,
                summary       TEXT NOT NULL,
                details       TEXT NOT NULL DEFAULT '{}',
                resident_id   TEXT NOT NULL,
                timestamp     TEXT NOT NULL,
                source_module TEXT NOT NULL DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS sensor_readings (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                sensor_id  TEXT NOT NULL,
                value      REAL NOT NULL,
                unit       TEXT NOT NULL,
                timestamp  TEXT NOT NULL,
                metadata   TEXT NOT NULL DEFAULT '{}'
            );

            CREATE TABLE IF NOT EXISTS mood_history (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                mood_label TEXT NOT NULL,
                confidence REAL NOT NULL DEFAULT 0.0,
                timestamp  TEXT NOT NULL,
                resident_id TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS medication_log (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                medication  TEXT NOT NULL,
                adherence   INTEGER,
                timestamp   TEXT NOT NULL,
                resident_id TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS daily_summary (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                date           TEXT NOT NULL,
                resident_id    TEXT NOT NULL,
                avg_bpm        REAL,
                avg_spo2       REAL,
                avg_temp       REAL,
                activity_score REAL,
                sleep_hours    REAL,
                mood_label     TEXT,
                event_count    INTEGER NOT NULL DEFAULT 0,
                UNIQUE(date, resident_id)
            );

            CREATE INDEX IF NOT EXISTS idx_events_resident_ts
                ON health_events(resident_id, timestamp);
            CREATE INDEX IF NOT EXISTS idx_sensor_ts
                ON sensor_readings(sensor_id, timestamp);
            CREATE INDEX IF NOT EXISTS idx_mood_resident_ts
                ON mood_history(resident_id, timestamp);
            CREATE INDEX IF NOT EXISTS idx_daily_resident_date
                ON daily_summary(resident_id, date);
            """
        )
        self._conn.commit()

    # ── writers ────────────────────────────────────────────────────────

    def store_event(self, event: HealthEvent) -> None:
        """Persist a HealthEvent to local storage."""
        assert self._conn is not None
        with self._lock:
            self._conn.execute(
                """
                INSERT OR REPLACE INTO health_events
                    (id, category, summary, details, resident_id, timestamp, source_module)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(event.id),
                    event.category.name,
                    event.summary,
                    json.dumps(event.details, default=str),
                    event.resident_id,
                    event.timestamp.isoformat(),
                    event.source_module,
                ),
            )
            self._conn.commit()

    def store_sensor_reading(self, reading: SensorReading) -> None:
        """Persist a SensorReading to local storage."""
        assert self._conn is not None
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO sensor_readings (sensor_id, value, unit, timestamp, metadata)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    reading.sensor_id,
                    reading.value,
                    reading.unit,
                    reading.timestamp.isoformat(),
                    json.dumps(reading.metadata, default=str),
                ),
            )
            self._conn.commit()

    def store_mood(
        self,
        mood_label: str,
        confidence: float = 0.0,
        resident_id: str | None = None,
    ) -> None:
        """Record a mood observation."""
        assert self._conn is not None
        rid = resident_id or self.resident_id
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO mood_history (mood_label, confidence, timestamp, resident_id)
                VALUES (?, ?, ?, ?)
                """,
                (mood_label, confidence, datetime.now().isoformat(), rid),
            )
            self._conn.commit()

    def store_medication_adherence(
        self,
        medication: str,
        adherence: bool | None,
        resident_id: str | None = None,
    ) -> None:
        """Record whether the resident took a specific medication."""
        assert self._conn is not None
        rid = resident_id or self.resident_id
        adh_int = None if adherence is None else (1 if adherence else 0)
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO medication_log (medication, adherence, timestamp, resident_id)
                VALUES (?, ?, ?, ?)
                """,
                (medication, adh_int, datetime.now().isoformat(), rid),
            )
            self._conn.commit()

    def upsert_daily_summary(
        self,
        date: str,
        resident_id: str | None = None,
        **metrics: Any,
    ) -> None:
        """Create or update a daily summary row.

        Parameters
        ----------
        date:
            ISO date string (YYYY-MM-DD).
        metrics:
            Any of: avg_bpm, avg_spo2, avg_temp, activity_score,
            sleep_hours, mood_label, event_count.
        """
        assert self._conn is not None
        rid = resident_id or self.resident_id

        allowed = {
            "avg_bpm", "avg_spo2", "avg_temp", "activity_score",
            "sleep_hours", "mood_label", "event_count",
        }
        filtered = {k: v for k, v in metrics.items() if k in allowed}

        with self._lock:
            # Try insert first
            try:
                cols = ", ".join(["date", "resident_id"] + list(filtered.keys()))
                placeholders = ", ".join(["?"] * (2 + len(filtered)))
                vals = [date, rid] + list(filtered.values())
                self._conn.execute(
                    f"INSERT INTO daily_summary ({cols}) VALUES ({placeholders})",
                    vals,
                )
            except sqlite3.IntegrityError:
                # Row exists — update only the provided columns
                if filtered:
                    set_clause = ", ".join(f"{k} = ?" for k in filtered)
                    vals = list(filtered.values()) + [date, rid]
                    self._conn.execute(
                        f"UPDATE daily_summary SET {set_clause} WHERE date = ? AND resident_id = ?",
                        vals,
                    )
            self._conn.commit()

    # ── readers ────────────────────────────────────────────────────────

    def get_events(
        self,
        category: EventCategory | None = None,
        since: datetime | None = None,
        limit: int = 100,
        resident_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Query health events from local storage."""
        assert self._conn is not None
        rid = resident_id or self.resident_id
        clauses = ["resident_id = ?"]
        params: list[Any] = [rid]

        if category is not None:
            clauses.append("category = ?")
            params.append(category.name)
        if since is not None:
            clauses.append("timestamp >= ?")
            params.append(since.isoformat())

        where = " AND ".join(clauses)
        params.append(limit)

        rows = self._conn.execute(
            f"SELECT * FROM health_events WHERE {where} ORDER BY timestamp DESC LIMIT ?",
            params,
        ).fetchall()
        return [dict(r) for r in rows]

    def get_sensor_readings(
        self,
        sensor_id: str | None = None,
        since: datetime | None = None,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        """Query sensor readings from local storage."""
        assert self._conn is not None
        clauses: list[str] = []
        params: list[Any] = []

        if sensor_id:
            clauses.append("sensor_id = ?")
            params.append(sensor_id)
        if since:
            clauses.append("timestamp >= ?")
            params.append(since.isoformat())

        where = " AND ".join(clauses) if clauses else "1=1"
        params.append(limit)

        rows = self._conn.execute(
            f"SELECT * FROM sensor_readings WHERE {where} ORDER BY timestamp DESC LIMIT ?",
            params,
        ).fetchall()
        return [dict(r) for r in rows]

    def get_recent_moods(
        self,
        count: int = 10,
        resident_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return the N most recent mood observations."""
        assert self._conn is not None
        rid = resident_id or self.resident_id
        rows = self._conn.execute(
            """
            SELECT * FROM mood_history
            WHERE LOWER(resident_id) = LOWER(?) OR resident_id = ?
            ORDER BY timestamp DESC LIMIT ?
            """,
            (rid, rid, count),
        ).fetchall()
        if not rows:
            rows = self._conn.execute(
                "SELECT * FROM mood_history ORDER BY timestamp DESC LIMIT ?",
                (count,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_daily_summaries(
        self,
        days: int = 7,
        resident_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return the last N days of daily summaries."""
        assert self._conn is not None
        rid = resident_id or self.resident_id
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        rows = self._conn.execute(
            """
            SELECT * FROM daily_summary
            WHERE resident_id = ? AND date >= ?
            ORDER BY date DESC
            """,
            (rid, cutoff),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_medication_adherence(
        self,
        days: int = 7,
        resident_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return medication adherence records for the last N days."""
        assert self._conn is not None
        rid = resident_id or self.resident_id
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        rows = self._conn.execute(
            """
            SELECT * FROM medication_log
            WHERE resident_id = ? AND timestamp >= ?
            ORDER BY timestamp DESC
            """,
            (rid, cutoff),
        ).fetchall()
        return [dict(r) for r in rows]

    def count_events_today(self, resident_id: str | None = None) -> int:
        """Count health events recorded today."""
        assert self._conn is not None
        rid = resident_id or self.resident_id
        today = datetime.now().strftime("%Y-%m-%d")
        row = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM health_events WHERE resident_id = ? AND timestamp >= ?",
            (rid, today),
        ).fetchone()
        return row["cnt"] if row else 0
