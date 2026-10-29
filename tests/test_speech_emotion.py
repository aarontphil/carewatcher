"""Tests for Speech Pattern & Emotion Recognition (SER) engine."""
from __future__ import annotations

import pytest

from carewatcher.stt.speech_emotion import SpeechEmotionAnalyzer, SpeechEmotionResult


class TestSpeechEmotionAnalyzer:
    def test_analyzer_initialization(self) -> None:
        analyzer = SpeechEmotionAnalyzer(baseline_wpm=120.0)
        assert analyzer.current_baseline_wpm == 120.0

    def test_calm_equilibrium_analysis(self) -> None:
        analyzer = SpeechEmotionAnalyzer()
        res = analyzer.analyze(
            text="I am doing okay and took a short walk around the garden.",
            duration_seconds=5.0,
        )
        assert isinstance(res, SpeechEmotionResult)
        assert 90.0 <= res.wpm <= 160.0
        assert res.primary_emotion in ("calm", "cheerful")
        assert 0.0 <= res.confidence <= 1.0
        assert res.cadence_label in ("Conversational Baseline", "Brisk (Engaged)", "Slow (Measured)")

    def test_fatigue_detection_from_speech_pattern(self) -> None:
        analyzer = SpeechEmotionAnalyzer()
        # Slow tempo (6 words over 8 seconds = 45 WPM), low energy, fatigue keywords
        res = analyzer.analyze(
            text="I am feeling so tired and exhausted today...",
            duration_seconds=8.0,
            audio_metrics={"avg_volume": 0.20, "pitch_variance": 0.20, "pause_ratio": 0.40},
        )
        assert res.primary_emotion == "fatigue"
        assert res.wpm < 105.0
        assert res.pitch_variance < 0.35
        assert "fatigue" in res.clinical_note.lower()

    def test_anxious_detection_from_speech_pattern(self) -> None:
        analyzer = SpeechEmotionAnalyzer()
        # Rapid tempo (18 words over 4 seconds = 270 WPM capped), high pitch variance, anxiety keywords
        res = analyzer.analyze(
            text="I am really worried and my heart is racing so fast what should I do right now please help",
            duration_seconds=4.0,
            audio_metrics={"avg_volume": 0.75, "pitch_variance": 0.80},
        )
        assert res.primary_emotion == "anxious"
        assert res.wpm > 150.0
        assert res.arousal > 0.50

    def test_cheerful_detection(self) -> None:
        analyzer = SpeechEmotionAnalyzer()
        res = analyzer.analyze(
            text="I had a wonderful morning and feeling great and fantastic today!",
            duration_seconds=4.0,
        )
        assert res.primary_emotion == "cheerful"
        assert res.valence > 0.20

    def test_baseline_drift_tracking(self) -> None:
        analyzer = SpeechEmotionAnalyzer(baseline_wpm=130.0)
        # Feed an extremely slow utterance
        res = analyzer.analyze(
            text="I am moving very slow today",
            duration_seconds=6.0,  # 6 words / 6s = 60 WPM
        )
        assert res.baseline_drift < -20.0  # At least 20% slower than baseline
        assert "slower than" in res.clinical_note

    def test_pcm_acoustic_extraction(self) -> None:
        import numpy as np

        analyzer = SpeechEmotionAnalyzer()
        # Generate dummy 16kHz sine wave PCM samples
        t = np.linspace(0, 1.0, 16000, False)
        sine = (np.sin(2 * np.pi * 440 * t) * 10000).astype(np.int16)
        raw_bytes = sine.tobytes()

        res = analyzer.analyze(
            text="Testing audio waveform acoustic extraction",
            duration_seconds=1.0,
            audio_chunk_samples=raw_bytes,
            sample_rate=16000,
        )
        assert res.rms_energy > 0.0
        assert res.pitch_variance > 0.0
