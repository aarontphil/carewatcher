"""
create_carewatcher_document.py
Generates a comprehensive Word document (.docx) covering all slides,
technical content, speaker scripts, and committee defense Q&A for CareWatcher Review 1.
"""
import os
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn

def set_cell_background(cell, fill_hex):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{fill_hex}"/>')
    tcPr.append(shd)

def set_cell_margins(cell, top=100, bottom=100, left=150, right=150):
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = parse_xml(f'<w:tcMar {nsdecls("w")}><w:top w:w="{top}" w:type="dxa"/><w:bottom w:w="{bottom}" w:type="dxa"/><w:left w:w="{left}" w:type="dxa"/><w:right w:w="{right}" w:type="dxa"/></w:tcMar>')
    tcPr.append(tcMar)

def generate_doc(output_path="CareWatcher_Review_1_Presentation_Document.docx"):
    doc = docx.Document()

    # Set 1-inch margins
    sections = doc.sections
    for section in sections:
        section.top_margin = Inches(1)
        section.bottom_margin = Inches(1)
        section.left_margin = Inches(1)
        section.right_margin = Inches(1)

    COLOR_CRIMSON = RGBColor(204, 0, 0)      # #CC0000 MITS Red
    COLOR_DARK = RGBColor(24, 24, 27)         # #18181B Dark Charcoal
    COLOR_GRAY = RGBColor(75, 85, 99)         # #4B5563 Medium Slate

    logo_path = os.path.abspath("data/mits_logo.png")
    screenshot_path = os.path.abspath("data/dashboard_screenshot.png")

    # Header / Logo
    if os.path.exists(logo_path):
        p_logo = doc.add_paragraph()
        p_logo.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run_logo = p_logo.add_run()
        run_logo.add_picture(logo_path, width=Inches(2.5))

    # Document Title
    p_title = doc.add_paragraph()
    p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_title.paragraph_format.space_before = Pt(6)
    p_title.paragraph_format.space_after = Pt(2)
    run_t = p_title.add_run("CAREWATCHER")
    run_t.font.name = "Arial"
    run_t.font.size = Pt(24)
    run_t.font.bold = True
    run_t.font.color.rgb = COLOR_DARK

    p_sub = doc.add_paragraph()
    p_sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_sub.paragraph_format.space_before = Pt(0)
    p_sub.paragraph_format.space_after = Pt(4)
    run_s = p_sub.add_run("Privacy-Preserving Ambient Healthcare Companion for Passive Wellness Monitoring")
    run_s.font.name = "Arial"
    run_s.font.size = Pt(13)
    run_s.font.bold = True
    run_s.font.color.rgb = COLOR_CRIMSON

    p_meta = doc.add_paragraph()
    p_meta.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_meta.paragraph_format.space_after = Pt(18)
    run_m = p_meta.add_run("B.Tech Major Project — Review 1 (Interim Evaluation) Presentation Documentation\nDepartment of Artificial Intelligence and Data Science\nMuthoot Institute of Technology and Science (MITS), Kochi\nAcademic Year: 2026 – 2027")
    run_m.font.name = "Arial"
    run_m.font.size = Pt(10)
    run_m.font.color.rgb = COLOR_GRAY

    doc.add_heading("Table of Contents / Slide Index", level=2)
    toc_items = [
        ("Slide 1: Project Title & Team Details", "Institutional identifiers, guide, and candidate details"),
        ("Slide 2: Problem Statement", "Solitary elder vulnerabilities, cloud privacy dilemmas, and failure modes"),
        ("Slide 3: Project Objectives", "Zero-cloud privacy shutter, multimodal ambient sensing, and isolated verifier"),
        ("Slide 4: Project Overview", "Concise 2-minute summary: problem, motivation, scope, and impact"),
        ("Slide 5: Progress Since Zeroth Review", "Comparative progress table and committee feedback incorporation"),
        ("Slide 6: System Requirements & Architecture Design", "5-layer decoupled edge pipeline and privacy root boundary"),
        ("Slide 7: Methodology & Execution Pipeline", "AI conversational extraction, ESP32 biosensing, and safety gating"),
        ("Slide 8: Technology Stack & Technical Justifications", "Curated edge AI models, sensors, languages, and protocol trade-offs"),
        ("Slide 9: Preliminary & Interim Results", "Empirical evidence: dashboard UI, 82/82 tests passing, and vital drift demo"),
        ("Slide 10: Remaining Work & Completion Status", "Quantified progress breakdown: 70% completed, 30% remaining"),
        ("Slide 11: Updated Timelines & Gantt Schedule", "20-week semester roadmap from specification to final viva defense"),
        ("Slide 12: References", "12 peer-reviewed academic, biomedical, and cryptographic citations")
    ]

    p_toc = doc.add_paragraph()
    for s_title, s_desc in toc_items:
        r_t = p_toc.add_run(f"• {s_title}: ")
        r_t.bold = True
        r_t.font.name = "Arial"
        r_t.font.size = Pt(9.5)
        r_d = p_toc.add_run(f"{s_desc}\n")
        r_d.font.name = "Arial"
        r_d.font.size = Pt(9.5)
        r_d.font.color.rgb = COLOR_GRAY

    doc.add_page_break()

    # SLIDE DETAILS LOOP
    slides_content = [
        {
            "num": 1,
            "title": "Project Title & Team Details",
            "objective": "Establish institutional identity, project classification, team credentials, and approved project title.",
            "onscreen": [
                ("Project Title: ", "CAREWATCHER — Privacy-Preserving Ambient Healthcare Companion for Passive Wellness Monitoring."),
                ("One-Line Summary: ", "100% On-Device Ambient Health Intelligence with Zero Cloud Egress."),
                ("Evaluation Category: ", "B.Tech Major Project — Review 1 (Interim Evaluation), Academic Year 2026–2027."),
                ("Department: ", "Department of Artificial Intelligence and Data Science, MITS Kochi (Autonomous)."),
                ("Project Guide: ", "[Guide Name], Assistant Professor, Dept of AI & DS."),
                ("Team Members: ", "Group [X]: Aaron (Roll No: [Roll No.]), [Member 2] ([Roll No.]), [Member 3] ([Roll No.]), [Member 4] ([Roll No.]).")
            ],
            "notes": "Good morning respected members of the evaluation committee. Today, we present Review 1 of our Major Project: CareWatcher. CareWatcher is an ambient healthcare companion designed for passive wellness monitoring of solitary and mobility-limited seniors. Unlike commercial smart assistants that stream personal home audio and video to remote clouds, CareWatcher is engineered with a strict 100% on-device architecture featuring a hardware Privacy Shutter gate. Our title and scope remain consistent with the approved Zeroth Review framework.",
            "viva": "Q: Why is ambient monitoring preferred over wearable smartwatches?\nA: Wearables suffer from poor compliance among seniors—elderly individuals often forget to charge them, take them off during sleep, or find them uncomfortable. CareWatcher provides non-intrusive ambient sensing without demanding manual intervention or compliance."
        },
        {
            "num": 2,
            "title": "Problem Statement",
            "objective": "Identify the critical healthcare, privacy, and technical challenges necessitating CareWatcher.",
            "onscreen": [
                ("1. Solitary Living & Silent Decline: ", "With 1 in 6 people aged 60+ by 2030, solitary seniors experience unmonitored medication non-adherence (>50% incidence), gradual cognitive decline, and prolonged immobilization after falls."),
                ("2. The Cloud Privacy Dilemma: ", "Commercial assistants (Alexa, Google Nest, cloud CCTV) stream raw audio/video to external servers. This violates HIPAA/GDPR, causes high resident rejection, and raises ongoing subscription barriers."),
                ("3. Operational Vulnerabilities: ", "Cloud-dependent solutions fail during network outages. Furthermore, unconstrained generative LLMs risk hallucinating dangerous medical diagnoses or prescribing drugs.")
            ],
            "notes": "Our problem statement spans three critical dimensions. First, the demographic reality: millions of elderly residents live alone. Subtle behavioral changes—such as missing heart medication or developing irregular sleep patterns—remain invisible until acute crises occur. Second, existing technology relies on the cloud. Placing microphones and cameras that transmit to third-party servers into private bedrooms is unacceptable to seniors and violates medical privacy laws. Third, cloud systems fail during internet outages and open-ended generative AI introduces hallucination risks.",
            "viva": "Q: What is the single biggest technical risk in your problem formulation?\nA: The primary risk is clinical hallucination from LLMs. We solve this by decoupling the conversational extraction from an independent safety verifier that enforces non-clinical bounds and deny-lists."
        },
        {
            "num": 3,
            "title": "Project Objectives",
            "objective": "Define measurable, rigorous engineering goals that directly solve the stated problem.",
            "onscreen": [
                ("Objective 1: Hardware-Enforced Zero-Cloud Privacy Architecture: ", "Design an edge-native computing hub with a physical Privacy Shutter hard gate, ensuring 100% on-device processing and mathematically verifiable zero network egress."),
                ("Objective 2: Multimodal Passive Ambient Sensing & Natural Dialogue: ", "Implement contactless acoustic speech (Faster-Whisper), local LLM reasoning, and ESP32 multi-biosensors (MAX30102 PPG, MLX90614 IR Temp, MPU-6050 Motion) for medication adherence and rolling baseline drift alerts."),
                ("Objective 3: Decoupled Proposer-Verifier Safety & Audit Chaining: ", "Construct an isolated dual-engine safety pipeline with an append-only, SHA-256 hash-chained cryptographic audit log to eliminate diagnostic claims and ensure tamper-evident provenance.")
            ],
            "notes": "To resolve these challenges, we defined three clear, cohesive objectives. Objective 1 establishes the root of trust: a physical Privacy Shutter that gates all microphone and sensor inputs at the hardware/driver level. Objective 2 realizes passive intelligence: we process ambient conversational check-ins using Faster-Whisper and local quantized LLMs, paired with an ESP32 hub capturing heart rate, blood oxygen, and contactless temperature. Objective 3 enforces medical safety: a completely isolated Verifier inspects every proposed reminder, ensuring zero clinical claims, and records all decisions in an immutable SHA-256 hash chain.",
            "viva": "Q: How do you verify Objective 1 mathematically?\nA: By running network socket inspection and automated fuzz testing with the Privacy Shutter closed, confirming exactly zero bytes exit downstream layers or transmit across network interfaces."
        },
        {
            "num": 4,
            "title": "Project Overview",
            "objective": "Deliver a concise 2-minute elevator pitch covering the 6 mandatory review elements.",
            "onscreen": [
                ("• Engineering Problem: ", "Executing real-time wake-word, speech recognition, LLM reasoning, and biosensing on consumer edge hardware with <8s latency and zero cloud dependency."),
                ("• Motivation: ", "Preserving dignity, independence, and peace of mind for elderly individuals while relieving caregiver burnout."),
                ("• Need for Project: ", "Severe caregiver shortages against a surging aging demographic, coupled with consumer refusal of cloud surveillance cameras."),
                ("• Target Users: ", "Solitary seniors, assisted living residents, post-operative recovering patients, family caregivers, and geriatric aides."),
                ("• Scope of Project: ", "Ambient conversational check-ins, medication adherence tracking, vital drift detection, immobility alerts, and local audit logging. Excludes clinical diagnosis."),
                ("• Expected Impact: ", "100% privacy preservation, zero recurring cloud subscriptions, high offline reliability, and prompt emergency escalations.")
            ],
            "notes": "In summary, CareWatcher solves the engineering challenge of delivering real-time multimodal intelligence directly on edge hardware. Our motivation is to provide proactive healthcare without surveillance. The target beneficiaries are independent seniors and their loved ones. Our scope is intentionally focused on wellness monitoring and passive trend detection, deliberately leaving clinical diagnosis to qualified doctors. The expected impact is total privacy, zero monthly fees, and continuous safety during internet outages.",
            "viva": "Q: Can CareWatcher operate during a total home internet blackout?\nA: Yes. Because Faster-Whisper, Mistral-7B GGUF, SQLite, and the local Web server all run 100% on the local hardware, CareWatcher functions entirely normally without an internet connection."
        },
        {
            "num": 5,
            "title": "Progress Since Zeroth Review",
            "objective": "Demonstrate tangible implementation progress and incorporation of committee guidance.",
            "onscreen": [
                ("Comparison Parameters: ", "Literature Survey (Surveyed Edge AI & Whisper), Problem Definition (Refined non-clinical scope), Architecture (8-stage pipeline with Shutter & Verifier), Algorithms (Faster-Whisper + GGUF + Z-score drift), Hardware (ESP32 hub + MAX30102 + MLX90614 + MPU-6050), Software (Complete Python 3.11 core with 82 passing tests + Web Dashboard)."),
                ("Committee Suggestion 1: ", "Prevent generative AI from diagnosing illness or prescribing drugs ➔ Implemented isolated SafetyVerifier with medical deny-list and tone verification."),
                ("Committee Suggestion 2: ", "Provide architectural proof of privacy ➔ Implemented PrivacyShutter hard gate with automated fuzz verification (0 bytes leaked).")
            ],
            "notes": "Since our Zeroth Review, we have transitioned from conceptual models to a fully operational software and hardware prototype. We completed extensive surveys on on-device Edge AI, formalized the architecture into an 8-stage pipeline, built the physical ESP32 sensor hub, and developed a complete Python 3.11 engine with 82 passing unit and integration tests. We also incorporated both committee recommendations: an isolated SafetyVerifier to prevent clinical hallucinations, and an automated fuzz-tested PrivacyShutter that guarantees 0 bytes leak when closed.",
            "viva": "Q: What is the isolation level between Proposer and Verifier?\nA: There is zero direct or transitive import between `carewatcher.proposer` and `carewatcher.verifier`. They communicate purely via immutable dataclasses passed through the orchestrator, preventing any prompt injection or bias leakage."
        },
        {
            "num": 6,
            "title": "System Requirements & Architecture Design",
            "objective": "Detail the 5-layer decoupled architecture and privacy root boundary.",
            "onscreen": [
                ("Layer 1: Perception Layer: ", "Mic audio source (16kHz PCM), Webcam presence (OpenCV Haar cascade; scalar counts only, zero video saved), ESP32 hub (MAX30102 PPG, MLX90614 IR Temp, MPU-6050 Motion)."),
                ("Layer 2: Privacy Root Boundary: ", "PrivacyShutter hard gate. Binary state (CLOSED/OPEN). Blocks 100% of data flow downstream when closed."),
                ("Layer 3: Cognition Layer: ", "Keyword wake-word ('hey care'), Faster-Whisper STT base model, quantized Mistral-7B via llama.cpp with schema JSON enforcement."),
                ("Layer 4: Memory & Trends: ", "SQLite3 `resident.db` store, 7-day rolling baseline statistics, Z-score vital drift anomaly detection."),
                ("Layer 5: Safety & Delivery: ", "Rule-Based Proposer, independent SafetyVerifier, local Piper neural TTS speech output, and append-only SHA-256 hash-chained audit ledger.")
            ],
            "notes": "Here we illustrate the 5-layer architecture of CareWatcher. Layer 1 captures ambient audio and biosensor telemetry. Crucially, before any data enters processing, it must traverse Layer 2: our Privacy Shutter. If closed, zero bytes exit. Layer 3 handles cognition using local Faster-Whisper and 4-bit quantized Mistral-7B, outputting schema-validated JSON. Layer 4 manages rolling 7-day baseline trends in SQLite. Finally, Layer 5 decouples the candidate proposal from our Safety Verifier, which audits the action before local Piper TTS delivery and commits the transaction to our SHA-256 audit log.",
            "viva": "Q: Why do you run OpenCV Haar cascade on CPU instead of a deep learning face detector?\nA: Haar cascades require less than 5% CPU utilization and zero GPU memory, making them ideal for lightweight presence sensing without competing for RAM with our LLM."
        },
        {
            "num": 7,
            "title": "Methodology & Execution Pipeline",
            "objective": "Explain the sequential multimodal workflow across both AI and hardware subsystems.",
            "onscreen": [
                ("• AI Project Workflow: ", "Raw PCM 16kHz audio ➔ Shutter check ➔ Faster-Whisper STT ➔ Mistral-7B prompt extraction ➔ Schema-validated `HealthEvent` (Medication, Mood, Distress) ➔ Rolling baseline drift evaluation."),
                ("• Hardware Project Workflow: ", "ESP32 hub samples MAX30102 (PPG) and MLX90614 (IR Temp) over I2C ➔ Formats JSON telemetry ➔ Transmits over USB Virtual COM @ 115200 baud ➔ Ingested into SQLite memory store."),
                ("• Safety Gating: ", "Proposer creates `Intervention(type=REMINDER/ESCALATE)` ➔ Verifier checks deny-list, rate limits, and quiet hours (22:00–07:00) ➔ Synthesized via Piper TTS ➔ SHA-256 hash chained.")
            ],
            "notes": "Our methodology unites edge AI and embedded hardware into a cohesive loop. The ESP32 collects PPG and temperature readings every second over I2C and streams them over UART. Simultaneously, when a resident speaks 'hey care', Faster-Whisper transcribes the utterance. The local LLM parses the transcript into a structured HealthEvent. If the resident mentions missing medication, or if the Trend Engine flags a vital drift—such as heart rate spiking to 110 BPM—the Proposer drafts a gentle nudge. The Verifier checks quiet hours, rate limits, and language safety before local Piper TTS speaks the reminder.",
            "viva": "Q: What happens if the LLM outputs malformed JSON?\nA: The schema parser catches the exception, rejects the response, and falls back to a deterministic rule-based template, ensuring system stability."
        },
        {
            "num": 8,
            "title": "Technology Stack & Technical Justifications",
            "objective": "Justify each technology choice based on edge constraints, latency, and privacy.",
            "onscreen": [
                ("• ESP32-WROOM-32: ", "Dual-core 240MHz microcontroller; hardware I2C/UART; ultra-low power; eliminates OS timing jitter for biosensing."),
                ("• MAX30102 & MLX90614: ", "Dual-wavelength red/IR photoplethysmography (BPM/SpO2) and medical-grade contactless infrared thermometry (±0.2°C)."),
                ("• Faster-Whisper (base): ", "CTranslate2 backend; 4x faster and 50% less RAM than vanilla Whisper; runs locally on CPU."),
                ("• Mistral-7B Q4_K_M (llama.cpp): ", "4-bit quantized edge LLM; fits within 4GB RAM on consumer CPU; provides high-quality structured reasoning."),
                ("• Piper TTS & SQLite 3: ", "Fast neural offline voice synthesis and serverless ACID relational storage with zero external cloud dependencies."),
                ("• Python http.server & Vanilla JS: ", "Standard library HTTP server with zero third-party web framework overhead; enables lightweight localhost dashboard.")
            ],
            "notes": "Every technology in our stack was chosen deliberately. ESP32 guarantees real-time biosensing without operating system jitter. Faster-Whisper with CTranslate2 enables speech transcription in under 2 seconds on standard CPUs. Quantized Mistral-7B provides nuanced reasoning within 4GB RAM without requiring an expensive GPU server. SQLite3 provides reliable local storage, and Python's standard library `http.server` provides our dashboard without bloated external web frameworks.",
            "viva": "Q: Why select Mistral-7B over smaller models like TinyLlama (1.1B)?\nA: TinyLlama exhibits high syntax failure rates when enforcing strict JSON schemas. Mistral-7B Q4_K_M achieves >98% schema compliance while maintaining acceptable CPU inference speed."
        },
        {
            "num": 9,
            "title": "Preliminary & Interim Results",
            "objective": "Present concrete empirical proof that the CareWatcher prototype is functional.",
            "onscreen": [
                ("• Functional Test Suite: ", "82 / 82 unit and integration tests passing (100% pass rate in 3.03s) across config, shutter, STT, LLM, memory, and audit modules."),
                ("• Privacy Shutter Efficacy: ", "Automated fuzz tests confirm exactly 0 bytes leak when the shutter is in CLOSED state."),
                ("• Live Conversational Extraction: ", "Resident voice utterance 'hey care I forgot to take my morning blood pressure pills' accurately transcribed and parsed into MEDICATION event."),
                ("• Vital Drift Detection: ", "Simulated 110 BPM tachycardia ingestion immediately triggered drift alert against resident's 72 BPM baseline."),
                ("• Safety Verifier: ", "100% rejection rate for diagnostic/prescriptive medical words in deny-list; rate-limiting successfully throttles excessive prompts."),
                ("• Cryptographic Audit Trail: ", "Deterministic SHA-256 hashing verified with 100% valid blockchain-style sequence integrity across all system events.")
            ],
            "notes": "We are proud to present working empirical evidence of our implementation. Our automated test suite has 82 out of 82 passing tests. Our automated fuzzing proves that when the Privacy Shutter is closed, zero bytes leak. In live end-to-end testing, spoken medication statements are transcribed and categorized accurately. When we injected a heart rate reading of 110 BPM against a 72 BPM baseline, our trend engine instantly fired a drift alert. Furthermore, our Safety Verifier blocked 100% of clinical deny-list words, and our SHA-256 audit log verified with 100% integrity.",
            "viva": "Q: Can you show the audit log verifying cryptographic integrity?\nA: Yes, our `verify_chain()` function traverses all JSONL blocks, recomputes the SHA-256 hashes against previous digests, and verifies 100% chain validity in runtime."
        },
        {
            "num": 10,
            "title": "Remaining Work & Completion Status",
            "objective": "Present a realistic, quantified breakdown of completed vs pending milestones.",
            "onscreen": [
                ("Overall Status: ", "70% Completed (Core Pipeline Operational)  |  30% Remaining (Housing & Field Pilot)."),
                ("1. Physical Enclosure & Hardware Packaging (40% complete): ", "CAD modeling and 3D printing of companion housing with integrated physical sliding shutter."),
                ("2. Extended Residential Field Pilot Trial (30% complete): ", "7-day residential deployment with an elderly participant to calibrate personal baseline drifts."),
                ("3. Edge Hardware Acceleration (60% complete): ", "Exploring INT4 NPU / Vulkan GPU offloading to reduce conversational latency to <1.5s."),
                ("4. Comprehensive Thesis & Academic Paper (45% complete): ", "Finalizing B.Tech project report and submitting paper: 'Decentralized Ambient Healthcare Companion via On-Device LLMs and Physical Privacy Gating'.")
            ],
            "notes": "As quantified in our progress bar, CareWatcher is 70% complete. All core algorithmic pipelines, edge models, safety verifiers, and database modules are functional and verified. The remaining 30% focuses on physical packaging and validation. Specifically: CAD design and 3D printing of the desktop enclosure with a mechanical sliding shutter, conducting a 7-day residential pilot trial to tune real-world baseline parameters, exploring Vulkan/NPU acceleration, and completing our comprehensive thesis and conference publication.",
            "viva": "Q: What ethical clearances are required for your residential pilot trial?\nA: The trial involves passive wellness logging with resident and guardian informed consent, zero cloud data transmission, and a physical privacy shutter allowing the resident to disconnect sensors at any time."
        },
        {
            "num": 11,
            "title": "Updated Timelines & Gantt Schedule",
            "objective": "Show a realistic 20-week roadmap from inception to final thesis defense.",
            "onscreen": [
                ("• Weeks 1–3: Survey & Specification (COMPLETED): ", "Literature review, system requirements, SPEC.md, interfaces definition."),
                ("• Weeks 4–6: Privacy Shutter & Drivers (COMPLETED): ", "Shutter state machine, mic driver, ESP32 sensor firmware."),
                ("• Weeks 7–9: STT & LLM Pipeline (COMPLETED): ", "Faster-Whisper integration, Mistral-7B schema JSON parsing."),
                ("• Weeks 10–12: Trend Engine & Verifier (COMPLETED): ", "Z-score drift algorithms, SafetyVerifier, SHA-256 audit chaining."),
                ("• Weeks 13–14: Dashboard & Integration (COMPLETED - REVIEW 1): ", "Web UI, HTTP API server, 82 unit tests passing."),
                ("• Weeks 15–16: 3D Packaging & Enclosure (IN PROGRESS): ", "CAD chassis, 3D printing, physical slider switch."),
                ("• Weeks 17–18: Residential Pilot & Optimization (PENDING - REVIEW 2): ", "7-day field trial, NPU acceleration, drift parameter tuning."),
                ("• Weeks 19–20: Final Thesis & Defense (PENDING): ", "Comprehensive report, conference paper, final viva defense.")
            ],
            "notes": "This Gantt roadmap outlines our 20-week semester schedule. We have met all milestones for Phases 1 through 5 on schedule, culminating in this Review 1 presentation with a fully working software core. In Weeks 15 and 16, we will fabricate the physical 3D enclosure. Weeks 17 and 18 are dedicated to the residential pilot and performance optimization for Review 2. Weeks 19 and 20 will be devoted to our final thesis submission and project viva defense.",
            "viva": "Q: Are you on schedule for Review 2?\nA: Yes, our software and hardware core is already fully operational ahead of schedule, giving us ample buffer to focus on the 3D enclosure and residential field pilot."
        },
        {
            "num": 12,
            "title": "References",
            "objective": "Provide 12 formal academic, biomedical, and cryptographic citations used during implementation.",
            "onscreen": [
                ("[1] A. Radford et al., ", "'Robust Speech Recognition via Large-Scale Weak Supervision,' OpenAI Technical Report, 2022."),
                ("[2] H. Touvron et al., ", "'LLaMA: Open and Efficient Foundation Language Models,' arXiv:2302.13971, 2023."),
                ("[3] P. Rashidi and A. Mihailidis, ", "'A Survey on Ambient-Assisted Living Tools for Older Adults,' IEEE TBME, 2013."),
                ("[4] T. Tamura et al., ", "'Wearable Photoplethysmographic Sensors—Past and Present,' Electronics, 2014."),
                ("[5] S. Gerke et al., ", "'Ethical and Legal Challenges of AI-Driven Healthcare,' Academic Press, 2020."),
                ("[6] S. Haber and W. S. Stornetta, ", "'How to Time-Stamp a Digital Document,' Journal of Cryptology, 1991."),
                ("[7] C. Dwork and A. Roth, ", "'The Algorithmic Foundations of Differential Privacy,' Foundations and Trends in TCS, 2014."),
                ("[8] World Health Organization, ", "'Regulatory Considerations on Artificial Intelligence for Health,' WHO Guidance, 2023."),
                ("[9] ISO/IEEE 11073-10408, ", "'Health Informatics—Personal Health Device Communication: Thermometer,' IEEE, 2020."),
                ("[10] ISO/IEEE 11073-10404, ", "'Health Informatics—Personal Health Device Communication: Pulse Oximeter,' IEEE, 2020."),
                ("[11] A. Q. Jiang et al., ", "'Mistral 7B,' arXiv:2310.06825, 2023."),
                ("[12] J. Varghese et al., ", "'Edge Computing in Ambient Assisted Living: Architectures and Privacy,' IEEE Access, 2021.")
            ],
            "notes": "Our implementation is grounded in peer-reviewed academic research and international biomedical standards. We build upon foundational speech recognition research by Radford et al., edge language model quantization by Touvron and Jiang et al., ambient assisted living surveys by Rashidi and Mihailidis, photoplethysmography principles from Tamura et al., tamper-evident hash chaining by Haber and Stornetta, and official ISO/IEEE 11073 medical communication standards. Thank you, and we now welcome any questions from the review committee.",
            "viva": "Q: Which specific standard governs your sensor communication?\nA: The ISO/IEEE 11073 personal health device communication standard, specifically 11073-10404 for pulse oximetry and 11073-10408 for thermometry."
        }
    ]

    for item in slides_content:
        h = doc.add_heading(f"Slide {item['num']}: {item['title']}", level=1)
        h.paragraph_format.space_before = Pt(14)
        h.paragraph_format.space_after = Pt(4)

        # Objective
        p_obj = doc.add_paragraph()
        r_oh = p_obj.add_run("Guideline Objective: ")
        r_oh.bold = True
        r_oh.font.color.rgb = COLOR_CRIMSON
        p_obj.add_run(item['objective'])

        # On-screen table
        doc.add_heading("On-Screen Presentation Content", level=3)
        for head, body in item['onscreen']:
            p_c = doc.add_paragraph()
            p_c.paragraph_format.space_before = Pt(2)
            p_c.paragraph_format.space_after = Pt(2)
            r_ch = p_c.add_run(head)
            r_ch.bold = True
            r_ch.font.name = "Arial"
            r_ch.font.size = Pt(10)
            r_ch.font.color.rgb = COLOR_DARK
            r_cb = p_c.add_run(body)
            r_cb.font.name = "Arial"
            r_cb.font.size = Pt(10)
            r_cb.font.color.rgb = COLOR_GRAY

        # If Slide 9, embed the dashboard screenshot
        if item['num'] == 9 and os.path.exists(screenshot_path):
            p_img = doc.add_paragraph()
            p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p_img.paragraph_format.space_before = Pt(8)
            p_img.paragraph_format.space_after = Pt(4)
            r_img = p_img.add_run()
            r_img.add_picture(screenshot_path, width=Inches(5.5))
            p_cap = doc.add_paragraph()
            p_cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
            r_cap = p_cap.add_run("Figure 9.1: Live CareWatcher Operational Dashboard with Active Privacy Shutter and Sensor Telemetry")
            r_cap.font.size = Pt(8.5)
            r_cap.font.italic = True
            r_cap.font.color.rgb = COLOR_GRAY

        # Speaker Script Box
        doc.add_heading("Speaker Presentation Script (What to Say in 60-90s)", level=3)
        tbl_script = doc.add_table(rows=1, cols=1)
        tbl_script.alignment = WD_TABLE_ALIGNMENT.CENTER
        cell_s = tbl_script.cell(0, 0)
        set_cell_background(cell_s, "F8FAFC")
        set_cell_margins(cell_s, top=120, bottom=120, left=180, right=180)
        p_sc = cell_s.paragraphs[0]
        r_sc = p_sc.add_run(f"\"{item['notes']}\"")
        r_sc.font.name = "Georgia"
        r_sc.font.size = Pt(10)
        r_sc.font.italic = True
        r_sc.font.color.rgb = COLOR_DARK

        # Committee Defense / Viva
        doc.add_heading("Expected Review Committee Viva Q&A", level=3)
        tbl_viva = doc.add_table(rows=1, cols=1)
        tbl_viva.alignment = WD_TABLE_ALIGNMENT.CENTER
        cell_v = tbl_viva.cell(0, 0)
        set_cell_background(cell_v, "FEF2F2")
        set_cell_margins(cell_v, top=120, bottom=120, left=180, right=180)
        p_v = cell_v.paragraphs[0]
        r_v = p_v.add_run(item['viva'])
        r_v.font.name = "Arial"
        r_v.font.size = Pt(9.5)
        r_v.font.color.rgb = COLOR_DARK

        doc.add_paragraph().paragraph_format.space_after = Pt(10)

    doc.save(output_path)
    print(f"Document saved successfully to: {os.path.abspath(output_path)}")

if __name__ == "__main__":
    generate_doc()
