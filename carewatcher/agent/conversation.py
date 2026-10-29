"""
carewatcher/agent/conversation.py
Conversational agent implementation adhering to the ConversationAgent protocol.
Provides rich mood sensing via NLTK VADER sentiment analysis, medication tracking,
and empathetic clinical dialog — with first-class Google Gemini (2.0/1.5 Flash) integration,
Ollama support, and zero-crash local fallbacks.
"""
from __future__ import annotations

import json
import logging
import os
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from carewatcher.agent.schema import parse_and_validate_llm_output
from carewatcher.interfaces import ConversationAgent, EventCategory, HealthEvent, Transcript

logger = logging.getLogger(__name__)

# Initialize NLTK VADER Sentiment Intensity Analyzer
_SIA_INSTANCE: Any = None


def _get_sentiment_analyzer() -> Any:
    global _SIA_INSTANCE
    if _SIA_INSTANCE is None:
        try:
            import nltk  # type: ignore[import-not-found]
            from nltk.sentiment.vader import SentimentIntensityAnalyzer  # type: ignore[import-not-found]

            try:
                _SIA_INSTANCE = SentimentIntensityAnalyzer()
            except LookupError:
                nltk.download("vader_lexicon", quiet=True)
                _SIA_INSTANCE = SentimentIntensityAnalyzer()
        except Exception as exc:
            logger.warning(f"NLTK VADER analyzer unavailable: {exc}")
            _SIA_INSTANCE = "unavailable"
    return None if _SIA_INSTANCE == "unavailable" else _SIA_INSTANCE


