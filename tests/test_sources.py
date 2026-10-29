"""Tests for carewatcher.sources — Audio and Sensor simulators."""
from __future__ import annotations

import pytest

from carewatcher.interfaces import AudioChunk, AudioSource, SensorReading, SensorSource
from carewatcher.sources.audio_sim import AudioSimulator
from carewatcher.sources.sensor_sim import SensorSimulator


class TestAudioSimulator:
    def test_implements_protocol(self) -> None:
        sim = AudioSimulator()
        assert isinstance(sim, AudioSource)

    def test_read_lifecycle(self) -> None:
        sim = AudioSimulator(num_chunks=3)
        with pytest.raises(RuntimeError, match="not open"):
            sim.read()

        sim.open()
        chunk1 = sim.read()
        assert isinstance(chunk1, AudioChunk)
        assert len(chunk1.samples) == 1024

        sim.read()
        sim.read()

        with pytest.raises(StopIteration):
            sim.read()

        sim.close()
        with pytest.raises(RuntimeError, match="not open"):
            sim.read()

    def test_iteration(self) -> None:
        sim = AudioSimulator(num_chunks=4)
        chunks = list(sim)
        assert len(chunks) == 4
        assert all(isinstance(c, AudioChunk) for c in chunks)


class TestSensorSimulator:
    def test_implements_protocol(self) -> None:
        sim = SensorSimulator()
        assert isinstance(sim, SensorSource)

    def test_read_lifecycle(self) -> None:
        sim = SensorSimulator(num_readings=2)
        with pytest.raises(RuntimeError, match="not open"):
            sim.read()

        sim.open()
        r1 = sim.read()
        assert isinstance(r1, SensorReading)
        assert r1.sensor_id == "sim_motion"

        sim.read()
        with pytest.raises(StopIteration):
            sim.read()

        sim.close()

    def test_iteration(self) -> None:
        sim = SensorSimulator(num_readings=5)
        readings = list(sim)
        assert len(readings) == 5
        assert all(isinstance(r, SensorReading) for r in readings)
