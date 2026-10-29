"""
carewatcher/interfaces.py
Shared protocols and data types for the CareWatcher pipeline.

Every module programs against these types — no module imports another
module's internals.  The pipeline wires concrete implementations together
via these protocols.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Iterator, Protocol, runtime_checkable
from uuid import UUID, uuid4


# ── Enums ────────────────────────────────────────────────────────────────────


class ShutterState(Enum):
    """Privacy shutter position."""

    OPEN = auto()
    CLOSED = auto()


class EventCategory(Enum):
    """Category of a health-relevant event."""

    MEDICATION = auto()
    SLEEP = auto()
    ACTIVITY = auto()
    MOOD = auto()
    DISTRESS = auto()
    INACTIVITY = auto()


class InterventionType(Enum):
    """Kind of action the system can take."""

    REMINDER = auto()
    CONVERSATION = auto()
    NOTIFY_CAREGIVER = auto()
    ESCALATE = auto()


class VerifierDecision(Enum):
    """Outcome of the Verifier's review."""

    APPROVED = auto()
    REJECTED = auto()
    ESCALATED = auto()


# ── Data Classes ─────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class AudioChunk:
    """Raw audio buffer from an audio source."""

    samples: bytes
    sample_rate: int
    channels: int = 1
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass(frozen=True)
class SensorReading:
    """A single sensor observation (heart rate, motion, etc.)."""

    sensor_id: str
    value: float
    unit: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Transcript:
    """Result of speech-to-text processing."""

    text: str
    confidence: float
    language: str = "en"
    timestamp: datetime = field(default_factory=datetime.now)
    duration_seconds: float = 0.0
    prosody: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class HealthEvent:
    """A detected health-relevant event produced by the agent or trend engine."""

    id: UUID = field(default_factory=uuid4)
    category: EventCategory = EventCategory.MEDICATION
    summary: str = ""
    details: dict[str, object] = field(default_factory=dict)
    resident_id: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    source_module: str = ""


@dataclass(frozen=True)
class Intervention:
    """A proposed action to take for a resident."""

    id: UUID = field(default_factory=uuid4)
    type: InterventionType = InterventionType.REMINDER
    event_id: UUID = field(default_factory=uuid4)
    resident_id: str = ""
    message: str = ""
    reasoning: str = ""
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass(frozen=True)
class VerifierResult:
    """Outcome of the Verifier's review of an Intervention."""

    intervention_id: UUID = field(default_factory=uuid4)
    decision: VerifierDecision = VerifierDecision.REJECTED
    reason: str = ""
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass(frozen=True)
class AuditEntry:
    """One row in the append-only, hash-chained audit log.

    ``prev_hash`` is the ``entry_hash`` of the preceding entry (empty string
    for the very first entry).  ``entry_hash`` is computed over all other
    fields so that any tampering breaks the chain.
    """

    sequence: int = 0
    timestamp: datetime = field(default_factory=datetime.now)
    event_type: str = ""
    payload: dict[str, object] = field(default_factory=dict)
    prev_hash: str = ""
    entry_hash: str = ""

    def compute_hash(self) -> str:
        """Return SHA-256 hex digest over all fields except ``entry_hash``."""
        content = (
            f"{self.sequence}|{self.timestamp.isoformat()}"
            f"|{self.event_type}|{self.payload}|{self.prev_hash}"
        )
        return hashlib.sha256(content.encode()).hexdigest()


# ── Protocols (interfaces for dependency injection) ──────────────────────────


@runtime_checkable
class AudioSource(Protocol):
    """Provides audio chunks — implemented by mic driver AND simulator."""

    def open(self) -> None:
        """Acquire the underlying resource (mic, file handle, etc.)."""
        ...

    def read(self) -> AudioChunk:
        """Return the next audio chunk.  Blocks until data is available."""
        ...

    def close(self) -> None:
        """Release the underlying resource."""
        ...

    def __iter__(self) -> Iterator[AudioChunk]:
        """Iterate over audio chunks until the source is exhausted."""
        ...


@runtime_checkable
class SensorSource(Protocol):
    """Provides sensor readings — implemented by real driver AND simulator."""

    def open(self) -> None:
        """Acquire the underlying resource."""
        ...

    def read(self) -> SensorReading:
        """Return the next sensor reading."""
        ...

    def close(self) -> None:
        """Release the underlying resource."""
        ...

    def __iter__(self) -> Iterator[SensorReading]:
        """Iterate over readings until the source is exhausted."""
        ...


@runtime_checkable
class STTEngine(Protocol):
    """Speech-to-text engine."""

    def transcribe(self, chunk: AudioChunk) -> Transcript:
        """Transcribe an audio chunk into text."""
        ...


@runtime_checkable
class WakeWordDetector(Protocol):
    """Detects a wake word/phrase in a transcript."""

    def detect(self, transcript: Transcript) -> bool:
        """Return True if the wake word is present in the transcript."""
        ...


@runtime_checkable
class ConversationAgent(Protocol):
    """LLM-backed conversational agent producing structured output."""

    def respond(self, transcript: Transcript) -> HealthEvent:
        """Process a transcript and return a structured health event."""
        ...


@runtime_checkable
class TrendEngine(Protocol):
    """Detects drift from per-resident baselines."""

    def update(self, event: HealthEvent) -> list[HealthEvent]:
        """Ingest an event and return any drift alerts (may be empty)."""
        ...


@runtime_checkable
class Proposer(Protocol):
    """Generates candidate interventions from health events."""

    def propose(self, event: HealthEvent) -> Intervention | None:
        """Return a proposed intervention, or None if no action needed."""
        ...


@runtime_checkable
class Verifier(Protocol):
    """Independently reviews a proposed intervention."""

    def verify(self, intervention: Intervention) -> VerifierResult:
        """Approve, reject, or escalate the proposed intervention."""
        ...


@runtime_checkable
class AuditLog(Protocol):
    """Append-only, hash-chained audit log."""

    def append(self, event_type: str, payload: dict[str, object]) -> AuditEntry:
        """Write a new entry and return it (with computed hash chain)."""
        ...

    def verify_chain(self) -> bool:
        """Return True if the entire log is intact (no tampered entries)."""
        ...