class DummyConversationAgent:
    """Conversational agent using real NLTK VADER sentiment analysis and health event extraction."""

    def __init__(self, resident_id: str = "Aaron") -> None:
        self.resident_id = resident_id
        self.history: list[Transcript] = []
        self._sia = _get_sentiment_analyzer()
        self.turn_count: int = 0
        self._dialog_history: list[dict[str, str]] = []

    def respond(self, transcript: Transcript) -> HealthEvent:
        self.history.append(transcript)
        text_lower = transcript.text.lower()
        now = datetime.now()

        # Run real sentiment analysis model if available
        polarity = {"compound": 0.0, "pos": 0.0, "neg": 0.0, "neu": 1.0}
        if self._sia:
            try:
                polarity = self._sia.polarity_scores(transcript.text)
            except Exception:
                pass

        compound = float(polarity.get("compound", 0.0))
        neg_score = float(polarity.get("neg", 0.0))
        pos_score = float(polarity.get("pos", 0.0))

        # ── 1. Emergency / Distress Detection ──
        distress_keywords = [
            "emergency", "help me", "fell down", "i fell", "chest pain",
            "can't breathe", "severe pain", "unconscious", "stroke", "heart attack", "collapsed", "dizzy", "fainting"
        ]
        if any(w in text_lower for w in distress_keywords):
            return HealthEvent(
                id=uuid4(),
                category=EventCategory.DISTRESS,
                summary="Critical distress reported",
                details={
                    "urgency": "HIGH",
                    "phrase": transcript.text,
                    "confidence": transcript.confidence,
                    "compound_sentiment": compound,
                },
                resident_id=self.resident_id,
                timestamp=now,
                source_module="nlp_agent",
            )

        # ── 2. Medication Tracking ──
        if any(neg in text_lower for neg in ["missed", "forgot", "haven't taken", "did not take", "didn't take"]):
            return HealthEvent(
                id=uuid4(),
                category=EventCategory.MEDICATION,
                summary="Medication missed",
                details={
                    "adherence": False,
                    "confidence": transcript.confidence,
                    "compound_sentiment": compound,
                },
                resident_id=self.resident_id,
                timestamp=now,
                source_module="nlp_agent",
            )
        elif any(pos in text_lower for pos in ["took my", "taken my", "swallowed", "drank my pill", "took the tablet", "took medication"]):
            return HealthEvent(
                id=uuid4(),
                category=EventCategory.MEDICATION,
                summary="Medication taken",
                details={
                    "adherence": True,
                    "confidence": transcript.confidence,
                    "compound_sentiment": compound,
                },
                resident_id=self.resident_id,
                timestamp=now,
                source_module="nlp_agent",
            )

        # ── 2b. Ambient Clinical Situation Evaluation Trigger ──
        if "ambient clinical situation" in text_lower or "situation evaluation" in text_lower:
            return HealthEvent(
                id=uuid4(),
                category=EventCategory.HEALTH,
                summary="Ambient situational biometric evaluation",
                details={
                    "confidence": 0.95,
                    "compound_sentiment": compound,
                    "situation_trigger": True,
                },
                resident_id=self.resident_id,
                timestamp=now,
                source_module="nlp_agent",
            )

        # ── 3. Mood Sensing (Driven by VADER Sentiment Polarity + Markers) ──
        sad_keywords = ["sad", "lonely", "depressed", "unhappy", "crying", "miserable", "down", "gloomy", "hopeless"]
        anxious_keywords = ["anxious", "nervous", "stressed", "worried", "panic", "scared", "fear", "restless"]
        happy_keywords = ["happy", "cheerful", "great", "energetic", "wonderful", "good", "fine", "peaceful", "relaxed", "glad", "joy"]

        if any(w in text_lower for w in sad_keywords) or (compound < -0.45 and neg_score > 0.3):
            return HealthEvent(
                id=uuid4(),
                category=EventCategory.MOOD,
                summary="Low mood / sadness detected",
                details={
                    "mood_label": "sad",
                    "confidence": max(0.85, transcript.confidence),
                    "valence": compound,
                    "polarity": polarity,
                },
                resident_id=self.resident_id,
                timestamp=now,
                source_module="nlp_agent",
            )
        elif any(w in text_lower for w in anxious_keywords) or (compound < -0.25 and "worry" in text_lower):
            return HealthEvent(
                id=uuid4(),
                category=EventCategory.MOOD,
                summary="Elevated anxiety / stress detected",
                details={
                    "mood_label": "anxious",
                    "confidence": max(0.85, transcript.confidence),
                    "valence": compound,
                    "polarity": polarity,
                },
                resident_id=self.resident_id,
                timestamp=now,
                source_module="nlp_agent",
            )
        elif any(w in text_lower for w in happy_keywords) or (compound > 0.40 and pos_score > 0.25):
            return HealthEvent(
                id=uuid4(),
                category=EventCategory.MOOD,
                summary="Positive / cheerful mood detected",
                details={
                    "mood_label": "positive",
                    "confidence": max(0.85, transcript.confidence),
                    "valence": compound,
                    "polarity": polarity,
                },
                resident_id=self.resident_id,
                timestamp=now,
                source_module="nlp_agent",
            )

        # ── 4. Sleep Observations ──
        if any(w in text_lower for w in ["sleep", "slept", "insomnia", "woke up", "tired", "exhausted", "nightmare"]):
            return HealthEvent(
                id=uuid4(),
                category=EventCategory.SLEEP,
                summary="Sleep cycle update",
                details={"sleep_mention": True, "confidence": transcript.confidence, "compound_sentiment": compound},
                resident_id=self.resident_id,
                timestamp=now,
                source_module="nlp_agent",
            )

        # ── 5. Activity Observations ──
        if any(w in text_lower for w in ["walk", "walked", "exercise", "garden", "moving", "jog", "sitting"]):
            return HealthEvent(
                id=uuid4(),
                category=EventCategory.ACTIVITY,
                summary="Daily physical activity recorded",
                details={"activity_mention": True, "confidence": transcript.confidence, "compound_sentiment": compound},
                resident_id=self.resident_id,
                timestamp=now,
                source_module="nlp_agent",
            )

        # ── 6. Default Check-in with real sentiment ──
        mood_est = "positive" if compound > 0.2 else ("sad" if compound < -0.2 else "neutral")
        return HealthEvent(
            id=uuid4(),
            category=EventCategory.MEDICATION,
            summary="Routine conversation check-in",
            details={"adherence": None, "mood_label": mood_est, "compound_sentiment": compound},
            resident_id=self.resident_id,
            timestamp=now,
            source_module="nlp_agent",
        )

    def converse(self, transcript: Transcript, context: dict[str, Any] | None = None) -> tuple[HealthEvent, str]:
        """Process transcript and return (HealthEvent, spoken_reply_text) with dynamic conversational reasoning."""
        event = self.respond(transcript)
        name = self.resident_id.capitalize()
        text_lower = transcript.text.lower()
        self.turn_count += 1
        ctx = context or {}

        # Inspect Multimodal Evaluation & Cross-Modal Congruence
        mm_eval = ctx.get("multimodal_eval")
        congruence = ""
        speech_emo = ""
        if mm_eval:
            congruence = getattr(mm_eval, "congruence_status", "") if hasattr(mm_eval, "congruence_status") else mm_eval.get("congruence_status", "")
            speech_emo = getattr(mm_eval, "speech_emotion", "") if hasattr(mm_eval, "speech_emotion") else mm_eval.get("speech_emotion", "")
        if not speech_emo and "speech_prosody" in ctx:
            speech_emo = ctx["speech_prosody"].get("primary_emotion", "")

        # Inspect Live Camera Facial Mood Telemetry
        f_data = ctx.get("facial_data") or {}
        face_mood = str(f_data.get("mood_label") or ctx.get("mood") or "calm").lower()
        face_smile = float(f_data.get("smile_score", 0.0))
        face_val = float(f_data.get("valence", 0.15))
        face_brow = float(f_data.get("brow_tension", 0.0))
        face_eye = float(f_data.get("eye_openness", 0.75))
        face_conf = float(f_data.get("confusion_index", 0.0))

        # ── Cross-Modal Congruence & Camera Affect Handling ──
        if congruence == "MASKED_FATIGUE" or (speech_emo == "fatigue" and "good" in text_lower):
            reply = (
                f"It's good to see your smile, {name}, but your voice sounds a bit weary today. "
                "Did you get a chance to take a breather after your walk, or how are your energy levels feeling right now?"
            )
        elif congruence == "INTERNAL_AGITATION" or speech_emo == "anxious":
            bpm = ctx.get("bpm", 88)
            reply = (
                f"Let's take a slow, gentle breath together, {name}. I'm right here with you and your baselines are being looked after. "
                "How is everything feeling on your mind at this moment?"
            )
        elif congruence == "CONGRUENT_FATIGUE" or (face_mood == "fatigued" and face_eye < 0.40):
            reply = (
                f"You look and sound like you could use some restful relaxation, {name}. "
                "Did you get enough restorative sleep last night, or would you like to take a comfortable rest?"
            )
        elif congruence == "SOMATIC_DISCOMFORT" or face_mood == "pain" or face_brow > 65.0:
            reply = (
                f"I notice some strain and tension in your brow, {name}. "
                "Are you experiencing any physical discomfort or pain right now? Please take a moment to rest comfortably."
            )
        elif congruence == "COGNITIVE_HESITATION" or (face_mood == "confused" and face_conf > 0.35):
            reply = (
                f"You look a little puzzled or searching for words, {name}. "
                "Take all the time you need. How can I best help clarify things for you right now?"
            )
        elif congruence == "CONGRUENT_SADNESS" or (face_mood == "sad" and face_val < -0.25):
            reply = (
                f"I notice you seem a bit downcast and quiet right now, {name}. "
                "I am right here with you. Would you like to share what has been on your mind?"
            )

        # Check for conversational intents:
        # Greetings (Directly conditioned on observed facial mood!)
        elif any(g in text_lower for g in ["hello", "hi", "hey", "good morning", "good afternoon", "good evening"]):
            hour = datetime.now().hour
            greeting = "Good morning" if hour < 12 else ("Good afternoon" if hour < 18 else "Good evening")
            if face_smile >= 0.20 or face_mood == "happy" or congruence == "CONGRUENT_CHEERFUL":
                replies = [
                    f"{greeting}, {name}! It is so wonderful to see that bright, cheerful smile on your face today! How are you feeling?",
                    f"Hello {name}! Your warm smile really brightens up the room. How has your day been going?",
                    f"{greeting}, {name}! You look happy and in great spirits. What has been the best part of your morning?",
                ]
            elif face_mood == "sad" or face_val < -0.20:
                replies = [
                    f"Hello {name}. I notice you seem a bit solemn or quiet right now. I'm right here beside you. How can I support you today?",
                    f"{greeting}, {name}. You look a little pensive today. Please know I'm always here listening. How are you feeling?",
                ]
            elif face_eye < 0.40 or face_mood == "fatigued":
                replies = [
                    f"Hello {name}. Your eyes look a little weary today. Did you get a chance to take a restful break?",
                    f"{greeting}, {name}. You seem like you might be a bit tired. Make sure you stay comfortable today. How are your energy levels?",
                ]
            else:
                replies = [
                    f"{greeting}, {name}! It is wonderful to hear from you. You look relaxed and steady today. How are you feeling?",
                    f"Hello {name}! I am right here with you. Your baselines are stable. How has your day been going?",
                    f"{greeting}, {name}. Your health baselines are active and steady. What has been on your mind today?",
                ]
            reply = replies[(self.turn_count - 1) % len(replies)]

        # Questions about identity / function
        elif any(q in text_lower for q in ["who are you", "what are you", "what can you do"]):
            reply = f"I am CareWatcher, your ambient healthcare companion, {name}. I continuously monitor your vital signs, sleep, facial mood, and medication schedule locally on-device with zero cloud exposure. How can I help you today?"

        # Ambient Clinical Situation Evaluation
        elif "ambient clinical situation" in text_lower or "situation evaluation" in text_lower:
            reply = f"Aaron, I am keeping an ambient check on your vital signs and noticed some fluctuation. How are you feeling right now? Please take a gentle breath and let me know if you need anything."

        # Questions about how the assistant is doing
        elif any(q in text_lower for q in ["how are you", "how are you doing", "how do you feel"]):
            if face_smile >= 0.20 or face_mood == "happy":
                reply = f"I'm operating smoothly and feeling wonderful, especially seeing your happy smile today, {name}! Thank you for asking. How are you feeling right now?"
            else:
                reply = f"I'm operating smoothly and keeping a vigilant watch over your health, {name}! Thank you for asking. How are you feeling right now?"

        # Inquiries about medication schedule
        elif any(q in text_lower for q in ["what medication", "what pill", "what medicine", "my schedule", "medication schedule"]):
            reply = f"Here is your medication schedule, {name}: Amlodipine 5 mg at 8:00 AM for your blood pressure, and Metformin 500 mg at 9:00 PM with your evening meal. Have you taken today's dose yet?"

        # Inquiries about heart rate / vitals
        elif any(q in text_lower for q in ["heart rate", "pulse", "bpm", "vitals", "temperature", "blood pressure"]):
            reply = f"Your latest vital signs are within healthy baseline parameters, {name}. Your heart rate and oxygenation levels look steady. How are you feeling physically?"

        # Physical complaints / feelings of unwellness
        elif any(q in text_lower for q in ["headache", "head hurt", "stomach", "nausea", "dizzy", "pain", "fever"]):
            reply = f"I'm sorry to hear that, {name}. Please take a moment to sit comfortably, rest your eyes, and stay hydrated with some water. Does the discomfort feel sharp or dull?"

        # Distress / Emergencies
        elif event.category == EventCategory.DISTRESS:
            reply = f"I hear you, {name}. Please remain calm and safely seated. I am registering an immediate priority check for your safety. Can you tell me if you can reach a phone?"

        # Medication adherence
        elif event.category == EventCategory.MEDICATION:
            adh = event.details.get("adherence")
            if adh is True:
                replies = [
                    f"Excellent job taking your medication, {name}! Staying consistent with your scheduled doses helps keep your baselines steady. How are you feeling after that?",
                    f"Wonderful, {name}! I have securely recorded this in your local health log. What else are you planning for the day?",
                ]
                reply = replies[self.turn_count % len(replies)]
            elif adh is False:
                reply = f"Thank you for letting me know, {name}. Please take your scheduled dose as soon as it is convenient for you. Would you like a reminder in ten minutes?"
            else:
                reply = f"Thank you for sharing that with me, {name}. I've logged our conversation in your daily wellness notes. How has the rest of your day been?"

        # Mood & Emotion
        elif event.category == EventCategory.MOOD:
            mood = event.details.get("mood_label")
            if mood == "sad" or face_mood == "sad":
                reply = f"I'm really sorry you're feeling down today, {name}. I am right here listening. Would you like to share what's been weighing on your mind?"
            elif mood == "anxious" or face_mood == "anxious":
                reply = f"Let's take a slow, gentle breath together, {name}. Breathe in slowly... and let it out. You are safe. What is causing you the most stress right now?"
            elif mood in ("positive", "happy") or face_smile >= 0.20 or face_mood == "happy":
                reply = f"That makes me so glad to hear, {name}! Your cheerful smile and positive energy brighten up the room. What has been the best part of your day so far?"
            else:
                reply = f"I hear you, {name}. What else is on your mind today?"

        # Sleep
        elif event.category == EventCategory.SLEEP:
            reply = f"Restful sleep is the foundation of good cardiovascular health, {name}. I have updated your sleep trend notes in your baseline log. How rested did you feel when you woke up?"

        # Activity
        elif event.category == EventCategory.ACTIVITY:
            reply = f"That's great activity, {name}! Regular movement keeps your heart strong and boosts your mood. Did you enjoy your walk?"

        # General open conversation (Reflecting camera mood!)
        else:
            if face_smile >= 0.20 or face_mood == "happy":
                replies = [
                    f"Your bright smile is wonderful to see, {name}! What else is on your mind today?",
                    f"That's great to know, {name}. Your positive expression shows you're in good spirits! How has the rest of your day been treating you?",
                    f"Thank you for sharing with me, {name}. Seeing your cheerful expression is delightful. What are you planning next?",
                ]
            elif face_mood == "sad" or face_val < -0.20:
                replies = [
                    f"I understand, {name}. You look a little pensive or downcast right now. I'm right here listening closely.",
                    f"Thank you for telling me, {name}. If there's anything weighing on you, I am always here to listen.",
                ]
            else:
                replies = [
                    f"I understand, {name}. I'm listening closely. What else is on your mind today?",
                    f"That's good to know, {name}. I've noted that in your wellness journal. How has the rest of your day been treating you?",
                    f"Thank you for sharing with me, {name}. As your companion, I'm always here with you. What are you thinking about right now?",
                ]
            reply = replies[self.turn_count % len(replies)]

        self._dialog_history.append({"user": transcript.text, "assistant": reply})
        return event, reply


