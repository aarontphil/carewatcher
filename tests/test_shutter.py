"""Tests for carewatcher.shutter.gate — PrivacyShutter hard gate."""
from __future__ import annotations

import pytest

from carewatcher.interfaces import ShutterState
from carewatcher.shutter.gate import PrivacyShutter


class TestPrivacyShutter:
    def test_default_state_closed(self) -> None:
        shutter = PrivacyShutter(ShutterState.CLOSED)
        assert shutter.state == ShutterState.CLOSED
        assert shutter.is_closed
        assert not shutter.is_open

    def test_open_close(self) -> None:
        shutter = PrivacyShutter(ShutterState.CLOSED)
        shutter.open()
        assert shutter.is_open
        assert not shutter.is_closed

        shutter.close()
        assert shutter.is_closed

    def test_toggle(self) -> None:
        shutter = PrivacyShutter(ShutterState.CLOSED)
        new_state = shutter.toggle()
        assert new_state == ShutterState.OPEN
        assert shutter.is_open

        new_state = shutter.toggle()
        assert new_state == ShutterState.CLOSED
        assert shutter.is_closed

    def test_gate_allows_when_open(self) -> None:
        shutter = PrivacyShutter(ShutterState.OPEN)
        data = "sensor_data_payload"
        assert shutter.gate(data) == data

    def test_gate_blocks_when_closed(self) -> None:
        shutter = PrivacyShutter(ShutterState.CLOSED)
        data = "sensor_data_payload"
        assert shutter.gate(data) is None

    def test_execute_gated(self) -> None:
        shutter = PrivacyShutter(ShutterState.OPEN)
        called = False

        def action() -> str:
            nonlocal called
            called = True
            return "result"

        assert shutter.execute_gated(action) == "result"
        assert called

        shutter.close()
        called = False
        assert shutter.execute_gated(action) is None
        assert not called
