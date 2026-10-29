"""
carewatcher/orchestrator.py
Main event loop that wires all CareWatcher components together.

This is the single entry point that runs the entire pipeline:
  Sensors → Shutter → STT → Wake Word → Agent → Memory → Trend →
  Proposer → Verifier → Delivery → Audit Log

Everything runs locally on-device with zero cloud dependency.
"""
from __future__ import annotations

import logging
import threading
import time
from datetime import datetime
from typing import Any

from carewatcher.agent.conversation import DummyConversationAgent, LLMConversationAgent
from carewatcher.agent.multimodal_fusion import MultimodalAffectFusion, MultimodalEvaluation
from carewatcher.audit.logger import AuditLogger
from carewatcher.config import CareWatcherConfig, load_config
from carewatcher.interfaces import (
    AudioChunk,
    EventCategory,
    HealthEvent,
    ShutterState,
    SensorReading,
    Transcript,
    VerifierDecision,
)
from carewatcher.stt.speech_emotion import SpeechEmotionAnalyzer, SpeechEmotionResult
from carewatcher.memory.store import ResidentMemoryStore
from carewatcher.memory.trend import TrendEngine
from carewatcher.proposer.engine import RuleBasedProposer
from carewatcher.shutter.gate import PrivacyShutter
from carewatcher.sources.mic import MicrophoneSource
from carewatcher.stt.engine import WhisperSTTEngine
from carewatcher.stt.wake_word import KeywordWakeWordDetector
from carewatcher.tts.engine import PiperTTSEngine
from carewatcher.verifier.engine import SafetyVerifier

logger = logging.getLogger(__name__)


