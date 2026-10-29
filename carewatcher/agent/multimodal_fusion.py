"""
carewatcher/agent/multimodal_fusion.py
Multimodal Affective Fusion & Continuous Evaluation Engine.

Synthesizes cross-modal clinical biomarkers across three real-time streams:
  1. Acoustic Speech Pattern & Prosodic Emotion (SpeechEmotionResult: WPM, RMS energy, pitch contour, pauses)
  2. High-Resolution Facial Affect (FACS v2.4 8-State: valence, smile score, brow corrugator tension, ptosis)
  3. Autonomic Cardiovascular Telemetry (Apple Watch & HypeRate: live BPM, HRV, pulse stability)

Performs Cross-Modal Congruence Checking to detect:
  - MASKED FATIGUE: Resident presents a smiling or pleasant facial expression, but vocal acoustics
    reveal significant psychomotor fatigue (<105 WPM, monotone pitch, low energy).
  - INTERNAL AGITATION: Resident presents a calm facial posture, but speech cadence is hurried (>160 WPM)
    or cardiac rhythm exhibits elevated sympathetic arousal (>88 BPM with low HRV).
  - CONGRUENT EQUILIBRIUM: Harmonious alignment across facial, vocal, and cardiovascular baselines.
  - CONGRUENT EXHAUSTION: Facial ptosis/weariness corroborated by vocal lethargy.
  - SOMATIC PAIN / DISTRESS: Facial grimace/corrugator tension corroborated by vocal distress markers.
  - COGNITIVE HESITATION: Elevated facial confusion corroborated by vocal pause latency (>35%).

Outputs continuous Clinical Stability Indices and Actionable Conversational Steering Directives
for the LLM companion agent (Google Gemini) to sustain an empathetic, continuous dialogue.
"""
from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from carewatcher.stt.speech_emotion import SpeechEmotionResult

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MultimodalEvaluation:
    """Integrated clinical assessment across vocal, facial, and autonomic modalities."""

    overall_affect: str  # "calm", "fatigue", "cheerful", "anxious", "sad", "pain", "confused"
    congruence_status: str  # "CONGRUENT_EQUILIBRIUM", "MASKED_FATIGUE", "INTERNAL_AGITATION", etc.
    congruence_badge: str  # Human-readable UI badge text
    fused_valence: float  # -1.0 to +1.0
    fused_arousal: float  # 0.0 to 1.0
    stability_index: float  # 0.0 to 1.0 (1.0 = optimal equilibrium)
    speech_emotion: str
    speech_wpm: float
    speech_cadence: str
    facial_emotion: str
    facial_valence: float
    heart_rate_bpm: float
    clinical_assessment: str
    conversational_steering_directive: str
    timestamp: datetime = field(default_factory=datetime.now)
    details: dict[str, Any] = field(default_factory=dict)


