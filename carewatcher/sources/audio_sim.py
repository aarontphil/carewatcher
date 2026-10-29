"""
carewatcher/sources/audio_sim.py
Audio source simulator implementing the AudioSource protocol.
"""
from __future__ import annotations

from datetime import datetime
from typing import Iterator

from carewatcher.interfaces import AudioChunk, AudioSource


class AudioSimulator:
    """Simulates an audio stream by producing configured or synthetic audio chunks."""

    def __init__(
        self,
        chunks: list[AudioChunk] | None = None,
        chunk_size_bytes: int = 1024,
        sample_rate: int = 16000,
        num_chunks: int = 5,
    ) -> None:
        self.chunk_size_bytes = chunk_size_bytes
        self.sample_rate = sample_rate
        self._is_open = False
        self._read_index = 0

        if chunks is not None:
            self._chunks = chunks
        else:
            # Generate synthetic silent/dummy audio chunks
            self._chunks = [
                AudioChunk(
                    samples=b"\x00" * chunk_size_bytes,
                    sample_rate=sample_rate,
                    channels=1,
                    timestamp=datetime.now(),
                )
                for _ in range(num_chunks)
            ]

    def open(self) -> None:
        self._is_open = True
        self._read_index = 0

    def read(self) -> AudioChunk:
        if not self._is_open:
            raise RuntimeError("AudioSource simulator is not open")
        if self._read_index >= len(self._chunks):
            raise StopIteration("End of audio stream simulation")
        chunk = self._chunks[self._read_index]
        self._read_index += 1
        return chunk

    def close(self) -> None:
        self._is_open = False

    def __iter__(self) -> Iterator[AudioChunk]:
        if not self._is_open:
            self.open()
        while self._read_index < len(self._chunks):
            yield self.read()
