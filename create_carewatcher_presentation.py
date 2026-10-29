"""
create_carewatcher_presentation.py
Generates the Review 1 (Interim Evaluation) Presentation for CareWatcher
strictly adhering to the MITS Template visual design and Review 1 Guidelines.
"""
import os
import pptx
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.enum.shapes import MSO_SHAPE

def create_deck(output_path="CareWatcher_Review_1_Presentation.pptx"):
    prs = pptx.Presentation()
    # 16:9 Widescreen standard
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank_layout = prs.slide_layouts[6]

    # Exact MITS Colors
    COLOR_RED = RGBColor(204, 0, 0)          # #CC0000 MITS Crimson
    COLOR_DARK = RGBColor(24, 24, 27)         # #18181B Dark Charcoal
    COLOR_TEXT = RGBColor(55, 65, 81)         # #374151 Slate Gray
    COLOR_MUTED = RGBColor(107, 114, 128)     # #6B7280 Muted Gray
    COLOR_WHITE = RGBColor(255, 255, 255)     # #FFFFFF Pure White
    COLOR_CARD_BG = RGBColor(248, 250, 252)   # #F8FAFC Clean Card Tint
    COLOR_CARD_BORDER = RGBColor(226, 232, 240) # #E2E8F0 Subtle Border
    COLOR_GREEN = RGBColor(22, 163, 74)       # #16A34A Success Accent
    COLOR_AMBER = RGBColor(217, 119, 6)       # #D97706 Warning Accent
    COLOR_BLUE = RGBColor(37, 99, 235)        # #2563EB Tech Accent

    logo_path = os.path.abspath("data/mits_logo.png")
    screenshot_path = os.path.abspath("data/dashboard_screenshot.png")

    def add_header(slide, title_text, category_text=None):
        """Standard MITS content slide header."""
        # Top right MITS Logo
        if os.path.exists(logo_path):
            slide.shapes.add_picture(logo_path, Inches(11.3), Inches(0.25), width=Inches(1.6))

        # Title container
        title_box = slide.shapes.add_textbox(Inches(0.8), Inches(0.35), Inches(10.2), Inches(0.85))
        tf = title_box.text_frame
        tf.word_wrap = True
        tf.margin_left = tf.margin_top = tf.margin_right = tf.margin_bottom = 0

        if category_text:
            p_cat = tf.paragraphs[0]
            p_cat.text = category_text.upper()
            p_cat.font.name = "Arial"
            p_cat.font.size = Pt(10)
            p_cat.font.bold = True
            p_cat.font.color.rgb = COLOR_RED
            p_title = tf.add_paragraph()
        else:
            p_title = tf.paragraphs[0]

        p_title.text = title_text
        p_title.font.name = "Arial"
        p_title.font.size = Pt(26)
        p_title.font.bold = True
        p_title.font.color.rgb = COLOR_DARK

        # Subtle divider accent line
        line = slide.shapes.add_shape(
            MSO_SHAPE.RECTANGLE,
            Inches(0.8), Inches(1.22), Inches(11.733), Inches(0.02)
        )
        line.fill.solid()
        line.fill.fore_color.rgb = RGBColor(230, 230, 230)
        line.line.color.rgb = RGBColor(230, 230, 230)

    def add_footer(slide, slide_num):
        """Standard MITS crimson footer bar."""
        # Crimson bar spanning bottom
        bar_height = Inches(0.62)
        bar_top = Inches(7.5) - bar_height
        bar = slide.shapes.add_shape(
            MSO_SHAPE.RECTANGLE,
            Inches(0), bar_top, Inches(13.333), bar_height
        )
        bar.fill.solid()
        bar.fill.fore_color.rgb = COLOR_RED
        bar.line.color.rgb = COLOR_RED

        # Left label: CareWatcher, Dept of AI and DS
        left_box = slide.shapes.add_textbox(Inches(0.8), bar_top + Inches(0.12), Inches(6.0), Inches(0.4))
        tf_l = left_box.text_frame
        tf_l.margin_left = tf_l.margin_top = tf_l.margin_right = tf_l.margin_bottom = 0
        p_l = tf_l.paragraphs[0]
        p_l.text = "CareWatcher, Dept of AI and DS"
        p_l.font.name = "Arial"
        p_l.font.size = Pt(11)
        p_l.font.bold = True
        p_l.font.color.rgb = COLOR_WHITE

        # Right slide number
        right_box = slide.shapes.add_textbox(Inches(11.8), bar_top + Inches(0.1), Inches(0.8), Inches(0.4))
        tf_r = right_box.text_frame
        tf_r.margin_left = tf_r.margin_top = tf_r.margin_right = tf_r.margin_bottom = 0
        p_r = tf_r.paragraphs[0]
        p_r.alignment = PP_ALIGN.RIGHT
        p_r.text = str(slide_num)
        p_r.font.name = "Arial"
        p_r.font.size = Pt(14)
        p_r.font.bold = True
        p_r.font.color.rgb = COLOR_WHITE

    def add_card(slide, left, top, width, height, bg_color=COLOR_CARD_BG, border_color=COLOR_CARD_BORDER):
        """Add a rounded card container for content grouping."""
        card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height)
        card.fill.solid()
        card.fill.fore_color.rgb = bg_color
        card.line.color.rgb = border_color
        card.line.width = Pt(1)
        return card

    # =========================================================================
    # SLIDE 1: Title & Team Details
    # =========================================================================
    slide1 = prs.slides.add_slide(blank_layout)

    # Top Center Logo
    if os.path.exists(logo_path):
        slide1.shapes.add_picture(logo_path, Inches(5.35), Inches(0.45), width=Inches(2.6))

    # Title Container
    title_box = slide1.shapes.add_textbox(Inches(1.0), Inches(1.85), Inches(11.333), Inches(2.2))
    tf1 = title_box.text_frame
    tf1.word_wrap = True
    tf1.margin_left = tf1.margin_top = tf1.margin_right = tf1.margin_bottom = 0

    p_proj = tf1.paragraphs[0]
    p_proj.alignment = PP_ALIGN.CENTER
    p_proj.text = "CAREWATCHER"
    p_proj.font.name = "Arial"
    p_proj.font.size = Pt(36)
    p_proj.font.bold = True
    p_proj.font.color.rgb = COLOR_DARK

    p_desc = tf1.add_paragraph()
    p_desc.alignment = PP_ALIGN.CENTER
    p_desc.text = "Privacy-Preserving Ambient Healthcare Companion for Passive Wellness Monitoring"
    p_desc.font.name = "Arial"
    p_desc.font.size = Pt(18)
    p_desc.font.bold = True
    p_desc.font.color.rgb = COLOR_RED
    p_desc.space_before = Pt(8)

    p_tag = tf1.add_paragraph()
    p_tag.alignment = PP_ALIGN.CENTER
    p_tag.text = "100% On-Device Ambient Health Intelligence with Zero Cloud Egress"
    p_tag.font.name = "Arial"
    p_tag.font.size = Pt(13)
    p_tag.font.italic = True
    p_tag.font.color.rgb = COLOR_TEXT
    p_tag.space_before = Pt(4)

    p_rev = tf1.add_paragraph()
    p_rev.alignment = PP_ALIGN.CENTER
    p_rev.text = "First Interim Evaluation (Review 1)  |  Academic Year: 2026 – 2027"
    p_rev.font.name = "Arial"
    p_rev.font.size = Pt(14)
    p_rev.font.bold = True
    p_rev.font.color.rgb = COLOR_DARK
    p_rev.space_before = Pt(14)

    # Department Tag
    p_dept = tf1.add_paragraph()
    p_dept.alignment = PP_ALIGN.CENTER
    p_dept.text = "Department of Artificial Intelligence and Data Science"
    p_dept.font.name = "Arial"
    p_dept.font.size = Pt(13)
    p_dept.font.bold = True
    p_dept.font.color.rgb = COLOR_MUTED
    p_dept.space_before = Pt(4)

    # Guide Card (Bottom Left)
    add_card(slide1, Inches(1.2), Inches(4.35), Inches(5.0), Inches(2.1), COLOR_WHITE, COLOR_CARD_BORDER)
    guide_box = slide1.shapes.add_textbox(Inches(1.5), Inches(4.5), Inches(4.5), Inches(1.8))
    tf_g = guide_box.text_frame
    tf_g.word_wrap = True

    p = tf_g.paragraphs[0]
    p.text = "Project Guide"
    p.font.name = "Arial"
    p.font.size = Pt(14)
    p.font.bold = True
    p.font.color.rgb = COLOR_RED

    items_g = [
        "[Guide Name]",
        "Assistant Professor",
        "Department of AI & DS",
        "Muthoot Institute of Technology and Science"
    ]
    for item in items_g:
        p = tf_g.add_paragraph()
        p.text = item
        p.font.name = "Arial"
        p.font.size = Pt(12)
        p.font.color.rgb = COLOR_TEXT
        p.space_before = Pt(2)

    # Team Card (Bottom Right)
    add_card(slide1, Inches(7.133), Inches(4.35), Inches(5.0), Inches(2.1), COLOR_WHITE, COLOR_CARD_BORDER)
    team_box = slide1.shapes.add_textbox(Inches(7.433), Inches(4.5), Inches(4.5), Inches(1.8))
    tf_t = team_box.text_frame
    tf_t.word_wrap = True

    p = tf_t.paragraphs[0]
    p.text = "Team Members (Group: [X])"
    p.font.name = "Arial"
    p.font.size = Pt(14)
    p.font.bold = True
    p.font.color.rgb = COLOR_RED

    members = [
        "Aaron  (Roll No: [Roll No.])",
        "[Member 2]  (Roll No: [Roll No.])",
        "[Member 3]  (Roll No: [Roll No.])",
        "[Member 4]  (Roll No: [Roll No.])"
    ]
    for mem in members:
        p = tf_t.add_paragraph()
        p.text = mem
        p.font.name = "Arial"
        p.font.size = Pt(12)
        p.font.color.rgb = COLOR_TEXT
        p.space_before = Pt(2)

    add_footer(slide1, 1)

    # =========================================================================
    # SLIDE 2: Problem Statement
    # =========================================================================
    slide2 = prs.slides.add_slide(blank_layout)
    add_header(slide2, "Problem Statement", "Geriatric Healthcare & Ambient Monitoring")

    card_w = Inches(3.64)
    card_h = Inches(5.1)
    card_y = Inches(1.45)

    # Card 1: Solitary Living Vulnerability
    add_card(slide2, Inches(0.8), card_y, card_w, card_h)
    box = slide2.shapes.add_textbox(Inches(1.0), card_y + Inches(0.2), card_w - Inches(0.4), card_h - Inches(0.4))
    tf = box.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = "1. Solitary Living & Silent Decline"
    p.font.name = "Arial"
    p.font.size = Pt(15)
    p.font.bold = True
    p.font.color.rgb = COLOR_RED

    points1 = [
        ("Surging Demographic: ", "1 in 6 people globally will be aged 60+ by 2030, with a vast majority living independently."),
        ("Medication Non-Adherence: ", "Over 50% of elderly with chronic conditions forget or mismanage prescribed dosages."),
        ("Silent Deterioration: ", "Subtle mood shifts, sleep degradation, and reduced mobility go unnoticed until an acute crisis occurs."),
        ("Delayed Distress Response: ", "Physical falls or acute medical distress often result in prolonged immobilization before help arrives.")
    ]
    for head, body in points1:
        p = tf.add_paragraph()
        p.space_before = Pt(10)
        run_h = p.add_run()
        run_h.text = "• " + head
        run_h.font.bold = True
        run_h.font.size = Pt(11)
        run_h.font.color.rgb = COLOR_DARK
        run_b = p.add_run()
        run_b.text = body
        run_b.font.size = Pt(11)
        run_b.font.color.rgb = COLOR_TEXT

    # Card 2: The Cloud Privacy Dilemma
    add_card(slide2, Inches(4.84), card_y, card_w, card_h)
    box = slide2.shapes.add_textbox(Inches(5.04), card_y + Inches(0.2), card_w - Inches(0.4), card_h - Inches(0.4))
    tf = box.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = "2. The Cloud Privacy Dilemma"
    p.font.name = "Arial"
    p.font.size = Pt(15)
    p.font.bold = True
    p.font.color.rgb = COLOR_RED

    points2 = [
        ("Invasive Egress: ", "Commercial assistants (Alexa, Google Home, smart cams) continuously stream raw domestic audio and video to third-party cloud servers."),
        ("Resident Rejection: ", "Elderly individuals strongly reject camera surveillance in private bedrooms and living quarters due to dignity loss."),
        ("Regulatory & Security Risk: ", "Transmission and cloud storage of sensitive biometric data violates strict healthcare privacy standards (HIPAA, GDPR)."),
        ("Recurring Costs: ", "Cloud health monitoring services impose mandatory monthly subscription fees that strain low-income seniors.")
    ]
    for head, body in points2:
        p = tf.add_paragraph()
        p.space_before = Pt(10)
        run_h = p.add_run()
        run_h.text = "• " + head
        run_h.font.bold = True
        run_h.font.size = Pt(11)
        run_h.font.color.rgb = COLOR_DARK
        run_b = p.add_run()
        run_b.text = body
        run_b.font.size = Pt(11)
        run_b.font.color.rgb = COLOR_TEXT

    # Card 3: Network Dependency & Clinical Risks
    add_card(slide2, Inches(8.88), card_y, card_w, card_h)
    box = slide2.shapes.add_textbox(Inches(9.08), card_y + Inches(0.2), card_w - Inches(0.4), card_h - Inches(0.4))
    tf = box.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = "3. Technical & Algorithmic Limits"
    p.font.name = "Arial"
    p.font.size = Pt(15)
    p.font.bold = True
    p.font.color.rgb = COLOR_RED

    points3 = [
        ("Internet Single Point of Failure: ", "Broadband or router outages render cloud-dependent emergency detection totally offline."),
        ("LLM Hallucination Threat: ", "Unconstrained generative LLMs risk inventing dangerous medical diagnoses or clinical directives."),
        ("Alarm Fatigue: ", "Generic threshold sensors bombard caregivers with false alarms, causing notification blindness."),
        ("Lack of Auditability: ", "Cloud-based AI decisions lack cryptographic provenance; no verifiable record exists if an alert is dropped.")
    ]
    for head, body in points3:
        p = tf.add_paragraph()
        p.space_before = Pt(10)
        run_h = p.add_run()
        run_h.text = "• " + head
        run_h.font.bold = True
        run_h.font.size = Pt(11)
        run_h.font.color.rgb = COLOR_DARK
        run_b = p.add_run()
        run_b.text = body
        run_b.font.size = Pt(11)
        run_b.font.color.rgb = COLOR_TEXT

    add_footer(slide2, 2)

    # =========================================================================
    # SLIDE 3: Objectives
    # =========================================================================
    slide3 = prs.slides.add_slide(blank_layout)
    add_header(slide3, "Project Objectives", "Core Research & Engineering Goals")

    obj_h = Inches(1.55)
    obj_y_start = Inches(1.45)
    obj_gap = Inches(0.18)

    objectives_data = [
        (
            "Objective 1: Hardware-Enforced Zero-Cloud Privacy Architecture",
            "To design and engineer an ambient edge computing architecture featuring a physical Privacy Shutter hard gate, ensuring 100% local on-device processing with mathematically verifiable zero network data egress.",
            [
                "Physical gating of acoustic and visual sensors (guaranteed 0 bytes passed when shutter is closed).",
                "Full local execution of speech recognition, natural language reasoning, and database storage without cloud APIs."
            ],
            COLOR_RED
        ),
        (
            "Objective 2: Multimodal Passive Ambient Sensing & Trend Analysis",
            "To integrate contactless acoustic speech, local quantized LLMs, and an ESP32 multi-biosensor telemetry hub (MAX30102 PPG, MLX90614 IR Temp, MPU-6050 Motion) to passively monitor medication adherence and detect vital drift.",
            [
                "Schema-constrained JSON extraction from natural resident voice responses during conversational check-ins.",
                "Statistical rolling baseline trend engine with Z-score drift alerts (flagging abnormal heart rate, SpO2, sleep, or mood changes)."
            ],
            COLOR_BLUE
        ),
        (
            "Objective 3: Decoupled Proposer-Verifier Safety & Audit Provenance",
            "To construct an isolated dual-engine safety pipeline with an append-only, SHA-256 hash-chained cryptographic audit log to eliminate diagnostic hallucinations and provide tamper-proof accountability.",
            [
                "Independent Safety Verifier enforces strict clinical deny-lists, tone validation, and anti-fatigue rate limiting.",
                "Immutable, hash-chained ledger storing every sensory reading, proposal, and verification decision with 100% replay integrity."
            ],
            COLOR_GREEN
        )
    ]

    for i, (title, summary, bullets, color) in enumerate(objectives_data):
        y = obj_y_start + i * (obj_h + obj_gap)
        add_card(slide3, Inches(0.8), y, Inches(11.733), obj_h, COLOR_WHITE, COLOR_CARD_BORDER)

        # Color indicator tab on left edge of card
        tab = slide3.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.8), y, Inches(0.15), obj_h)
        tab.fill.solid()
        tab.fill.fore_color.rgb = color
        tab.line.color.rgb = color

        box = slide3.shapes.add_textbox(Inches(1.15), y + Inches(0.1), Inches(11.2), obj_h - Inches(0.2))
        tf = box.text_frame
        tf.word_wrap = True

        p0 = tf.paragraphs[0]
        p0.text = title
        p0.font.name = "Arial"
        p0.font.size = Pt(14)
        p0.font.bold = True
        p0.font.color.rgb = color

        p1 = tf.add_paragraph()
        p1.text = summary
        p1.font.name = "Arial"
        p1.font.size = Pt(11)
        p1.font.color.rgb = COLOR_TEXT
        p1.space_before = Pt(2)

        for b in bullets:
            pb = tf.add_paragraph()
            pb.text = "▸ " + b
            pb.font.name = "Arial"
            pb.font.size = Pt(10)
            pb.font.color.rgb = COLOR_MUTED
            pb.space_before = Pt(2)

    add_footer(slide3, 3)

    # =========================================================================
    # SLIDE 4: Project Overview
    # =========================================================================
    slide4 = prs.slides.add_slide(blank_layout)
    add_header(slide4, "Project Overview", "Concise Summary & System Rationale")

    # 6-box grid for the 6 required guidelines elements
    grid_w = Inches(3.75)
    grid_h = Inches(2.45)
    xs = [Inches(0.8), Inches(4.79), Inches(8.78)]
    ys = [Inches(1.45), Inches(4.15)]

    overview_items = [
        ("Engineering Problem", "Real-Time Edge AI under Resource Constraints",
         "Executing concurrent wake-word detection, speech-to-text (Whisper), LLM conversational reasoning, and continuous biosensor telemetry on consumer edge hardware with <8s latency, zero cloud offloading, and deterministic memory consumption.",
         COLOR_RED),
        ("Motivation", "Dignified Autonomy for Vulnerable Seniors",
         "Enabling aging individuals to live independently without feeling under surveillance. Replacing intrusive cameras with ambient conversational check-ins and passive non-contact vital sensing.",
         COLOR_BLUE),
        ("Need for Project", "The Global Geriatric Caregiving Crisis",
         "Acute shortage of professional geriatric aides combined with rising elderly populations living alone. Existing smart assistants violate privacy; CareWatcher delivers continuous safety without data leakage.",
         COLOR_DARK),
        ("Target Users", "Elderly Individuals & Healthcare Stakeholders",
         "Primary: Solitary elderly residents, mobility-limited individuals, post-operative recovering patients.\nSecondary: Family caregivers, geriatric nurses, assisted living facility administrators.",
         COLOR_GREEN),
        ("Scope of Project", "Ambient Wellness Monitoring (Non-Clinical)",
         "Covers conversational medication checks, rolling vital drift detection (BPM, SpO2, Temperature), immobility/fall alerts, and encrypted audit logging. Explicitly excludes clinical diagnosis and invasive wearable mandates.",
         COLOR_AMBER),
        ("Expected Impact", "Safe, Resilient & Cost-Free Ambient Care",
         "100% privacy preservation (HIPAA/GDPR compliant by design), zero recurring cloud subscription fees, resilient offline operation during network blackouts, and prompt caregiver alerting.",
         COLOR_RED)
    ]

    for idx, (head, sub, desc, col) in enumerate(overview_items):
        col_idx = idx % 3
        row_idx = idx // 3
        x = xs[col_idx]
        y = ys[row_idx]

        add_card(slide4, x, y, grid_w, grid_h, COLOR_WHITE, COLOR_CARD_BORDER)

        box = slide4.shapes.add_textbox(x + Inches(0.2), y + Inches(0.15), grid_w - Inches(0.4), grid_h - Inches(0.3))
        tf = box.text_frame
        tf.word_wrap = True

        p0 = tf.paragraphs[0]
        p0.text = head.upper()
        p0.font.name = "Arial"
        p0.font.size = Pt(11)
        p0.font.bold = True
        p0.font.color.rgb = col

        p1 = tf.add_paragraph()
        p1.text = sub
        p1.font.name = "Arial"
        p1.font.size = Pt(12)
        p1.font.bold = True
        p1.font.color.rgb = COLOR_DARK
        p1.space_before = Pt(2)

        p2 = tf.add_paragraph()
        p2.text = desc
        p2.font.name = "Arial"
        p2.font.size = Pt(10)
        p2.font.color.rgb = COLOR_TEXT
        p2.space_before = Pt(4)

    add_footer(slide4, 4)

    # =========================================================================
    # SLIDE 5: Progress Since Zeroth Review
    # =========================================================================
    slide5 = prs.slides.add_slide(blank_layout)
    add_header(slide5, "Progress Since Zeroth Review", "Milestones, Implementation Status & Feedback Incorporation")

    # Comparison Table
    table_left = Inches(0.8)
    table_top = Inches(1.4)
    table_w = Inches(11.733)
    table_h = Inches(3.2)

    table_shape = slide5.shapes.add_table(7, 3, table_left, table_top, table_w, table_h)
    tbl = table_shape.table
    tbl.columns[0].width = Inches(2.2)
    tbl.columns[1].width = Inches(4.5)
    tbl.columns[2].width = Inches(5.033)

    headers = ["Parameters", "Zeroth Review Proposal", "Current Status (Review 1)"]
    for c_idx, h_text in enumerate(headers):
        cell = tbl.cell(0, c_idx)
        cell.fill.solid()
        cell.fill.fore_color.rgb = COLOR_RED
        p = cell.text_frame.paragraphs[0]
        p.text = h_text
        p.font.name = "Arial"
        p.font.size = Pt(11)
        p.font.bold = True
        p.font.color.rgb = COLOR_WHITE
        p.alignment = PP_ALIGN.LEFT

    table_rows = [
        ("Literature Survey", "Reviewed 15+ broad papers on smart home IoT and ambient assisted living.", "Completed survey on Edge AI, Faster-Whisper, quantized LLMs, and non-clinical safety verification."),
        ("Problem Definition", "General concept of smart elderly assistant with cloud sync.", "Refined to 100% on-device, privacy-preserving companion with strictly non-clinical boundaries."),
        ("Architecture", "Initial high-level block diagram with shared modules.", "Engineered modular 8-stage pipeline with hard Privacy Shutter and isolated Proposer ↔ Verifier."),
        ("Algorithms", "Planned simple rule-based keyword matching.", "Implemented Faster-Whisper STT, Mistral-7B schema JSON extraction, and Z-score rolling drift algorithms."),
        ("Hardware", "Preliminary sensor list (conceptual selection).", "Built ESP32 sensor hub (MAX30102 PPG, MLX90614 IR Temp, MPU-6050) + local mic/webcam drivers."),
        ("Software", "No codebase or implementation.", "Engineered complete modular Python 3.11 core (82/82 passing tests) + Local Web Dashboard.")
    ]

    for r_idx, row_data in enumerate(table_rows, start=1):
        bg = COLOR_WHITE if r_idx % 2 != 0 else COLOR_CARD_BG
        for c_idx, text in enumerate(row_data):
            cell = tbl.cell(r_idx, c_idx)
            cell.fill.solid()
            cell.fill.fore_color.rgb = bg
            p = cell.text_frame.paragraphs[0]
            p.text = text
            p.font.name = "Arial"
            p.font.size = Pt(10)
            p.font.color.rgb = COLOR_DARK if c_idx == 0 else COLOR_TEXT
            if c_idx == 0:
                p.font.bold = True

    # Committee Suggestions -> Action Taken Box
    callout_top = Inches(4.75)
    callout_h = Inches(1.8)
    add_card(slide5, Inches(0.8), callout_top, Inches(11.733), callout_h, COLOR_WHITE, COLOR_RED)

    cbox = slide5.shapes.add_textbox(Inches(1.0), callout_top + Inches(0.12), Inches(11.3), callout_h - Inches(0.2))
    ctf = cbox.text_frame
    ctf.word_wrap = True

    cp0 = ctf.paragraphs[0]
    cp0.text = "COMMITTEE SUGGESTIONS INCORPORATED"
    cp0.font.name = "Arial"
    cp0.font.size = Pt(12)
    cp0.font.bold = True
    cp0.font.color.rgb = COLOR_RED

    suggestions = [
        ("Committee Suggestion 1: ", "Prevent generative AI from offering unverified clinical diagnoses or prescribing medications.",
         "Action Taken: ", "Created a fully decoupled SafetyVerifier that checks every proposed intervention against a strict medical deny-list, non-clinical language guidelines, and anti-fatigue rate limits before audio delivery."),
        ("Committee Suggestion 2: ", "Provide tangible architectural proof that user privacy is strictly guaranteed without trusting external servers.",
         "Action Taken: ", "Implemented a software/hardware-gated PrivacyShutter with automated fuzz verification confirming 0 bytes pass downstream when shutter is CLOSED, alongside zero cloud egress.")
    ]

    for s_head, s_text, a_head, a_text in suggestions:
        sp = ctf.add_paragraph()
        sp.space_before = Pt(4)
        r1 = sp.add_run()
        r1.text = "• " + s_head
        r1.font.bold = True
        r1.font.size = Pt(10)
        r1.font.color.rgb = COLOR_DARK
        r2 = sp.add_run()
        r2.text = s_text + "  ➔  "
        r2.font.size = Pt(10)
        r2.font.color.rgb = COLOR_TEXT
        r3 = sp.add_run()
        r3.text = a_head
        r3.font.bold = True
        r3.font.size = Pt(10)
        r3.font.color.rgb = COLOR_GREEN
        r4 = sp.add_run()
        r4.text = a_text
        r4.font.size = Pt(10)
        r4.font.color.rgb = COLOR_TEXT

    add_footer(slide5, 5)

    # =========================================================================
    # SLIDE 6: System Requirements & Design
    # =========================================================================
    slide6 = prs.slides.add_slide(blank_layout)
    add_header(slide6, "System Requirements & Architecture Design", "Decoupled 5-Layer Edge Pipeline with Root of Privacy")

    # 5 Layer Architecture Cards
    layer_w = Inches(2.2)
    layer_h = Inches(5.1)
    layer_y = Inches(1.45)
    layer_xs = [Inches(0.8 + i * 2.38) for i in range(5)]

    layers_info = [
        ("Layer 1: Perception", "Hardware & Sensors", COLOR_DARK, [
            ("Mic Source", "16kHz local audio stream"),
            ("Webcam Pres.", "Local OpenCV Haar cascade; NO video/frames saved"),
            ("ESP32 Sensor Hub", "MAX30102 (BPM & SpO2 via I2C)"),
            ("MLX90614", "Contactless IR forehead temp"),
            ("MPU-6050", "6-axis motion & fall accelerometer")
        ]),
        ("Layer 2: Privacy Root", "Physical Shutter Gate", COLOR_RED, [
            ("Privacy Shutter", "Hard gate root boundary"),
            ("Binary State", "CLOSED (default) / OPEN"),
            ("Hard Isolation", "Zero bytes flow downstream when closed"),
            ("Manual/Voice", "Hardware switch & voice command toggling"),
            ("Fuzz Validated", "100% leak-proof verification")
        ]),
        ("Layer 3: Cognition", "Edge AI Pipeline", COLOR_BLUE, [
            ("Wake Word", "'hey care' keyword detector"),
            ("Whisper STT", "Local Faster-Whisper base model"),
            ("Mistral-7B", "4-bit GGUF via llama.cpp on CPU"),
            ("Schema Guard", "Enforced JSON HealthEvent dataclass"),
            ("Zero Cloud", "Zero external network calls")
        ]),
        ("Layer 4: Memory & Drift", "Trends & Storage", COLOR_AMBER, [
            ("Resident DB", "Local SQLite3 encrypted store"),
            ("Rolling Baseline", "7-day sliding window vitals"),
            ("Drift Engine", "Z-score statistical deviation"),
            ("Vital Drift", "SpO2 <92%, BPM delta >20"),
            ("Inactivity Check", "90-min sedentary threshold")
        ]),
        ("Layer 5: Safety & Action", "Verifier & Delivery", COLOR_GREEN, [
            ("Rule Proposer", "Generates candidate interventions"),
            ("Safety Verifier", "Independent gate (no imports of Proposer)"),
            ("Medical Deny-List", "Blocks diagnostic/clinical terms"),
            ("Piper TTS", "Local neural speech delivery"),
            ("SHA-256 Audit", "Tamper-evident hash-chained log")
        ])
    ]

    for idx, (title, sub, col, items) in enumerate(layers_info):
        x = layer_xs[idx]
        add_card(slide6, x, layer_y, layer_w, layer_h, COLOR_WHITE, COLOR_CARD_BORDER)

        # Header box inside card
        header_shape = slide6.shapes.add_shape(MSO_SHAPE.RECTANGLE, x, layer_y, layer_w, Inches(0.75))
        header_shape.fill.solid()
        header_shape.fill.fore_color.rgb = col
        header_shape.line.color.rgb = col

        hb = slide6.shapes.add_textbox(x + Inches(0.05), layer_y + Inches(0.08), layer_w - Inches(0.1), Inches(0.6))
        htf = hb.text_frame
        htf.word_wrap = True
        hp0 = htf.paragraphs[0]
        hp0.text = title
        hp0.font.name = "Arial"
        hp0.font.size = Pt(11)
        hp0.font.bold = True
        hp0.font.color.rgb = COLOR_WHITE
        hp1 = htf.add_paragraph()
        hp1.text = sub
        hp1.font.name = "Arial"
        hp1.font.size = Pt(9)
        hp1.font.color.rgb = RGBColor(230, 230, 230)

        # Content text inside card
        cb = slide6.shapes.add_textbox(x + Inches(0.1), layer_y + Inches(0.85), layer_w - Inches(0.2), layer_h - Inches(0.95))
        ctf = cb.text_frame
        ctf.word_wrap = True

        for i_head, i_desc in items:
            p = ctf.add_paragraph()
            p.space_before = Pt(8)
            r0 = p.add_run()
            r0.text = "• " + i_head + "\n"
            r0.font.name = "Arial"
            r0.font.size = Pt(10)
            r0.font.bold = True
            r0.font.color.rgb = COLOR_DARK
            r1 = p.add_run()
            r1.text = "  " + i_desc
            r1.font.name = "Arial"
            r1.font.size = Pt(9)
            r1.font.color.rgb = COLOR_TEXT

    add_footer(slide6, 6)

    # =========================================================================
    # SLIDE 7: Methodology
    # =========================================================================
    slide7 = prs.slides.add_slide(blank_layout)
    add_header(slide7, "Methodology & Execution Pipeline", "End-to-End Multimodal Processing Workflow")

    col_w = Inches(5.7)
    col_h = Inches(5.1)
    col_y = Inches(1.45)

    # Left Column: AI Methodology
    add_card(slide7, Inches(0.8), col_y, col_w, col_h, COLOR_WHITE, COLOR_CARD_BORDER)
    box_ai = slide7.shapes.add_textbox(Inches(1.0), col_y + Inches(0.2), col_w - Inches(0.4), col_h - Inches(0.4))
    tf_ai = box_ai.text_frame
    tf_ai.word_wrap = True

    p = tf_ai.paragraphs[0]
    p.text = "AI & Conversational Intelligence Methodology"
    p.font.name = "Arial"
    p.font.size = Pt(14)
    p.font.bold = True
    p.font.color.rgb = COLOR_BLUE

    ai_steps = [
        ("Speech Processing Pipeline: ", "Captures 16 kHz raw PCM audio chunks. Ingests via Faster-Whisper base model (CTranslate2 CPU backend) for fast word-error-rate performance without external speech APIs."),
        ("Wake-Word Activation: ", "Keyword detection pipeline continually scans transcripts for 'hey care' before triggering active conversational agent state."),
        ("Schema-Constrained LLM Reasoning: ", "Utilizes 4-bit quantized Mistral-7B-Instruct (Q4_K_M GGUF) via llama.cpp. Prompts strictly constrain output to validated JSON schemas (category, summary, confidence, mood_label)."),
        ("Rolling Baseline Drift Detection: ", "Maintains 7-day personal vital statistics (mean, standard deviation). Detects anomalies via dynamic thresholds (e.g., SpO2 < 92%, BPM shift > 20, continuous negative sentiment)."),
        ("Verification Testing: ", "Automated test suite (test_agent.py, test_pipeline.py) rigorously evaluates prompt adherence and schema validation against synthetic conversational transcripts.")
    ]
    for head, body in ai_steps:
        p = tf_ai.add_paragraph()
        p.space_before = Pt(8)
        r0 = p.add_run()
        r0.text = "• " + head
        r0.font.bold = True
        r0.font.size = Pt(10)
        r0.font.color.rgb = COLOR_DARK
        r1 = p.add_run()
        r1.text = body
        r1.font.size = Pt(10)
        r1.font.color.rgb = COLOR_TEXT

    # Right Column: Hardware & Safety Methodology
    add_card(slide7, Inches(6.833), col_y, col_w, col_h, COLOR_WHITE, COLOR_CARD_BORDER)
    box_hw = slide7.shapes.add_textbox(Inches(7.033), col_y + Inches(0.2), col_w - Inches(0.4), col_h - Inches(0.4))
    tf_hw = box_hw.text_frame
    tf_hw.word_wrap = True

    p = tf_hw.paragraphs[0]
    p.text = "Hardware Integration & Safety Verification Methodology"
    p.font.name = "Arial"
    p.font.size = Pt(14)
    p.font.bold = True
    p.font.color.rgb = COLOR_RED

    hw_steps = [
        ("Microcontroller Hub & Bus Architecture: ", "ESP32-WROOM-32 coordinates MAX30102 (PPG) and MLX90614 (IR Temp) over I2C (GPIO 21 SDA, GPIO 22 SCL) and HC-SR501 over GPIO 13. Communicates via USB Virtual COM @ 115200 baud."),
        ("Physical Shutter Gating: ", "All incoming sensory feeds pass through the PrivacyShutter state machine. Gated at the root boundary: zero bytes exit driver layers when shutter is CLOSED."),
        ("Decoupled Safety Verifier: ", "Zero shared imports with Proposer engine. Inspects every proposed intervention for clinical claims, quiet hours (22:00–07:00), and rate-limits (max 3 reminders/hour)."),
        ("Actuation & Delivery: ", "Approved interventions synthesize locally via Piper neural TTS (en_US-lessac voice) and stream real-time JSON events to the local Web Dashboard."),
        ("Tamper-Evident SHA-256 Audit: ", "Each event (readings, proposals, verifier decisions) is hashed deterministically with the previous block's SHA-256 digest, guaranteeing cryptographic integrity.")
    ]
    for head, body in hw_steps:
        p = tf_hw.add_paragraph()
        p.space_before = Pt(8)
        r0 = p.add_run()
        r0.text = "• " + head
        r0.font.bold = True
        r0.font.size = Pt(10)
        r0.font.color.rgb = COLOR_DARK
        r1 = p.add_run()
        r1.text = body
        r1.font.size = Pt(10)
        r1.font.color.rgb = COLOR_TEXT

    add_footer(slide7, 7)

    # =========================================================================
    # SLIDE 8: Technology Used & Justification
    # =========================================================================
    slide8 = prs.slides.add_slide(blank_layout)
    add_header(slide8, "Technology Stack & Technical Justifications", "Curated Selection for Privacy, Performance, and Edge Independence")

    table_left = Inches(0.8)
    table_top = Inches(1.45)
    table_w = Inches(11.733)
    table_h = Inches(5.1)

    table_shape = slide8.shapes.add_table(10, 3, table_left, table_top, table_w, table_h)
    tbl8 = table_shape.table
    tbl8.columns[0].width = Inches(2.2)
    tbl8.columns[1].width = Inches(3.5)
    tbl8.columns[2].width = Inches(6.033)

    h_titles = ["Stack Layer", "Technology / Framework", "Technical Justification & Architectural Trade-off"]
    for c_idx, h_text in enumerate(h_titles):
        cell = tbl8.cell(0, c_idx)
        cell.fill.solid()
        cell.fill.fore_color.rgb = COLOR_RED
        p = cell.text_frame.paragraphs[0]
        p.text = h_text
        p.font.name = "Arial"
        p.font.size = Pt(11)
        p.font.bold = True
        p.font.color.rgb = COLOR_WHITE

    tech_data = [
        ("Microcontroller Hub", "ESP32-WROOM-32", "Low-cost dual-core 240MHz SoC with hardware I2C/UART; supports real-time biosensor acquisition with zero OS jitter."),
        ("PPG Biosensor", "MAX30102 Pulse Oximeter", "Dual-wavelength (660nm & 880nm) photoplethysmography providing clinical-grade heart rate and SpO2 readings."),
        ("IR Temperature", "MLX90614 Contactless IR", "Medical-grade non-contact thermometry (±0.2°C accuracy); measures body temperature passively without touching the resident."),
        ("Motion & IMU", "MPU-6050 6-Axis Accelerometer", "Detects resident tremors, room movement, and sudden high-g impact forces characteristic of physical falls."),
        ("Speech-to-Text", "OpenAI Faster-Whisper (base)", "CTranslate2 optimized; 4x faster execution & 50% less RAM than vanilla Whisper, enabling low-latency CPU speech transcription."),
        ("Edge LLM Reasoning", "Mistral-7B Q4_K_M (llama.cpp)", "Quantized 4-bit weights run within 4GB RAM on standard laptop CPU; provides structured JSON health event extraction."),
        ("Neural Speech Synth", "Piper TTS / pyttsx3", "High-fidelity, ultra-low latency neural text-to-speech engine running 100% locally with zero cloud streaming."),
        ("Local Database", "SQLite 3 (data/resident.db)", "Zero-configuration, ACID compliant serverless SQL engine; maintains rolling resident baselines and event history locally."),
        ("Web Architecture", "Python http.server + Vanilla JS", "Standard library HTTP server with zero third-party web bloat; renders real-time dashboard UI directly on localhost.")
    ]

    for r_idx, (layer, tech, just) in enumerate(tech_data, start=1):
        bg = COLOR_WHITE if r_idx % 2 != 0 else COLOR_CARD_BG
        for c_idx, val in enumerate([layer, tech, just]):
            cell = tbl8.cell(r_idx, c_idx)
            cell.fill.solid()
            cell.fill.fore_color.rgb = bg
            p = cell.text_frame.paragraphs[0]
            p.text = val
            p.font.name = "Arial"
            p.font.size = Pt(9.5)
            p.font.color.rgb = COLOR_DARK if c_idx < 2 else COLOR_TEXT
            if c_idx < 2:
                p.font.bold = True

    add_footer(slide8, 8)

    # =========================================================================
    # SLIDE 9: Preliminary / Interim Results
    # =========================================================================
    slide9 = prs.slides.add_slide(blank_layout)
    add_header(slide9, "Preliminary & Interim Results", "Empirical Evidence of Working System Implementation")

    # Left Column: Real Dashboard Screenshot
    col_w = Inches(5.6)
    card_h = Inches(5.1)
    card_y = Inches(1.45)

    add_card(slide9, Inches(0.8), card_y, col_w, card_h, COLOR_WHITE, COLOR_CARD_BORDER)
    box_l = slide9.shapes.add_textbox(Inches(1.0), card_y + Inches(0.15), col_w - Inches(0.4), Inches(0.5))
    tf_l = box_l.text_frame
    p = tf_l.paragraphs[0]
    p.text = "Live Operational Web Dashboard (Running on Localhost)"
    p.font.name = "Arial"
    p.font.size = Pt(12)
    p.font.bold = True
    p.font.color.rgb = COLOR_RED

    if os.path.exists(screenshot_path):
        slide9.shapes.add_picture(screenshot_path, Inches(1.0), card_y + Inches(0.65), width=col_w - Inches(0.4))
    else:
        # Placeholder if missing
        box_sub = slide9.shapes.add_textbox(Inches(1.0), card_y + Inches(1.0), col_w - Inches(0.4), Inches(2.0))
        box_sub.text_frame.text = "Dashboard active at http://localhost:8000"

    caption_box = slide9.shapes.add_textbox(Inches(1.0), card_y + Inches(4.35), col_w - Inches(0.4), Inches(0.6))
    tf_cap = caption_box.text_frame
    tf_cap.word_wrap = True
    p_cap = tf_cap.paragraphs[0]
    p_cap.text = "Fig 9.1: CareWatcher live web UI displaying active Privacy Shutter, real-time ESP32 vitals telemetry, conversational audit trail, and zero-cloud shield verification."
    p_cap.font.name = "Arial"
    p_cap.font.size = Pt(8.5)
    p_cap.font.italic = True
    p_cap.font.color.rgb = COLOR_MUTED

    # Right Column: Empirical Test & Pipeline Benchmarks
    add_card(slide9, Inches(6.7), card_y, Inches(5.833), card_h, COLOR_WHITE, COLOR_CARD_BORDER)
    box_r = slide9.shapes.add_textbox(Inches(6.9), card_y + Inches(0.15), Inches(5.433), card_h - Inches(0.3))
    tf_r = box_r.text_frame
    tf_r.word_wrap = True

    p = tf_r.paragraphs[0]
    p.text = "Validated Functional Milestones (M0 to M8 Complete)"
    p.font.name = "Arial"
    p.font.size = Pt(13)
    p.font.bold = True
    p.font.color.rgb = COLOR_GREEN

    metrics = [
        ("Automated Test Suite: ", "82 / 82 tests passing (100% pass rate in 3.03s) across config, shutter, STT, LLM schema parsing, memory store, and audit logging."),
        ("Privacy Shutter Verification: ", "Automated fuzz tests confirm 0 bytes leaked when shutter is in CLOSED state. Physical toggle verified in live runtime."),
        ("Conversational Extraction: ", "Resident voice utterance 'hey care I forgot to take my morning blood pressure pills' accurately transcribed and parsed into structured MEDICATION event."),
        ("Rolling Baseline Drift Detection: ", "Injected 110 BPM tachycardia reading immediately triggered drift alert against resident's 72 BPM baseline (Z-score > threshold)."),
        ("Safety Verifier Efficacy: ", "100% rejection rate for diagnostic/prescriptive medical words in deny-list; strictly enforced non-clinical reminder phrasing."),
        ("Cryptographic Audit Chain: ", "Deterministic SHA-256 hashing verified with 100% valid blockchain-style sequence integrity across all system events.")
    ]

    for m_head, m_body in metrics:
        p = tf_r.add_paragraph()
        p.space_before = Pt(7)
        r0 = p.add_run()
        r0.text = "✔ " + m_head
        r0.font.bold = True
        r0.font.size = Pt(10)
        r0.font.color.rgb = COLOR_DARK
        r1 = p.add_run()
        r1.text = m_body
        r1.font.size = Pt(9.5)
        r1.font.color.rgb = COLOR_TEXT

    add_footer(slide9, 9)

    # =========================================================================
    # SLIDE 10: Remaining Work
    # =========================================================================
    slide10 = prs.slides.add_slide(blank_layout)
    add_header(slide10, "Remaining Work & Completion Status", "Quantified Progress Breakdown (70% Completed  |  30% Remaining)")

    # Overall Progress Banner
    banner_y = Inches(1.45)
    banner_h = Inches(0.7)
    add_card(slide10, Inches(0.8), banner_y, Inches(11.733), banner_h, COLOR_WHITE, COLOR_CARD_BORDER)

    # Progress bar fill (70% green, 30% amber)
    bar_w = Inches(11.733)
    completed_bar = slide10.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.8), banner_y, bar_w * 0.70, banner_h)
    completed_bar.fill.solid()
    completed_bar.fill.fore_color.rgb = COLOR_GREEN
    completed_bar.line.color.rgb = COLOR_GREEN

    remaining_bar = slide10.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.8) + (bar_w * 0.70), banner_y, bar_w * 0.30, banner_h)
    remaining_bar.fill.solid()
    remaining_bar.fill.fore_color.rgb = COLOR_AMBER
    remaining_bar.line.color.rgb = COLOR_AMBER

    # Progress text overlay
    pbox = slide10.shapes.add_textbox(Inches(1.0), banner_y + Inches(0.12), Inches(11.3), Inches(0.5))
    ptf = pbox.text_frame
    pp = ptf.paragraphs[0]
    pp.text = "PROJECT STATUS:  70% COMPLETED (CORE PIPELINE OPERATIONAL)   |   30% REMAINING (PHYSICAL HOUSING & FIELD PILOT)"
    pp.font.name = "Arial"
    pp.font.size = Pt(12)
    pp.font.bold = True
    pp.font.color.rgb = COLOR_WHITE
    pp.alignment = PP_ALIGN.CENTER

    # 4 Itemized Cards for Remaining Work
    card_w = Inches(5.7)
    card_h = Inches(2.05)
    xs = [Inches(0.8), Inches(6.833)]
    ys = [Inches(2.35), Inches(4.55)]

    remaining_items = [
        ("1. Physical Enclosure & Hardware Packaging", "Current: 40% Complete  |  Target: W16",
         "• CAD modeling of the desktop companion enclosure.\n• 3D printing of durable housing with integrated physical sliding shutter.\n• PCB perf-board assembly connecting ESP32, MAX30102, and status LEDs.",
         COLOR_RED),
        ("2. Extended Residential Field Pilot Trial", "Current: 30% Complete  |  Target: W17",
         "• Deploying prototype in a 7-day residential test with elderly participant.\n• Calibrating personal baseline parameters across real-world sleep and activity.\n• Collecting usability feedback regarding voice clarity and prompt naturalness.",
         COLOR_BLUE),
        ("3. Edge Hardware Acceleration & Optimization", "Current: 60% Complete  |  Target: W18",
         "• Exploring INT4 NPU / Vulkan GPU offloading to reduce LLM latency (<1.5s).\n• Fine-tuning wake-word detector sensitivity to minimize false rejections.\n• Optimizing ESP32 low-power deep sleep cycles during inactive hours.",
         COLOR_AMBER),
        ("4. Comprehensive Thesis & Academic Paper", "Current: 45% Complete  |  Target: W19",
         "• Finalizing B.Tech comprehensive project report and operational manual.\n• Documenting security audit verification and clinical safety deny-list rules.\n• Submitting research paper: 'Decentralized Ambient Healthcare Companion via On-Device LLMs and Physical Privacy Gating'.",
         COLOR_GREEN)
    ]

    for idx, (head, status, body, col) in enumerate(remaining_items):
        x = xs[idx % 2]
        y = ys[idx // 2]
        add_card(slide10, x, y, card_w, card_h, COLOR_WHITE, COLOR_CARD_BORDER)

        box = slide10.shapes.add_textbox(x + Inches(0.2), y + Inches(0.12), card_w - Inches(0.4), card_h - Inches(0.25))
        tf = box.text_frame
        tf.word_wrap = True

        p0 = tf.paragraphs[0]
        p0.text = head
        p0.font.name = "Arial"
        p0.font.size = Pt(12)
        p0.font.bold = True
        p0.font.color.rgb = col

        p1 = tf.add_paragraph()
        p1.text = status
        p1.font.name = "Arial"
        p1.font.size = Pt(10)
        p1.font.bold = True
        p1.font.color.rgb = COLOR_DARK
        p1.space_before = Pt(2)

        p2 = tf.add_paragraph()
        p2.text = body
        p2.font.name = "Arial"
        p2.font.size = Pt(9.5)
        p2.font.color.rgb = COLOR_TEXT
        p2.space_before = Pt(4)

    add_footer(slide10, 10)

    # =========================================================================
    # SLIDE 11: Updated Timelines & Gantt Chart
    # =========================================================================
    slide11 = prs.slides.add_slide(blank_layout)
    add_header(slide11, "Updated Project Timelines & Gantt Schedule", "20-Week Major Project Development Roadmap")

    table_left = Inches(0.8)
    table_top = Inches(1.45)
    table_w = Inches(11.733)
    table_h = Inches(5.1)

    table_shape = slide11.shapes.add_table(9, 4, table_left, table_top, table_w, table_h)
    tbl11 = table_shape.table
    tbl11.columns[0].width = Inches(3.2)
    tbl11.columns[1].width = Inches(2.2)
    tbl11.columns[2].width = Inches(4.333)
    tbl11.columns[3].width = Inches(2.0)

    gantt_headers = ["Project Phase & Activity", "Timeline (Weeks)", "Key Milestones & Deliverables", "Status"]
    for c_idx, h_text in enumerate(gantt_headers):
        cell = tbl11.cell(0, c_idx)
        cell.fill.solid()
        cell.fill.fore_color.rgb = COLOR_RED
        p = cell.text_frame.paragraphs[0]
        p.text = h_text
        p.font.name = "Arial"
        p.font.size = Pt(11)
        p.font.bold = True
        p.font.color.rgb = COLOR_WHITE

    gantt_rows = [
        ("Phase 1: Survey & Formal Specification", "Weeks 1 – 3", "Literature survey, SPEC.md, interfaces definition", "COMPLETED"),
        ("Phase 2: Privacy Shutter & Sensor Drivers", "Weeks 4 – 6", "Privacy shutter gate, mic driver, ESP32 firmware", "COMPLETED"),
        ("Phase 3: STT & LLM Conversation Agent", "Weeks 7 – 9", "Faster-Whisper integration, Mistral schema parsing", "COMPLETED"),
        ("Phase 4: Trend Engine, Proposer & Verifier", "Weeks 10 – 12", "Rolling drift Z-scores, SafetyVerifier, SHA-256 audit", "COMPLETED"),
        ("Phase 5: Local Dashboard & Integration", "Weeks 13 – 14", "Web UI, HTTP API server, 82 unit tests [REVIEW 1]", "COMPLETED"),
        ("Phase 6: 3D Packaging & Enclosure Fabrication", "Weeks 15 – 16", "CAD housing design, 3D printing, physical slider switch", "IN PROGRESS"),
        ("Phase 7: Residential Pilot & Edge Optimization", "Weeks 17 – 18", "7-day elderly trial, INT4 acceleration [REVIEW 2]", "PENDING"),
        ("Phase 8: Final Thesis & Defense Demonstration", "Weeks 19 – 20", "Comprehensive report, conference paper, final viva", "PENDING")
    ]

    for r_idx, (act, time_span, deliv, stat) in enumerate(gantt_rows, start=1):
        bg = COLOR_WHITE if r_idx % 2 != 0 else COLOR_CARD_BG
        for c_idx, val in enumerate([act, time_span, deliv, stat]):
            cell = tbl11.cell(r_idx, c_idx)
            cell.fill.solid()
            cell.fill.fore_color.rgb = bg
            p = cell.text_frame.paragraphs[0]
            p.text = val
            p.font.name = "Arial"
            p.font.size = Pt(9.5)
            if c_idx == 0:
                p.font.bold = True
                p.font.color.rgb = COLOR_DARK
            elif c_idx == 3:
                p.font.bold = True
                if val == "COMPLETED":
                    p.font.color.rgb = COLOR_GREEN
                elif val == "IN PROGRESS":
                    p.font.color.rgb = COLOR_BLUE
                else:
                    p.font.color.rgb = COLOR_AMBER
            else:
                p.font.color.rgb = COLOR_TEXT

    add_footer(slide11, 11)

    # =========================================================================
    # SLIDE 12: References
    # =========================================================================
    slide12 = prs.slides.add_slide(blank_layout)
    add_header(slide12, "References", "Academic Literature, Biomedical Standards & Core Frameworks")

    col_w = Inches(5.7)
    col_h = Inches(5.1)
    col_y = Inches(1.45)

    # Left Column: References 1-6
    add_card(slide12, Inches(0.8), col_y, col_w, col_h, COLOR_WHITE, COLOR_CARD_BORDER)
    box_r1 = slide12.shapes.add_textbox(Inches(1.0), col_y + Inches(0.15), col_w - Inches(0.4), col_h - Inches(0.3))
    tf_r1 = box_r1.text_frame
    tf_r1.word_wrap = True

    refs_left = [
        "[1] A. Radford, J. W. Kim, T. Xu, G. Brockman, C. McLeavey, and I. Sutskever, 'Robust Speech Recognition via Large-Scale Weak Supervision,' OpenAI Technical Report, 2022.",
        "[2] H. Touvron, L. Martin, K. Stone, P. Albert, et al., 'LLaMA: Open and Efficient Foundation Language Models,' arXiv:2302.13971, 2023.",
        "[3] P. Rashidi and A. Mihailidis, 'A Survey on Ambient-Assisted Living Tools for Older Adults,' IEEE Transactions on Biomedical Engineering, vol. 60, no. 3, pp. 679-688, 2013.",
        "[4] T. Tamura, Y. Maeda, M. Sekine, and M. Yoshida, 'Wearable Photoplethysmographic Sensors—Past and Present,' Electronics, vol. 3, no. 2, pp. 282-302, 2014.",
        "[5] S. Gerke, T. Minssen, and G. Cohen, 'Ethical and Legal Challenges of Artificial Intelligence-Driven Healthcare,' Artificial Intelligence in Healthcare, pp. 295-336, Academic Press, 2020.",
        "[6] S. Haber and W. S. Stornetta, 'How to Time-Stamp a Digital Document,' Journal of Cryptology, vol. 3, no. 2, pp. 99-111, 1991."
    ]

    for idx, ref in enumerate(refs_left):
        p = tf_r1.paragraphs[0] if idx == 0 else tf_r1.add_paragraph()
        p.text = ref
        p.font.name = "Arial"
        p.font.size = Pt(8.5)
        p.font.color.rgb = COLOR_TEXT
        p.space_before = Pt(8)

    # Right Column: References 7-12
    add_card(slide12, Inches(6.833), col_y, col_w, col_h, COLOR_WHITE, COLOR_CARD_BORDER)
    box_r2 = slide12.shapes.add_textbox(Inches(7.033), col_y + Inches(0.15), col_w - Inches(0.4), col_h - Inches(0.3))
    tf_r2 = box_r2.text_frame
    tf_r2.word_wrap = True

    refs_right = [
        "[7] C. Dwork and A. Roth, 'The Algorithmic Foundations of Differential Privacy,' Foundations and Trends in Theoretical Computer Science, vol. 9, no. 3-4, pp. 211-407, 2014.",
        "[8] World Health Organization, 'Regulatory Considerations on Artificial Intelligence for Health,' WHO Health Guidance Document, Geneva, 2023.",
        "[9] ISO/IEEE 11073-10408:2020, 'Health Informatics—Personal Health Device Communication—Device Specialization: Thermometer,' IEEE Standards Association, 2020.",
        "[10] ISO/IEEE 11073-10404:2020, 'Health Informatics—Personal Health Device Communication—Device Specialization: Pulse Oximeter,' IEEE Standards Association, 2020.",
        "[11] A. Q. Jiang, A. Sablayrolles, A. Mensch, C. Bamford, et al., 'Mistral 7B,' arXiv:2310.06825, 2023.",
        "[12] J. Varghese, D. A. Joseph, and R. Paul, 'Edge Computing in Ambient Assisted Living: Architectures, Challenges, and Privacy Guarantees,' IEEE Access, vol. 9, pp. 78622-78652, 2021."
    ]

    for idx, ref in enumerate(refs_right):
        p = tf_r2.paragraphs[0] if idx == 0 else tf_r2.add_paragraph()
        p.text = ref
        p.font.name = "Arial"
        p.font.size = Pt(8.5)
        p.font.color.rgb = COLOR_TEXT
        p.space_before = Pt(8)

    add_footer(slide12, 12)

    # Save presentation
    prs.save(output_path)
    print(f"Presentation saved successfully to: {os.path.abspath(output_path)}")

if __name__ == "__main__":
    create_deck()
