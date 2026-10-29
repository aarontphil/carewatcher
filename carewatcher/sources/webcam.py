"""
carewatcher/sources/webcam.py
Webcam source for continuous presence detection and real-time facial mood analysis.

Uses OpenCV to capture frames from the laptop camera and passes them through
the FacialMoodDetector to continuously measure resident mood, valence, arousal,
and facial expressions on-device.

All processing is 100% local — no images are ever transmitted or stored.
"""
from __future__ import annotations

import logging
import threading
import time
from datetime import datetime
from typing import Any, Iterator

from carewatcher.interfaces import SensorReading, SensorSource
from carewatcher.vision.facial_mood import FacialMoodDetector, FacialMoodReading

logger = logging.getLogger(__name__)


class WebcamPresenceSource:
    """Continuously monitors resident presence and facial mood via webcam.

    Uses OpenCV and Haar cascades for face detection, smile tracking, ocular
    analysis, and forehead tension gradients without requiring cloud APIs.

    Parameters
    ----------
    camera_index:
        OpenCV camera index (0 = default laptop camera).
    check_interval_sec:
        Seconds between frame captures (default 1.5s for continuous monitoring).
    """

    def __init__(
        self,
        camera_index: int = 0,
        check_interval_sec: float = 1.5,
    ) -> None:
        self.camera_index = camera_index
        self.check_interval_sec = check_interval_sec
        self._cap: Any = None
        self._is_open = False
        self._cv2: Any = None
        self._detector = FacialMoodDetector()
        self._last_reading: FacialMoodReading | None = None
        self._lock = threading.Lock()

    def open(self) -> None:
        """Open the webcam."""
        try:
            import cv2  # type: ignore[import-not-found]
            self._cv2 = cv2
            import sys

            # Use CAP_DSHOW on Windows for instant hardware initialization and clean release
            if sys.platform == "win32":
                self._cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
            else:
                self._cap = cv2.VideoCapture(self.camera_index)

            if not self._cap.isOpened():
                logger.warning(f"Webcam index {self.camera_index} could not be opened directly")
                self._cap = None
            else:
                logger.info(f"Webcam hardware opened (camera index {self.camera_index})")

            self._is_open = True
        except ImportError:
            logger.warning("opencv-python not installed — webcam source unavailable")
            self._cv2 = None
            self._is_open = True

    def read(self) -> SensorReading:
        """Capture a frame and return a continuous presence/mood reading.

        Returns a SensorReading with:
        - sensor_id: 'facial_mood'
        - value: continuous valence (-1.0 to +1.0)
        - unit: 'valence'
        - metadata: mood_label, confidence, smile_score, brow_tension, face_count
        """
        now = datetime.now()

        with self._lock:
            if not self._is_open or self._cap is None or self._cv2 is None:
                # Standby reading if hardware camera device is released or closed
                return SensorReading(
                    sensor_id="webcam_presence",
                    value=0.0,
                    unit="faces",
                    timestamp=now,
                    metadata={"source": "camera_standby", "status": "hardware_released"},
                )

            ret, frame = self._cap.read()
            if not ret or frame is None:
                return SensorReading(
                    sensor_id="webcam_presence",
                    value=0.0,
                    unit="faces",
                    timestamp=now,
                    metadata={"source": "camera_frame_miss"},
                )

            # Analyze frame through FacialMoodDetector
            mood_res = self._detector.analyze_frame(frame)
            self._last_reading = mood_res

            # When a face is detected, emit continuous facial_mood reading
            if mood_res.face_detected:
                return SensorReading(
                    sensor_id="facial_mood",
                    value=mood_res.valence,
                    unit="valence",
                    timestamp=now,
                    metadata={
                        "source": "webcam",
                        "mood_label": mood_res.mood_label,
                        "confidence": str(mood_res.confidence),
                        "valence": str(mood_res.valence),
                        "arousal": str(mood_res.arousal),
                        "smile_score": str(mood_res.smile_score),
                        "brow_tension": str(mood_res.brow_tension),
                        "face_count": str(mood_res.face_count),
                        "secondary_emotion": mood_res.secondary_emotion,
                        "eye_openness": str(mood_res.eye_openness),
                        "mouth_openness": str(mood_res.mouth_openness),
                        "head_tilt": str(mood_res.head_tilt),
                        "symmetry_score": str(mood_res.symmetry_score),
                        "confusion_index": str(mood_res.confusion_index),
                        "discomfort_index": str(mood_res.discomfort_index),
                        "attention_score": str(mood_res.attention_score),
                    },
                )
            else:
                # Inactivity / no face reading
                return SensorReading(
                    sensor_id="webcam_presence",
                    value=0.0,
                    unit="faces",
                    timestamp=now,
                    metadata={"source": "webcam", "face_count": "0"},
                )

    def analyze_external_frame(self, frame: Any) -> FacialMoodReading:
        """Allow external sources (e.g. browser canvas post) to be analyzed."""
        res = self._detector.analyze_frame(frame)
        self._last_reading = res
        return res

    def close(self) -> None:
        """Release the webcam and guarantee physical hardware shutoff."""
        with self._lock:
            self._is_open = False
            if self._cap is not None:
                try:
                    self._cap.release()
                except Exception as exc:
                    logger.debug(f"Error releasing VideoCapture: {exc}")
                del self._cap
                self._cap = None
            if self._cv2 is not None:
                try:
                    self._cv2.destroyAllWindows()
                except Exception:
                    pass
            time.sleep(0.05)

    def __iter__(self) -> Iterator[SensorReading]:
        if not self._is_open:
            self.open()
        while self._is_open:
            yield self.read()
            time.sleep(self.check_interval_sec)

    def is_someone_present(self) -> bool:
        """Quick check: is resident face visible?"""
        if self._last_reading is not None:
            return self._last_reading.face_detected
        reading = self.read()
        return reading.value > 0 or reading.sensor_id == "facial_mood"