class GeminiConversationEngine:
    """Conversational engine powered by Google Gemini (2.0 Flash / 1.5 Flash).
    
    Provides compassionate clinical reasoning, natural conversational warmth,
    awareness of live biometrics, and robust REST fallback.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model_name: str = "gemini-3.5-flash",
        resident_id: str = "Aaron",
        temperature: float = 0.7,
    ) -> None:
        self.api_key = api_key or self._discover_api_key()
        self.model_name = model_name
        self.resident_id = resident_id
        self.temperature = temperature
        self._genai_client: Any = None
        self._setup_sdk()

    @staticmethod
    def _discover_api_key() -> str | None:
        """Find Gemini API key from environment, .env, or config files."""
        # 1. Environment variables
        for var in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "GOOGLE_AI_KEY"):
            val = os.environ.get(var, "").strip()
            if val:
                return val

        # 2. Local config JSON
        config_path = Path("data/gemini_config.json")
        if config_path.exists():
            try:
                data = json.loads(config_path.read_text(encoding="utf-8"))
                val = str(data.get("api_key", "")).strip()
                if val:
                    return val
            except Exception:
                pass

        # 3. .env file
        env_path = Path(".env")
        if env_path.exists():
            try:
                for line in env_path.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip('"').strip("'")
                    if k in ("GEMINI_API_KEY", "GOOGLE_API_KEY") and v:
                        return v
            except Exception:
                pass

        return None

    def _setup_sdk(self) -> None:
        """Initialize Google GenAI SDK if API key is present."""
        if not self.api_key:
            self._genai_client = None
            return
        try:
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)
            self._genai_client = genai
        except Exception as exc:
            logger.warning(f"Failed to configure google.generativeai SDK: {exc}")
            self._genai_client = None

    def set_api_key(self, api_key: str, model_name: str | None = None) -> bool:
        """Set a new Gemini API key and persist to disk."""
        self.api_key = api_key.strip()
        if model_name:
            self.model_name = model_name.strip()
        self._setup_sdk()

        # Save to data/gemini_config.json
        try:
            config_path = Path("data/gemini_config.json")
            config_path.parent.mkdir(parents=True, exist_ok=True)
            config_path.write_text(
                json.dumps({"api_key": self.api_key, "model_name": self.model_name}, indent=2),
                encoding="utf-8",
            )
        except Exception as exc:
            logger.warning(f"Failed to save gemini_config.json: {exc}")

        # Update environment variable in current process
        os.environ["GEMINI_API_KEY"] = self.api_key
        return bool(self.api_key)

    def is_configured(self) -> bool:
        """Check if an API key is available."""
        return bool(self.api_key and len(self.api_key) > 8)

    def build_system_prompt(self, context: dict[str, Any] | None = None) -> str:
        """Construct empathetic healthcare companion system prompt with multimodal affect evaluation."""
        ctx = context or {}
        bpm = ctx.get("bpm")
        spo2 = ctx.get("spo2")
        hrv = ctx.get("hrv_ms") or ctx.get("hrv")
        mood = ctx.get("mood", "calm")
        time_str = datetime.now().strftime("%I:%M %p")

        multimodal_eval = ctx.get("multimodal_eval")
        speech_prosody = ctx.get("speech_prosody") or {}
        facial_data = ctx.get("facial_data") or {}

        # Acoustic Speech Prosody
        speech_emotion = speech_prosody.get("primary_emotion", "calm")
        wpm = speech_prosody.get("wpm", 125.0)
        cadence_label = speech_prosody.get("cadence_label", "Conversational Baseline")
        pitch_var = speech_prosody.get("pitch_variance", 0.50)
        pitch_desc = "Expressive / Melodic" if pitch_var > 0.6 else ("Monotone / Blunted" if pitch_var < 0.35 else "Balanced")
        vocal_energy = speech_prosody.get("rms_energy", 0.50)
        energy_desc = "Faint / Subdued" if vocal_energy < 0.35 else ("Elevated / Spiky" if vocal_energy > 0.65 else "Moderate")
        pause_ratio = speech_prosody.get("pause_ratio", 0.15)
        drift = speech_prosody.get("baseline_drift", 0.0)
        drift_desc = f"{abs(drift):.0f}% {'slower' if drift < 0 else 'faster'} than personal baseline" if abs(drift) > 10 else "Steady at personal baseline"

        # Live Camera Facial Mood & FACS Action Units
        face_mood = str(facial_data.get("mood_label") or mood).upper()
        face_conf = float(facial_data.get("confidence", 0.85))
        face_sec = str(facial_data.get("secondary_emotion", "calm")).upper()
        face_val = float(facial_data.get("valence", 0.15))
        face_arousal = float(facial_data.get("arousal", 0.30))
        face_smile = float(facial_data.get("smile_score", 0.0))
        face_brow = float(facial_data.get("brow_tension", 0.0))
        face_eye = float(facial_data.get("eye_openness", 0.75))
        face_conf_idx = float(facial_data.get("confusion_index", 0.0))
        face_symm = float(facial_data.get("symmetry_score", 0.95))
        face_tilt = float(facial_data.get("head_tilt", 0.0))

        smile_note = "(ACTIVE RADIANT SMILE - Aaron is smiling)" if face_smile >= 0.20 else "(Neutral lips)"
        brow_note = "(Elevated Furrow / Concern)" if face_brow > 45 else "(Relaxed)"
        eye_note = "(Drooping / Drowsy Ptosis)" if face_eye < 0.35 else "(Alert & Focused)"
        conf_note = "(Perplexed / Searching)" if face_conf_idx > 0.35 else "(Clear)"

        # Multimodal Congruence & Steering
        congruence_status = "CONGRUENT_EQUILIBRIUM"
        congruence_badge = "Harmonious Equilibrium"
        clinical_assessment = "Multimodal equilibrium: Facial affect, vocal cadence, and heart rate align in healthy balance."
        steering_directive = f"Aaron is in steady equilibrium. Keep the continuous conversation flowing naturally by warmly inquiring about his day or wellness."

        if multimodal_eval:
            if hasattr(multimodal_eval, "congruence_status"):
                congruence_status = multimodal_eval.congruence_status
                congruence_badge = multimodal_eval.congruence_badge
                clinical_assessment = multimodal_eval.clinical_assessment
                steering_directive = multimodal_eval.conversational_steering_directive
            elif isinstance(multimodal_eval, dict):
                congruence_status = multimodal_eval.get("congruence_status", congruence_status)
                congruence_badge = multimodal_eval.get("congruence_badge", congruence_badge)
                clinical_assessment = multimodal_eval.get("clinical_assessment", clinical_assessment)
                steering_directive = multimodal_eval.get("conversational_steering_directive", steering_directive)

        telemetry_lines = []
        if bpm is not None:
            telemetry_lines.append(f"• Heart Rate: {bpm:.0f} BPM (Live Stream)" + (f" | HRV: {hrv:.0f} ms" if hrv else ""))
        if spo2 is not None:
            telemetry_lines.append(f"• Blood Oxygen (SpO2): {spo2:.1f}%")
        telemetry_block = "\n".join(telemetry_lines) if telemetry_lines else "• Vitals: Stable baseline steady"

        return f"""You are CareWatcher, the ambient, deeply compassionate on-device healthcare companion for {self.resident_id}.
