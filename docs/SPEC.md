# CareWatcher — System Specification

> Privacy-preserving ambient healthcare companion for passive wellness monitoring.
> B.Tech Major Project — October 2026

---

## 1  Problem Statement

Elderly and mobility-limited residents living alone or in assisted-living
facilities often miss medications, experience undetected mood changes, and face
delayed emergency responses. Cloud-based health monitoring systems raise serious
privacy concerns and depend on reliable internet.

**CareWatcher** addresses this by running **entirely on-device**: a local
conversational agent conducts natural check-ins, a trend engine flags
deviations from personal baselines, a proposer suggests interventions, and an
independent verifier gates every suggestion before it reaches the resident or
caregiver — all without any data leaving the device.

---

## 2  Users

| Role        | Description | Interaction |
|-------------|-------------|-------------|
| **Resident**  | The person being monitored (elderly, mobility-limited, or recovering). | Voice conversations, passive sensing. Receives gentle nudges and reminders. |
| **Caregiver** | Family member, nurse, or aide responsible for the resident. | Reviews escalation alerts, reads audit trail, adjusts settings. |

---

## 3  Core Scenarios

### 3.1  Medication Check-In

1. At a scheduled time, CareWatcher opens a natural voice conversation:
   *"Good morning, Arun. Did you take your blood-pressure tablet?"*
2. STT transcribes the resident's reply; the LLM extracts adherence status
   (taken / missed / unsure) as structured JSON.
3. If missed → the **Proposer** creates an `Intervention(type=REMINDER)`.
4. The **Verifier** confirms the reminder is safe and non-clinical, then
   approves delivery.
5. TTS speaks the reminder; the event is logged in the audit trail.

### 3.2  Sleep / Activity Trend Drift

1. The trend engine accumulates daily sleep-duration and step-count estimates
   (from sensor simulators or real sensors).
2. When a metric drifts beyond the resident's personal baseline threshold
   (e.g., ≥ 2 h less sleep for 3 consecutive nights), a `HealthEvent` is
   emitted.
3. The Proposer suggests an intervention — e.g., a conversational check-in
   about sleep quality.
4. The Verifier reviews the suggestion for plausibility and safety, then
   approves or requests modification.

### 3.3  Mood Change Detected from Conversation

1. During routine conversations, the LLM outputs a sentiment/mood label
   alongside the primary structured response.
2. The trend engine compares the mood label against the resident's rolling
   baseline.
3. A significant negative shift (e.g., neutral → sad for 3+ interactions)
   triggers a `HealthEvent(category=MOOD)`.
4. The Proposer may suggest an empathetic follow-up conversation or a caregiver
   notification.

### 3.4  Distress or Prolonged Inactivity Escalation

1. Audio amplitude analysis or sensor data detects a possible distress signal
   (loud cry, fall-like impact) or prolonged inactivity (no movement for
   configurable duration).
2. CareWatcher initiates a welfare check: *"Are you okay? I noticed you've
   been very still."*
3. If the resident does not respond within a timeout, the Proposer emits
   `Intervention(type=ESCALATE)`.
4. The Verifier marks the escalation as urgent and flags the caregiver.

---

## 4  Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                        Privacy Shutter                          │
│               (hard gate — open / closed)                       │
└──────────┬───────────────────────────────────────────────────────┘
           │  shutter open
           ▼
┌─────────────────────┐    ┌─────────────────────┐
│   Audio Source       │    │   Sensor Source      │
│ (mic / simulator)    │    │ (cam / sim / ESP32)  │
└─────────┬───────────┘    └─────────┬───────────┘
          │                          │
          ▼                          │
┌─────────────────────┐              │
│  Wake-Word Detector │              │
│  + STT Engine       │              │
└─────────┬───────────┘              │
          │ Transcript               │ SensorReading
          ▼                          ▼
┌──────────────────────────────────────────────┐
│           Conversation Agent (LLM)           │
│     (schema-validated JSON output)           │
└─────────┬────────────────────────────────────┘
          │ HealthEvent
          ▼
