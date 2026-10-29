"""
demo.py — End-to-End Visual Demonstration of CareWatcher (M0 to M8 Complete Pipeline).
Runs entirely locally with zero cloud dependencies.
"""
from datetime import datetime
from carewatcher.config import load_config
from carewatcher.interfaces import (
    AudioChunk, ShutterState, EventCategory, HealthEvent, InterventionType
)
from carewatcher.shutter.gate import PrivacyShutter
from carewatcher.sources.audio_sim import AudioSimulator
from carewatcher.stt.engine import DummySTTEngine
from carewatcher.stt.wake_word import KeywordWakeWordDetector
from carewatcher.agent.conversation import DummyConversationAgent
from carewatcher.memory.store import ResidentMemoryStore
from carewatcher.memory.trend import TrendEngine
from carewatcher.proposer.engine import RuleBasedProposer
from carewatcher.verifier.engine import SafetyVerifier
from carewatcher.audit.logger import AuditLogger


def main() -> None:
    print("=" * 70)
    print("      CAREWATCHER -- FULL LOCAL PIPELINE DEMO (M0 to M8)")
    print("             100% On-Device  |  Zero Cloud Egress")
    print("=" * 70)

    # 1. Config
    print("\n[1] Loading Configuration...")
    cfg = load_config("config.yaml")
    print(f"    Resident Name : {cfg.resident.name}")
    print(f"    STT Engine    : {cfg.stt.engine} ({cfg.stt.model_size})")
    print(f"    Wake Word     : '{cfg.wake_word.keyword}'")
    print(f"    Audit Path    : {cfg.audit.log_path}")

    # 2. Privacy Shutter Hard Gate
    print("\n[2] Privacy Shutter (Hardware Root Boundary)...")
    shutter = PrivacyShutter(initial_state=ShutterState.CLOSED)
    print(f"    Initial State : {shutter.state.name}")

    audio_sim = AudioSimulator(num_chunks=1)
    audio_sim.open()
    chunk = audio_sim.read()
    gated = shutter.gate(chunk)
    print(f"    Attempting read while CLOSED : {'PASSED' if gated is not None else 'BLOCKED by Shutter (0 bytes passed)'}")

    shutter.open()
    print(f"    Toggled State : {shutter.state.name}")
    gated_open = shutter.gate(chunk)
    print(f"    Attempting read while OPEN   : ALLOWED ({len(gated_open.samples)} bytes passed)")
    audio_sim.close()

    # 3. STT, Wake Word & Agent
    print("\n[3] Speech-to-Text & Conversational Agent...")
    stt = DummySTTEngine(default_text="hey care I forgot to take my morning blood pressure pills")
    wake_detector = KeywordWakeWordDetector(keyword=cfg.wake_word.keyword)
    agent = DummyConversationAgent(resident_id=cfg.resident.name)

    transcript = stt.transcribe(gated_open)
    wake_hit = wake_detector.detect(transcript)
    health_event = agent.respond(transcript)

    print(f"    Spoken Text    : \"{transcript.text}\"")
    print(f"    Wake Detected  : {wake_hit} ('{cfg.wake_word.keyword}')")
    print(f"    Agent Output   : Category={health_event.category.name} | Summary=\"{health_event.summary}\"")

    # 4. Local SQLite Memory Store
    print("\n[4] Local SQLite Memory Store (data/resident.db)...")
    memory = ResidentMemoryStore(db_path="data/demo_resident.db", resident_id=cfg.resident.name)
    memory.open()
    memory.store_event(health_event)
    events = memory.get_events(category=EventCategory.MEDICATION)
    print(f"    Events in DB   : {len(events)} persisted locally")

    # 5. Trend Engine & Baseline Drift Detection
    print("\n[5] Rolling Baseline Trend Engine...")
    trend = TrendEngine(resident_id=cfg.resident.name, spo2_low_threshold=92.0, bpm_drift_threshold=15.0)
    summaries = [
        {"avg_bpm": 72.0, "date": "2026-10-10"},
        {"avg_bpm": 70.0, "date": "2026-10-11"},
        {"avg_bpm": 74.0, "date": "2026-10-12"},
    ]
    trend.seed_from_summaries(summaries)
    drift_alerts = trend.ingest_sensor_reading("max30102_bpm", 110.0, "bpm")
    print(f"    Ingested Vital : 110 BPM (Baseline ~72 BPM)")
    print(f"    Drift Alerts   : {len(drift_alerts)} detected -> {[a.summary for a in drift_alerts]}")

    # 6. Proposer & Independent Safety Verifier
    print("\n[6] Intervention Proposer & Independent Verifier...")
    proposer = RuleBasedProposer(resident_id=cfg.resident.name)
    verifier = SafetyVerifier(
        max_reminders_per_hour=3,
        quiet_start="22:00",
        quiet_end="07:00",
        deny_list_path=cfg.verifier.deny_list_path
    )

    proposed = proposer.propose(health_event)
    print(f"    Proposed Action: Type={proposed.type.name} | Message=\"{proposed.message}\"")

    decision = verifier.verify(proposed)
    print(f"    Verifier Review: Decision={decision.decision.name} | Reason=\"{decision.reason}\"")

    # 7. Hash-Chained Cryptographic Audit Ledger
    print("\n[7] Hash-Chained Cryptographic Audit Log (data/audit.jsonl)...")
    audit = AuditLogger(log_path="data/demo_audit.jsonl")
    audit.append("event_ingested", {"summary": health_event.summary})
    audit.append("intervention_verified", {"decision": decision.decision.name})
    chain_valid = audit.verify_chain()
    print(f"    Total Blocks   : {audit.entry_count()}")
    print(f"    Chain Verified : {'[OK] VALID (Tamper-proof)' if chain_valid else '[FAIL] INVALID'}")

    memory.close()

    print("\n" + "=" * 70)
    print("  All M0 to M8 components operational! Run `python server.py` for Web UI.")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
