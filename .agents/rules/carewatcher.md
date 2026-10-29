# CareWatcher — Project Rules

## Runtime & Deployment
- **Edge-only**: No network imports or network calls anywhere under `/carewatcher` at runtime.
  Offline model loading only. No REST, gRPC, or HTTP clients in production code paths.
- Target platform is a high-spec laptop standing in for an edge device.
  Keep code portable and lightweight enough to move to smaller hardware later.

## Language & Tooling
- Python 3.11+. Use type hints on every public function, method, and dataclass field.
- Test framework: **pytest**. Run tests before declaring any module done.
- No new third-party dependency may be added without explicit user approval.

## Sources & Simulators
- Every sensor and audio source **must** implement a shared protocol/interface.
- Each real driver has a matching **simulator** behind the same interface.
- Real sources for now: laptop microphone, laptop webcam.
- Optional future sources (ESP32, MAX30102, mmWave) are out of scope until requested.

## Configuration
- All model choices (STT model/size, LLM model name, TTS voice) live in a
  **single config file** (`config.yaml` or equivalent).
- Swapping a model must not require code changes — only a config edit.

## Privacy Shutter
- The shutter is a **hard gate**: when closed, **zero data** reaches any downstream module.
- Current implementation: software gate.
- Stretch goal: physical shutter / hardware mic cut-off.

## Architecture Constraints
- **Proposer** and **Verifier** must never import each other, directly or transitively.
- One module per task — keep responsibilities cleanly separated.
- LLM outputs must be **schema-validated JSON**. Reject malformed responses.
- The system must **never** make clinical or diagnostic claims.

## Audit Log
- The audit log is **append-only** and **hash-chained** (each entry includes the
  hash of the previous entry).
- No entry may be deleted or mutated after writing.

## Workflow
- **Plan first**, present the plan, and wait for user approval before writing code.
- Run all relevant tests before declaring a module done.
