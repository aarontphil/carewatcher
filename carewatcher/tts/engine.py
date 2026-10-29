"""
carewatcher/tts/engine.py
Local text-to-speech engine implementations.

Provides a Piper TTS wrapper for fully offline speech synthesis,
plus a fallback that uses the Web Speech API (browser-side) or
the Windows SAPI via pyttsx3.
"""
from __future__ import annotations

import io
import subprocess
import tempfile
import wave
from pathlib import Path
from typing import Any


class PiperTTSEngine:
    """Offline TTS using Piper (a fast, local neural TTS engine).

    Piper runs entirely on-device — no cloud, no network.
    Models are downloaded once and stored locally.

    Parameters
    ----------
    voice:
        Piper voice identifier (e.g., 'en_US-lessac-medium').
    sample_rate:
        Output audio sample rate.
    model_dir:
        Directory where Piper voice models are stored.
    """

    def __init__(
        self,
        voice: str = "en_US-lessac-medium",
        sample_rate: int = 22050,
        model_dir: str = "models/piper",
    ) -> None:
        self.voice = voice
        self.sample_rate = sample_rate
        self.model_dir = Path(model_dir)
        self._piper_available: bool | None = None

    def _check_piper(self) -> bool:
        """Check if piper-tts is available."""
        if self._piper_available is not None:
            return self._piper_available
        try:
            import piper  # type: ignore[import-not-found]
            self._piper_available = True
        except ImportError:
            self._piper_available = False
        return self._piper_available

    def speak(self, text: str) -> bytes | None:
        """Convert text to speech and return WAV audio bytes.

        Returns None if Piper is not installed (caller should use fallback).
        """
        if not text or not text.strip():
            return None

        if not self._check_piper():
            return self._fallback_speak(text)

        try:
            import piper  # type: ignore[import-not-found]

            model_path = self.model_dir / f"{self.voice}.onnx"
            config_path = self.model_dir / f"{self.voice}.onnx.json"

            if not model_path.exists():
                # Model not downloaded yet — use fallback
                return self._fallback_speak(text)

            voice = piper.PiperVoice.load(str(model_path), str(config_path))

            # Synthesize to WAV bytes
            wav_buffer = io.BytesIO()
            with wave.open(wav_buffer, "wb") as wav_file:
                voice.synthesize(text, wav_file)

            return wav_buffer.getvalue()

        except Exception:
            return self._fallback_speak(text)

    def speak_to_file(self, text: str, output_path: str) -> bool:
        """Convert text to speech and save as a WAV file.

        Returns True if successful, False otherwise.
        """
        audio_bytes = self.speak(text)
        if audio_bytes is None:
            return False

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(audio_bytes)
        return True

    def _fallback_speak(self, text: str) -> bytes | None:
        """Fallback TTS using pyttsx3 (Windows SAPI) or espeak.

        Returns WAV bytes or None if no TTS engine is available.
        """
        try:
            import pyttsx3  # type: ignore[import-not-found]

            engine = pyttsx3.init()
            engine.setProperty("rate", 150)
            engine.setProperty("volume", 0.9)

            # Save to a temp WAV file
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp_path = tmp.name

            engine.save_to_file(text, tmp_path)
            engine.runAndWait()

            wav_data = Path(tmp_path).read_bytes()
            Path(tmp_path).unlink(missing_ok=True)
            return wav_data

        except (ImportError, Exception):
            pass

        # Last resort: return None and let the web UI use browser SpeechSynthesis
        return None


class BrowserTTSEngine:
    """Placeholder for browser-side TTS via Web Speech API.

    This doesn't generate audio on the server — instead, the server sends
    the text to the frontend, which uses the browser's built-in
    SpeechSynthesis API to speak it aloud.

    This is already implemented in web/app.js (speakReply function).
    """

    def speak(self, text: str) -> dict[str, str]:
        """Return the text payload for the browser to speak.

        The server sends this as JSON; the frontend's speakReply() handles it.
        """
        return {"action": "speak", "text": text}
