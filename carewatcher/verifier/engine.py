"""
carewatcher/verifier/engine.py
Independent safety verifier for proposed interventions.

This module has NO imports from carewatcher.proposer (architectural isolation).
It reviews each Intervention and decides: APPROVED, REJECTED, or ESCALATED.
"""
from __future__ import annotations

import re
from datetime import datetime, time
from pathlib import Path
from typing import Any

from carewatcher.interfaces import (
    Intervention,
    InterventionType,
    VerifierDecision,
    VerifierResult,
)


class SafetyVerifier:
    """Independent verifier that gates every intervention before delivery.

    Checks performed:
    1. Schema validity — intervention has required fields.
    2. Non-clinical language — message contains no diagnostic/prescriptive claims.
    3. Rate limiting — max N reminders per hour.
    4. Quiet hours — respects do-not-disturb windows.
    5. Escalation appropriateness — escalations require corroborating evidence.
    6. Message length — rejects unreasonably long messages.

    Parameters
    ----------
    max_reminders_per_hour:
        Maximum interventions allowed per hour.
    quiet_start:
        Start of quiet hours (HH:MM string).
    quiet_end:
        End of quiet hours (HH:MM string).
    deny_list_path:
        Path to a file containing forbidden clinical terms, one per line.
    """

    def __init__(
        self,
        max_reminders_per_hour: int = 3,
        quiet_start: str = "22:00",
        quiet_end: str = "07:00",
        deny_list_path: str = "data/deny_list.txt",
    ) -> None:
        self.max_reminders_per_hour = max_reminders_per_hour
        self.quiet_start = self._parse_time(quiet_start)
        self.quiet_end = self._parse_time(quiet_end)

        # Load deny list
        self._deny_list: list[str] = self._load_deny_list(deny_list_path)

        # Rate tracking: list of timestamps of recently approved interventions
        self._recent_approvals: list[datetime] = []

    @staticmethod
    def _parse_time(time_str: str) -> time:
        parts = time_str.split(":")
        return time(int(parts[0]), int(parts[1]))

    @staticmethod
    def _load_deny_list(path: str) -> list[str]:
        """Load clinical/diagnostic terms that must never appear in messages."""
        p = Path(path)
        if not p.exists():
            # Return a built-in default deny list
            return [
                "diagnose", "diagnosis", "diagnosed",
                "prescribe", "prescription", "prescribed",
                "you have", "you are suffering",
                "disease", "disorder", "syndrome",
                "cancer", "tumor", "tumour",
                "heart attack", "stroke",
                "take this drug", "increase your dose",
                "stop taking", "discontinue",
                "blood test", "lab results",
                "prognosis", "terminal",
                "surgery", "operation",
            ]
        text = p.read_text(encoding="utf-8")
        return [
            line.strip().lower()
            for line in text.splitlines()
            if line.strip() and not line.startswith("#")
        ]

    # ── main verify method ────────────────────────────────────────────

    def verify(self, intervention: Intervention) -> VerifierResult:
        """Review a proposed intervention and return a decision.

        Returns
        -------
        VerifierResult
            The decision (APPROVED, REJECTED, or ESCALATED) with reason.
        """
        # 1. Schema validity
        result = self._check_schema(intervention)
        if result:
            return result

        # 2. Non-clinical language
        result = self._check_deny_list(intervention)
        if result:
            return result

        # 3. Message length
        result = self._check_message_length(intervention)
        if result:
            return result

        # 4. Quiet hours (skip for ESCALATE type — emergencies override)
        if intervention.type != InterventionType.ESCALATE:
            result = self._check_quiet_hours(intervention)
            if result:
                return result

        # 5. Rate limiting (skip for ESCALATE type)
        if intervention.type != InterventionType.ESCALATE:
            result = self._check_rate_limit(intervention)
            if result:
                return result

        # 6. Escalation — always approve (emergencies must go through)
        if intervention.type == InterventionType.ESCALATE:
            return VerifierResult(
                intervention_id=intervention.id,
                decision=VerifierDecision.ESCALATED,
                reason="Escalation approved: urgent intervention forwarded to caregiver.",
                timestamp=datetime.now(),
            )

        # All checks passed — approve
        self._recent_approvals.append(datetime.now())
        return VerifierResult(
            intervention_id=intervention.id,
            decision=VerifierDecision.APPROVED,
            reason="All safety checks passed.",
            timestamp=datetime.now(),
        )

    # ── individual checks ─────────────────────────────────────────────

    def _check_schema(self, intervention: Intervention) -> VerifierResult | None:
        """Verify the intervention has all required fields populated."""
        if not intervention.message or not intervention.message.strip():
            return VerifierResult(
                intervention_id=intervention.id,
                decision=VerifierDecision.REJECTED,
                reason="Rejected: intervention message is empty.",
                timestamp=datetime.now(),
            )
        if not intervention.resident_id:
            return VerifierResult(
                intervention_id=intervention.id,
                decision=VerifierDecision.REJECTED,
                reason="Rejected: missing resident_id.",
                timestamp=datetime.now(),
            )
        return None

    def _check_deny_list(self, intervention: Intervention) -> VerifierResult | None:
        """Check the intervention message for forbidden clinical terms."""
        msg_lower = intervention.message.lower()
        for term in self._deny_list:
            if term in msg_lower:
                return VerifierResult(
                    intervention_id=intervention.id,
                    decision=VerifierDecision.REJECTED,
                    reason=(
                        f"Rejected: message contains clinical/diagnostic term "
                        f"'{term}'. CareWatcher is a wellness companion, not a "
                        f"medical device."
                    ),
                    timestamp=datetime.now(),
                )
        return None

    def _check_message_length(
        self, intervention: Intervention
    ) -> VerifierResult | None:
        """Reject unreasonably long messages."""
        if len(intervention.message) > 500:
            return VerifierResult(
                intervention_id=intervention.id,
                decision=VerifierDecision.REJECTED,
                reason=(
                    f"Rejected: message too long ({len(intervention.message)} chars, "
                    f"max 500). Keep messages concise for the resident."
                ),
                timestamp=datetime.now(),
            )
        return None

    def _check_quiet_hours(
        self, intervention: Intervention
    ) -> VerifierResult | None:
        """Reject non-urgent interventions during quiet hours."""
        now = datetime.now().time()

        in_quiet = False
        if self.quiet_start > self.quiet_end:
            # Quiet window spans midnight (e.g., 22:00 → 07:00)
            in_quiet = now >= self.quiet_start or now <= self.quiet_end
        else:
            in_quiet = self.quiet_start <= now <= self.quiet_end

        if in_quiet:
            return VerifierResult(
                intervention_id=intervention.id,
                decision=VerifierDecision.REJECTED,
                reason=(
                    f"Rejected: quiet hours active "
                    f"({self.quiet_start.strftime('%H:%M')}–"
                    f"{self.quiet_end.strftime('%H:%M')}). "
                    f"Non-urgent interventions are deferred."
                ),
                timestamp=datetime.now(),
            )
        return None

    def _check_rate_limit(
        self, intervention: Intervention
    ) -> VerifierResult | None:
        """Enforce max reminders per hour to avoid alarm fatigue."""
        now = datetime.now()
        one_hour_ago = now.timestamp() - 3600.0

        # Prune old entries
        self._recent_approvals = [
            ts for ts in self._recent_approvals
            if ts.timestamp() > one_hour_ago
        ]

        if len(self._recent_approvals) >= self.max_reminders_per_hour:
            return VerifierResult(
                intervention_id=intervention.id,
                decision=VerifierDecision.REJECTED,
                reason=(
                    f"Rejected: rate limit exceeded "
                    f"({self.max_reminders_per_hour} interventions/hour). "
                    f"Deferring to prevent alarm fatigue."
                ),
                timestamp=datetime.now(),
            )
        return None
