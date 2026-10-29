"""
carewatcher/shutter/gate.py
Privacy shutter hard-gate implementation.

When closed, no data is allowed to pass downstream.
"""
from __future__ import annotations

import threading
from typing import Any, Callable, TypeVar

from carewatcher.interfaces import ShutterState

T = TypeVar("T")


class PrivacyShutter:
    """Thread-safe privacy shutter hard gate."""

    def __init__(self, initial_state: ShutterState = ShutterState.CLOSED) -> None:
        self._state = initial_state
        self._lock = threading.Lock()

    @property
    def state(self) -> ShutterState:
        with self._lock:
            return self._state

    @property
    def is_open(self) -> bool:
        return self.state == ShutterState.OPEN

    @property
    def is_closed(self) -> bool:
        return self.state == ShutterState.CLOSED

    def open(self) -> None:
        with self._lock:
            self._state = ShutterState.OPEN

    def close(self) -> None:
        with self._lock:
            self._state = ShutterState.CLOSED

    def toggle(self) -> ShutterState:
        with self._lock:
            if self._state == ShutterState.OPEN:
                self._state = ShutterState.CLOSED
            else:
                self._state = ShutterState.OPEN
            return self._state

    def gate(self, data: T) -> T | None:
        """Pass data through if shutter is OPEN, otherwise return None."""
        if self.is_open:
            return data
        return None

    def execute_gated(self, func: Callable[[], T]) -> T | None:
        """Execute callback if shutter is OPEN, otherwise return None."""
        if self.is_open:
            return func()
        return None
