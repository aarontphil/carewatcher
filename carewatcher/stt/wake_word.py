"""
carewatcher/stt/wake_word.py
Keyword-based wake word detector implementing the WakeWordDetector protocol.
"""
from __future__ import annotations

import re

from carewatcher.interfaces import Transcript, WakeWordDetector


class KeywordWakeWordDetector:
    """Detects a wake word phrase inside a transcript with punctuation tolerance and alias support."""

    def __init__(self, keyword: str = "hey care", threshold: float = 0.6) -> None:
        self.keyword = keyword.lower().strip()
        self.threshold = threshold

        # Build list of normalized trigger variants
        self._variants: set[str] = {self.keyword}
        clean_kw = re.sub(r"[^\w\s]", "", self.keyword)
        self._variants.add(clean_kw)

        # Standard CareWatcher & Resident wake triggers
        if "care" in self.keyword or "aaron" in self.keyword:
            self._variants.update([
                "hey care", "care", "carewatcher", "care watcher",
                "hey aaron", "aaron", "okay care", "hi care", "hello care",
            ])

    def detect(self, transcript: Transcript) -> bool:
        """Return True if any configured wake keyword is found in the transcript text."""
        if not transcript.text:
            return False

        if transcript.confidence < self.threshold:
            return False

        # Normalize transcript text: lowercase and strip punctuation
        raw_text = transcript.text.lower()
        clean_text = re.sub(r"[^\w\s]", " ", raw_text)
        normalized_words = " ".join(clean_text.split())

        for variant in self._variants:
            if not variant:
                continue
            # Check exact substring or word boundary match
            if variant in raw_text or variant in normalized_words:
                return True

        return False
