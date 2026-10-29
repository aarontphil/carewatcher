"""
carewatcher/proposer/engine.py
Rule-based intervention proposer.

Generates candidate Intervention objects from HealthEvents.
This module has NO imports from carewatcher.verifier (architectural isolation).
"""
from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from carewatcher.interfaces import (
    EventCategory,
    HealthEvent,
    Intervention,
    InterventionType,
)


class RuleBasedProposer:
    """Generates candidate interventions based on health event rules.

    The proposer examines each incoming HealthEvent and, when appropriate,
    creates a proposed Intervention that must be reviewed by the Verifier
    before reaching the resident or caregiver.

    Parameters
    ----------
    resident_id:
        Default resident identifier.
    """

    def __init__(self, resident_id: str = "arun") -> None:
        self.resident_id = resident_id

    def propose(self, event: HealthEvent) -> Intervention | None:
        """Return a proposed Intervention, or None if no action is needed."""
        category = event.category
        details = event.details or {}

        if category == EventCategory.MEDICATION:
            return self._propose_medication(event, details)
        elif category == EventCategory.SLEEP:
            return self._propose_sleep(event, details)
        elif category == EventCategory.ACTIVITY:
            return self._propose_activity(event, details)
        elif category == EventCategory.MOOD:
            return self._propose_mood(event, details)
        elif category == EventCategory.DISTRESS:
            return self._propose_distress(event, details)
        elif category == EventCategory.INACTIVITY:
            return self._propose_inactivity(event, details)

        return None

    # ── category-specific proposal logic ──────────────────────────────

    def _propose_medication(
        self, event: HealthEvent, details: dict
    ) -> Intervention | None:
        adherence = details.get("adherence")

        if adherence is False:
            return Intervention(
                id=uuid4(),
                type=InterventionType.REMINDER,
                event_id=event.id,
                resident_id=event.resident_id or self.resident_id,
                message=(
                    f"Gentle reminder: it looks like you may have missed your "
                    f"medication. Please take it when you get a chance."
                ),
                reasoning=(
                    f"Resident reported missing medication. "
                    f"Event summary: {event.summary}"
                ),
                timestamp=datetime.now(),
            )

        # Medication taken — no intervention needed
        return None

    def _propose_sleep(
        self, event: HealthEvent, details: dict
    ) -> Intervention | None:
        deficit = details.get("deficit", 0)
        return Intervention(
            id=uuid4(),
            type=InterventionType.CONVERSATION,
            event_id=event.id,
            resident_id=event.resident_id or self.resident_id,
            message=(
                "I noticed you haven't been sleeping as well lately. "
                "How have you been feeling? Is everything okay?"
            ),
            reasoning=(
                f"Sleep deficit of {deficit:.1f}h detected over baseline. "
                f"Suggesting a conversational check-in about sleep quality."
            ),
            timestamp=datetime.now(),
        )

    def _propose_activity(
        self, event: HealthEvent, details: dict
    ) -> Intervention | None:
        # Low activity — gentle encouragement
        return Intervention(
            id=uuid4(),
            type=InterventionType.CONVERSATION,
            event_id=event.id,
            resident_id=event.resident_id or self.resident_id,
            message=(
                "You've been a bit less active today. Would you like to try "
                "a short walk or some light stretching?"
            ),
            reasoning=f"Activity level below baseline. Event: {event.summary}",
            timestamp=datetime.now(),
        )

    def _propose_mood(
        self, event: HealthEvent, details: dict
    ) -> Intervention | None:
        consecutive = details.get("consecutive_negative", 0)

        if consecutive >= 3:
            # Persistent negative mood — notify caregiver
            return Intervention(
                id=uuid4(),
                type=InterventionType.NOTIFY_CAREGIVER,
                event_id=event.id,
                resident_id=event.resident_id or self.resident_id,
                message=(
                    "Your loved one has been feeling down for several "
                    "interactions in a row. They might benefit from a visit "
                    "or a call."
                ),
                reasoning=(
                    f"Persistent negative mood detected: {consecutive} consecutive "
                    f"negative observations. Notifying caregiver."
                ),
                timestamp=datetime.now(),
            )

        # Single negative mood observation — empathetic conversation
        return Intervention(
            id=uuid4(),
            type=InterventionType.CONVERSATION,
            event_id=event.id,
            resident_id=event.resident_id or self.resident_id,
            message=(
                "I'm here for you. Would you like to talk about how "
                "you're feeling today?"
            ),
            reasoning=f"Negative mood detected. Event: {event.summary}",
            timestamp=datetime.now(),
        )

    def _propose_distress(
        self, event: HealthEvent, details: dict
    ) -> Intervention | None:
        # Distress signals (abnormal vitals, fall, loud cry) → escalate
        return Intervention(
            id=uuid4(),
            type=InterventionType.ESCALATE,
            event_id=event.id,
            resident_id=event.resident_id or self.resident_id,
            message=(
                "A potential health concern has been detected. "
                "Alerting your caregiver immediately."
            ),
            reasoning=f"Distress signal detected: {event.summary}",
            timestamp=datetime.now(),
        )

    def _propose_inactivity(
        self, event: HealthEvent, details: dict
    ) -> Intervention | None:
        inactive_minutes = details.get("inactive_minutes", 0)

        if inactive_minutes >= 180:  # 3+ hours — escalate
            return Intervention(
                id=uuid4(),
                type=InterventionType.ESCALATE,
                event_id=event.id,
                resident_id=event.resident_id or self.resident_id,
                message=(
                    "No activity detected for an extended period. "
                    "Alerting caregiver for a welfare check."
                ),
                reasoning=(
                    f"Prolonged inactivity: {inactive_minutes:.0f} minutes. "
                    f"Exceeds escalation threshold."
                ),
                timestamp=datetime.now(),
            )

        # Shorter inactivity — verbal welfare check
        return Intervention(
            id=uuid4(),
            type=InterventionType.CONVERSATION,
            event_id=event.id,
            resident_id=event.resident_id or self.resident_id,
            message=(
                "Are you okay? I noticed you've been very still "
                "for a while. Just checking in."
            ),
            reasoning=(
                f"Inactivity detected: {inactive_minutes:.0f} minutes. "
                f"Initiating welfare check conversation."
            ),
            timestamp=datetime.now(),
        )