class MultimodalAffectFusion:
    """Fuses speech emotion, facial FACS affect, and cardiac telemetry into continuous evaluation."""

    def __init__(self, history_size: int = 20) -> None:
        self.history_size = history_size
        self._eval_history: deque[MultimodalEvaluation] = deque(maxlen=history_size)

    def evaluate(
        self,
        speech_result: SpeechEmotionResult,
        facial_data: Any | None = None,
        biometrics: dict[str, Any] | None = None,
    ) -> MultimodalEvaluation:
        """Synthesize multimodal signals and determine cross-modal congruence."""
        bio = biometrics or {}
        bpm = float(bio.get("bpm") or bio.get("max30102_bpm") or 72.0)
        hrv = float(bio.get("hrv_ms") or 45.0)

        # ── 1. Unpack Facial Mood Data ──
        facial_label = "calm"
        facial_val = 0.20
        facial_arousal = 0.30
        smile_score = 0.0
        brow_tension = 18.0
        eye_openness = 0.75
        discomfort_idx = 0.0
        confusion_idx = 0.0

        if facial_data is not None:
            if hasattr(facial_data, "mood_label"):
                facial_label = getattr(facial_data, "mood_label", "calm")
                facial_val = float(getattr(facial_data, "valence", 0.20))
                facial_arousal = float(getattr(facial_data, "arousal", 0.30))
                smile_score = float(getattr(facial_data, "smile_score", 0.0))
                brow_tension = float(getattr(facial_data, "brow_tension", 18.0))
                eye_openness = float(getattr(facial_data, "eye_openness", 0.75))
                discomfort_idx = float(getattr(facial_data, "discomfort_index", 0.0))
                confusion_idx = float(getattr(facial_data, "confusion_index", 0.0))
            elif isinstance(facial_data, dict):
                facial_label = str(facial_data.get("mood_label", "calm"))
                facial_val = float(facial_data.get("valence", 0.20))
                facial_arousal = float(facial_data.get("arousal", 0.30))
                smile_score = float(facial_data.get("smile_score", 0.0))
                brow_tension = float(facial_data.get("brow_tension", 18.0))
                eye_openness = float(getattr(facial_data, "eye_openness", 0.75) if not isinstance(facial_data, dict) else facial_data.get("eye_openness", 0.75))
                discomfort_idx = float(facial_data.get("discomfort_index", 0.0))
                confusion_idx = float(facial_data.get("confusion_index", 0.0))

        # ── 2. Cross-Modal Congruence Analysis ──
        sp_emotion = speech_result.primary_emotion
        wpm = speech_result.wpm
        pitch_var = speech_result.pitch_variance
        vocal_energy = speech_result.rms_energy
        pause_ratio = speech_result.pause_ratio

        congruence_status = "CONGRUENT_EQUILIBRIUM"
        congruence_badge = "Harmonious Equilibrium"
        assessment = ""
        steering = ""

        # Scenario A: Masked Fatigue / Affective Suppression
        # Face is smiling or cheerful, BUT voice shows slow cadence, flat intonation, or vocal exhaustion
        if (smile_score > 0.35 or facial_label in ("happy", "cheerful")) and (
            sp_emotion in ("fatigue", "sad") or (wpm < 100.0 and pitch_var < 0.35 and vocal_energy < 0.38)
        ):
            congruence_status = "MASKED_FATIGUE"
            congruence_badge = "Masked Fatigue Detected"
            assessment = (
                f"Vocal-Facial Discordance: Aaron presents a pleasant facial smile ({smile_score:.0%}), "
                f"yet vocal cadence is noticeably slowed ({wpm:.0f} WPM) with flat intonation ({pitch_var:.2f}). "
                "Suggests masked physical weariness or social masking."
            )
            steering = (
                "Aaron exhibits masked fatigue: smiling outwardly but his voice sounds weary, quiet, and slowed down. "
                "Gently acknowledge his warmth, but softly inquire if he has been exerting himself or feeling tired today. "
                "Keep your voice gentle, concise, and end with an open caring question asking if he'd like to take a restful break."
            )

        # Scenario B: Internal Agitation / Masked Sympathetic Arousal
        # Face is calm/neutral, BUT voice is anxious/hurried or heart rate is elevated (>88 BPM) with low HRV
        elif (facial_label in ("calm", "neutral") and smile_score < 0.25) and (
            sp_emotion == "anxious" or (wpm > 158.0 and pitch_var > 0.60) or (bpm >= 90.0 and hrv < 35.0)
        ):
            congruence_status = "INTERNAL_AGITATION"
            congruence_badge = "Internal Agitation / Sympathetic Arousal"
            assessment = (
                f"Autonomic/Vocal Hyperarousal: Cardiac rate is elevated ({bpm:.0f} BPM) and vocal cadence is rapid "
                f"({wpm:.0f} WPM) despite a neutral facial expression. Indicates internal stress or apprehension."
            )
            steering = (
                f"Aaron exhibits internal sympathetic arousal: elevated heart rate ({bpm:.0f} BPM) or hurried vocal tempo, "
                "despite a calm face. Respond with a slow, grounding, calming presence. Reassure him that everything is safe, "
                "offer a gentle breathing pause, and ask what is on his mind."
            )

        # Scenario C: Somatic Discomfort / Pain Episode
        elif sp_emotion == "pain" or discomfort_idx > 0.55 or facial_label == "pain":
            congruence_status = "SOMATIC_DISCOMFORT"
            congruence_badge = "Somatic Discomfort Marker"
            assessment = (
                f"Cross-modal pain indicator: Brow tension ({brow_tension:.1f}) and vocal distress cues observed. "
                f"Current heart rate is {bpm:.0f} BPM."
            )
            steering = (
                "Aaron exhibits signs of physical discomfort or pain. Prioritize his physical comfort: gently ask where "
                "it hurts or if he needs support sitting down, and reassure him that you are staying right beside him."
            )

        # Scenario D: Congruent Fatigue / Psychomotor Lethargy
        elif (facial_label in ("fatigued", "sad") or eye_openness < 0.40) and (
            sp_emotion in ("fatigue", "sad") or wpm < 105.0
        ):
            congruence_status = "CONGRUENT_FATIGUE"
            congruence_badge = "Congruent Exhaustion"
            assessment = (
                f"Corroborated Fatigue: Low ocular alertness ({eye_openness:.0%}) aligned with subdued speech cadence "
                f"({wpm:.0f} WPM) and low acoustic amplitude ({vocal_energy:.2f})."
            )
            steering = (
                "Aaron is visibly and audibly exhausted. Keep your response short, calm, and soothing (1-2 sentences). "
                "Suggest resting comfortably or having a warm glass of water, and ask how his sleep was last night."
            )

        # Scenario E: Congruent Cheerful / Social Vitality & Radiant Smile
        elif (facial_label in ("happy", "cheerful") or smile_score >= 0.25) and (
            sp_emotion not in ("fatigue", "sad", "pain", "anxious")
        ):
            congruence_status = "CONGRUENT_CHEERFUL"
            congruence_badge = "Vibrant Positive Engagement"
            assessment = (
                f"Congruent Cheerful Vitality: Radiant smile ({smile_score:.0%}), vocal cadence ({wpm:.0f} WPM), "
                f"and stable pulse ({bpm:.0f} BPM)."
            )
            steering = (
                "Aaron is visibly in good spirits and smiling on camera. Celebrate his cheerful expression! "
                "Warmly acknowledge his smile, match his positive energy, and ask an uplifting question about his day."
            )

        # Scenario F: Cognitive Hesitation / Disorientation
        elif (confusion_idx > 0.55 or sp_emotion == "confused" or (pause_ratio > 0.42 and sp_emotion not in ("calm", "cheerful"))) and smile_score < 0.20:
            congruence_status = "COGNITIVE_HESITATION"
            congruence_badge = "Cognitive Hesitation / Processing Latency"
            assessment = (
                f"Processing Latency: Vocal pause ratio is elevated ({pause_ratio:.0%}) with asymmetric facial confusion markers."
            )
            steering = (
                "Aaron seems hesitant, puzzled, or searching for words. Speak with extra clarity, warmth, and patient simplicity. "
                "Reassure him gently and ask how you can help clarify things for him."
            )

        # Scenario G: Congruent Low Mood / Solemn Facial Affect
        elif (facial_label in ("sad", "melancholy") or facial_val < -0.25) and (
            sp_emotion not in ("cheerful", "happy")
        ):
            congruence_status = "CONGRUENT_SADNESS"
            congruence_badge = "Solemn / Low Mood Observed"
            assessment = (
                f"Subdued Affect: Solemn or downcast facial expression ({facial_label}, valence {facial_val:+.2f}). "
                f"Heart rate is {bpm:.0f} BPM."
            )
            steering = (
                "Aaron appears quiet, downcast, or melancholic on camera. Speak with gentle warmth, compassionately "
                "acknowledge his quiet demeanor, and softly ask what has been on his mind."
            )

        # Scenario H: Baseline Equilibrium
        else:
            congruence_status = "CONGRUENT_EQUILIBRIUM"
            congruence_badge = "Harmonious Equilibrium"
            assessment = (
                f"Multimodal Equilibrium: Vocal cadence ({wpm:.0f} WPM), facial affect ({facial_label}), "
                f"and cardiac baseline ({bpm:.0f} BPM) are in balanced homeostatic harmony."
            )
            steering = (
                "Aaron is in a calm, balanced state. Maintain a pleasant, proactive conversation: "
                "briefly acknowledge what he shared, and ask a thoughtful, open-ended question about his day or wellness."
            )

        # ── 3. Unified Continuous Evaluation Metrics ──
        # Fused Valence (-1.0 to 1.0): 45% speech valence + 45% facial valence + 10% heart rate balance
        hr_val_offset = 0.0 if (60.0 <= bpm <= 82.0) else (-0.15 if bpm > 88.0 else -0.05)
        fused_valence = (speech_result.valence * 0.45) + (facial_val * 0.45) + hr_val_offset
        fused_valence = max(-1.0, min(1.0, fused_valence))

        # Fused Arousal (0.0 to 1.0): 40% speech arousal + 35% facial arousal + 25% cardiac arousal
        cardiac_arousal = min(1.0, max(0.0, (bpm - 55.0) / 45.0))
        fused_arousal = (speech_result.arousal * 0.40) + (facial_arousal * 0.35) + (cardiac_arousal * 0.25)
        fused_arousal = max(0.0, min(1.0, fused_arousal))

        # Overall affect classification
        if congruence_status == "MASKED_FATIGUE":
            overall_affect = "fatigue"
        elif congruence_status == "INTERNAL_AGITATION":
            overall_affect = "anxious"
        elif congruence_status == "SOMATIC_DISCOMFORT":
            overall_affect = "pain"
        elif congruence_status == "COGNITIVE_HESITATION":
            overall_affect = "confused"
        elif congruence_status == "CONGRUENT_CHEERFUL":
            overall_affect = "cheerful"
        elif congruence_status == "CONGRUENT_FATIGUE":
            overall_affect = "fatigue"
        elif congruence_status == "CONGRUENT_SADNESS":
            overall_affect = "sad"
        else:
            overall_affect = "calm"

        # Stability Index: Higher when modalities agree and heart rate is steady
        if congruence_status in ("CONGRUENT_EQUILIBRIUM", "CONGRUENT_CHEERFUL"):
            stability = 0.92
        elif congruence_status == "MASKED_FATIGUE":
            stability = 0.65
        elif congruence_status in ("INTERNAL_AGITATION", "COGNITIVE_HESITATION", "CONGRUENT_SADNESS"):
            stability = 0.55
        elif congruence_status == "SOMATIC_DISCOMFORT":
            stability = 0.40
        else:
            stability = 0.75

        eval_result = MultimodalEvaluation(
            overall_affect=overall_affect,
            congruence_status=congruence_status,
            congruence_badge=congruence_badge,
            fused_valence=round(fused_valence, 3),
            fused_arousal=round(fused_arousal, 3),
            stability_index=round(stability, 2),
            speech_emotion=sp_emotion,
            speech_wpm=speech_result.wpm,
            speech_cadence=speech_result.cadence_label,
            facial_emotion=facial_label,
            facial_valence=facial_val,
            heart_rate_bpm=round(bpm, 1),
            clinical_assessment=assessment,
            conversational_steering_directive=steering,
            details={
                "pitch_variance": speech_result.pitch_variance,
                "rms_energy": speech_result.rms_energy,
                "pause_ratio": speech_result.pause_ratio,
                "smile_score": smile_score,
                "brow_tension": brow_tension,
                "eye_openness": eye_openness,
                "confusion_index": confusion_idx,
                "discomfort_index": discomfort_idx,
                "head_tilt": getattr(facial_data, "head_tilt", 0.0) if hasattr(facial_data, "head_tilt") else (facial_data.get("head_tilt", 0.0) if isinstance(facial_data, dict) else 0.0),
                "symmetry_score": getattr(facial_data, "symmetry_score", 0.95) if hasattr(facial_data, "symmetry_score") else (facial_data.get("symmetry_score", 0.95) if isinstance(facial_data, dict) else 0.95),
                "hrv_ms": hrv,
            },
        )

        self._eval_history.append(eval_result)
        return eval_result
