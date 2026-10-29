"""
carewatcher/sources/sensor_sim.py
Sensor source simulator implementing the SensorSource protocol.
"""
from __future__ import annotations

from datetime import datetime
from typing import Iterator

from carewatcher.interfaces import SensorReading, SensorSource


class SensorSimulator:
    """Simulates a sensor stream by producing configured or synthetic sensor readings."""

    def __init__(
        self,
        readings: list[SensorReading] | None = None,
        sensor_id: str = "sim_motion",
        default_value: float = 1.0,
        unit: str = "activity_score",
        num_readings: int = 5,
    ) -> None:
        self._is_open = False
        self._read_index = 0

        if readings is not None:
            self._readings = readings
        else:
            self._readings = [
                SensorReading(
                    sensor_id=sensor_id,
                    value=default_value,
                    unit=unit,
                    timestamp=datetime.now(),
                    metadata={"source": "simulator"},
                )
                for _ in range(num_readings)
            ]

    def open(self) -> None:
        self._is_open = True
        self._read_index = 0

    def read(self) -> SensorReading:
        if not self._is_open:
            raise RuntimeError("SensorSource simulator is not open")
        if self._read_index >= len(self._readings):
            raise StopIteration("End of sensor stream simulation")
        reading = self._readings[self._read_index]
        self._read_index += 1
        return reading

    def close(self) -> None:
        self._is_open = False

    def __iter__(self) -> Iterator[SensorReading]:
        if not self._is_open:
            self.open()
        while self._read_index < len(self._readings):
            yield self.read()
