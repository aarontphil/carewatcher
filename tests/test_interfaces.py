"""Tests for carewatcher.interfaces — dataclasses and protocols."""
from __future__ import annotations

from datetime import datetime
from typing import Iterator

import pytest

from carewatcher.interfaces import (
    AudioChunk,
    AudioSource,
    AuditEntry,
    AuditLog,
    ConversationAgent,
    EventCategory,
    HealthEvent,
    Intervention,
    InterventionType,
    Proposer,
    STTEngine,
    SensorReading,
    SensorSource,
    ShutterState,
    Transcript,
    TrendEngine,
    Verifier,
    VerifierDecision,
    VerifierResult,
    WakeWordDetector,
)


# ── Dataclass Immutability ───────────────────────────────────────────────────


class TestFrozenDataclasses:
    """All data types are frozen — fields cannot be reassigned."""

    def test_audio_chunk_frozen(self, sample_audio_chunk: AudioChunk) -> None:
        with pytest.raises(AttributeError):
            sample_audio_chunk.sample_rate = 44100  # type: ignore[misc]

    def test_sensor_reading_frozen(self, sample_sensor_reading: SensorReading) -> None:
        with pytest.raises(AttributeError):
            sample_sensor_reading.value = 999.0  # type: ignore[misc]

    def test_transcript_frozen(self, sample_transcript: Transcript) -> None:
        with pytest.raises(AttributeError):
            sample_transcript.text = "tampered"  # type: ignore[misc]

    def test_health_event_frozen(self, sample_health_event: HealthEvent) -> None:
        with pytest.raises(AttributeError):
            sample_health_event.summary = "tampered"  # type: ignore[misc]

    def test_intervention_frozen(self, sample_intervention: Intervention) -> None:
        with pytest.raises(AttributeError):
            sample_intervention.message = "tampered"  # type: ignore[misc]

    def test_verifier_result_frozen(self) -> None:
        vr = VerifierResult()
        with pytest.raises(AttributeError):
            vr.decision = VerifierDecision.APPROVED  # type: ignore[misc]

    def test_audit_entry_frozen(self) -> None:
        ae = AuditEntry()
        with pytest.raises(AttributeError):
            ae.sequence = 999  # type: ignore[misc]


# ── AuditEntry Hash ──────────────────────────────────────────────────────────


class TestAuditEntryHash:
    """AuditEntry.compute_hash() is deterministic and content-sensitive."""

    def test_hash_is_deterministic(self) -> None:
        ts = datetime(2026, 10, 5, 12, 0, 0)
        entry = AuditEntry(
            sequence=1,
            timestamp=ts,
            event_type="test",
            payload={"key": "value"},
            prev_hash="abc123",
        )
        h1 = entry.compute_hash()
        h2 = entry.compute_hash()
        assert h1 == h2
        assert len(h1) == 64  # SHA-256 hex digest

    def test_different_content_different_hash(self) -> None:
        ts = datetime(2026, 10, 5, 12, 0, 0)
        entry_a = AuditEntry(sequence=1, timestamp=ts, event_type="A", prev_hash="")
        entry_b = AuditEntry(sequence=1, timestamp=ts, event_type="B", prev_hash="")
        assert entry_a.compute_hash() != entry_b.compute_hash()

    def test_different_prev_hash_different_result(self) -> None:
        ts = datetime(2026, 10, 5, 12, 0, 0)
        entry_a = AuditEntry(sequence=1, timestamp=ts, event_type="X", prev_hash="aaa")
        entry_b = AuditEntry(sequence=1, timestamp=ts, event_type="X", prev_hash="bbb")
        assert entry_a.compute_hash() != entry_b.compute_hash()


# ── Enum Values ──────────────────────────────────────────────────────────────


class TestEnums:
    """Enums have expected members."""

    def test_shutter_state(self) -> None:
        assert ShutterState.OPEN != ShutterState.CLOSED

    def test_event_categories(self) -> None:
        expected = {"MEDICATION", "SLEEP", "ACTIVITY", "MOOD", "DISTRESS", "INACTIVITY"}
        assert {e.name for e in EventCategory} == expected

    def test_intervention_types(self) -> None:
        expected = {"REMINDER", "CONVERSATION", "NOTIFY_CAREGIVER", "ESCALATE"}
        assert {e.name for e in InterventionType} == expected

    def test_verifier_decisions(self) -> None:
        expected = {"APPROVED", "REJECTED", "ESCALATED"}
        assert {e.name for e in VerifierDecision} == expected


# ── Protocol Runtime Checks ──────────────────────────────────────────────────


class _FakeAudioSource:
    def open(self) -> None: ...
    def read(self) -> AudioChunk: ...
    def close(self) -> None: ...
    def __iter__(self) -> Iterator[AudioChunk]: ...


class _FakeSensorSource:
    def open(self) -> None: ...
    def read(self) -> SensorReading: ...
    def close(self) -> None: ...
    def __iter__(self) -> Iterator[SensorReading]: ...


class _FakeSTT:
    def transcribe(self, chunk: AudioChunk) -> Transcript: ...


class _FakeWakeWord:
    def detect(self, transcript: Transcript) -> bool: ...


class _FakeAgent:
    def respond(self, transcript: Transcript) -> HealthEvent: ...


class _FakeTrend:
    def update(self, event: HealthEvent) -> list[HealthEvent]: ...


class _FakeProposer:
    def propose(self, event: HealthEvent) -> Intervention | None: ...


class _FakeVerifier:
    def verify(self, intervention: Intervention) -> VerifierResult: ...


class _FakeAuditLog:
    def append(self, event_type: str, payload: dict[str, object]) -> AuditEntry: ...
    def verify_chain(self) -> bool: ...


class TestProtocolRuntimeChecks:
    """All protocols are runtime-checkable with isinstance()."""

    def test_audio_source(self) -> None:
        assert isinstance(_FakeAudioSource(), AudioSource)

    def test_sensor_source(self) -> None:
        assert isinstance(_FakeSensorSource(), SensorSource)

    def test_stt_engine(self) -> None:
        assert isinstance(_FakeSTT(), STTEngine)

    def test_wake_word_detector(self) -> None:
        assert isinstance(_FakeWakeWord(), WakeWordDetector)

    def test_conversation_agent(self) -> None:
        assert isinstance(_FakeAgent(), ConversationAgent)

    def test_trend_engine(self) -> None:
        assert isinstance(_FakeTrend(), TrendEngine)

    def test_proposer(self) -> None:
        assert isinstance(_FakeProposer(), Proposer)

    def test_verifier(self) -> None:
        assert isinstance(_FakeVerifier(), Verifier)

    def test_audit_log(self) -> None:
        assert isinstance(_FakeAuditLog(), AuditLog)
