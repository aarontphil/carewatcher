"""
tests/test_mood.py — Unit tests for continuous facial mood detection,
affect metrics, and trend drift alerting.
"""
from __future__ import annotations

import numpy as np
import pytest

from carewatcher.interfaces import EventCategory, HealthEvent, SensorReading
from carewatcher.memory.trend import TrendEngine
from carewatcher.sources.webcam import WebcamPresenceSource
from carewatcher.vision.facial_mood import FacialMoodDetector, FacialMoodReading


class TestFacialMoodDetector:
    def test_detector_initialization(self) -> None:
        detector = FacialMoodDetector()
        assert detector.history_size == 5

    def test_empty_frame_returns_baseline(self) -> None:
        detector = FacialMoodDetector()
        blank_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        reading = detector.analyze_frame(blank_frame)
        assert isinstance(reading, FacialMoodReading)
        assert reading.face_detected is False
        assert reading.mood_label == "calm"
        assert -1.0 <= reading.valence <= 1.0
        assert 0.0 <= reading.arousal <= 1.0

    def test_synthetic_smiling_face_detection(self) -> None:
        import cv2
        detector = FacialMoodDetector()
        img = np.zeros((300, 300, 3), dtype=np.uint8)
        # Draw a synthetic face circle
        cv2.circle(img, (150, 150), 90, (200, 200, 200), -1)
        reading = detector.analyze_frame(img)
        assert isinstance(reading, FacialMoodReading)
        assert -1.0 <= reading.valence <= 1.0

    def test_discomfort_and_pain_sensitivity_suppression_on_neutral_face(self) -> None:
        import cv2
        detector = FacialMoodDetector()
        img = np.zeros((300, 300, 3), dtype=np.uint8)
        # Neutral face circle with soft facial contours
        cv2.circle(img, (150, 150), 90, (180, 180, 180), -1)
        reading = detector.analyze_frame(img)
        assert reading.discomfort_index == 0.0
        # Pain probability should be strongly suppressed on resting neutral face (< 5%)
        assert reading.emotion_probabilities.get("pain", 0.0) < 0.05
        assert reading.mood_label != "pain"

    def test_facial_mood_guardrail_prevents_false_pain_without_sustained_discomfort(self) -> None:
        detector = FacialMoodDetector()
        assert len(detector._discomfort_history) == 0
        detector._discomfort_history.append(0.10)
        # With low discomfort, guardrail guarantees mood_label cannot be pain
        blank_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        reading = detector.analyze_frame(blank_frame)
        assert reading.mood_label != "pain"
        assert reading.discomfort_index == 0.0

    def test_smile_detection_triggers_happy_and_suppresses_pain(self) -> None:
        detector = FacialMoodDetector()
        # Preload smile history showing user smiling
        detector._smile_history.append(0.65)
        detector._mood_history.append("happy")
        assert detector.smile_threshold == 0.25

    @staticmethod
    def _render_realistic_face(
        bangs: bool = False,
        glasses: bool = False,
        side_light: bool = False,
        beard: bool = False,
        smile: bool = False,
        closed_eyes: bool = False,
        surprised: bool = False,
    ) -> np.ndarray:
        import cv2

        img = np.full((360, 480, 3), (225, 225, 225), dtype=np.uint8)
        cv2.ellipse(img, (240, 185), (86, 112), 0, 0, 360, (142, 174, 218), -1)
        cv2.ellipse(img, (240, 128), (58, 22), 0, 0, 360, (158, 190, 232), -1)
        cv2.ellipse(img, (198, 200), (24, 16), 0, 0, 360, (155, 186, 228), -1)
        cv2.ellipse(img, (282, 200), (24, 16), 0, 0, 360, (155, 186, 228), -1)
        cv2.ellipse(img, (240, 92), (90, 38), 0, 180, 360, (30, 35, 45), -1)
        if bangs:
            for bx in range(175, 305, 14):
                cv2.line(img, (bx, 82), (bx - 6, 130), (28, 32, 42), 6)
        cv2.ellipse(img, (200, 146), (24, 6), -3, 180, 360, (40, 45, 58), -1)
        cv2.ellipse(img, (280, 146), (24, 6), 3, 180, 360, (40, 45, 58), -1)
        cv2.ellipse(img, (200, 166), (25, 14), 0, 0, 360, (92, 114, 148), -1)
        cv2.ellipse(img, (280, 166), (25, 14), 0, 0, 360, (92, 114, 148), -1)
        cv2.rectangle(img, (230, 152), (250, 210), (165, 196, 238), -1)
        if not closed_eyes:
            eh = 11 if surprised else 7
            cv2.ellipse(img, (200, 166), (16, eh), 0, 0, 360, (242, 244, 248), -1)
            cv2.ellipse(img, (280, 166), (16, eh), 0, 0, 360, (242, 244, 248), -1)
            cv2.circle(img, (200, 166), 6, (28, 28, 35), -1)
            cv2.circle(img, (280, 166), 6, (28, 28, 35), -1)
        else:
            cv2.ellipse(img, (200, 166), (18, 9), 0, 0, 360, (132, 162, 204), -1)
            cv2.ellipse(img, (280, 166), (18, 9), 0, 0, 360, (132, 162, 204), -1)
            cv2.line(img, (186, 168), (214, 168), (105, 128, 162), 2)
            cv2.line(img, (266, 168), (294, 168), (105, 128, 162), 2)
        if glasses:
            cv2.rectangle(img, (174, 150), (225, 182), (25, 25, 30), 3)
            cv2.rectangle(img, (255, 150), (306, 182), (25, 25, 30), 3)
            cv2.line(img, (225, 162), (255, 162), (25, 25, 30), 3)
        cv2.ellipse(img, (240, 214), (14, 7), 0, 0, 180, (98, 122, 156), 2)
        if beard:
            overlay = img.copy()
            cv2.ellipse(overlay, (240, 245), (72, 52), 0, 0, 180, (65, 70, 80), -1)
            img = cv2.addWeighted(overlay, 0.42, img, 0.58, 0)
        if surprised:
            cv2.ellipse(img, (240, 250), (18, 16), 0, 0, 360, (22, 18, 28), -1)
        elif smile:
            cv2.ellipse(img, (240, 236), (34, 16), 0, 10, 170, (65, 70, 140), -1)
            cv2.ellipse(img, (240, 238), (28, 9), 0, 15, 165, (248, 248, 250), -1)
        else:
            cv2.line(img, (215, 246), (265, 246), (95, 105, 155), 3)
        if side_light:
            grad = np.linspace(1.25, 0.65, 480).reshape(1, 480, 1)
            img = np.clip(img.astype(np.float32) * grad, 0, 255).astype(np.uint8)
        return cv2.GaussianBlur(img, (5, 5), 0)

    def test_no_false_positives_on_bangs_glasses_beard_and_side_lighting(self) -> None:
        for variant in (
            {},
            {"bangs": True},
            {"glasses": True},
            {"side_light": True},
            {"beard": True},
        ):
            detector = FacialMoodDetector()
            frame = self._render_realistic_face(**variant)
            reading = detector.analyze_frame(frame)
            for _ in range(4):
                reading = detector.analyze_frame(frame)
            assert reading.face_detected is True
            assert reading.mood_label == "calm", f"Unexpected false positive {reading.mood_label} on {variant}"
            assert reading.discomfort_index == 0.0
            assert reading.confusion_index < 0.35

    def test_single_frame_blink_does_not_trigger_false_fatigue(self) -> None:
        detector = FacialMoodDetector()
        open_frame = self._render_realistic_face()
        blink_frame = self._render_realistic_face(closed_eyes=True)
        for _ in range(3):
            detector.analyze_frame(open_frame)
        # Transient 1-frame ocular blink must remain calm
        blink_reading = detector.analyze_frame(blink_frame)
        assert blink_reading.face_detected is True
        assert blink_reading.mood_label == "calm"

    def test_sustained_closed_eyes_detects_fatigued_and_smile_detects_happy(self) -> None:
        drowsy_det = FacialMoodDetector()
        closed_frame = self._render_realistic_face(closed_eyes=True)
        drowsy_reading = drowsy_det.analyze_frame(closed_frame)
        for _ in range(4):
            drowsy_reading = drowsy_det.analyze_frame(closed_frame)
        assert drowsy_reading.face_detected is True
        assert drowsy_reading.mood_label == "fatigued"

        smile_det = FacialMoodDetector()
        smile_frame = self._render_realistic_face(smile=True)
        smile_reading = smile_det.analyze_frame(smile_frame)
        for _ in range(4):
            smile_reading = smile_det.analyze_frame(smile_frame)
        assert smile_reading.face_detected is True
        assert smile_reading.mood_label == "happy"
        assert smile_reading.discomfort_index == 0.0


