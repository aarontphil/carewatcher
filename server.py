"""
server.py — CareWatcher Web Dashboard Local Server
Uses standard library http.server (no external web framework required).

This server wires up the full CareWatcher orchestrator and exposes
API endpoints for the web dashboard to control and monitor the system.
"""
import json
import logging
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from carewatcher.config import load_config
from carewatcher.orchestrator import CareWatcherOrchestrator
from carewatcher.sources.hyperate_source import HyperateStreamSource

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("carewatcher.server")

# Initialize the full orchestrator (all components wired together)
CONFIG = load_config("config.yaml")
ORCHESTRATOR = CareWatcherOrchestrator(config=CONFIG)

def _on_hyperate_reading(bpm: float, channel: str) -> None:
    """Callback when a real live beat arrives from HypeRate."""
    ORCHESTRATOR.ingest_apple_watch_data({
        "bpm": bpm,
        "source": f"HypeRate Live (Apple Watch {channel})",
    })

HYPERATE_SOURCE = HyperateStreamSource(channel_id="034A7", on_reading=_on_hyperate_reading)

WEB_DIR = Path(__file__).parent / "web"



class CareWatcherHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the CareWatcher web dashboard."""

    def log_message(self, format: str, *args) -> None:
        """Suppress default stderr logging — use Python logging instead."""
        logger.debug(format % args)

    def _send_json(self, data: dict, status: int = 200) -> None:
        try:
            body = json.dumps(data, default=str).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
            pass

    def _serve_file(self, rel_path: str) -> None:
        try:
            file_path = WEB_DIR / rel_path
            if not file_path.exists() or not file_path.is_file():
                self.send_error(404, "File Not Found")
                return

            mime_type, _ = mimetypes.guess_type(str(file_path))
            content = file_path.read_bytes()

            self.send_response(200)
            self.send_header("Content-Type", mime_type or "text/plain")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
            pass

    def do_HEAD(self) -> None:
        path = self.path.split("?")[0]
        if path in ("/", "/landing", "/landing.html"):
            self._serve_file_head("landing.html")
        elif path in ("/dashboard", "/index.html", "/app", "/audit", "/ledger", "/logs"):
            self._serve_file_head("index.html")
        elif (WEB_DIR / path.lstrip("/")).is_file():
            self._serve_file_head(path.lstrip("/"))
        else:
            self.send_response(200)
            self.end_headers()

    def _serve_file_head(self, rel_path: str) -> None:
        try:
            file_path = WEB_DIR / rel_path
            if not file_path.exists() or not file_path.is_file():
                self.send_error(404, "File Not Found")
                return

            mime_type, _ = mimetypes.guess_type(str(file_path))
            content = file_path.read_bytes()

            self.send_response(200)
            self.send_header("Content-Type", mime_type or "text/plain")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
            pass

    def do_GET(self) -> None:
        path = self.path.split("?")[0]
        # ── static files ──────────────────────────────────────────────
        if path in ("/", "/landing", "/landing.html"):
            self._serve_file("landing.html")
        elif path in ("/dashboard", "/index.html", "/app", "/audit", "/ledger", "/logs"):
            self._serve_file("index.html")
        elif (WEB_DIR / path.lstrip("/")).is_file():
            self._serve_file(path.lstrip("/"))

        # ── API: system status ────────────────────────────────────────
        elif path == "/api/status":
            self._send_json(ORCHESTRATOR.get_status())

        # ── API: recent events ────────────────────────────────────────
        elif path == "/api/events":
            self._send_json({"events": ORCHESTRATOR.get_recent_events()})

        # ── API: sensor data ──────────────────────────────────────────
        elif path == "/api/sensors":
            s_data = ORCHESTRATOR.get_recent_sensor_data()
            self._send_json({
                "sensors": s_data,
                "readings": ORCHESTRATOR.memory.get_sensor_readings(limit=25),
                "shutter_state": ORCHESTRATOR.shutter.state.name,
                "vital_source": s_data.get("vital_source", "Simulated Hardware Twin"),
                "vital_source_timestamp": s_data.get("vital_source_timestamp", ""),
                "apple_watch_steps": s_data.get("apple_watch_steps"),
                "apple_watch_hrv": s_data.get("apple_watch_hrv"),
                "hardware_connected": (
                    ORCHESTRATOR._serial_source is not None
                    and getattr(ORCHESTRATOR._serial_source, "_serial", None) is not None
                ),
            })

        # ── API: audit log ────────────────────────────────────────────
        elif path == "/api/audit":
            self._send_json({
                "entries": ORCHESTRATOR.get_audit_log(),
                "chain_valid": ORCHESTRATOR.audit.verify_chain(),
                "total_entries": ORCHESTRATOR.audit.entry_count(),
            })

        # ── API: medication adherence ─────────────────────────────────
        elif path == "/api/medication":
            self._send_json({
                "adherence": ORCHESTRATOR.get_medication_adherence(),
            })

        # ── API: mood history ─────────────────────────────────────────
        elif path == "/api/mood":
            self._send_json({
                "moods": ORCHESTRATOR.get_mood_history(),
                "latest_valence": ORCHESTRATOR._recent_sensor_data.get("facial_mood_valence"),
                "latest_label": ORCHESTRATOR._recent_sensor_data.get("facial_mood_label"),
                "latest_facial_reading": ORCHESTRATOR._last_facial_reading,
            })

        # ── API: audio & mic hardware status ─────────────────────────
        elif path == "/api/audio/status":
            dev_info = []
            def_dev_name = "Default"
            try:
                import sounddevice as sd
                devs = sd.query_devices()
                def_in = sd.default.device[0]
                def_dev_name = devs[def_in]["name"] if def_in is not None and def_in < len(devs) else "Default"
                for idx, d in enumerate(devs):
                    if d.get("max_input_channels", 0) > 0:
                        dev_info.append({
                            "index": idx,
                            "name": d.get("name", ""),
                            "channels": d.get("max_input_channels", 1),
                            "is_default": (idx == def_in),
                        })
            except Exception as e:
                dev_info = [{"index": 0, "name": f"Error: {e}", "channels": 1, "is_default": True}]

            self._send_json({
                "devices": dev_info,
                "default_device": def_dev_name,
                "stt_engine": ORCHESTRATOR.config.stt.engine,
                "stt_model": ORCHESTRATOR.config.stt.model_size,
                "shutter_state": ORCHESTRATOR.shutter.state.name,
            })

        # ── API: HypeRate live stream status ─────────────────────────
        elif path == "/api/hyperate/status":
            self._send_json(HYPERATE_SOURCE.get_status())

        # ── API: AI conversational model status ──────────────────────
        elif path == "/api/llm/status":
            agent = getattr(ORCHESTRATOR, "agent", None)
            if hasattr(agent, "get_status"):
                self._send_json(agent.get_status())
            else:
                self._send_json({
                    "provider": "gemini",
                    "model": "gemini-2.0-flash",
                    "has_key": False,
                    "status": "needs_key"
                })

        else:
            self.send_error(404, "Not Found")


    def do_POST(self) -> None:
        path = self.path.split("?")[0]
        content_len = int(self.headers.get("Content-Length", 0))
        post_body = self.rfile.read(content_len).decode("utf-8") if content_len > 0 else ""

        # ── API: toggle shutter ───────────────────────────────────────
        if path == "/api/shutter/toggle":
            new_state = ORCHESTRATOR.toggle_shutter()
            ORCHESTRATOR.audit.append("shutter_toggled", {
                "new_state": new_state.name,
            })
            self._send_json({"new_state": new_state.name})

        # ── API: Apple Watch / HealthKit biometric webhook ────────────
        elif path == "/api/sensor/apple_watch":
            try:
                payload = json.loads(post_body) if post_body else {}
                result = ORCHESTRATOR.ingest_apple_watch_data(payload)
                self._send_json(result)
            except Exception as exc:
                self._send_json({"error": str(exc)}, status=400)

        # ── API: Apple Watch quick simulation test ────────────────────
        elif path == "/api/sensor/apple_watch/simulate_test":
            sample_payload = {
                "source": "Apple Watch Ultra 2",
                "bpm": 74.5,
                "spo2": 98.8,
                "wrist_temp": 36.6,
                "steps": 6480,
                "hrv_ms": 48.5,
            }
            result = ORCHESTRATOR.ingest_apple_watch_data(sample_payload)
            self._send_json(result)

        # ── API: HypeRate live stream connect / update channel ────────
        elif path == "/api/hyperate/connect":
            try:
                payload = json.loads(post_body) if post_body else {}
                raw_channel = payload.get("channel") or payload.get("url") or "034A7"
                ch = HyperateStreamSource.clean_channel_id(raw_channel)
                HYPERATE_SOURCE.stop()
                HYPERATE_SOURCE.start(channel_id=ch)
                self._send_json({"status": "connecting", "channel_id": ch})
            except Exception as exc:
                self._send_json({"error": str(exc)}, status=400)

        # ── API: HypeRate live stream disconnect ──────────────────────
        elif path == "/api/hyperate/disconnect":
            HYPERATE_SOURCE.stop()
            self._send_json({"status": "disconnected"})


        # ── API: direct hardware microphone record & transcribe ───────
        elif path == "/api/audio/record_and_transcribe":
            try:
                payload = json.loads(post_body) if post_body else {}
                duration = float(payload.get("duration", 3.0))
            except Exception:
                duration = 3.0

            # Record directly from laptop microphone
            chunk = ORCHESTRATOR.mic.record_seconds(duration_sec=duration)
            transcript = ORCHESTRATOR.stt.transcribe(chunk)

            transcribed_text = transcript.text.strip()
            if not transcribed_text:
                self._send_json({
                    "transcript": {"text": "", "confidence": 0.0},
                    "message": "No audible speech recognized in the recorded audio sample.",
                })
                return

            # Feed through conversation agent & clinical pipeline with raw audio samples
            result = ORCHESTRATOR.process_voice_input(
                transcribed_text,
                audio_chunk_samples=chunk.samples,
            )
            self._send_json(result)

        # ── API: process voice/text input ─────────────────────────────
        elif path == "/api/process_transcript":
            try:
                payload = json.loads(post_body) if post_body else {}
                text = payload.get("text", "")
                audio_metrics = payload.get("audio_metrics")
                facial_data = payload.get("facial_data")
            except Exception:
                text = ""
                audio_metrics = None
                facial_data = None

            if not text.strip():
                self._send_json({"error": "Empty input"}, status=400)
                return

            if facial_data and isinstance(facial_data, dict) and facial_data.get("face_detected"):
                ORCHESTRATOR.store_facial_reading(facial_data)

            result = ORCHESTRATOR.process_voice_input(text, audio_metrics=audio_metrics)
            self._send_json(result)

        # ── API: analyze video frame for continuous facial mood ───────
        elif path == "/api/mood/analyze_frame":
            try:
                import base64
                import cv2
                import numpy as np

                payload = json.loads(post_body) if post_body else {}
                img_data = payload.get("image", "")
                if "," in img_data:
                    img_data = img_data.split(",", 1)[1]

                img_bytes = base64.b64decode(img_data)
                np_arr = np.frombuffer(img_bytes, np.uint8)
                frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

                if ORCHESTRATOR.shutter.state.name != "OPEN":
                    self._send_json({"blocked": True, "reason": "Privacy shutter is CLOSED"}, status=403)
                    return

                if frame is not None and ORCHESTRATOR._webcam_source:
                    mood_res = ORCHESTRATOR._webcam_source.analyze_external_frame(frame)
                    if mood_res.face_detected:
                        facial_data_dict = {
                            "mood_label": mood_res.mood_label,
                            "confidence": mood_res.confidence,
                            "valence": mood_res.valence,
                            "arousal": mood_res.arousal,
                            "smile_score": mood_res.smile_score,
                            "brow_tension": mood_res.brow_tension,
                            "eye_openness": getattr(mood_res, "eye_openness", 0.75),
                            "mouth_openness": getattr(mood_res, "mouth_openness", 0.10),
                            "head_tilt": getattr(mood_res, "head_tilt", 0.0),
                            "symmetry_score": getattr(mood_res, "symmetry_score", 0.95),
                            "secondary_emotion": getattr(mood_res, "secondary_emotion", "calm"),
                            "confusion_index": getattr(mood_res, "confusion_index", 0.0),
                            "discomfort_index": getattr(mood_res, "discomfort_index", 0.0),
                            "attention_score": getattr(mood_res, "attention_score", 0.85),
                            "lighting_quality": getattr(mood_res, "lighting_quality", "Optimal (Daylight)"),
                            "emotion_probabilities": getattr(mood_res, "emotion_probabilities", {}),
                            "face_detected": mood_res.face_detected,
                            "bbox": mood_res.bbox,
                        }
                        # Stores cached facial reading, updates mood history, and runs trend drift check once
                        ORCHESTRATOR.store_facial_reading(facial_data_dict)

                        from carewatcher.interfaces import SensorReading
                        reading = SensorReading(
                            sensor_id="facial_mood",
                            value=mood_res.valence,
                            unit="valence",
                            metadata={
                                "mood_label": mood_res.mood_label,
                                "confidence": str(mood_res.confidence),
                                "valence": str(mood_res.valence),
                                "arousal": str(mood_res.arousal),
                                "smile_score": str(mood_res.smile_score),
                                "brow_tension": str(mood_res.brow_tension),
                                "source": "webcam_stream",
                            },
                        )
                        gated = ORCHESTRATOR.shutter.gate(reading)
                        if gated:
                            ORCHESTRATOR.memory.store_sensor_reading(gated)
                            # Note: Camera rPPG BPM is switched off. Real BPM is exclusively from HypeRate.

                    self._send_json({
                        "face_detected": mood_res.face_detected,
                        "mood_label": mood_res.mood_label,
                        "confidence": mood_res.confidence,
                        "valence": mood_res.valence,
                        "arousal": mood_res.arousal,
                        "smile_score": mood_res.smile_score,
                        "brow_tension": mood_res.brow_tension,
                        "bbox": mood_res.bbox,
                        "frame_width": int(frame.shape[1]),
                        "frame_height": int(frame.shape[0]),
                        "secondary_emotion": getattr(mood_res, "secondary_emotion", "calm"),
                        "eye_openness": getattr(mood_res, "eye_openness", 0.75),
                        "mouth_openness": getattr(mood_res, "mouth_openness", 0.10),
                        "head_tilt": getattr(mood_res, "head_tilt", 0.0),
                        "symmetry_score": getattr(mood_res, "symmetry_score", 0.95),
                        "confusion_index": getattr(mood_res, "confusion_index", 0.0),
                        "discomfort_index": getattr(mood_res, "discomfort_index", 0.0),
                        "attention_score": getattr(mood_res, "attention_score", 0.85),
                        "lighting_quality": getattr(mood_res, "lighting_quality", "Optimal (Daylight)"),
                        "emotion_probabilities": getattr(mood_res, "emotion_probabilities", {}),
                    })

                else:
                    self._send_json({"error": "Unable to decode frame"}, status=400)
            except Exception as exc:
                self._send_json({"error": str(exc)}, status=400)

        # ── API: deep multimodal AI clinical vision scan ─────────────
        elif path == "/api/mood/deep_scan":
            try:
                import base64
                import cv2
                import numpy as np

                payload = json.loads(post_body) if post_body else {}
                img_data = payload.get("image", "")
                if "," in img_data:
                    img_data = img_data.split(",", 1)[1]

                img_bytes = base64.b64decode(img_data)
                np_arr = np.frombuffer(img_bytes, np.uint8)
                frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

                if frame is not None and ORCHESTRATOR._webcam_source:
                    mood_res = ORCHESTRATOR._webcam_source.analyze_external_frame(frame)
                    # Compose clinical reasoning from multi-parametric features
                    primary = mood_res.mood_label.upper()
                    conf = int(mood_res.confidence * 100)
                    sec = getattr(mood_res, "secondary_emotion", "calm").title()
                    eye_op = getattr(mood_res, "eye_openness", 0.75)
                    disc = getattr(mood_res, "discomfort_index", 0.0)
                    conf_idx = getattr(mood_res, "confusion_index", 0.0)
                    symm = int(getattr(mood_res, "symmetry_score", 0.95) * 100)
                    brow = getattr(mood_res, "brow_tension", 25.0)

                    # Clinical evaluation logic
                    clinical_summary = []
                    clinical_summary.append(f"Resident Aaron presents primarily with **{primary}** affect ({conf}% confidence), with secondary subtle **{sec}** indicators.")
                    if getattr(mood_res, "smile_score", 0.0) >= 0.20:
                        clinical_summary.append(f"😊 **Positive Affect Indicator**: Active zygomatic cheer observed ({int(getattr(mood_res, 'smile_score', 0.0)*100)}% smile).")
                    elif eye_op < 0.35:
                        clinical_summary.append(f"😴 **Fatigue / Drowsiness Indicator**: Ocular aperture is constricted ({int(eye_op*100)}% openness), suggesting sleep pressure or cognitive fatigue.")
                    elif conf_idx > 0.40:
                        clinical_summary.append(f"🤔 **Cognitive Strain**: Brow asymmetry and focal head tilt indicate active cognitive processing or slight perplexity ({int(conf_idx*100)}%).")
                    else:
                        clinical_summary.append(f"✓ **Equilibrium Maintained**: Facial musculature is relaxed with stable bilateral symmetry ({symm}%). No acute distress observed.")

                    self._send_json({
                        "status": "success",
                        "model": "Clinical Multi-Parametric FACS Engine v2.4",
                        "primary_emotion": primary,
                        "confidence": conf,
                        "secondary_emotion": sec,
                        "valence": mood_res.valence,
                        "arousal": mood_res.arousal,
                        "eye_openness": eye_op,
                        "discomfort_index": disc,
                        "confusion_index": conf_idx,
                        "symmetry_pct": symm,
                        "clinical_narrative": " ".join(clinical_summary),
                        "probabilities": getattr(mood_res, "emotion_probabilities", {}),
                    })
                else:
                    self._send_json({"error": "Unable to decode frame for deep scan"}, status=400)
            except Exception as exc:
                self._send_json({"error": str(exc)}, status=400)

        # ── API: record telemetry / browser sensor data ───────────────
        elif path == "/api/sensor/record":
            try:
                from carewatcher.interfaces import SensorReading
                payload = json.loads(post_body) if post_body else {}
                s_id = str(payload.get("sensor_id", "webcam_presence"))
                val = float(payload.get("value", 1.0))
                unit = str(payload.get("unit", "detected"))
                reading = SensorReading(sensor_id=s_id, value=val, unit=unit)
                gated = ORCHESTRATOR.shutter.gate(reading)
                if gated:
                    ORCHESTRATOR.memory.store_sensor_reading(gated)
                    ORCHESTRATOR._recent_sensor_data[gated.sensor_id] = gated.value
                    if "mood" in payload:
                        mood_str = str(payload["mood"])
                        conf = float(payload.get("confidence", 0.9))
                        ORCHESTRATOR.memory.store_mood(mood_str, conf)
                        alerts = ORCHESTRATOR.trend.ingest_mood(mood_str)
                        for alert in alerts:
                            ORCHESTRATOR._process_health_event(alert)
                self._send_json({"recorded": gated is not None})
            except Exception as exc:
                self._send_json({"error": str(exc)}, status=400)

        # ── API: explicit camera hardware release ─────────────────────
        elif path == "/api/camera/release":
            try:
                if hasattr(ORCHESTRATOR, "_webcam_source") and ORCHESTRATOR._webcam_source:
                    ORCHESTRATOR._webcam_source.close()
                self._send_json({"released": True, "message": "Hardware camera device released"})
            except Exception as exc:
                self._send_json({"error": str(exc)}, status=500)

        # ── API: configure Gemini API Key and model ──────────────────
        elif path == "/api/llm/config":
            try:
                payload = json.loads(post_body) if post_body else {}
                api_key = str(payload.get("api_key", "")).strip()
                model_name = str(payload.get("model_name", "gemini-2.0-flash")).strip()
                agent = getattr(ORCHESTRATOR, "agent", None)
                if hasattr(agent, "set_api_key"):
                    success = agent.set_api_key(api_key, model_name=model_name)
                    self._send_json({
                        "success": success,
                        "status": agent.get_status(),
                        "message": "Gemini configuration saved and loaded into active companion"
                    })
                else:
                    self._send_json({"error": "Conversation agent does not support runtime key updates"}, status=400)
            except Exception as exc:
                self._send_json({"error": str(exc)}, status=400)

        # ── API: test Gemini connection ──────────────────────────────
        elif path == "/api/llm/test":
            try:
                from carewatcher.interfaces import Transcript
                from datetime import datetime
                agent = getattr(ORCHESTRATOR, "agent", None)
                test_prompt = "Hello! Are you ready to care for Aaron?"
                t = Transcript(text=test_prompt, confidence=1.0, timestamp=datetime.now())
                if hasattr(agent, "converse"):
                    sensors = ORCHESTRATOR.get_recent_sensor_data()
                    recent_moods = ORCHESTRATOR.get_mood_history(1)
                    latest_mood = recent_moods[0]["mood_label"] if recent_moods else "calm"
                    context = {
                        "bpm": sensors.get("max30102_bpm"),
                        "spo2": sensors.get("max30102_spo2"),
                        "mood": latest_mood,
                    }
                    event, reply = agent.converse(t, context=context)
                    self._send_json({
                        "prompt": test_prompt,
                        "reply": reply,
                        "event": {"category": event.category.name, "summary": event.summary},
                        "status": agent.get_status() if hasattr(agent, "get_status") else {}
                    })
                else:
                    self._send_json({"error": "No active conversation agent"}, status=400)
            except Exception as exc:
                self._send_json({"error": str(exc)}, status=500)

        else:
            self.send_error(404, "Not Found")


def run_server(port: int = 8000) -> None:
    """Start the CareWatcher local web server."""
    # Start the orchestrator (opens database, initializes sensors)
    ORCHESTRATOR.start()

    server_address = ("0.0.0.0", port)
    httpd = ThreadingHTTPServer(server_address, CareWatcherHandler)
    httpd.daemon_threads = True

    print("=" * 60)
    print("  +---------------------------------------------------+")
    print("  |         CAREWATCHER -- Local Dashboard            |")
    print(f"  |   Running at: http://localhost:{port}              |")
    print("  |   Press Ctrl+C to stop                            |")
    print("  +---------------------------------------------------+")
    print("=" * 60)
    print(f"  Resident     : {CONFIG.resident.name}")
    print(f"  Shutter      : {ORCHESTRATOR.shutter.state.name}")
    print(f"  STT          : Whisper ({CONFIG.stt.model_size})")
    print(f"  Wake Word    : '{CONFIG.wake_word.keyword}'")
    print(f"  LLM          : {CONFIG.llm.backend}")
    print(f"  Database     : data/resident.db")
    print(f"  Audit Log    : {CONFIG.audit.log_path}")
    print(f"  HypeRate Live: wss://app.hyperate.io (Channel {HYPERATE_SOURCE.channel_id})")
    print("=" * 60)

    # Automatically start HypeRate live stream listener
    try:
        HYPERATE_SOURCE.start()
    except Exception as e:
        logger.warning(f"Could not start HypeRate live listener: {e}")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping CareWatcher...")
        HYPERATE_SOURCE.stop()
        ORCHESTRATOR.stop()
        httpd.server_close()
        print("CareWatcher stopped.")



if __name__ == "__main__":
    run_server()
