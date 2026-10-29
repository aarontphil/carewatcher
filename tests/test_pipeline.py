"""
tests/test_pipeline.py
Unit tests for Memory (ResidentMemoryStore), Trend (TrendEngine),
Proposer (RuleBasedProposer), Verifier (SafetyVerifier), and Audit (AuditLogger).
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pytest

from carewatcher.memory.store import ResidentMemoryStore
from carewatcher.memory.trend import TrendEngine
from carewatcher.proposer.engine import RuleBasedProposer
from carewatcher.verifier.engine import SafetyVerifier
from carewatcher.audit.logger import AuditLogger
from carewatcher.interfaces import (
    HealthEvent, EventCategory, Intervention, InterventionType,
    VerifierDecision, SensorReading
)


class TestMemoryStore:
    def test_record_and_query_events(self, tmp_path):
        db_path = tmp_path / "test.db"
        store = ResidentMemoryStore(db_path=db_path, resident_id="Arun")
        store.open()

        event = HealthEvent(
            timestamp=datetime.now(),
            category=EventCategory.MEDICATION,
            summary="Took blood pressure medicine",
            details={"medication": "Amlodipine", "adherence": True},
            resident_id="Arun"
        )
        store.store_event(event)

        events = store.get_events(category=EventCategory.MEDICATION)
        assert len(events) == 1
        assert events[0]["summary"] == "Took blood pressure medicine"
        store.close()

    def test_record_and_query_sensors(self, tmp_path):
        db_path = tmp_path / "test.db"
        store = ResidentMemoryStore(db_path=db_path)
        store.open()

        reading = SensorReading(
            timestamp=datetime.now(),
            sensor_id="max30102",
            value=74.5,
            unit="bpm"
        )
        store.store_sensor_reading(reading)

        readings = store.get_sensor_readings(sensor_id="max30102")
        assert len(readings) == 1
        assert readings[0]["value"] == 74.5
        store.close()

    def test_medication_adherence_log(self, tmp_path):
        db_path = tmp_path / "test.db"
        store = ResidentMemoryStore(db_path=db_path)
        store.open()

        store.store_medication_adherence("Lisinopril", adherence=True)
        adherence = store.get_medication_adherence(days=7)
        assert len(adherence) == 1
        assert adherence[0]["medication"] == "Lisinopril"
        assert adherence[0]["adherence"] == 1
        store.close()


class TestTrendEngine:
    def test_vital_signs_drift_spo2(self):
        engine = TrendEngine(
            resident_id="Arun",
            spo2_low_threshold=92.0
        )
        event = HealthEvent(
            timestamp=datetime.now(),
            category=EventCategory.ACTIVITY,
            summary="Vital signs reading",
            details={"spo2": 88.0}
        )
        alerts = engine.update(event)
        assert len(alerts) >= 1
        assert any(a.category == EventCategory.DISTRESS for a in alerts)
        assert any("Blood oxygen low" in a.summary for a in alerts)

    def test_vital_signs_drift_bpm(self):
        engine = TrendEngine(
            resident_id="Arun",
            bpm_drift_threshold=15.0
        )
        summaries = [
            {"avg_bpm": 70.0, "date": "2026-10-01"},
            {"avg_bpm": 72.0, "date": "2026-10-02"},
            {"avg_bpm": 69.0, "date": "2026-10-03"},
        ]
        engine.seed_from_summaries(summaries)

        event = HealthEvent(
            timestamp=datetime.now(),
            category=EventCategory.ACTIVITY,
            summary="Pulse check",
            details={"bpm": 115.0}
        )
        alerts = engine.update(event)
        assert len(alerts) >= 1
        assert any("Heart rate" in a.summary or "bpm" in a.summary.lower() for a in alerts)


class TestProposerAndVerifier:
    def test_proposer_generates_intervention(self):
        proposer = RuleBasedProposer(resident_id="Arun")
        event = HealthEvent(
            timestamp=datetime.now(),
            category=EventCategory.MEDICATION,
            summary="Missed morning medicine",
            details={"medication": "Amlodipine", "adherence": False},
            resident_id="Arun"
        )
        intervention = proposer.propose(event)
        assert intervention is not None
        assert intervention.type == InterventionType.REMINDER
        assert "medication" in intervention.message.lower()

    def test_verifier_blocks_clinical_terms(self, tmp_path):
        deny_file = tmp_path / "deny.txt"
        deny_file.write_text("diagnose\ndiabetes\nhypertension\ninfarction\n", encoding="utf-8")

        verifier = SafetyVerifier(
            deny_list_path=str(deny_file)
        )
        intervention = Intervention(
            timestamp=datetime.now(),
            type=InterventionType.CONVERSATION,
            resident_id="Arun",
            message="We can diagnose your hypertension today."
        )
        res = verifier.verify(intervention)
        assert res.decision == VerifierDecision.REJECTED
        assert "clinical" in res.reason.lower()

    def test_verifier_enforces_rate_limits(self, tmp_path):
        deny_file = tmp_path / "deny.txt"
        deny_file.write_text("", encoding="utf-8")

        verifier = SafetyVerifier(
            max_reminders_per_hour=2,
            quiet_start="00:00",
            quiet_end="00:01",
            deny_list_path=str(deny_file)
        )
        it = Intervention(
            timestamp=datetime.now(),
            type=InterventionType.REMINDER,
            resident_id="Arun",
            message="Time for a drink of water, Arun."
        )
        assert verifier.verify(it).decision == VerifierDecision.APPROVED
        assert verifier.verify(it).decision == VerifierDecision.APPROVED
        # 3rd time in the hour should be rate-limited
        assert verifier.verify(it).decision == VerifierDecision.REJECTED


class TestAuditLog:
    def test_hash_chain_integrity(self, tmp_path):
        log_file = tmp_path / "audit.jsonl"
        audit = AuditLogger(
            log_path=str(log_file),
            hash_algorithm="sha256"
        )

        audit.append("system_boot", {"status": "ok"})
        audit.append("event_recorded", {"category": "medication_taken"})
        audit.append("intervention_delivered", {"text": "Good morning Arun"})

        assert audit.entry_count() == 3
        assert audit.verify_chain() is True

        # Reload from disk and verify chain persists
        audit_reloaded = AuditLogger(
            log_path=str(log_file)
        )
        assert audit_reloaded.entry_count() == 3
        assert audit_reloaded.verify_chain() is True