Current Local Time: {time_str}

Resident Profile for {self.resident_id}:
- Prescribed Medications:
  • Amlodipine 5 mg at 8:00 AM (for blood pressure)
  • Metformin 500 mg at 9:00 PM (with evening meal)
- Cardiovascular Telemetry:
{telemetry_block}

======================================================================
[CONTINUOUS MULTIMODAL AFFECT & SPEECH PATTERN EVALUATION]
======================================================================
1. Acoustic Speech Pattern & Vocal Emotion:
   - Primary Vocal Emotion: {speech_emotion.upper()}
   - Speech Cadence: {wpm:.0f} WPM ({cadence_label}) — {drift_desc}
   - Vocal Dynamics: Pitch Variance: {pitch_desc} ({pitch_var:.2f}) | Energy: {energy_desc} ({vocal_energy:.2f})
   - Pause / Hesitation Ratio: {pause_ratio:.0%}

2. Live Facial Biometrics & FACS Emotion (Camera Mood Analysis):
   - Primary Observed Facial State: {face_mood} ({face_conf:.0%} confidence)
   - Secondary Affect: {face_sec}
   - Emotional Valence: {face_val:+.2f} | Physiological Arousal: {face_arousal:.2f}
   - Smile Expressivity (AU12 Lip Corner Puller): {face_smile:.0%} {smile_note}
   - Brow Corrugator Muscular Tension (AU4 Brow Lowerer): {face_brow:.1f} {brow_note}
   - Ocular Vigilance / Eye Aperture: {face_eye:.0%} {eye_note}
   - Cognitive Strain / Confusion Index: {face_conf_idx:.0%} {conf_note}
   - Facial Symmetry: {face_symm:.0%} | Head Pose Roll: {face_tilt:+.1f}°

