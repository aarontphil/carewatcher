"""
carewatcher/sources/hyperate_source.py
Direct real-time WebSocket client for HypeRate.io live heart rate streaming.

Connects to HypeRate's Phoenix WebSocket channel (e.g. hr:034A7) and streams
live beats directly into the CareWatcher Orchestrator, SQLite database, and
tamper-evident audit ledger with sub-second latency.
"""
from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
from typing import Any, Callable

logger = logging.getLogger(__name__)

HYPERATE_WS_URL = (
    "wss://app.hyperate.io/socket/websocket"
    "?token=bnQ1FoJmfiRprrSUJzrFxt8x8BbllHyqIWq4LsRjV7aCrLuLot6QyCQM9NZRkd9z"
)


class HyperateStreamSource:
    """Manages a background WebSocket connection to HypeRate.io."""

    def __init__(self, channel_id: str = "034A7", on_reading: Callable[[float, str], None] | None = None) -> None:
        self.channel_id = self.clean_channel_id(channel_id)
        self.on_reading = on_reading
        self._running = False
        self._connected = False
        self._thread: threading.Thread | None = None
        self._latest_bpm: float | None = None
        self._last_seen: float = 0.0
        self._error_msg: str | None = None

    @staticmethod
    def clean_channel_id(val: str) -> str:
        """Extract the channel code from a URL or raw ID (e.g. 'https://app.hyperate.io/animation/79/034A7' -> '034A7')."""
        val = (val or "").strip()
        if "/" in val:
            parts = [p for p in val.split("/") if p]
            return parts[-1] if parts else "034A7"
        return val or "034A7"

    def start(self, channel_id: str | None = None) -> None:
        """Start the background listener thread."""
        if channel_id:
            self.channel_id = self.clean_channel_id(channel_id)

        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(
            target=self._run_event_loop,
            daemon=True,
            name=f"hyperate_{self.channel_id}",
        )
        self._thread.start()
        logger.info(f"HypeRate stream thread started for channel '{self.channel_id}'")

    def stop(self) -> None:
        """Stop the background listener thread."""
        self._running = False
        self._connected = False

    def get_status(self) -> dict[str, Any]:
        """Return connection state and telemetry."""
        now = time.time()
        is_active = self._connected and (now - self._last_seen < 30.0) if self._last_seen else self._connected
        return {
            "channel_id": self.channel_id,
            "running": self._running,
            "connected": self._connected,
            "active": is_active,
            "latest_bpm": self._latest_bpm,
            "seconds_since_last_beat": round(now - self._last_seen, 1) if self._last_seen else None,
            "error": self._error_msg,
        }

    def _run_event_loop(self) -> None:
        """Run asyncio event loop in thread."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._connect_and_listen())
        except Exception as exc:
            logger.error(f"HypeRate loop terminated: {exc}")
        finally:
            loop.close()

    async def _connect_and_listen(self) -> None:
        """Maintain persistent WebSocket connection with Phoenix protocol."""
        import websockets

        while self._running:
            ref = 1
            try:
                logger.info(f"Connecting to HypeRate WebSocket for channel {self.channel_id}...")
                async with websockets.connect(HYPERATE_WS_URL) as ws:
                    self._connected = True
                    self._error_msg = None

                    # Join Phoenix channel
                    join_msg = {
                        "topic": f"hr:{self.channel_id}",
                        "event": "phx_join",
                        "payload": {},
                        "ref": ref,
                    }
                    ref += 1
                    await ws.send(json.dumps(join_msg))
                    logger.info(f"HypeRate joined topic hr:{self.channel_id}")

                    last_heartbeat = time.time()

                    while self._running:
                        try:
                            # Periodic Phoenix heartbeat every 25s
                            if time.time() - last_heartbeat >= 25.0:
                                hb_msg = {
                                    "topic": "phoenix",
                                    "event": "heartbeat",
                                    "payload": {},
                                    "ref": ref,
                                }
                                ref += 1
                                await ws.send(json.dumps(hb_msg))
                                last_heartbeat = time.time()

                            # Read next message with short timeout to allow heartbeat checks
                            try:
                                raw_msg = await asyncio.wait_for(ws.recv(), timeout=2.0)
                            except asyncio.TimeoutError:
                                continue

                            data = json.loads(raw_msg)
                            topic = data.get("topic")
                            event = data.get("event")
                            payload = data.get("payload", {})

                            if topic == f"hr:{self.channel_id}" and event == "hr_update":
                                hr_val = payload.get("hr")
                                if hr_val and isinstance(hr_val, (int, float)):
                                    bpm = float(hr_val)
                                    if 30 <= bpm <= 230:
                                        self._latest_bpm = bpm
                                        self._last_seen = time.time()
                                        if self.on_reading:
                                            try:
                                                self.on_reading(bpm, self.channel_id)
                                            except Exception as cb_err:
                                                logger.error(f"Error in HypeRate reading callback: {cb_err}")

                        except websockets.ConnectionClosed:
                            logger.warning("HypeRate WebSocket closed by remote server")
                            break
                        except Exception as loop_err:
                            logger.error(f"Error in HypeRate loop: {loop_err}")
                            break

            except Exception as conn_err:
                self._connected = False
                self._error_msg = str(conn_err)
                logger.warning(f"HypeRate connection failed: {conn_err}. Reconnecting in 3s...")
                await asyncio.sleep(3.0)

            self._connected = False
            if self._running:
                await asyncio.sleep(2.0)