┌──────────────────────┐
│   Resident Memory    │───────┐
│   + Trend Engine     │       │ baseline drift
└─────────┬────────────┘       │
          │ HealthEvent        ▼
          │              ┌───────────────┐
          └─────────────▶│   Proposer    │
                         └──────┬────────┘
                                │ Intervention (proposed)
                                ▼
                         ┌───────────────┐
                         │   Verifier    │  (no import of Proposer)
                         └──────┬────────┘
                                │ Intervention (approved / rejected / escalated)
                                ▼
                         ┌───────────────┐
                         │  Delivery /   │
                         │  Escalation   │
                         └──────┬────────┘
                                │
                                ▼
                         ┌───────────────┐
                         │  Audit Log    │
                         │ (append-only, │
                         │  hash-chained)│
                         └───────────────┘
```

### Key Properties

| Property | Guarantee |
|----------|-----------|
| Privacy shutter | Hard gate — zero data flows downstream when closed. |
| Proposer ↔ Verifier isolation | No direct or transitive imports between the two. |
| LLM output safety | Schema-validated JSON; no clinical/diagnostic claims. |
| Audit integrity | Append-only, hash-chained log. Every decision is recorded. |
| Edge-only | No network calls at runtime. All models loaded locally. |

---

## 5  Verifier Checks

The Verifier is the last gate before any intervention reaches the resident or
caregiver. It enforces:

1. **Schema validity** — The proposed intervention matches the `Intervention`
   dataclass schema.
2. **Non-clinical language** — Text does not contain diagnostic or prescriptive
   medical claims (checked against a deny-list and LLM self-check).
3. **Rate limiting** — No more than N reminders per hour to avoid alarm
   fatigue.
4. **Escalation appropriateness** — Escalations require corroborating evidence
   (e.g., inactivity *and* no verbal response).
5. **Baseline plausibility** — The trend data backing the intervention is
   within reasonable bounds (guards against sensor glitches).
6. **Resident preference** — Respects quiet hours, do-not-disturb flags, and
   per-resident settings.

The Verifier may **approve**, **reject** (with reason logged), or **escalate**
(flag caregiver immediately).

---

## 6  Non-Goals

- **Clinical diagnosis or treatment.** CareWatcher is a wellness companion,
  not a medical device. It never diagnoses, prescribes, or replaces
  professional medical advice.
- **Cloud processing.** No data leaves the device at runtime.
- **Real-time vital-sign monitoring.** Optional sensor integration is a stretch
  goal; the MVP uses simulators.
- **Multi-resident simultaneous conversation.** V1 supports one active
  conversation at a time.
- **Mobile app.** The interface is voice-first on the edge device; a companion
  app is out of scope.

---

## 7  Evaluation Metrics

| Metric | Target | How Measured |
|--------|--------|--------------|
| Medication reminder accuracy | ≥ 90% correct adherence extraction | Ground-truth labels on test transcripts |
| Trend drift detection | ≥ 85% recall, ≤ 15% false-positive | Synthetic time-series with injected drifts |
| Intervention safety | 0 clinical claims in approved interventions | Automated deny-list + manual review |
| Verifier agreement | ≥ 95% inter-rater with human reviewer | 50-case sample audit |
| Audit log integrity | 100% chain-valid on replay | Automated hash-chain verification test |
| End-to-end latency (check-in) | ≤ 8 s wake-word → spoken response | Wall-clock benchmark on target laptop |
| Privacy shutter | 0 data leaks when closed | Fuzz test: inject data with shutter closed |

---

## 8  Milestones

| #  | Milestone | Deliverables | Est. Weeks |
|----|-----------|--------------|------------|
| M0 | **Project scaffold & interfaces** | Repo layout, `interfaces.py`, config schema, CI with pytest | 1 |
| M1 | **Privacy shutter + sources** | Shutter gate, mic source, sensor simulators, unit tests | 1 |
| M2 | **STT + wake-word pipeline** | Whisper STT integration, simple wake-word, transcript tests | 1.5 |
| M3 | **Conversation agent** | LLM integration, schema validation, medication check-in flow | 2 |
| M4 | **Memory + trend engine** | Per-resident memory store, rolling baselines, drift detection | 1.5 |
| M5 | **Proposer + verifier** | Intervention proposal, independent verification, isolation test | 1.5 |
| M6 | **Audit log** | Append-only hash-chained log, integrity verification tool | 1 |
| M7 | **Integration & scenarios** | End-to-end tests for all four core scenarios | 1.5 |
| M8 | **Polish & evaluation** | Metrics collection, documentation, demo script | 1 |