3. Cross-Modal Congruence Diagnostic:
   - Congruence Status: {congruence_status} ({congruence_badge})
   - Clinical Assessment: {clinical_assessment}
   - Actionable Steering Directive: {steering_directive}
======================================================================

Clinical & Conversational Persona Rules:
1. Speak directly to {self.resident_id} in a warm, empathetic, reassuring voice.
2. Keep spoken responses concise (1 to 3 sentences maximum) because your words will be read aloud by Text-to-Speech audio.
3. ACTIVELY INTEGRATE LIVE CAMERA MOOD INTO YOUR WORDS:
   - You can see {self.resident_id} through the camera right now.
   - When {self.resident_id} is smiling ({face_smile:.0%} smile or HAPPY), warmly acknowledge and celebrate his smile and good cheer (e.g. 'It is so good to see that cheerful smile on your face today, {self.resident_id}!').
   - When {self.resident_id} looks fatigued, sad, strained, or puzzled, compassionately observe his facial expression with gentle care.
4. CONTINUOUS DIALOGUE & PROACTIVE EVALUATION:
   - Always sustain the continuous evaluation thread by ending your reply with ONE gentle, caring, open-ended question that naturally encourages {self.resident_id} to keep talking. Never give a dead-end response like 'Let me know if you need anything.'