class TestTrendEngineMoodDrift:
    def test_consecutive_negative_mood_drift(self) -> None:
        trend = TrendEngine(resident_id="arun", mood_drift_consecutive=3)

        # Ingest 2 sad states — should not trigger yet
        alerts1 = trend.ingest_mood("sad")
        assert len(alerts1) == 0

        alerts2 = trend.ingest_mood("sad")
        assert len(alerts2) == 0

        # Ingest 3rd consecutive negative state — must trigger drift alert!
        alerts3 = trend.ingest_mood("anxious")
        assert len(alerts3) == 1
        assert alerts3[0].category == EventCategory.MOOD
        assert "Persistent negative mood" in alerts3[0].summary

    def test_positive_mood_resets_streak(self) -> None:
        trend = TrendEngine(resident_id="arun", mood_drift_consecutive=3)

        trend.ingest_mood("sad")
        trend.ingest_mood("sad")
        # Resident has a happy moment
        trend.ingest_mood("happy")

        # Next sad reading should not trigger since streak was broken
        alerts = trend.ingest_mood("sad")
        assert len(alerts) == 0


class TestWebcamPresenceSourceMood:
    def test_webcam_reading_contains_mood(self) -> None:
        cam = WebcamPresenceSource()
        cam.open()
        reading = cam.read()
        assert isinstance(reading, SensorReading)
        assert reading.sensor_id in ("facial_mood", "webcam_presence")
        cam.close()


