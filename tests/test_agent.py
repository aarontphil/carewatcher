"""Tests for carewatcher.agent — Conversation Agent and Schema validation."""
from __future__ import annotations

from datetime import datetime

import pytest

from carewatcher.agent.conversation import DummyConversationAgent, LLMConversationAgent
from carewatcher.agent.schema import SchemaValidationError, parse_and_validate_llm_output
from carewatcher.interfaces import ConversationAgent, EventCategory, HealthEvent, Transcript


class TestSchemaValidation:
    def test_valid_json_parsing(self) -> None:
        raw_json = '{"category": "MEDICATION", "summary": "Pills taken", "details": {"adherence": true}}'
        data = parse_and_validate_llm_output(raw_json)
        assert data["category"] == "MEDICATION"
        assert data["summary"] == "Pills taken"
        assert data["details"]["adherence"] is True

    def test_markdown_code_block_stripping(self) -> None:
        raw_json = "```json\n{\"category\": \"MOOD\", \"summary\": \"Feeling good\"}\n```"
        data = parse_and_validate_llm_output(raw_json)
        assert data["category"] == "MOOD"

    def test_invalid_json_raises(self) -> None:
        with pytest.raises(SchemaValidationError, match="Invalid JSON"):
            parse_and_validate_llm_output("not json")

    def test_missing_category_raises(self) -> None:
        with pytest.raises(SchemaValidationError, match="category"):
            parse_and_validate_llm_output('{"summary": "No category"}')

    def test_invalid_category_raises(self) -> None:
        with pytest.raises(SchemaValidationError, match="Invalid category"):
            parse_and_validate_llm_output('{"category": "INVALID_CAT", "summary": "Bad"}')


class TestConversationAgent:
    def test_dummy_agent_implements_protocol(self) -> None:
        agent = DummyConversationAgent()
        assert isinstance(agent, ConversationAgent)

    def test_llm_agent_implements_protocol(self) -> None:
        agent = LLMConversationAgent()
        assert isinstance(agent, ConversationAgent)

    def test_medication_taken_extraction(self) -> None:
        agent = DummyConversationAgent(resident_id="arun")
        t = Transcript(text="Yes I took my BP tablet this morning", confidence=0.9, timestamp=datetime.now())
        event = agent.respond(t)
        assert isinstance(event, HealthEvent)
        assert event.category == EventCategory.MEDICATION
        assert event.details.get("adherence") is True

    def test_medication_missed_extraction(self) -> None:
        agent = DummyConversationAgent(resident_id="arun")
        t = Transcript(text="Oh no I forgot to take my pills", confidence=0.85, timestamp=datetime.now())
        event = agent.respond(t)
        assert isinstance(event, HealthEvent)
        assert event.category == EventCategory.MEDICATION
        assert event.details.get("adherence") is False

    def test_mood_sad_extraction(self) -> None:
        agent = DummyConversationAgent(resident_id="arun")
        t = Transcript(text="I'm feeling quite sad today", confidence=0.9, timestamp=datetime.now())
        event = agent.respond(t)
        assert isinstance(event, HealthEvent)
        assert event.category == EventCategory.MOOD
        assert event.details.get("mood_label") == "sad"
