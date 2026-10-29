"""Tests for Multimodal Affect Fusion & Continuous Evaluation Engine."""
from __future__ import annotations

import pytest

from carewatcher.agent.multimodal_fusion import MultimodalAffectFusion, MultimodalEvaluation
from carewatcher.stt.speech_emotion import SpeechEmotionAnalyzer


class TestMultimodalAffectFusion:
    def test_masked_fatigue_detection(self) -> None:
        analyzer = SpeechEmotionAnalyzer()
        fusion = MultimodalAffectFusion()

        # Aaron says "I am doing good" but speech is slow, quiet, and monotone
        speech_res = analyzer.analyze(
            text="I am doing good just sitting here...",
            duration_seconds=7.0,  # Slow: ~60 WPM
            audio_metrics={"avg_volume": 0.22, "pitch_variance": 0.20},
        )

        # Facial camera detects a smile (social masking)
        facial_data = {
            "mood_label": "happy",
            "valence": 0.55,
            "arousal": 0.35,
            "smile_score": 0.60,
            "brow_tension": 30.0,
            "eye_openness": 0.65,
        }

        eval_res = fusion.evaluate(
            speech_result=speech_res,
            facial_data=facial_data,
            biometrics={"bpm": 70.0, "spo2": 98.0},
        )

        assert isinstance(eval_res, MultimodalEvaluation)
        assert eval_res.congruence_status == "MASKED_FATIGUE"
        assert "Masked Fatigue" in eval_res.congruence_badge
        assert "weary" in eval_res.conversational_steering_directive.lower() or "fatigue" in eval_res.conversational_steering_directive.lower()

    def test_internal_agitation_detection(self) -> None:
        analyzer = SpeechEmotionAnalyzer()
        fusion = MultimodalAffectFusion()

        # Fast, anxious speech pattern
        speech_res = analyzer.analyze(
            text="I am not sure what is happening my chest feels strange",
            duration_seconds=2.5,  # Rapid: >200 WPM
            audio_metrics={"avg_volume": 0.70, "pitch_variance": 0.75},
        )

        # Neutral face, but tachycardia on Apple Watch / HypeRate
        facial_data = {
            "mood_label": "calm",
            "valence": 0.05,
            "arousal": 0.25,
            "smile_score": 0.05,
        }

        eval_res = fusion.evaluate(
            speech_result=speech_res,
            facial_data=facial_data,
            biometrics={"bpm": 96.0, "hrv_ms": 28.0},
        )

        assert eval_res.congruence_status == "INTERNAL_AGITATION"
        assert "Agitation" in eval_res.congruence_badge
        assert "grounding" in eval_res.conversational_steering_directive.lower() or "breath" in eval_res.conversational_steering_directive.lower()

    def test_congruent_equilibrium(self) -> None:
        analyzer = SpeechEmotionAnalyzer()
        fusion = MultimodalAffectFusion()

        speech_res = analyzer.analyze(
            text="The afternoon has been pleasant and quiet.",
            duration_seconds=3.0,
        )

        facial_data = {
            "mood_label": "calm",
            "valence": 0.25,
            "arousal": 0.25,
            "smile_score": 0.10,
        }

        eval_res = fusion.evaluate(
            speech_result=speech_res,
            facial_data=facial_data,
            biometrics={"bpm": 72.0, "spo2": 98.5},
        )

        assert eval_res.congruence_status == "CONGRUENT_EQUILIBRIUM"
        assert eval_res.stability_index >= 0.85
