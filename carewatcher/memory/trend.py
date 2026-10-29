"""
carewatcher/memory/trend.py
Rolling-baseline trend engine with drift detection.

Compares recent sensor/health data against personal baselines and emits
HealthEvent alerts when a metric breaches the configured threshold.
All computation is local — no network calls.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

from carewatcher.interfaces import EventCategory, HealthEvent


@dataclass
class BaselineStats:
    """Rolling baseline statistics for a single metric."""

    metric_name: str
    mean: float
    stdev: float
    sample_count: int
    window_days: int


class TrendEngine:
    """Detects drift from per-resident rolling baselines.

    The engine maintains in-memory running statistics that can be seeded
    from the memory store's daily summaries.  When ``update()`` is called
    with a new HealthEvent, it checks the event's details against the
    current baseline and returns any drift alerts.

    Parameters
    ----------
    resident_id:
        Identifier of the resident whose baselines are tracked.
    window_days:
        Number of days for the rolling baseline window.
    sleep_drift_hours:
        Hours below baseline sleep average to trigger an alert.
    inactivity_timeout_minutes:
        Minutes of zero activity to trigger a welfare check.
    mood_drift_consecutive:
        Consecutive negative mood observations to trigger alert.
    bpm_drift_threshold:
        BPM deviation from mean to trigger alert.
    spo2_low_threshold:
        SpO2 percentage below which an alert fires.
    temp_drift_threshold:
        Degrees Celsius deviation from mean body temperature.
    """

    def __init__(
        self,
        resident_id: str = "arun",
        window_days: int = 7,
        sleep_drift_hours: float = 2.0,
        inactivity_timeout_minutes: int = 90,
        mood_drift_consecutive: int = 3,
        bpm_drift_threshold: float = 20.0,
        spo2_low_threshold: float = 92.0,
        temp_drift_threshold: float = 1.5,
    ) -> None:
        self.resident_id = resident_id
        self.window_days = window_days
        self.sleep_drift_hours = sleep_drift_hours
        self.inactivity_timeout_minutes = inactivity_timeout_minutes
        self.mood_drift_consecutive = mood_drift_consecutive
        self.bpm_drift_threshold = bpm_drift_threshold
        self.spo2_low_threshold = spo2_low_threshold
        self.temp_drift_threshold = temp_drift_threshold

        # Rolling data buffers (populated from memory store or live data)
        self._sleep_hours: list[float] = []
        self._activity_scores: list[float] = []
        self._mood_labels: list[str] = []
        self._bpm_values: list[float] = []
        self._spo2_values: list[float] = []
        self._temp_values: list[float] = []

        self._last_activity_time: datetime = datetime.now()

    # ── seed from stored daily summaries ──────────────────────────────

    def seed_from_summaries(self, summaries: list[dict[str, Any]]) -> None:
        """Pre-populate baselines from historical daily summary rows.

        Call this at startup with data from ``ResidentMemoryStore.get_daily_summaries()``.
        """
        for row in summaries:
            if row.get("sleep_hours") is not None:
                self._sleep_hours.append(float(row["sleep_hours"]))
            if row.get("activity_score") is not None:
                self._activity_scores.append(float(row["activity_score"]))
            if row.get("mood_label"):
                self._mood_labels.append(str(row["mood_label"]))
            if row.get("avg_bpm") is not None:
                self._bpm_values.append(float(row["avg_bpm"]))
            if row.get("avg_spo2") is not None:
                self._spo2_values.append(float(row["avg_spo2"]))
            if row.get("avg_temp") is not None:
                self._temp_values.append(float(row["avg_temp"]))

    # ── baseline computation ──────────────────────────────────────────

    def _compute_baseline(self, values: list[float]) -> BaselineStats | None:
        """Compute mean and stdev over the rolling window."""
        # Keep only last N entries (window_days worth)
        trimmed = values[-self.window_days :]
        if len(trimmed) < 2:
            return None
        return BaselineStats(
            metric_name="",
            mean=statistics.mean(trimmed),
            stdev=statistics.stdev(trimmed),
            sample_count=len(trimmed),
            window_days=self.window_days,
        )

    def get_baselines(self) -> dict[str, BaselineStats | None]:
        """Return current baselines for all tracked metrics."""
        baselines: dict[str, BaselineStats | None] = {}
        for name, values in [
            ("sleep_hours", self._sleep_hours),
            ("activity_score", self._activity_scores),
            ("bpm", self._bpm_values),
            ("spo2", self._spo2_values),
            ("body_temp", self._temp_values),
        ]:
            b = self._compute_baseline(values)
            if b:
                b.metric_name = name
            baselines[name] = b
        return baselines

    # ── core update method ────────────────────────────────────────────

    def update(self, event: HealthEvent) -> list[HealthEvent]:
        """Ingest a HealthEvent, check for drift, return any alerts.

        This method also ingests raw sensor values embedded in the event's
        ``details`` dict (keys: ``bpm``, ``spo2``, ``temp_c``,
        ``sleep_hours``, ``activity_score``, ``mood_label``).
        """
        alerts: list[HealthEvent] = []
        details = event.details or {}

        # ── ingest new data points ────────────────────────────────────
        if "bpm" in details and details["bpm"] is not None:
            bpm = float(details["bpm"])  # type: ignore[arg-type]
            self._bpm_values.append(bpm)
            alerts.extend(self._check_bpm_drift(bpm))

        if "spo2" in details and details["spo2"] is not None:
            spo2 = float(details["spo2"])  # type: ignore[arg-type]
            self._spo2_values.append(spo2)
            alerts.extend(self._check_spo2_drift(spo2))

        if "temp_c" in details and details["temp_c"] is not None:
            temp = float(details["temp_c"])  # type: ignore[arg-type]
            self._temp_values.append(temp)
            alerts.extend(self._check_temp_drift(temp))

        if "sleep_hours" in details and details["sleep_hours"] is not None:
            sleep = float(details["sleep_hours"])  # type: ignore[arg-type]
            self._sleep_hours.append(sleep)
            alerts.extend(self._check_sleep_drift(sleep))

        if "activity_score" in details and details["activity_score"] is not None:
            score = float(details["activity_score"])  # type: ignore[arg-type]
            self._activity_scores.append(score)
            self._last_activity_time = datetime.now()

        if "mood_label" in details and details["mood_label"]:
            label = str(details["mood_label"])
            self._mood_labels.append(label)
            alerts.extend(self._check_mood_drift())

        # ── check inactivity ──────────────────────────────────────────
        if event.category == EventCategory.ACTIVITY:
            self._last_activity_time = datetime.now()

        alerts.extend(self._check_inactivity())

        return alerts

    # ── sensor reading ingestion (bypass HealthEvent) ─────────────────

    def ingest_sensor_reading(
        self,
        sensor_id: str,
        value: float,
        unit: str,
    ) -> list[HealthEvent]:
        """Ingest a raw sensor reading and check for drift.

        This provides a direct path for sensor data that hasn't been
        wrapped in a HealthEvent (e.g., from the serial sensor driver).
        """
        alerts: list[HealthEvent] = []

        if "bpm" in sensor_id.lower() or "heart" in sensor_id.lower():
            self._bpm_values.append(value)
            alerts.extend(self._check_bpm_drift(value))
        elif "spo2" in sensor_id.lower() or "oxygen" in sensor_id.lower():
            self._spo2_values.append(value)
            alerts.extend(self._check_spo2_drift(value))
        elif "temp" in sensor_id.lower():
            self._temp_values.append(value)
            alerts.extend(self._check_temp_drift(value))
        elif "activity" in sensor_id.lower() or "motion" in sensor_id.lower():
            self._activity_scores.append(value)
            self._last_activity_time = datetime.now()
        elif "mood" in sensor_id.lower() or unit == "valence":
            # Map valence value back to mood label if not passed directly
            label = "happy" if value > 0.3 else ("sad" if value < -0.3 else "calm")
            alerts.extend(self.ingest_mood(label))

        return alerts

    def ingest_mood(self, mood_label: str) -> list[HealthEvent]:
        """Directly ingest a continuous mood observation (e.g. from facial or vocal sensing)."""
        self._mood_labels.append(str(mood_label))
        return self._check_mood_drift()

    def ingest_bpm(self, bpm: float) -> list[HealthEvent]:
        """Directly ingest a continuous heart rate observation (e.g. from Apple Watch / HypeRate)."""
        return self.ingest_sensor_reading("max30102_bpm", float(bpm), "bpm")


    # ── drift checks ──────────────────────────────────────────────────

    def _check_bpm_drift(self, current: float) -> list[HealthEvent]:
        baseline = self._compute_baseline(self._bpm_values)
        if baseline is None:
            return []
        deviation = abs(current - baseline.mean)
        if deviation > self.bpm_drift_threshold:
            direction = "elevated" if current > baseline.mean else "low"
            return [
                self._make_alert(
                    EventCategory.DISTRESS,
                    f"Heart rate {direction}: {current:.0f} BPM "
                    f"(baseline: {baseline.mean:.0f} ± {baseline.stdev:.1f})",
                    {"bpm": current, "baseline_mean": baseline.mean, "deviation": deviation},
                )
            ]
        return []

    def _check_spo2_drift(self, current: float) -> list[HealthEvent]:
        if current < self.spo2_low_threshold:
            return [
                self._make_alert(
                    EventCategory.DISTRESS,
                    f"Blood oxygen low: {current:.1f}% (threshold: {self.spo2_low_threshold}%)",
                    {"spo2": current, "threshold": self.spo2_low_threshold},
                )
            ]
        return []

    def _check_temp_drift(self, current: float) -> list[HealthEvent]:
        baseline = self._compute_baseline(self._temp_values)
        if baseline is None:
            # Use a sensible default baseline if not enough history
            if current > 38.0 or current < 35.0:
                return [
                    self._make_alert(
                        EventCategory.DISTRESS,
                        f"Body temperature abnormal: {current:.1f}°C",
                        {"temp_c": current},
                    )
                ]
            return []
        deviation = abs(current - baseline.mean)
        if deviation > self.temp_drift_threshold:
            direction = "elevated" if current > baseline.mean else "low"
            return [
                self._make_alert(
                    EventCategory.DISTRESS,
                    f"Body temperature {direction}: {current:.1f}°C "
                    f"(baseline: {baseline.mean:.1f}°C)",
                    {"temp_c": current, "baseline_mean": baseline.mean},
                )
            ]
        return []

    def _check_sleep_drift(self, current: float) -> list[HealthEvent]:
        baseline = self._compute_baseline(self._sleep_hours)
        if baseline is None:
            return []
        deficit = baseline.mean - current
        if deficit >= self.sleep_drift_hours:
            return [
                self._make_alert(
                    EventCategory.SLEEP,
                    f"Sleep deficit detected: {current:.1f}h "
                    f"(baseline: {baseline.mean:.1f}h, deficit: {deficit:.1f}h)",
                    {"sleep_hours": current, "baseline_mean": baseline.mean, "deficit": deficit},
                )
            ]
        return []

    def _check_mood_drift(self) -> list[HealthEvent]:
        if len(self._mood_labels) < self.mood_drift_consecutive:
            return []
        recent = self._mood_labels[-self.mood_drift_consecutive :]
        negative_labels = {"sad", "depressed", "anxious", "lonely", "unhappy", "angry", "frustrated"}
        if all(m.lower() in negative_labels for m in recent):
            return [
                self._make_alert(
                    EventCategory.MOOD,
                    f"Persistent negative mood: {self.mood_drift_consecutive} consecutive "
                    f"negative observations ({', '.join(recent)})",
                    {"consecutive_negative": self.mood_drift_consecutive, "labels": recent},
                )
            ]
        return []

    def _check_inactivity(self) -> list[HealthEvent]:
        elapsed = (datetime.now() - self._last_activity_time).total_seconds() / 60.0
        if elapsed >= self.inactivity_timeout_minutes:
            return [
                self._make_alert(
                    EventCategory.INACTIVITY,
                    f"No activity detected for {elapsed:.0f} minutes "
                    f"(threshold: {self.inactivity_timeout_minutes} min)",
                    {"inactive_minutes": elapsed},
                )
            ]
        return []

    # ── helpers ────────────────────────────────────────────────────────

    def _make_alert(
        self,
        category: EventCategory,
        summary: str,
        details: dict[str, object],
    ) -> HealthEvent:
        return HealthEvent(
            id=uuid4(),
            category=category,
            summary=summary,
            details=details,
            resident_id=self.resident_id,
            timestamp=datetime.now(),
            source_module="trend_engine",
        )
