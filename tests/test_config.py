"""Tests for carewatcher.config — config loading and validation."""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from carewatcher.config import CareWatcherConfig, ConfigError, load_config


class TestLoadConfig:
    """Config loading from YAML."""

    def test_loads_valid_config(self, tmp_config: Path) -> None:
        cfg = load_config(tmp_config)
        assert isinstance(cfg, CareWatcherConfig)

    def test_resident_name(self, tmp_config: Path) -> None:
        cfg = load_config(tmp_config)
        assert cfg.resident.name == "TestUser"

    def test_stt_model_size(self, tmp_config: Path) -> None:
        cfg = load_config(tmp_config)
        assert cfg.stt.model_size == "base"

    def test_medication_schedule_parsed(self, tmp_config: Path) -> None:
        cfg = load_config(tmp_config)
        assert len(cfg.resident.medication_schedule) == 1
        assert cfg.resident.medication_schedule[0].medication == "TestMed 10 mg"

    def test_sources_default_to_simulator(self, tmp_config: Path) -> None:
        cfg = load_config(tmp_config)
        assert cfg.sources.audio.driver == "simulator"
        assert cfg.sources.sensor.driver == "simulator"

    def test_privacy_shutter_default(self, tmp_config: Path) -> None:
        cfg = load_config(tmp_config)
        assert cfg.privacy.shutter_default == "closed"

    def test_nested_quiet_hours(self, tmp_config: Path) -> None:
        cfg = load_config(tmp_config)
        assert cfg.verifier.quiet_hours.start == "22:00"
        assert cfg.verifier.quiet_hours.end == "07:00"


class TestConfigValidation:
    """Config rejects invalid values."""

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ConfigError, match="not found"):
            load_config(tmp_path / "nonexistent.yaml")

    def test_invalid_shutter_default(self, tmp_path: Path) -> None:
        content = textwrap.dedent("""\
            privacy:
              shutter_default: half_open
        """)
        path = tmp_path / "bad.yaml"
        path.write_text(content, encoding="utf-8")
        with pytest.raises(ConfigError, match="shutter_default"):
            load_config(path)

    def test_invalid_stt_model_size(self, tmp_path: Path) -> None:
        content = textwrap.dedent("""\
            stt:
              model_size: gigantic
        """)
        path = tmp_path / "bad.yaml"
        path.write_text(content, encoding="utf-8")
        with pytest.raises(ConfigError, match="model_size"):
            load_config(path)

    def test_invalid_stt_device(self, tmp_path: Path) -> None:
        content = textwrap.dedent("""\
            stt:
              device: tpu
        """)
        path = tmp_path / "bad.yaml"
        path.write_text(content, encoding="utf-8")
        with pytest.raises(ConfigError, match="device"):
            load_config(path)

    def test_invalid_audio_driver(self, tmp_path: Path) -> None:
        content = textwrap.dedent("""\
            sources:
              audio:
                driver: bluetooth
        """)
        path = tmp_path / "bad.yaml"
        path.write_text(content, encoding="utf-8")
        with pytest.raises(ConfigError, match="driver"):
            load_config(path)

    def test_invalid_yaml_raises(self, tmp_path: Path) -> None:
        path = tmp_path / "bad.yaml"
        path.write_text("{{{{not valid yaml", encoding="utf-8")
        with pytest.raises(ConfigError, match="parse"):
            load_config(path)

    def test_non_mapping_yaml_raises(self, tmp_path: Path) -> None:
        path = tmp_path / "bad.yaml"
        path.write_text("- just\n- a\n- list\n", encoding="utf-8")
        with pytest.raises(ConfigError, match="mapping"):
            load_config(path)


class TestConfigImmutability:
    """Config objects are frozen (immutable)."""

    def test_top_level_frozen(self, tmp_config: Path) -> None:
        cfg = load_config(tmp_config)
        with pytest.raises(AttributeError):
            cfg.privacy = None  # type: ignore[misc]

    def test_nested_frozen(self, tmp_config: Path) -> None:
        cfg = load_config(tmp_config)
        with pytest.raises(AttributeError):
            cfg.stt.model_size = "large"  # type: ignore[misc]