class TestCameraMoodIntegration:
    def test_store_facial_reading_populates_all_parameters(self) -> None:
        from carewatcher.orchestrator import CareWatcherOrchestrator
        orch = CareWatcherOrchestrator()
        facial_data = {
            "mood_label": "happy",
            "confidence": 0.94,
            "valence": 0.65,
            "arousal": 0.55,
            "smile_score": 0.72,
            "brow_tension": 12.0,
            "eye_openness": 0.88,
            "secondary_emotion": "calm",
            "confusion_index": 0.05,
            "discomfort_index": 0.0,
            "head_tilt": 2.5,
            "symmetry_score": 0.96,
        }
        orch.store_facial_reading(facial_data)
        assert orch._last_facial_reading == facial_data
        sensors = orch.get_recent_sensor_data()
        assert sensors["facial_mood_label"] == "happy"
        assert sensors["facial_mood_valence"] == 0.65
        assert sensors["facial_smile_score"] == 0.72
        assert sensors["facial_eye_openness"] == 0.88
        assert sensors["facial_brow_tension"] == 12.0
        assert sensors["facial_confidence"] == 0.94

    def test_conversational_agent_takes_camera_smile_into_consideration(self) -> None:
        from carewatcher.agent.conversation import DummyConversationAgent
        from carewatcher.interfaces import Transcript
        agent = DummyConversationAgent(resident_id="Aaron")
        transcript = Transcript(text="Hello CareWatcher", confidence=0.95)

        # Context with active smile on camera
        context = {
            "mood": "happy",
            "facial_data": {
                "mood_label": "happy",
                "smile_score": 0.65,
                "valence": 0.70,
                "eye_openness": 0.85,
            },
        }
        event, reply = agent.converse(transcript, context=context)
        assert "smile" in reply.lower() or "cheerful" in reply.lower() or "happy" in reply.lower()

    def test_conversational_agent_takes_camera_sadness_into_consideration(self) -> None:
        from carewatcher.agent.conversation import DummyConversationAgent
        from carewatcher.interfaces import Transcript
        agent = DummyConversationAgent(resident_id="Aaron")
        transcript = Transcript(text="Good morning", confidence=0.95)

        context = {
            "mood": "sad",
            "facial_data": {
                "mood_label": "sad",
                "smile_score": 0.0,
                "valence": -0.45,
                "eye_openness": 0.55,
            },
        }
        event, reply = agent.converse(transcript, context=context)
        assert "solemn" in reply.lower() or "quiet" in reply.lower() or "pensive" in reply.lower() or "downcast" in reply.lower()

