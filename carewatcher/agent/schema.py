"""
carewatcher/agent/schema.py
Structured JSON schema validation for LLM conversation outputs.
"""
from __future__ import annotations

import json
from typing import Any

from carewatcher.interfaces import EventCategory


class SchemaValidationError(Exception):
    """Raised when LLM output fails JSON schema validation."""


def parse_and_validate_llm_output(json_str: str) -> dict[str, Any]:
    """Parse raw LLM response string and validate schema.

    Expected JSON Schema:
    {
        "category": "MEDICATION" | "SLEEP" | "ACTIVITY" | "MOOD" | "DISTRESS" | "INACTIVITY",
        "summary": str,
        "details": {
            "adherence": bool | None,
            "medication": str | None,
            "mood_label": str | None,
            ...
        },
        "resident_id": str
    }
    """
    if not json_str or not json_str.strip():
        raise SchemaValidationError("Empty LLM output")

    # Clean potential markdown code blocks ```json ... ```
    cleaned = json_str.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise SchemaValidationError(f"Invalid JSON string: {exc}") from exc

    if not isinstance(data, dict):
        raise SchemaValidationError("LLM output root must be a JSON object")

    if "category" not in data or not isinstance(data["category"], str):
        raise SchemaValidationError("Missing or non-string field 'category'")

    valid_categories = {c.name for c in EventCategory}
    category_str = data["category"].upper()
    if category_str not in valid_categories:
        raise SchemaValidationError(
            f"Invalid category '{data['category']}'; must be one of {valid_categories}"
        )

    if "summary" not in data or not isinstance(data["summary"], str):
        raise SchemaValidationError("Missing or non-string field 'summary'")

    if "details" in data and not isinstance(data["details"], dict):
        raise SchemaValidationError("Field 'details' must be a JSON object if present")

    data["category"] = category_str
    return data
