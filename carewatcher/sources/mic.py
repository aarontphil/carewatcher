"""
carewatcher/sources/mic.py
Real laptop microphone driver implementing the AudioSource protocol.
"""
from __future__ import annotations

from datetime import datetime
from typing import Iterator

from carewatcher.interfaces import AudioChunk, AudioSource


class MicrophoneSource:
    """Real laptop microphone audio source using sounddevice."""

    def __init__(
        self,
        sample_rate: int = 16000,
        channels: int = 1,
        chunk_duration_sec: float = 1.0,
    ) -> None:
        self.sample_rate = sample_rate
        self.channels = channels
        self.chunk_duration_sec = chunk_duration_sec
        self.chunk_size_samples = int(sample_rate * chunk_duration_sec)
        self._is_open = False
        self._stream = None

    def open(self) -> None:
        try:
            import sounddevice as sd  # type: ignore[import-not-found]
            self._sd = sd
        except ImportError:
            self._sd = None

        self._is_open = True

    def read(self) -> AudioChunk:
        if not self._is_open:
            raise RuntimeError("MicrophoneSource is not open")

        if self._sd is None:
            # Fallback for environments without sounddevice/hardware audio device
            num_bytes = self.chunk_size_samples * 2 * self.channels
            return AudioChunk(
                samples=b"\x00" * num_bytes,
                sample_rate=self.sample_rate,
                channels=self.channels,
                timestamp=datetime.now(),
            )

        # Record audio chunk synchronously from mic
        recording = self._sd.rec(
            self.chunk_size_samples,
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype="int16",
        )
        self._sd.wait()
        pcm_bytes = recording.tobytes()

        return AudioChunk(
            samples=pcm_bytes,
            sample_rate=self.sample_rate,
            channels=self.channels,
            timestamp=datetime.now(),
        )

    def record_seconds(self, duration_sec: float = 3.0) -> AudioChunk:
        """Record audio directly from laptop microphone for specified duration."""
        if not self._is_open:
            self.open()

        num_samples = int(self.sample_rate * max(0.5, duration_sec))
        if self._sd is None:
            return AudioChunk(
                samples=b"\x00" * (num_samples * 2 * self.channels),
                sample_rate=self.sample_rate,
                channels=self.channels,
                timestamp=datetime.now(),
            )

        try:
            # Query devices to see if default device is a virtual cable and find Realtek if so
            target_device = None
            try:
                devs = self._sd.query_devices()
                def_in = self._sd.default.device[0]
                def_name = devs[def_in]["name"].lower() if def_in is not None and def_in < len(devs) else ""
                if "virtual" in def_name or "line 1" in def_name:
                    for i, d in enumerate(devs):
                        dname = d.get("name", "").lower()
                        if d.get("max_input_channels", 0) > 0 and ("realtek" in dname or "mic" in dname) and "virtual" not in dname:
                            target_device = i
                            break
            except Exception:
                pass

            recording = self._sd.rec(
                num_samples,
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype="int16",
                device=target_device,
            )
            self._sd.wait()
            pcm_bytes = recording.tobytes()
            return AudioChunk(
                samples=pcm_bytes,
                sample_rate=self.sample_rate,
                channels=self.channels,
                timestamp=datetime.now(),
            )
        except Exception:
            return AudioChunk(
                samples=b"\x00" * (num_samples * 2 * self.channels),
                sample_rate=self.sample_rate,
                channels=self.channels,
                timestamp=datetime.now(),
            )

    def close(self) -> None:
        self._is_open = False
        self._stream = None

    def __iter__(self) -> Iterator[AudioChunk]:
        if not self._is_open:
            self.open()
        while self._is_open:
            yield self.read()
