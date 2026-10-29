"""Tests for carewatcher.stt — STT engine and wake-word detector."""
from __future__ import annotations

from datetime import datetime

import pytest

from carewatcher.interfaces import AudioChunk, AudioSource, STTEngine, Transcript, WakeWordDetector
from carewatcher.sources.mic import MicrophoneSource
from carewatcher.stt.engine import DummySTTEngine, WhisperSTTEngine
from carewatcher.stt.wake_word import KeywordWakeWordDetector


class TestSTTEngine:
    def test_dummy_stt_implements_protocol(self) -> None:
        engine = DummySTTEngine()
        assert isinstance(engine, STTEngine)

    def test_whisper_stt_implements_protocol(self) -> None:
        engine = WhisperSTTEngine()
        assert isinstance(engine, STTEngine)

    def test_dummy_stt_transcribes(self, sample_audio_chunk: AudioChunk) -> None:
        engine = DummySTTEngine(default_text="hello world", confidence=0.9)
        t = engine.transcribe(sample_audio_chunk)
        assert isinstance(t, Transcript)
        assert t.text == "hello world"
        assert 0.0 <= t.confidence <= 1.0

    def test_empty_audio_returns_empty_transcript(self) -> None:
        engine = DummySTTEngine()
        empty_chunk = AudioChunk(samples=b"", sample_rate=16000)
        t = engine.transcribe(empty_chunk)
        assert t.text == ""
        assert t.confidence == 0.0

    def test_whisper_fallback_transcribes(self, sample_audio_chunk: AudioChunk) -> None:
        engine = WhisperSTTEngine()
        t = engine.transcribe(sample_audio_chunk)
        assert isinstance(t, Transcript)
        assert t.text != ""
        assert 0.0 <= t.confidence <= 1.0


class TestWakeWordDetector:
    def test_implements_protocol(self) -> None:
        detector = KeywordWakeWordDetector()
        assert isinstance(detector, WakeWordDetector)

    def test_detects_keyword(self) -> None:
        detector = KeywordWakeWordDetector(keyword="hey care", threshold=0.6)
        t = Transcript(text="Hey Care, what time is it?", confidence=0.8, language="en")
        assert detector.detect(t) is True

    def test_rejects_non_keyword(self) -> None:
        detector = KeywordWakeWordDetector(keyword="hey care", threshold=0.6)
        t = Transcript(text="The weather is nice today", confidence=0.9, language="en")
        assert detector.detect(t) is False

    def test_rejects_low_confidence(self) -> None:
        detector = KeywordWakeWordDetector(keyword="hey care", threshold=0.6)
        t = Transcript(text="hey care", confidence=0.4, language="en")
        assert detector.detect(t) is False

    def test_handles_empty_transcript(self) -> None:
        detector = KeywordWakeWordDetector()
        t = Transcript(text="", confidence=0.0, language="en")
        assert detector.detect(t) is False


class TestMicrophoneSource:
    def test_implements_protocol(self) -> None:
        mic = MicrophoneSource()
        assert isinstance(mic, AudioSource)

    def test_mic_read_fallback(self) -> None:
        mic = MicrophoneSource()
        mic.open()
        chunk = mic.read()
        assert isinstance(chunk, AudioChunk)
        assert len(chunk.samples) > 0
        mic.close()