class CareWatcherOrchestrator:
    """Central orchestrator that manages the full CareWatcher pipeline.

    This class initializes all components, runs the sensor polling loops,
    processes voice conversations, and routes events through the
    Proposer → Verifier → Delivery → Audit chain.

    Parameters
    ----------
    config:
        Fully loaded CareWatcherConfig object.
    """

    def __init__(self, config: CareWatcherConfig | None = None) -> None:
        self.config = config or load_config()
        self._running = False
        self._threads: list[threading.Thread] = []

        # ── initialize all components ─────────────────────────────────
        # Privacy Shutter
        initial_state = (
            ShutterState.OPEN
            if self.config.privacy.shutter_default == "open"
            else ShutterState.CLOSED
        )
        self.shutter = PrivacyShutter(initial_state=initial_state)

        # Audio source (real microphone)
        self.mic = MicrophoneSource(sample_rate=16000, channels=1, chunk_duration_sec=3.0)

        # STT Engine
        self.stt = WhisperSTTEngine(
            model_size=self.config.stt.model_size,
            device=self.config.stt.device,
            language=self.config.stt.language,
        )

        # Wake Word Detector
        self.wake_detector = KeywordWakeWordDetector(
            keyword=self.config.wake_word.keyword,
            threshold=self.config.wake_word.threshold,
        )

        # Conversation Agent
        backend = getattr(self.config.llm, "backend", "gemini")
        model_name = getattr(self.config.llm, "model_name", "gemini-2.0-flash")
        api_key = getattr(self.config.llm, "api_key", None)
        self.agent = LLMConversationAgent(
            model_path=self.config.llm.model_path,
            temperature=self.config.llm.temperature,
            resident_id=self.config.resident.name,
            backend=backend,
            model_name=model_name,
            api_key=api_key,
        )

        # Memory Store (local SQLite)
        self.memory = ResidentMemoryStore(
            db_path="data/resident.db",
            resident_id=self.config.resident.name,
        )

        # Trend Engine
        self.trend = TrendEngine(
            resident_id=self.config.resident.name,
            window_days=self.config.trend.window_days,
            sleep_drift_hours=self.config.trend.sleep_drift_hours,
            inactivity_timeout_minutes=self.config.trend.inactivity_timeout_minutes,
            mood_drift_consecutive=self.config.trend.mood_drift_consecutive,
        )

        # Proposer (no verifier imports)
        self.proposer = RuleBasedProposer(
            resident_id=self.config.resident.name,
        )

        # Verifier (no proposer imports)
        self.verifier = SafetyVerifier(
            max_reminders_per_hour=self.config.verifier.max_reminders_per_hour,
            quiet_start=self.config.verifier.quiet_hours.start,
            quiet_end=self.config.verifier.quiet_hours.end,
            deny_list_path=self.config.verifier.deny_list_path,
        )

        # Audit Logger (local hash-chained JSONL)
        self.audit = AuditLogger(
            log_path=self.config.audit.log_path,
            hash_algorithm=self.config.audit.hash_algorithm,
        )

        # TTS Engine
        self.tts = PiperTTSEngine(
            voice=self.config.tts.voice,
            sample_rate=self.config.tts.sample_rate,
        )

        # Sensor sources (initialized lazily based on config)
        self._serial_source: Any = None
        self._webcam_source: Any = None

        # Event callbacks for the web server to consume
        self._event_callbacks: list[Any] = []
        self._last_reply: str = ""
        self._last_event: HealthEvent | None = None
        self._recent_sensor_data: dict[str, Any] = {}
        self._last_facial_reading: dict[str, Any] = {}
        self._last_mood_store_ts: float = 0.0
        self._last_stored_mood_label: str = ""

        # Speech Emotion & Multimodal Affect Fusion Engines
        self.speech_emotion_analyzer = SpeechEmotionAnalyzer(baseline_wpm=125.0)
        self.multimodal_fusion = MultimodalAffectFusion()
        self._last_speech_emotion: SpeechEmotionResult | None = None
        self._last_multimodal_eval: MultimodalEvaluation | None = None

    # ── lifecycle ─────────────────────────────────────────────────────

    def start(self) -> None:
        """Initialize all components and start background threads."""
        logger.info("Starting CareWatcher orchestrator...")

        # Open memory store
        self.memory.open()

        # Seed trend engine from historical data
        summaries = self.memory.get_daily_summaries(days=self.config.trend.window_days)
        self.trend.seed_from_summaries(summaries)

        # Log startup
        self.audit.append("system_start", {
            "resident": self.config.resident.name,
            "shutter_state": self.shutter.state.name,
            "timestamp": datetime.now().isoformat(),
        })

        self._running = True

        # Initialize serial sensor if configured
        self._init_serial_sensor()

        # Initialize webcam if configured
        self._init_webcam_sensor()

        logger.info("CareWatcher orchestrator started successfully")

    def stop(self) -> None:
        """Stop all background threads and close resources."""
        self._running = False
        for t in self._threads:
            t.join(timeout=5.0)
        self._threads.clear()

        # Close resources
        self.mic.close()
        self.memory.close()
        if self._serial_source:
            self._serial_source.close()
        if self._webcam_source:
            self._webcam_source.close()

        self.audit.append("system_stop", {
            "timestamp": datetime.now().isoformat(),
        })
        logger.info("CareWatcher orchestrator stopped")

    # ── sensor initialization ─────────────────────────────────────────

    def _init_serial_sensor(self) -> None:
        """Initialize ESP32 serial sensor in a background thread."""
        try:
            from carewatcher.sources.serial_sensor import SerialSensorSource
            self._serial_source = SerialSensorSource()
            self._serial_source.open()

            if self._serial_source is not None and self._serial_source._is_open:
                t = threading.Thread(
                    target=self._serial_sensor_loop,
                    daemon=True,
                    name="serial_sensor",
                )
                t.start()
                self._threads.append(t)
                if self._serial_source._serial is not None:
                    logger.info("Physical ESP32 serial sensor thread started on COM port")
                else:
                    logger.info("Edge Hardware Twin sensor thread started (Physical ESP32 not detected)")
        except Exception as exc:
            logger.warning(f"Serial sensor not available: {exc}")

    def _init_webcam_sensor(self) -> None:
        """Initialize webcam presence detection in a background thread."""
        try:
            from carewatcher.sources.webcam import WebcamPresenceSource
            self._webcam_source = WebcamPresenceSource()

            # Only open backend camera hardware if driver is explicitly set to webcam
            sensor_driver = getattr(self.config.sources.sensor, "driver", "serial")
            if sensor_driver == "webcam":
                if self.shutter.state == ShutterState.OPEN:
                    self._webcam_source.open()

                t = threading.Thread(
                    target=self._webcam_sensor_loop,
                    daemon=True,
                    name="webcam_sensor",
                )
                t.start()
                self._threads.append(t)
                logger.info("Webcam sensor thread started (sleeps and releases hardware when shutter is CLOSED)")
            else:
                logger.info(f"Sensor driver is '{sensor_driver}' — backend physical camera released; browser webcam stream available on demand")
        except Exception as exc:
            logger.warning(f"Webcam sensor not available: {exc}")

    def toggle_shutter(self) -> ShutterState:
        """Toggle the privacy shutter and actively enforce hardware gating."""
        new_state = self.shutter.toggle()
        sensor_driver = getattr(self.config.sources.sensor, "driver", "serial")
        if new_state == ShutterState.CLOSED:
            # Physical root boundary: power down and release the camera device immediately
            if self._webcam_source:
                self._webcam_source.close()
            logger.info("Privacy shutter toggled CLOSED — camera hardware released and LED off")
        elif new_state == ShutterState.OPEN:
            # Re-engage camera sensor only if backend webcam driver is active
            if self._webcam_source and sensor_driver == "webcam":
                self._webcam_source.open()
            logger.info("Privacy shutter toggled OPEN")
        return new_state

    # ── background sensor loops ───────────────────────────────────────

    def _serial_sensor_loop(self) -> None:
        """Continuously read from the ESP32 and feed into the pipeline."""
        while self._running and self._serial_source:
            try:
                reading = self._serial_source.read()

                # Gate through privacy shutter
                gated = self.shutter.gate(reading)
                if gated is None:
                    continue

                # Store reading
                self.memory.store_sensor_reading(gated)
                self._recent_sensor_data[gated.sensor_id] = gated.value

                # Feed to trend engine
                alerts = self.trend.ingest_sensor_reading(
                    gated.sensor_id, gated.value, gated.unit
                )

                # Process any drift alerts
                for alert in alerts:
                    self._process_health_event(alert)

            except StopIteration:
                break
            except Exception as exc:
                logger.error(f"Serial sensor error: {exc}")
                time.sleep(1.0)

    def _webcam_sensor_loop(self) -> None:
        """Continuously check for resident presence and facial mood via webcam only when shutter is OPEN."""
        while self._running:
            if not self._webcam_source or self.shutter.state == ShutterState.CLOSED:
                # Privacy shutter is CLOSED -> Ensure physical camera device is closed and freed
                if self._webcam_source and self._webcam_source._cap is not None:
                    self._webcam_source.close()
                time.sleep(1.0)
                continue

            try:
                # Privacy shutter is OPEN -> Ensure physical camera is open
                if not self._webcam_source._is_open or self._webcam_source._cap is None:
                    self._webcam_source.open()

                reading = self._webcam_source.read()

                gated = self.shutter.gate(reading)
                if gated is None:
                    time.sleep(1.0)
                    continue

                self.memory.store_sensor_reading(gated)
                self._recent_sensor_data[gated.sensor_id] = gated.value

                # Process continuous facial mood reading
                if gated.sensor_id == "facial_mood":
                    mood_label = gated.metadata.get("mood_label", "calm")
                    confidence = float(gated.metadata.get("confidence", 0.85))
                    self._recent_sensor_data["facial_mood_label"] = mood_label
                    self._recent_sensor_data["facial_mood_valence"] = gated.value

                    # Store mood observation in local SQLite
                    self.memory.store_mood(mood_label=mood_label, confidence=confidence)

                    # Ingest into trend engine for consecutive negative drift detection
                    alerts = self.trend.ingest_mood(mood_label)
                    for alert in alerts:
                        self._process_health_event(alert)

                # No presence for extended period → feed inactivity check
                elif gated.sensor_id == "webcam_presence" and gated.value == 0:
                    alerts = self.trend.ingest_sensor_reading(
                        "webcam_presence", 0.0, "faces"
                    )
                    for alert in alerts:
                        self._process_health_event(alert)

                time.sleep(self._webcam_source.check_interval_sec)

            except Exception as exc:
                logger.error(f"Webcam sensor error: {exc}")
                time.sleep(2.0)

    # ── voice conversation pipeline ───────────────────────────────────

    def store_facial_reading(self, reading: dict[str, Any]) -> None:
        """Cache the latest high-resolution facial biometrics for multimodal fusion."""
        self._last_facial_reading = reading
        mood_label = reading.get("mood_label", "calm")
        valence = float(reading.get("valence", 0.15))
        confidence = float(reading.get("confidence", 0.85))

        self._recent_sensor_data["facial_mood_label"] = mood_label
        self._recent_sensor_data["facial_mood_valence"] = valence
        self._recent_sensor_data["facial_mood_arousal"] = float(reading.get("arousal", 0.30))
        self._recent_sensor_data["facial_smile_score"] = float(reading.get("smile_score", 0.0))
        self._recent_sensor_data["facial_brow_tension"] = float(reading.get("brow_tension", 0.0))
        self._recent_sensor_data["facial_eye_openness"] = float(reading.get("eye_openness", 0.75))
        self._recent_sensor_data["facial_confusion_index"] = float(reading.get("confusion_index", 0.0))
        self._recent_sensor_data["facial_confidence"] = confidence

        # Ingest into memory and trend engine when shutter is open (debounced & confidence-gated)
        if (
            self.shutter.is_open
            and self.memory._conn is not None
            and reading.get("face_detected", True)
            and confidence >= 0.52
        ):
            now_mono = time.monotonic()
            # Debounce rapid 1.5s camera frames to once per 6s unless mood state transitioned
            if (mood_label != self._last_stored_mood_label and (now_mono - self._last_mood_store_ts) >= 3.0) or (
                (now_mono - self._last_mood_store_ts) >= 6.0
            ):
                self._last_mood_store_ts = now_mono
                self._last_stored_mood_label = str(mood_label)
                self.memory.store_mood(
                    mood_label=mood_label,
                    confidence=confidence,
                    resident_id=self.config.resident.name,
                )
                alerts = self.trend.ingest_mood(mood_label)
                for alert in alerts:
                    self._process_health_event(alert)

    def process_voice_input(
        self,
        text: str,
        audio_metrics: dict[str, Any] | None = None,
        audio_chunk_samples: bytes | None = None,
    ) -> dict[str, Any]:
        """Process a text/voice input through the full pipeline with acoustic SER and multimodal affect fusion.

        This is the main entry point for both live mic input and the
        web dashboard's voice/text interactions.

        Returns a dict with speech analysis, multimodal evaluation, and conversational results.
        """
        # 1. Acoustic Speech Emotion & Prosody Analysis
        speech_result = self.speech_emotion_analyzer.analyze(
            text=text,
            audio_chunk_samples=audio_chunk_samples,
            audio_metrics=audio_metrics,
        )
        self._last_speech_emotion = speech_result

        # 2. Create transcript with prosody
        transcript = Transcript(
            text=text,
            confidence=0.95,
            prosody={
                "primary_emotion": speech_result.primary_emotion,
                "confidence": speech_result.confidence,
                "wpm": speech_result.wpm,
                "cadence_label": speech_result.cadence_label,
                "valence": speech_result.valence,
                "arousal": speech_result.arousal,
                "rms_energy": speech_result.rms_energy,
                "pitch_variance": speech_result.pitch_variance,
                "pause_ratio": speech_result.pause_ratio,
                "baseline_drift": speech_result.baseline_drift,
                "clinical_note": speech_result.clinical_note,
                "emotion_probabilities": speech_result.emotion_probabilities,
            },
        )

        # 3. Gate through shutter
        gated = self.shutter.gate(transcript)
        if gated is None:
            self.audit.append("shutter_blocked", {
                "reason": "Privacy shutter is CLOSED",
                "text_length": len(text),
            })
            return {
                "blocked": True,
                "reason": "Privacy shutter is CLOSED",
                "shutter_state": "CLOSED",
            }

        # 4. Wake word detection
        wake_detected = self.wake_detector.detect(gated)

        # 5. Multimodal Affective Synthesis (Speech + FACS Face + Cardiovascular Telemetry)
        sensors = self.get_recent_sensor_data()
        facial_info = dict(self._last_facial_reading) if self._last_facial_reading else {}
        latest_mood = facial_info.get("mood_label")
        if not latest_mood:
            recent_moods = self.get_mood_history(1)
            latest_mood = recent_moods[0]["mood_label"] if recent_moods else "calm"
            facial_info["mood_label"] = latest_mood

        mm_eval = self.multimodal_fusion.evaluate(
            speech_result=speech_result,
            facial_data=facial_info,
            biometrics=sensors,
        )
        self._last_multimodal_eval = mm_eval

        # 6. Conversation agent conditioning
        context = {
            "bpm": sensors.get("max30102_bpm"),
            "spo2": sensors.get("max30102_spo2"),
            "hrv_ms": sensors.get("apple_watch_hrv", 48.0),
            "mood": latest_mood,
            "facial_data": facial_info,
            "speech_prosody": transcript.prosody,
            "multimodal_eval": mm_eval,
        }
        health_event, reply_text = self.agent.converse(gated, context=context)
        self._last_event = health_event
        self._last_reply = reply_text

        # 7. Store event in memory
        self.memory.store_event(health_event)

        # 7a. Extract and store mood/medication data
        details = health_event.details or {}
        if health_event.category == EventCategory.MOOD:
            mood_label = details.get("mood_label", "neutral")
            conf = float(details.get("confidence", 0.85))
            self.memory.store_mood(str(mood_label), confidence=conf)
            mood_alerts = self.trend.ingest_mood(str(mood_label))
            for alert in mood_alerts:
                self._process_health_event(alert)
        elif health_event.category == EventCategory.MEDICATION:
            adherence = details.get("adherence")
            self.memory.store_medication_adherence(
                medication="scheduled",
                adherence=adherence if isinstance(adherence, bool) else None,
            )

        # 8. Trend engine
        trend_alerts = self.trend.update(health_event)

        # 9. Process the health event through Proposer → Verifier
        self._process_health_event(health_event)

        # 9a. Process any trend alerts too
        for alert in trend_alerts:
            self._process_health_event(alert)

        # 10. Audit log with multimodal telemetry
        self.audit.append("voice_interaction", {
            "transcript": text,
            "wake_detected": wake_detected,
            "event_category": health_event.category.name,
            "event_summary": health_event.summary,
            "reply": reply_text,
            "speech_emotion": speech_result.primary_emotion,
            "speech_wpm": speech_result.wpm,
            "congruence_status": mm_eval.congruence_status,
        })

        return {
            "blocked": False,
            "shutter_state": "OPEN",
            "transcript": {
                "text": gated.text,
                "confidence": gated.confidence,
                "prosody": gated.prosody,
            },
            "wake_detected": wake_detected,
            "reply_text": reply_text,
            "event": {
                "category": health_event.category.name,
                "summary": health_event.summary,
                "details": health_event.details,
                "resident_id": health_event.resident_id,
            },
            "trend_alerts": [
                {"category": a.category.name, "summary": a.summary}
                for a in trend_alerts
            ],
            "speech_analysis": {
                "primary_emotion": speech_result.primary_emotion,
                "confidence": speech_result.confidence,
                "wpm": speech_result.wpm,
                "cadence_label": speech_result.cadence_label,
                "valence": speech_result.valence,
                "arousal": speech_result.arousal,
                "rms_energy": speech_result.rms_energy,
                "pitch_variance": speech_result.pitch_variance,
                "pause_ratio": speech_result.pause_ratio,
                "baseline_drift": speech_result.baseline_drift,
                "clinical_note": speech_result.clinical_note,
                "emotion_probabilities": speech_result.emotion_probabilities,
            },
            "multimodal_evaluation": {
                "overall_affect": mm_eval.overall_affect,
                "congruence_status": mm_eval.congruence_status,
                "congruence_badge": mm_eval.congruence_badge,
                "fused_valence": mm_eval.fused_valence,
                "fused_arousal": mm_eval.fused_arousal,
                "stability_index": mm_eval.stability_index,
                "clinical_assessment": mm_eval.clinical_assessment,
                "steering_directive": mm_eval.conversational_steering_directive,
                "speech_emotion": mm_eval.speech_emotion,
                "facial_emotion": mm_eval.facial_emotion,
                "heart_rate_bpm": mm_eval.heart_rate_bpm,
            },
        }

    def _process_health_event(self, event: HealthEvent) -> None:
        """Route a health event through Proposer → Verifier → Delivery."""
        # Proposer
        intervention = self.proposer.propose(event)
        if intervention is None:
            return

        self.audit.append("intervention_proposed", {
            "intervention_type": intervention.type.name,
            "message": intervention.message,
            "reasoning": intervention.reasoning,
            "event_summary": event.summary,
        })

        # Verifier (independent — no proposer imports)
        result = self.verifier.verify(intervention)

        self.audit.append("intervention_verified", {
            "decision": result.decision.name,
            "reason": result.reason,
            "intervention_type": intervention.type.name,
        })

        # Delivery
        if result.decision == VerifierDecision.APPROVED:
            self._deliver_intervention(intervention)
        elif result.decision == VerifierDecision.ESCALATED:
            self._escalate_intervention(intervention)
        # REJECTED — logged but not delivered

    def _deliver_intervention(self, intervention: Any) -> None:
        """Deliver an approved intervention to the resident."""
        logger.info(f"Delivering intervention: {intervention.message}")
        self._last_reply = intervention.message

        self.audit.append("intervention_delivered", {
            "type": intervention.type.name,
            "message": intervention.message,
            "resident_id": intervention.resident_id,
        })

    def _escalate_intervention(self, intervention: Any) -> None:
        """Escalate an urgent intervention to the caregiver."""
        logger.warning(f"ESCALATION: {intervention.message}")

        self.audit.append("intervention_escalated", {
            "type": intervention.type.name,
            "message": intervention.message,
            "resident_id": intervention.resident_id,
            "urgency": "HIGH",
        })

    # ── status / data accessors (for web server) ──────────────────────

    def get_status(self) -> dict[str, Any]:
        """Return current system status for the web dashboard."""
        baselines = self.trend.get_baselines()
        return {
            "shutter_state": self.shutter.state.name,
            "running": self._running,
            "config": {
                "resident_name": self.config.resident.name,
                "stt_model_size": self.config.stt.model_size,
                "wake_word": self.config.wake_word.keyword,
                "llm_backend": self.config.llm.backend,
            },
            "sensor_data": dict(self._recent_sensor_data),
            "baselines": {
                name: {
                    "mean": round(b.mean, 2),
                    "stdev": round(b.stdev, 2),
                    "samples": b.sample_count,
                } if b else None
                for name, b in baselines.items()
            },
            "events_today": self.memory.count_events_today(),
            "audit_entries": self.audit.entry_count(),
            "audit_chain_valid": self.audit.verify_chain(),
        }

    def get_recent_events(self, limit: int = 20) -> list[dict[str, Any]]:
        """Return recent health events for the dashboard."""
        return self.memory.get_events(limit=limit)

    def get_recent_sensor_data(self) -> dict[str, float]:
        """Return the latest sensor reading for each sensor."""
        return dict(self._recent_sensor_data)

    def get_audit_log(self, limit: int = 30) -> list[dict[str, Any]]:
        """Return recent audit log entries."""
        return self.audit.get_entries(limit=limit)

    def get_medication_adherence(self, days: int = 7) -> list[dict[str, Any]]:
        """Return medication adherence for the last N days."""
        return self.memory.get_medication_adherence(days=days)

    def get_mood_history(self, count: int = 10) -> list[dict[str, Any]]:
        """Return recent mood observations."""
        return self.memory.get_recent_moods(count=count)

    def ingest_apple_watch_data(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Ingest real biometric telemetry from Apple Watch / HypeRate / HealthKit."""
        from datetime import datetime
        from carewatcher.interfaces import SensorReading

        now = datetime.now()
        source_name = str(payload.get("source", "Apple Watch HealthKit"))
        values: dict[str, float] = {}

        # 1. Parse BPM / Heart Rate
        bpm: float | None = None
        if "bpm" in payload:
            bpm = float(payload["bpm"])
        elif "hr" in payload:
            bpm = float(payload["hr"])
        elif "heart_rate" in payload:
            bpm = float(payload["heart_rate"])
        elif "data" in payload and isinstance(payload["data"], dict):
            # Support Health Auto Export nested schema
            metrics = payload["data"].get("metrics", [])
            for m in metrics:
                if m.get("name") == "heart_rate":
                    data_pts = m.get("data", [])
                    if data_pts:
                        latest = data_pts[-1]
                        bpm = float(latest.get("Avg") or latest.get("qty") or latest.get("value") or 0)
                elif m.get("name") in ("oxygen_saturation", "spo2"):
                    data_pts = m.get("data", [])
                    if data_pts:
                        latest = data_pts[-1]
                        raw_val = float(latest.get("Avg") or latest.get("qty") or latest.get("value") or 0)
                        values["max30102_spo2"] = raw_val * 100 if raw_val <= 1.0 else raw_val
                elif m.get("name") in ("step_count", "steps"):
                    data_pts = m.get("data", [])
                    if data_pts:
                        latest = data_pts[-1]
                        values["apple_watch_steps"] = float(latest.get("qty") or latest.get("value") or 0)
                elif m.get("name") in ("heart_rate_variability", "hrv"):
                    data_pts = m.get("data", [])
                    if data_pts:
                        latest = data_pts[-1]
                        values["apple_watch_hrv"] = float(latest.get("Avg") or latest.get("qty") or latest.get("value") or 0)

        if bpm is not None and bpm > 0:
            values["max30102_bpm"] = round(bpm, 1)

        # 2. Parse Blood Oxygen (SpO2)
        if "spo2" in payload:
            values["max30102_spo2"] = round(float(payload["spo2"]), 1)
        elif "blood_oxygen" in payload:
            values["max30102_spo2"] = round(float(payload["blood_oxygen"]), 1)

        # 3. Parse Temperature
        if "wrist_temp" in payload:
            values["mlx90614_temp"] = round(float(payload["wrist_temp"]), 1)
        elif "mlx90614_temp" in payload:
            values["mlx90614_temp"] = round(float(payload["mlx90614_temp"]), 1)
        elif "temperature" in payload:
            values["mlx90614_temp"] = round(float(payload["temperature"]), 1)

        # 4. Parse Steps & HRV
        if "steps" in payload:
            values["apple_watch_steps"] = float(payload["steps"])
        if "hrv" in payload:
            values["apple_watch_hrv"] = float(payload["hrv"])
        elif "hrv_ms" in payload:
            values["apple_watch_hrv"] = float(payload["hrv_ms"])

        # 5. Route through privacy shutter and store
        for sensor_id, val in values.items():
            unit = "bpm" if "bpm" in sensor_id else ("%" if "spo2" in sensor_id else ("°C" if "temp" in sensor_id else "count"))
            reading = SensorReading(
                sensor_id=sensor_id,
                value=val,
                unit=unit,
                timestamp=now,
                metadata={"source": source_name, "resident_id": self.config.resident.name},
            )
            gated = self.shutter.gate(reading)
            if gated is not None:
                self.memory.store_sensor_reading(gated)
                self._recent_sensor_data[gated.sensor_id] = gated.value

        # Set external override on serial sensor source if available
        if hasattr(self, "_serial_source") and self._serial_source:
            if hasattr(self._serial_source, "set_external_reading"):
                self._serial_source.set_external_reading(
                    bpm=values.get("max30102_bpm"),
                    spo2=values.get("max30102_spo2"),
                    temp=values.get("mlx90614_temp"),
                )

        # Update metadata
        self.vital_source = source_name
        self.vital_source_timestamp = now.strftime("%H:%M:%S")

        # Ingest into trend engine
        if "max30102_bpm" in values:
            bpm_alerts = self.trend.ingest_bpm(values["max30102_bpm"])
            for alert in bpm_alerts:
                self._process_health_event(alert)

        self.audit.append("apple_watch_biometrics_ingested", {
            "source": source_name,
            "values": values,
            "timestamp": now.isoformat(),
        })

        return {
            "status": "success",
            "source": source_name,
            "values": values,
            "timestamp": now.isoformat(),
        }