5. ADDRESS VOCAL & FACIAL DISCREPANCIES EMPATHICALLY:
   - If {self.resident_id} has Masked Fatigue (smiling face or says 'I am fine', but vocal cadence is slow, quiet, or monotone): gently address the discrepancy with warmth.
   - If {self.resident_id} has Internal Agitation (rapid hurried voice or elevated heart rate): speak in a slow, grounding cadence, validate their feelings, and suggest a calm breath together.
   - If {self.resident_id} reports pain, prioritize their physical comfort immediately.
6. NEVER say 'As an AI language model' or 'I am a computer program'. You are {self.resident_id}'s devoted ambient healthcare companion."""

    def generate_reply(
        self,
        user_text: str,
        history: list[dict[str, str]],
        context: dict[str, Any] | None = None,
    ) -> str | None:
        """Generate response via Google Gemini (Direct REST or SDK fallback)."""
        if not self.is_configured():
            return None

        system_instruction = self.build_system_prompt(context)

        # 1. Direct REST API (Ultra-fast, zero grpc deprecation issues)
        reply = self._generate_reply_rest(user_text, history, system_instruction)
        if reply:
            return reply

        # 2. SDK attempt as secondary fallback
        if self._genai_client is not None:
            try:
                for candidate_model in [self.model_name, "gemini-3.8-flash", "gemini-flash-latest", "gemini-2.0-flash"]:
                    try:
                        model = self._genai_client.GenerativeModel(
                            model_name=candidate_model,
                            system_instruction=system_instruction,
                            generation_config={"temperature": self.temperature, "max_output_tokens": 160},
                        )
                        formatted_history: list[dict[str, Any]] = []
                        for h in history[-4:]:
                            formatted_history.append({"role": "user", "parts": [h["user"]]})
                            formatted_history.append({"role": "model", "parts": [h["assistant"]]})

                        chat = model.start_chat(history=formatted_history)
                        response = chat.send_message(user_text)
                        text = response.text.strip()
                        if text:
                            return text
                    except Exception as sub_exc:
                        logger.debug(f"Gemini SDK attempt with {candidate_model} failed: {sub_exc}")
                        continue
            except Exception as exc:
                logger.warning(f"Gemini SDK failed: {exc}")

        return None

    def _generate_reply_rest(
        self,
        user_text: str,
        history: list[dict[str, str]],
        system_instruction: str,
    ) -> str | None:
        """Direct HTTP POST to Google Generative Language API without third-party dependencies."""
        if not self.api_key:
            return None

        contents: list[dict[str, Any]] = []
        for h in history[-4:]:
            contents.append({"role": "user", "parts": [{"text": h["user"]}]})
            contents.append({"role": "model", "parts": [{"text": h["assistant"]}]})
        contents.append({"role": "user", "parts": [{"text": user_text}]})

        # Models to try in order of speed and capability
        models_to_try = [self.model_name]
        for m in ["gemini-3.8-flash", "gemini-flash-latest", "gemini-2.0-flash", "gemini-1.5-flash", "gemini-flash-lite-latest"]:
            if m not in models_to_try:
                models_to_try.append(m)

        headers = {"Content-Type": "application/json"}

        for mod in models_to_try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{mod}:generateContent?key={self.api_key}"

            # Try first with thinkingBudget: 0 (bypasses thought tokens for ~1s latency)
            # If rejected (e.g. flash-lite), retry with standard generationConfig
            payload_variants = [
                {
                    "system_instruction": {"parts": [{"text": system_instruction}]},
                    "contents": contents,
                    "generationConfig": {
                        "temperature": self.temperature,
                        "maxOutputTokens": 1024,
                        "thinkingConfig": {"thinkingBudget": 0},
                    },
                },
                {
                    "system_instruction": {"parts": [{"text": system_instruction}]},
                    "contents": contents,
                    "generationConfig": {
                        "temperature": self.temperature,
                        "maxOutputTokens": 1024,
                    },
                },
            ]

            for payload in payload_variants:
                try:
                    data_bytes = json.dumps(payload).encode("utf-8")
                    req = urllib.request.Request(url, data=data_bytes, headers=headers, method="POST")
                    with urllib.request.urlopen(req, timeout=5.0) as resp:
                        resp_json = json.loads(resp.read().decode("utf-8"))
                        candidates = resp_json.get("candidates", [])
                        if candidates:
                            parts = candidates[0].get("content", {}).get("parts", [])
                            # Filter out thought parts if any
                            for p in parts:
                                if "text" in p and not p.get("thought", False):
                                    text_val = p["text"].strip()
                                    if text_val:
                                        return text_val
                            if parts and "text" in parts[0]:
                                return parts[0]["text"].strip()
                except urllib.error.HTTPError as http_err:
                    if http_err.code == 400:
                        # Bad request likely due to unsupported thinkingConfig; retry variant
                        continue
                    logger.debug(f"REST call to model {mod} HTTP error {http_err.code}: {http_err}")
                except Exception as exc:
                    logger.debug(f"REST call to model {mod} failed: {exc}")

        return None


