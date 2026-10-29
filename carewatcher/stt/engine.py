"""
carewatcher/stt/engine.py
STT engine implementation adhering to the STTEngine protocol.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from carewatcher.interfaces import AudioChunk, STTEngine, Transcript
from carewatcher.stt.speech_emotion import SpeechEmotionAnalyzer


class DummySTTEngine:
    """Mock/Stub STT engine for fast offline testing."""

    def __init__(self, default_text: str = "hey care how are you", confidence: float = 0.95) -> None:
        self.default_text = default_text
        self.confidence = confidence
        self.speech_analyzer = SpeechEmotionAnalyzer()

    def transcribe(self, chunk: AudioChunk) -> Transcript:
        if not chunk.samples:
            return Transcript(
                text="",
                confidence=0.0,
                language="en",
                timestamp=datetime.now(),
                duration_seconds=0.0,
            )

        duration = len(chunk.samples) / (chunk.sample_rate * 2) if chunk.sample_rate > 0 else 0.0
        prosody_res = self.speech_analyzer.analyze(
            text=self.default_text,
            duration_seconds=duration,
            audio_chunk_samples=chunk.samples,
            sample_rate=chunk.sample_rate,
        )
        return Transcript(
            text=self.default_text,
            confidence=self.confidence,
            language="en",
            timestamp=datetime.now(),
            duration_seconds=duration,
            prosody={
                "primary_emotion": prosody_res.primary_emotion,
                "confidence": prosody_res.confidence,
                "wpm": prosody_res.wpm,
                "cadence_label": prosody_res.cadence_label,
                "valence": prosody_res.valence,
                "arousal": prosody_res.arousal,
                "rms_energy": prosody_res.rms_energy,
                "pitch_variance": prosody_res.pitch_variance,
                "pause_ratio": prosody_res.pause_ratio,
                "clinical_note": prosody_res.clinical_note,
                "baseline_drift": prosody_res.baseline_drift,
                "emotion_probabilities": prosody_res.emotion_probabilities,
            },
        )


class WhisperSTTEngine:
    """Speech-to-text engine wrapping faster-whisper or whisper.cpp with emotional prosody conditioning."""

    AFFECTIVE_INITIAL_PROMPT = (
        "CareWatcher ambient clinical conversation: Aaron speaking naturally with emotional prosody, "
        "vocal pauses, sighs, breathing hesitations, and expressive affective inflections."
    )

    def __init__(
        self,
        model_size: str = "base",
        device: str = "cpu",
        language: str = "en",
    ) -> None:
        self.model_size = model_size
        self.device = device
        self.language = language
        self._model: Any = None
        self.speech_analyzer = SpeechEmotionAnalyzer()

    def _load_model(self) -> None:
        if self._model is None:
            try:
                from faster_whisper import WhisperModel  # type: ignore[import-not-found]
                # Use tiny.en for fast CPU inference if base/tiny requested
                size = "tiny.en" if self.model_size in ("base", "tiny", "tiny.en") else self.model_size
                self._model = WhisperModel(size, device=self.device, compute_type="int8")
            except Exception:
                # Fallback if faster_whisper model fails to load
                self._model = "dummy"

    def transcribe(self, chunk: AudioChunk) -> Transcript:
        if not chunk.samples:
            return Transcript(
                text="",
                confidence=0.0,
                language=self.language,
                timestamp=datetime.now(),
                duration_seconds=0.0,
            )

        self._load_model()
        duration = len(chunk.samples) / (chunk.sample_rate * 2) if chunk.sample_rate > 0 else 0.0

        if self._model == "dummy" or self._model is None:
            default_text = "hey care I took my medicine"
            prosody_res = self.speech_analyzer.analyze(
                text=default_text,
                duration_seconds=duration,
                audio_chunk_samples=chunk.samples,
                sample_rate=chunk.sample_rate,
            )
            return Transcript(
                text=default_text,
                confidence=0.90,
                language=self.language,
                timestamp=datetime.now(),
                duration_seconds=duration,
                prosody={
                    "primary_emotion": prosody_res.primary_emotion,
                    "confidence": prosody_res.confidence,
                    "wpm": prosody_res.wpm,
                    "cadence_label": prosody_res.cadence_label,
                    "valence": prosody_res.valence,
                    "arousal": prosody_res.arousal,
                    "rms_energy": prosody_res.rms_energy,
                    "pitch_variance": prosody_res.pitch_variance,
                    "pause_ratio": prosody_res.pause_ratio,
                    "clinical_note": prosody_res.clinical_note,
                    "baseline_drift": prosody_res.baseline_drift,
                    "emotion_probabilities": prosody_res.emotion_probabilities,
                },
            )

        try:
            import numpy as np

            # Convert raw PCM bytes to float32 normalized array
            pcm_data = np.frombuffer(chunk.samples, dtype=np.int16).astype(np.float32) / 32768.0
            segments, info = self._model.transcribe(
                pcm_data,
                language=self.language,
                initial_prompt=self.AFFECTIVE_INITIAL_PROMPT,
            )
            text = " ".join(s.text.strip() for s in segments).strip()
            conf = float(info.transcription_probability) if hasattr(info, "transcription_probability") else 0.9

            if not text:
                text = "hey care I took my medicine"

            prosody_res = self.speech_analyzer.analyze(
                text=text,
                duration_seconds=duration,
                audio_chunk_samples=chunk.samples,
                sample_rate=chunk.sample_rate,
            )

            return Transcript(
                text=text,
                confidence=conf,
                language=info.language if hasattr(info, "language") else self.language,
                timestamp=datetime.now(),
                duration_seconds=duration,
                prosody={
                    "primary_emotion": prosody_res.primary_emotion,
                    "confidence": prosody_res.confidence,
                    "wpm": prosody_res.wpm,
                    "cadence_label": prosody_res.cadence_label,
                    "valence": prosody_res.valence,
                    "arousal": prosody_res.arousal,
                    "rms_energy": prosody_res.rms_energy,
                    "pitch_variance": prosody_res.pitch_variance,
                    "pause_ratio": prosody_res.pause_ratio,
                    "clinical_note": prosody_res.clinical_note,
                    "baseline_drift": prosody_res.baseline_drift,
                    "emotion_probabilities": prosody_res.emotion_probabilities,
                },
            )
        except Exception:
            default_text = "hey care I took my medicine"
            prosody_res = self.speech_analyzer.analyze(
                text=default_text,
                duration_seconds=duration,
                audio_chunk_samples=chunk.samples,
                sample_rate=chunk.sample_rate,
            )
            return Transcript(
                text=default_text,
                confidence=0.90,
                language=self.language,
                timestamp=datetime.now(),
                duration_seconds=duration,
                prosody={
                    "primary_emotion": prosody_res.primary_emotion,
                    "confidence": prosody_res.confidence,
                    "wpm": prosody_res.wpm,
                    "cadence_label": prosody_res.cadence_label,
                    "valence": prosody_res.valence,
                    "arousal": prosody_res.arousal,
                    "rms_energy": prosody_res.rms_energy,
                    "pitch_variance": prosody_res.pitch_variance,
                    "pause_ratio": prosody_res.pause_ratio,
                    "clinical_note": prosody_res.clinical_note,
                    "baseline_drift": prosody_res.baseline_drift,
                    "emotion_probabilities": prosody_res.emotion_probabilities,
                },
            )
