"""Shared pytest fixtures for CareWatcher tests."""
from __future__ import annotations

import textwrap
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import pytest

from carewatcher.interfaces import (
    AudioChunk,
    EventCategory,
    HealthEvent,
    Intervention,
    InterventionType,
    SensorReading,
    Transcript,
)


# ── Paths ────────────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def project_root() -> Path:
    return PROJECT_ROOT


@pytest.fixture
def default_config_path() -> Path:
    return PROJECT_ROOT / "config.yaml"


@pytest.fixture
def tmp_config(tmp_path: Path) -> Path:
    """Write a minimal valid config.yaml to a temp directory and return path."""
    content = textwrap.dedent("""\
        privacy:
          shutter_default: closed
        stt:
          engine: whisper
          model_size: base
          language: en
          device: cpu
        wake_word:
          keyword: "hey care"
          threshold: 0.6
        llm:
          backend: llama_cpp
          model_path: models/test-model.gguf
          context_length: 2048
          temperature: 0.3
          max_tokens: 512
        tts:
          engine: piper
          voice: en_US-lessac-medium
          sample_rate: 22050
        sources:
          audio:
            driver: simulator
          sensor:
            driver: simulator
        resident:
          name: TestUser
          medication_schedule:
            - time: "08:00"
              medication: "TestMed 10 mg"
        trend:
          window_days: 7
          sleep_drift_hours: 2.0
          inactivity_timeout_minutes: 90
          mood_drift_consecutive: 3
        verifier:
          max_reminders_per_hour: 3
          quiet_hours:
            start: "22:00"
            end: "07:00"
          deny_list_path: data/deny_list.txt
        audit:
          log_path: data/audit.jsonl
          hash_algorithm: sha256
    """)
    path = tmp_path / "config.yaml"
    path.write_text(content, encoding="utf-8")
    return path


# ── Sample Data Factories ────────────────────────────────────────────────────

NOW = datetime(2026, 10, 5, 12, 0, 0)


@pytest.fixture
def sample_audio_chunk() -> AudioChunk:
    return AudioChunk(
        samples=b"\x00\x01\x02\x03" * 1000,
        sample_rate=16000,
        channels=1,
        timestamp=NOW,
    )


@pytest.fixture
def sample_sensor_reading() -> SensorReading:
    return SensorReading(
        sensor_id="heart_rate_sim",
        value=72.0,
        unit="bpm",
        timestamp=NOW,
        metadata={"source": "simulator"},
    )


@pytest.fixture
def sample_transcript() -> Transcript:
    return Transcript(
        text="Yes I took my medicine this morning",
        confidence=0.92,
        language="en",
        timestamp=NOW,
        duration_seconds=3.5,
    )


@pytest.fixture
def sample_health_event() -> HealthEvent:
    return HealthEvent(
        category=EventCategory.MEDICATION,
        summary="Medication taken",
        details={"adherence": True, "medication": "Amlodipine 5 mg"},
        resident_id="arun",
        timestamp=NOW,
        source_module="agent",
    )


@pytest.fixture
def sample_intervention() -> Intervention:
    return Intervention(
        type=InterventionType.REMINDER,
        event_id=uuid4(),
        resident_id="arun",
        message="Just a gentle reminder to take your evening medicine.",
        reasoning="Medication was missed at scheduled time.",
        timestamp=NOW,
    )