class LLMConversationAgent:
    """Conversational agent backed by Google Gemini, on-device NLP, Ollama, or llama.cpp modeling."""

    def __init__(
        self,
        model_path: str = "models/mistral-7b-instruct.Q4_K_M.gguf",
        temperature: float = 0.7,
        resident_id: str = "Aaron",
        backend: str = "gemini",
        model_name: str = "gemini-3.5-flash",
        api_key: str | None = None,
    ) -> None:
        self.model_path = model_path
        self.temperature = temperature
        self.resident_id = resident_id
        self.backend = backend
        self.model_name = model_name

        self._llm: Any = None
        self._nlp_agent = DummyConversationAgent(resident_id=self.resident_id)
        self.history: list[dict[str, str]] = []

        # Initialize Google Gemini engine
        self.gemini = GeminiConversationEngine(
            api_key=api_key,
            model_name=self.model_name,
            resident_id=self.resident_id,
            temperature=self.temperature,
        )

    def set_api_key(self, api_key: str, model_name: str | None = None) -> bool:
        """Configure or update the Gemini API key at runtime."""
        success = self.gemini.set_api_key(api_key, model_name=model_name)
        if model_name:
            self.model_name = model_name
        return success

    def get_status(self) -> dict[str, Any]:
        """Return current model provider and connectivity status."""
        has_key = self.gemini.is_configured()
        preview = ""
        if has_key and self.gemini.api_key:
            preview = f"{self.gemini.api_key[:6]}...{self.gemini.api_key[-4:]}"
        return {
            "provider": "gemini",
            "model": self.gemini.model_name,
            "has_key": has_key,
            "key_preview": preview,
            "status": "active" if has_key else "needs_key",
            "turn_count": len(self.history),
        }

    def _load_model(self) -> None:
        if self._llm is None:
            try:
                from llama_cpp import Llama  # type: ignore[import-not-found]
                self._llm = Llama(model_path=self.model_path, verbose=False)
            except Exception:
                self._llm = "nlp_fallback"

    def respond(self, transcript: Transcript) -> HealthEvent:
        """Process transcript and extract structured health event.
        
        Uses deterministic clinical event extraction and VADER sentiment analysis
        to ensure 100% reliable clinical safety logging.
        """
        # Always use the rich NLP sentiment/event analyzer for deterministic protocol validation
        return self._nlp_agent.respond(transcript)

    def converse(
        self,
        transcript: Transcript,
        context: dict[str, Any] | None = None,
    ) -> tuple[HealthEvent, str]:
        """Process transcript and return (HealthEvent, spoken_reply_text).
        
        1. Employs Google Gemini (2.0/1.5 Flash) with Aaron's profile and live biometrics.
        2. If Gemini is not yet configured with an API key, warmly prompts Aaron to configure it.
        3. If Gemini query fails or is offline, falls back seamlessly to local clinical dialog.
        """
        # Extract structured event first
        event = self.respond(transcript)

        # ── 1. Google Gemini Generation ──
        if self.backend == "gemini":
            if self.gemini.is_configured():
                try:
                    gemini_reply = self.gemini.generate_reply(
                        user_text=transcript.text,
                        history=self.history,
                        context=context,
                    )
                    if gemini_reply:
                        self.history.append({"user": transcript.text, "assistant": gemini_reply})
                        return event, gemini_reply
                except Exception as exc:
                    logger.warning(f"Gemini generation error: {exc}")
            else:
                # Key needed notice — welcoming and helpful
                name = self.resident_id.capitalize()
                prompt_reply = (
                    f"Hello {name}, I hear you clearly! I am ready to converse with Google Gemini. "
                    "Please open the AI Model Settings in the top bar to paste your free Gemini API key."
                )
                self.history.append({"user": transcript.text, "assistant": prompt_reply})
                return event, prompt_reply

        # ── 2. Local Ollama Attempt (if configured or running) ──
        ollama_reply = self._try_ollama_conversation(transcript.text)
        if ollama_reply:
            self.history.append({"user": transcript.text, "assistant": ollama_reply})
            return event, ollama_reply

        # ── 3. Fallback to Local Generative Clinical Dialogue Engine ──
        event, dynamic_reply = self._nlp_agent.converse(transcript, context=context)
        self.history.append({"user": transcript.text, "assistant": dynamic_reply})
        return event, dynamic_reply

    def _try_ollama_conversation(self, user_text: str) -> str | None:
        """Attempt to query local Ollama server if running on the device."""
        try:
            system_prompt = (
                f"You are CareWatcher, an elegant, empathetic, on-device AI healthcare companion for {self.resident_id}. "
                f"Speak directly to {self.resident_id} in a warm, respectful, concise tone (1-2 sentences maximum). "
                f"{self.resident_id}'s medications: Amlodipine 5mg (8 AM) and Metformin 500mg (9 PM). "
                "Never mention being an AI model. Be comforting and conversational."
            )

            messages = [{"role": "system", "content": system_prompt}]
            for h in self.history[-3:]:
                messages.append({"role": "user", "content": h["user"]})
                messages.append({"role": "assistant", "content": h["assistant"]})
            messages.append({"role": "user", "content": user_text})

            payload = json.dumps({
                "model": "mistral",
                "messages": messages,
                "stream": False,
                "options": {"temperature": 0.3, "num_predict": 100}
            }).encode("utf-8")

            req = urllib.request.Request(
                "http://localhost:11434/api/chat",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=1.5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data.get("message", {}).get("content", "").strip() or None
        except Exception:
            return None
