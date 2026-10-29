"""
carewatcher/config.py
Loads and validates config.yaml into typed dataclasses.

Usage:
    from carewatcher.config import load_config
    cfg = load_config()                       # loads ./config.yaml
    cfg = load_config("path/to/config.yaml")  # loads a specific file
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


# ── Config Errors ────────────────────────────────────────────────────────────


class ConfigError(Exception):
    """Raised when the configuration is missing or invalid."""


# ── Section Dataclasses ──────────────────────────────────────────────────────


@dataclass(frozen=True)
class PrivacyConfig:
    shutter_default: str = "closed"

    def __post_init__(self) -> None:
        if self.shutter_default not in ("open", "closed"):
            raise ConfigError(
                f"privacy.shutter_default must be 'open' or 'closed', "
                f"got '{self.shutter_default}'"
            )


@dataclass(frozen=True)
class STTConfig:
    engine: str = "whisper"
    model_size: str = "base"
    language: str = "en"
    device: str = "cpu"

    def __post_init__(self) -> None:
        valid_sizes = {"tiny", "base", "small", "medium", "large"}
        if self.model_size not in valid_sizes:
            raise ConfigError(
                f"stt.model_size must be one of {valid_sizes}, "
                f"got '{self.model_size}'"
            )
        if self.device not in ("cpu", "cuda"):
            raise ConfigError(
                f"stt.device must be 'cpu' or 'cuda', got '{self.device}'"
            )


@dataclass(frozen=True)
class WakeWordConfig:
    keyword: str = "hey care"
    threshold: float = 0.6


@dataclass(frozen=True)
class LLMConfig:
    backend: str = "gemini"
    model_path: str = "models/mistral-7b-instruct.Q4_K_M.gguf"
    model_name: str = "gemini-2.0-flash"
    api_key: str = ""
    context_length: int = 2048
    temperature: float = 0.7
    max_tokens: int = 512


@dataclass(frozen=True)
class TTSConfig:
    engine: str = "piper"
    voice: str = "en_US-lessac-medium"
    sample_rate: int = 22050


@dataclass(frozen=True)
class AudioSourceConfig:
    driver: str = "simulator"
    simulator_script: str | None = None

    def __post_init__(self) -> None:
        if self.driver not in ("mic", "simulator"):
            raise ConfigError(
                f"sources.audio.driver must be 'mic' or 'simulator', "
                f"got '{self.driver}'"
            )


@dataclass(frozen=True)
class SensorSourceConfig:
    driver: str = "simulator"
    simulator_data: str | None = None
    serial_port: str = "COM3"
    serial_baud: int = 115200

    def __post_init__(self) -> None:
        valid_drivers = {"webcam", "simulator", "serial"}
        if self.driver not in valid_drivers:
            raise ConfigError(
                f"sources.sensor.driver must be one of {valid_drivers}, "
                f"got '{self.driver}'"
            )


@dataclass(frozen=True)
class SourcesConfig:
    audio: AudioSourceConfig = field(default_factory=AudioSourceConfig)
    sensor: SensorSourceConfig = field(default_factory=SensorSourceConfig)


@dataclass(frozen=True)
class MedicationEntry:
    time: str = "08:00"
    medication: str = ""


@dataclass(frozen=True)
class ResidentConfig:
    name: str = "Arun"
    medication_schedule: list[MedicationEntry] = field(default_factory=list)


@dataclass(frozen=True)
class TrendConfig:
    window_days: int = 7
    sleep_drift_hours: float = 2.0
    inactivity_timeout_minutes: int = 90
    mood_drift_consecutive: int = 3
    bpm_drift_threshold: float = 20.0
    spo2_low_threshold: float = 92.0
    temp_drift_threshold: float = 1.5


@dataclass(frozen=True)
class QuietHoursConfig:
    start: str = "22:00"
    end: str = "07:00"


@dataclass(frozen=True)
class VerifierConfig:
    max_reminders_per_hour: int = 3
    quiet_hours: QuietHoursConfig = field(default_factory=QuietHoursConfig)
    deny_list_path: str = "data/deny_list.txt"


@dataclass(frozen=True)
class AuditConfig:
    log_path: str = "data/audit.jsonl"
    hash_algorithm: str = "sha256"


@dataclass(frozen=True)
class CareWatcherConfig:
    """Top-level configuration container."""

    privacy: PrivacyConfig = field(default_factory=PrivacyConfig)
    stt: STTConfig = field(default_factory=STTConfig)
    wake_word: WakeWordConfig = field(default_factory=WakeWordConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    tts: TTSConfig = field(default_factory=TTSConfig)
    sources: SourcesConfig = field(default_factory=SourcesConfig)
    resident: ResidentConfig = field(default_factory=ResidentConfig)
    trend: TrendConfig = field(default_factory=TrendConfig)
    verifier: VerifierConfig = field(default_factory=VerifierConfig)
    audit: AuditConfig = field(default_factory=AuditConfig)


# ── Helpers ──────────────────────────────────────────────────────────────────


def _build_section(cls: type, data: dict[str, Any] | None) -> Any:
    """Instantiate a config dataclass from a raw dict, handling nesting."""
    if data is None:
        return cls()

    # Handle nested dataclasses that need special construction
    if cls is SourcesConfig:
        return SourcesConfig(
            audio=_build_section(AudioSourceConfig, data.get("audio")),
            sensor=_build_section(SensorSourceConfig, data.get("sensor")),
        )
    if cls is VerifierConfig:
        quiet = data.pop("quiet_hours", None)
        obj = cls(
            quiet_hours=_build_section(QuietHoursConfig, quiet),
            **data,
        )
        return obj
    if cls is ResidentConfig:
        schedule_raw = data.pop("medication_schedule", [])
        schedule = [MedicationEntry(**entry) for entry in schedule_raw]
        return cls(medication_schedule=schedule, **data)

    return cls(**data)


# ── Public API ───────────────────────────────────────────────────────────────


def load_config(path: str | Path = "config.yaml") -> CareWatcherConfig:
    """Load and validate the YAML config file.

    Parameters
    ----------
    path:
        Path to the YAML configuration file.

    Returns
    -------
    CareWatcherConfig
        A fully validated, immutable configuration object.

    Raises
    ------
    ConfigError
        If the file is missing, unreadable, or contains invalid values.
    """
    config_path = Path(path)
    if not config_path.exists():
        raise ConfigError(f"Config file not found: {config_path}")

    try:
        raw: dict[str, Any] = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigError(f"Failed to parse YAML: {exc}") from exc

    if not isinstance(raw, dict):
        raise ConfigError("Config file must contain a YAML mapping at the top level")

    try:
        return CareWatcherConfig(
            privacy=_build_section(PrivacyConfig, raw.get("privacy")),
            stt=_build_section(STTConfig, raw.get("stt")),
            wake_word=_build_section(WakeWordConfig, raw.get("wake_word")),
            llm=_build_section(LLMConfig, raw.get("llm")),
            tts=_build_section(TTSConfig, raw.get("tts")),
            sources=_build_section(SourcesConfig, raw.get("sources")),
            resident=_build_section(ResidentConfig, raw.get("resident")),
            trend=_build_section(TrendConfig, raw.get("trend")),
            verifier=_build_section(VerifierConfig, raw.get("verifier")),
            audit=_build_section(AuditConfig, raw.get("audit")),
        )
    except TypeError as exc:
        raise ConfigError(f"Invalid config structure: {exc}") from exc
