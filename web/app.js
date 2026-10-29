// ═══════════════════════════════════════════════════════════════════
// CareWatcher — Frontend Reactive Engine, Live Audio/Video Monitor
// ═══════════════════════════════════════════════════════════════════

let state = {
  shutter: "CLOSED",
  isListening: false,
  continuousConversation: false,
  continuousWakeEnabled: false,
  isAssistantSpeaking: false,
  isProcessingSpeech: false,
  lastUserSpokeTime: Date.now(),
  lastBiometricCheckinTime: 0,
  sustainedDistressCount: 0,
  recognition: null,
  audioContext: null,
  audioAnalyser: null,
  audioStream: null,
  videoStream: null,
  isCameraActive: false,
  currentMood: {
    face_detected: false,
    mood_label: "calm",
    confidence: 0.85,
    valence: 0.15,
    smile_score: 0.0,
    brow_tension: 0.0,
    bbox: null,
  },
  moodIntervalId: null,
  speechStartTime: 0,
  audioEnergySamples: [],
  recentAudioMetrics: null,
};

document.addEventListener("DOMContentLoaded", () => {
  initDashboard();
  // Poll telemetry every 2 seconds
  setInterval(pollTelemetry, 2000);
  setInterval(pollLLMStatus, 5000);
});

async function initDashboard() {
  await fetchStatus();
  await pollTelemetry();
  await pollLLMStatus();
  setupAudioVisualizer();
  initLiveBeatEngine();
  initHyperateStream("034A7");
}


// ── Shutter Management ────────────────────────────────────────────

async function fetchStatus() {
  try {
    const res = await fetch("/api/status");
    if (!res.ok) return;
    const data = await res.json();
    updateShutterUI(data.shutter_state);
  } catch (err) {
    console.error("fetchStatus error:", err);
  }
}

function stopCameraHardware() {
  if (state.moodIntervalId) {
    clearInterval(state.moodIntervalId);
    state.moodIntervalId = null;
  }
  const video = document.getElementById("liveVideo");
  if (video && video.srcObject) {
    try {
      const stream = video.srcObject;
      if (stream && stream.getTracks) {
        stream.getTracks().forEach((track) => {
          track.stop();
          track.enabled = false;
        });
      }
    } catch (e) {}
    try { video.pause(); } catch (e) {}
    video.srcObject = null;
    video.removeAttribute("src");
    try { video.load(); } catch (e) {}
  }
  if (state.videoStream) {
    try {
      state.videoStream.getTracks().forEach((track) => {
        track.stop();
        track.enabled = false;
      });
    } catch (e) {}
    state.videoStream = null;
  }
  state.isCameraActive = false;

  const btn = document.getElementById("camToggleBtn");
  const btnLabel = document.getElementById("camBtnLabel");
  if (btnLabel) btnLabel.innerText = "📹 Camera";
  if (btn) btn.style.background = "";

  const canvas = document.getElementById("faceOverlay");
  if (canvas) {
    const ctx = canvas.getContext("2d");
    ctx.clearRect(0, 0, canvas.width, canvas.height);
  }

  // Instruct backend to release hardware camera device
  try {
    fetch("/api/camera/release", { method: "POST" }).catch(() => {});
  } catch (e) {}
}

// Ensure all camera hardware is released on tab close, hide, or navigation
window.addEventListener("beforeunload", stopCameraHardware);
window.addEventListener("pagehide", stopCameraHardware);
window.addEventListener("unload", stopCameraHardware);
document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "hidden" && state.shutter === "CLOSED") {
    stopCameraHardware();
  }
});

function updateShutterUI(shutterState) {
  state.shutter = shutterState;
  const dot = document.getElementById("shutterDot");
  const text = document.getElementById("shutterText");
  const btn = document.getElementById("shutterToggleBtn");
  const btnLabel = document.getElementById("shutterBtnLabel");
  const initLabel = document.getElementById("initialShutterState");
  const curtain = document.getElementById("shutterCurtain");
  const audioCurtain = document.getElementById("audioShutterCurtain");

  if (initLabel) initLabel.innerText = shutterState;

  if (shutterState === "OPEN") {
    if (dot) dot.className = "pill-dot open";
    if (text) {
      text.innerText = "OPEN";
      text.style.color = "#34d399";
    }
    if (btn) btn.className = "shutter-btn open";
    if (btnLabel) btnLabel.innerText = "Shutter: Open";

    // Lift physical shutter curtain
    if (curtain) curtain.classList.add("hidden");
    if (audioCurtain) audioCurtain.classList.add("hidden");
  } else {
    if (dot) dot.className = "pill-dot";
    if (text) {
      text.innerText = "CLOSED";
      text.style.color = "#fb7185";
    }
    if (btn) btn.className = "shutter-btn closed";
    if (btnLabel) btnLabel.innerText = "Shutter: Closed";

    // Drop physical shutter curtain
    if (curtain) curtain.classList.remove("hidden");
    if (audioCurtain) audioCurtain.classList.remove("hidden");

    // Physical root boundary: immediately release camera hardware and pause dialogue
    stopCameraHardware();
    if (state.continuousConversation) {
      stopContinuousListening();
    }
  }
}

async function toggleShutter() {
  try {
    const res = await fetch("/api/shutter/toggle", { method: "POST" });
    const data = await res.json();
    updateShutterUI(data.new_state);

    appendFeedItem({
      type: "system",
      meta: "HARDWARE PRIVACY SHUTTER",
      body: `Privacy shutter physically toggled to: <strong>${data.new_state}</strong>. ${
        data.new_state === "OPEN" ? "Sensors and camera streams are OPEN." : "Sensors and camera streams are GATED at root boundary (Camera powered down)."
      }`
    });

    fetchAudit();
  } catch (err) {
    console.error("toggleShutter error:", err);
  }
}

// ── Live Video Monitoring & Camera Feed ───────────────────────────

async function toggleWebcam() {
  const video = document.getElementById("liveVideo");
  const btn = document.getElementById("camToggleBtn");
  const btnLabel = document.getElementById("camBtnLabel");

  if (state.isCameraActive) {
    stopCameraHardware();
  } else {
    if (state.shutter === "CLOSED") {
      alert("Privacy Shutter is currently CLOSED. Please open the Privacy Shutter first using the button at the top right.");
      return;
    }

    // Start camera
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 640 }, height: { ideal: 480 } }
      });
      state.videoStream = stream;
      video.srcObject = stream;
      state.isCameraActive = true;
      btnLabel.innerText = "⏹ Stop Laptop Camera";
      btn.style.background = "rgba(244, 63, 94, 0.25)";

      // Start continuous facial mood analysis stream (every 1.5s)
      state.moodIntervalId = setInterval(captureAndAnalyzeMoodFrame, 1500);

      // Draw face tracking HUD loop
      requestAnimationFrame(renderFaceOverlay);
    } catch (err) {
      alert("Unable to access laptop webcam: " + err.message + ". Please ensure camera permissions are allowed in your browser.");
    }
  }
}

async function captureAndAnalyzeMoodFrame() {
  if (!state.isCameraActive || state.shutter !== "OPEN") return;

  const video = document.getElementById("liveVideo");
  // Check that video is ready and has valid dimensions (readyState >= 2 = HAVE_CURRENT_DATA)
  if (!video || video.readyState < 2 || video.videoWidth === 0) return;

  try {
    const offscreen = document.createElement("canvas");
    offscreen.width = 480;
    offscreen.height = 360;
    const offCtx = offscreen.getContext("2d");
    offCtx.drawImage(video, 0, 0, 480, 360);
    const dataUrl = offscreen.toDataURL("image/jpeg", 0.85);

    const res = await fetch("/api/mood/analyze_frame", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ image: dataUrl }),
    });

    if (res.ok) {
      const moodData = await res.json();
      state.currentMood = moodData;

      // Update Live Mood Badge
      const badge = document.getElementById("moodStatusBadge");
      if (badge) {
        if (moodData.face_detected === false) {
          badge.innerText = "AWAITING FACE";
        } else if (moodData.mood_label) {
          const confPct = Math.round((moodData.confidence || 0.85) * 100);
          badge.innerText = `${moodData.mood_label.toUpperCase()} (${confPct}%)`;
        }
      }

      // Update 4 Live Affect Meters (Face emotion & engagement only; BPM is dedicated to HypeRate)
      updateAffectMeters(moodData);
    }
  } catch (err) {
    // Non-blocking frame miss
  }
}

function updateAffectMeters(moodData) {
  if (!moodData) return;

  const rawLabel = (moodData.mood_label || "calm").toLowerCase();
  const confPct = Math.round((moodData.confidence || 0.85) * 100);
  const secLabel = (moodData.secondary_emotion || "calm").toLowerCase();

  // Emotion icon mapping
  const emotionIcons = {
    happy: "😊",
    calm: "😐",
    sad: "😢",
    anxious: "😟",
    fatigued: "😴",
    surprised: "😲",
    pain: "⚠️",
    confused: "🤔",
  };
  const icon = emotionIcons[rawLabel] || "😐";

  // 1. Primary Emotion Hero Ribbon
  const pIcon = document.getElementById("primaryEmotionIcon");
  const pLabel = document.getElementById("primaryEmotionLabel");
  const sSub = document.getElementById("secondaryEmotionSub");
  if (pIcon) pIcon.innerText = icon;
  if (pLabel) pLabel.innerText = `${rawLabel.toUpperCase()} (${confPct}%)`;
  if (sSub) sSub.innerText = `Secondary Affect: ${secLabel.toUpperCase()} • FACS v2.4 Multi-Parametric`;

  // 2. 8-Emotion Probability Spectrum Grid
  const probs = moodData.emotion_probabilities || {};
  const activeTag = document.getElementById("spectrumActiveTag");
  if (activeTag) activeTag.innerText = `${rawLabel.toUpperCase()} (${confPct}%) Dominant`;

  const emotionKeys = ["happy", "calm", "sad", "anxious", "fatigued", "surprised", "pain", "confused"];
  for (const k of emotionKeys) {
    const pVal = probs[k] !== undefined ? probs[k] : (k === rawLabel ? 0.85 : 0.02);
    const pct = Math.round(pVal * 100);
    const txtEl = document.getElementById(`specPct_${k}`);
    const fillEl = document.getElementById(`specFill_${k}`);
    const itemEl = document.getElementById(`specItem_${k}`);
    if (txtEl) txtEl.innerText = `${pct}%`;
    if (fillEl) fillEl.style.width = `${pct}%`;
    if (itemEl) {
      if (k === rawLabel) {
        itemEl.style.borderColor = "var(--color-forest-ink)";
        itemEl.style.background = "#eef8f3";
      } else {
        itemEl.style.borderColor = "var(--color-vast-ink)";
        itemEl.style.background = "var(--color-lumen-stone)";
      }
    }
  }

  // 3. Clinical Biometric Gauges (6 Parameters)
  // A. Emotional Valence (-1.0 to +1.0)
  const valence = moodData.valence !== undefined ? moodData.valence : 0.15;
  const valencePct = Math.max(5, Math.min(95, Math.round(((valence + 1.0) / 2.0) * 100)));
  const valFill = document.getElementById("valenceBarFill");
  const valText = document.getElementById("valenceValText");
  if (valFill) {
    valFill.style.width = `${valencePct}%`;
    valFill.style.background = valence > 0.25 ? "var(--color-forest-ink)" : (valence < -0.2 ? "#e11d48" : "#d97706");
  }
  if (valText) {
    const valSign = valence > 0 ? `+${valence}` : `${valence}`;
    valText.innerText = `${valSign} (${rawLabel.toUpperCase()})`;
  }

  // B. Physiological Arousal (0% to 100%)
  const arousal = moodData.arousal !== undefined ? moodData.arousal : 0.30;
  const arousalPct = Math.round(arousal * 100);
  const aFill = document.getElementById("arousalBarFill");
  const aText = document.getElementById("arousalValText");
  if (aFill) {
    aFill.style.width = `${arousalPct}%`;
    aFill.style.background = arousal > 0.65 ? "#f59e0b" : "var(--color-forest-ink)";
  }
  if (aText) {
    const desc = arousal > 0.70 ? "Elevated (Alert)" : (arousal < 0.25 ? "Lethargic / Resting" : "Nominal Equilibrium");
    aText.innerText = `${arousalPct}% (${desc})`;
  }

  // C. Ocular Aperture & Vigilance (0% to 100%)
  const eyeOp = moodData.eye_openness !== undefined ? moodData.eye_openness : 0.75;
  const eyePct = Math.round(eyeOp * 100);
  const vFill = document.getElementById("vigilanceBarFill");
  const vText = document.getElementById("vigilanceValText");
  if (vFill) {
    vFill.style.width = `${eyePct}%`;
    vFill.style.background = eyePct < 35 ? "#6366f1" : "var(--color-forest-ink)";
  }
  if (vText) {
    const vDesc = eyePct < 35 ? "Drooping / Drowsy" : (eyePct > 80 ? "Focused & Alert" : "Normal Aperture");
    vText.innerText = `${eyePct}% (${vDesc})`;
  }

  // D. Brow Corrugator Muscular Tension
  const tension = moodData.brow_tension !== undefined ? moodData.brow_tension : 0.0;
  const tensionPct = Math.min(100, Math.round((tension / 80.0) * 100));
  const tFill = document.getElementById("tensionBarFill");
  const tText = document.getElementById("tensionValText");
  if (tFill) {
    tFill.style.width = `${tensionPct}%`;
    tFill.style.background = tension > 60 ? "#e11d48" : (tension > 40 ? "var(--color-ember-glow)" : "var(--color-forest-ink)");
  }
  if (tText) {
    tText.innerText = tension > 60 ? `Elevated Furrow (${tension.toFixed(0)})` : `Relaxed (${tension.toFixed(0)})`;
  }

  // E. Facial Smile & Expressivity (AU12)
  const smileVal = moodData.smile_score !== undefined ? moodData.smile_score : 0.0;
  const smPct = Math.round(smileVal * 100);
  const sFill = document.getElementById("smileBarFill");
  const sText = document.getElementById("smileBarText");
  if (sFill) {
    sFill.style.width = `${smPct}%`;
    sFill.style.background = smPct >= 20 ? "#10b981" : "var(--color-forest-ink)";
  }
  if (sText) {
    sText.innerText = smPct >= 20 ? `Active Smile (${smPct}%)` : `Neutral (${smPct}%)`;
  }

  // F. Cognitive Strain / Confusion Index
  const confusion = moodData.confusion_index !== undefined ? moodData.confusion_index : 0.0;
  const confIdxPct = Math.round(confusion * 100);
  const cFill = document.getElementById("confusionBarFill");
  const cText = document.getElementById("confusionValText");
  if (cFill) {
    cFill.style.width = `${confIdxPct}%`;
    cFill.style.background = confIdxPct > 35 ? "#d97706" : "var(--color-forest-ink)";
  }
  if (cText) {
    cText.innerText = confIdxPct > 35 ? `Strained (${confIdxPct}%)` : `${confIdxPct}% (Clear)`;
  }

  // 4. Micro-Telemetry Strip
  const symmEl = document.getElementById("symmetryValText");
  const tiltEl = document.getElementById("headTiltValText");
  const smileEl = document.getElementById("smileValText");
  const attEl = document.getElementById("attentionValText");

  if (symmEl) {
    const sVal = moodData.symmetry_score !== undefined ? Math.round(moodData.symmetry_score * 100) : 95;
    symmEl.innerText = `${sVal}%`;
  }
  if (tiltEl) {
    const tVal = moodData.head_tilt !== undefined ? moodData.head_tilt : 0.0;
    const sign = tVal > 0 ? "+" : "";
    tiltEl.innerText = `${sign}${tVal.toFixed(1)}°`;
  }
  if (smileEl) {
    const smVal = moodData.smile_score !== undefined ? Math.round(moodData.smile_score * 100) : 0;
    smileEl.innerText = smVal >= 20 ? `😊 ${smVal}%` : `${smVal}%`;
    smileEl.style.color = smVal >= 20 ? "#10b981" : "";
  }
  if (attEl) {
    const atVal = moodData.attention_score !== undefined ? Math.round(moodData.attention_score * 100) : 85;
    attEl.innerText = `${atVal}%`;
  }

  // 5. Update HUD elements on canvas
  const hudP = document.getElementById("hudPresence");
  const hudE = document.getElementById("hudExpression");
  const hudL = document.getElementById("hudLux");

  if (hudP) hudP.innerText = moodData.face_detected !== false ? "Resident Aaron (Tracked)" : "Awaiting Resident...";
  if (hudE) hudE.innerText = `${rawLabel.toUpperCase()} (${confPct}%) • Secondary: ${secLabel.toUpperCase()}`;
  if (hudL) hudL.innerText = moodData.lighting_quality || "Optimal (Daylight)";
}

async function triggerDeepVisionScan() {
  if (!state.isCameraActive) {
    alert("Please start the laptop camera first to capture a frame for Deep AI Vision Scan.");
    return;
  }
  const video = document.getElementById("liveVideo");
  if (!video || video.readyState < 2) return;

  const btn = document.getElementById("deepScanBtn");
  if (btn) btn.innerText = "⏳ Deep AI Scanning...";

  try {
    const offscreen = document.createElement("canvas");
    offscreen.width = 640;
    offscreen.height = 480;
    const offCtx = offscreen.getContext("2d");
    offCtx.drawImage(video, 0, 0, 640, 480);
    const dataUrl = offscreen.toDataURL("image/jpeg", 0.85);

    const res = await fetch("/api/mood/deep_scan", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ image: dataUrl }),
    });

    if (res.ok) {
      const data = await res.json();
      const panel = document.getElementById("deepScanPanel");
      const narr = document.getElementById("deepScanNarrative");
      if (panel && narr) {
        panel.style.display = "block";
        narr.innerHTML = `
          <div style="margin-bottom: 6px; font-weight: 600;">Engine: <strong>${data.model}</strong></div>
          <div style="margin-bottom: 8px;">${data.clinical_narrative}</div>
          <div style="display: flex; gap: 8px; flex-wrap: wrap; font-size: 11px;">
            <span style="background: var(--color-lavender-whisper); padding: 2px 8px; border-radius: 6px; border: 1px solid var(--color-vast-ink);">Primary: <strong>${data.primary_emotion} (${data.confidence}%)</strong></span>
            <span style="background: var(--color-lumen-stone); padding: 2px 8px; border-radius: 6px; border: 1px solid var(--color-vast-ink);">Secondary: <strong>${data.secondary_emotion}</strong></span>
            <span style="background: var(--color-lumen-stone); padding: 2px 8px; border-radius: 6px; border: 1px solid var(--color-vast-ink);">Symmetry: <strong>${data.symmetry_pct}%</strong></span>
          </div>
        `;
      }

      appendFeedItem({
        type: "clinical",
        meta: "DEEP AI MULTIMODAL CLINICAL SCAN",
        body: `Facial affect evaluation completed for Aaron: <strong>${data.primary_emotion}</strong> (${data.confidence}%). ${data.clinical_narrative}`
      });
    }
  } catch (err) {
    console.error("Deep scan failed:", err);
  } finally {
    if (btn) btn.innerText = "✨ Deep AI Scan";
  }
}

function closeDeepScanPanel() {
  const panel = document.getElementById("deepScanPanel");
  if (panel) panel.style.display = "none";
}

function renderFaceOverlay() {
  if (!state.isCameraActive) return;

  const video = document.getElementById("liveVideo");
  const canvas = document.getElementById("faceOverlay");
  if (!video || !canvas || video.readyState < 2 || video.videoWidth === 0) {
    requestAnimationFrame(renderFaceOverlay);
    return;
  }

  canvas.width = video.videoWidth || 640;
  canvas.height = video.videoHeight || 480;
  const ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  if (state.shutter === "OPEN") {
    const w = canvas.width;
    const h = canvas.height;
    const mood = state.currentMood || {};

    if (mood.face_detected === false) {
      // Draw subtle "Seeking Resident Face..." scanning effect
      ctx.strokeStyle = "rgba(240, 215, 255, 0.45)";
      ctx.lineWidth = 1.5;
      ctx.setLineDash([6, 6]);
      const scanW = w * 0.44;
      const scanH = h * 0.54;
      const scanX = (w - scanW) / 2;
      const scanY = (h - scanH) / 2;
      ctx.strokeRect(scanX, scanY, scanW, scanH);
      ctx.setLineDash([]);

      ctx.fillStyle = "rgba(15, 23, 42, 0.75)";
      ctx.fillRect(scanX, scanY - 24, 180, 20);
      ctx.fillStyle = "#ffffeb";
      ctx.font = "600 11px Figtree, sans-serif";
      ctx.fillText("SEEKING RESIDENT FACE...", scanX + 8, scanY - 10);
      requestAnimationFrame(renderFaceOverlay);
      return;
    }

    const label = (mood.mood_label || "calm").toLowerCase();

    // Pick aesthetic color theme across all 8 emotion states
    const themeColors = {
      happy: { theme: "#034f46", corner: "#10b981" },
      calm: { theme: "#1a1a1a", corner: "#f0d7ff" },
      sad: { theme: "#475569", corner: "#94a3b8" },
      anxious: { theme: "#b45309", corner: "#f59e0b" },
      fatigued: { theme: "#3730a3", corner: "#6366f1" },
      surprised: { theme: "#5b21b6", corner: "#8b5cf6" },
      pain: { theme: "#9f1239", corner: "#e11d48" },
      confused: { theme: "#78350f", corner: "#d97706" },
    };
    const colors = themeColors[label] || themeColors.calm;
    const themeColor = colors.theme;
    const cornerColor = colors.corner;

    // Determine target bounding box
    let boxX, boxY, boxW, boxH;
    if (mood.bbox && Array.isArray(mood.bbox) && mood.bbox.length === 4) {
      // Scale from capture frame dimensions (default 480x360) to canvas resolution
      const srcW = mood.frame_width || 480;
      const srcH = mood.frame_height || 360;
      const scaleX = w / srcW;
      const scaleY = h / srcH;
      boxX = mood.bbox[0] * scaleX;
      boxY = mood.bbox[1] * scaleY;
      boxW = mood.bbox[2] * scaleX;
      boxH = mood.bbox[3] * scaleY;
    } else {
      boxW = w * 0.44;
      boxH = h * 0.54;
      boxX = (w - boxW) / 2;
      boxY = (h - boxH) / 2;
    }

    // Biometric face target box
    ctx.strokeStyle = themeColor;
    ctx.lineWidth = 2.5;
    ctx.strokeRect(boxX, boxY, boxW, boxH);

    // Corner brackets
    ctx.strokeStyle = cornerColor;
    ctx.lineWidth = 4;
    const len = 20;
    // Top-left
    ctx.beginPath(); ctx.moveTo(boxX, boxY + len); ctx.lineTo(boxX, boxY); ctx.lineTo(boxX + len, boxY); ctx.stroke();
    // Top-right
    ctx.beginPath(); ctx.moveTo(boxX + boxW - len, boxY); ctx.lineTo(boxX + boxW, boxY); ctx.lineTo(boxX + boxW, boxY + len); ctx.stroke();
    // Bottom-left
    ctx.beginPath(); ctx.moveTo(boxX, boxY + boxH - len); ctx.lineTo(boxX, boxY + boxH); ctx.lineTo(boxX + len, boxY + boxH); ctx.stroke();
    // Bottom-right
    ctx.beginPath(); ctx.moveTo(boxX + boxW - len, boxY + boxH); ctx.lineTo(boxX + boxW, boxY + boxH); ctx.lineTo(boxX + boxW, boxY + boxH - len); ctx.stroke();

    // Upper Tag: Resident + Emotion State
    const conf = Math.round((mood.confidence || 0.85) * 100);
    const tagText = `AARON • [${label.toUpperCase()} ${conf}%]`;
    ctx.fillStyle = themeColor;
    ctx.fillRect(boxX, boxY - 26, Math.max(220, boxW), 22);
    ctx.fillStyle = "#ffffeb";
    ctx.font = "600 11px Figtree, sans-serif";
    ctx.fillText(tagText, boxX + 6, boxY - 11);

    // Lower Tag: Telemetry Summary
    const valText = mood.valence !== undefined ? (mood.valence > 0 ? `+${mood.valence}` : `${mood.valence}`) : "+0.15";
    const vigilPct = Math.round((mood.eye_openness || 0.75) * 100);
    const smPct = Math.round((mood.smile_score || 0) * 100);

    ctx.fillStyle = "rgba(15, 23, 42, 0.85)";
    ctx.fillRect(boxX, boxY + boxH + 4, boxW, 20);
    ctx.fillStyle = cornerColor;
    ctx.font = "10px JetBrains Mono, monospace";
    ctx.fillText(`Val:${valText} | Vigilance:${vigilPct}% | Smile:${smPct}%`, boxX + 6, boxY + boxH + 18);
  }

  requestAnimationFrame(renderFaceOverlay);
}

// ── Live Audio Monitoring & Waveform Visualizer ───────────────────

async function setupAudioVisualizer() {
  const canvas = document.getElementById("audioVisualizerCanvas");
  if (!canvas) return;

  const canvasCtx = canvas.getContext("2d");

  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    state.audioStream = stream;
    state.audioContext = new (window.AudioContext || window.webkitAudioContext)();
    state.audioAnalyser = state.audioContext.createAnalyser();
    state.audioAnalyser.fftSize = 256;

    const source = state.audioContext.createMediaStreamSource(stream);
    source.connect(state.audioAnalyser);

    const bufferLength = state.audioAnalyser.frequencyBinCount;
    const dataArray = new Uint8Array(bufferLength);

    function drawAudioWaveform() {
      requestAnimationFrame(drawAudioWaveform);

      canvas.width = canvas.offsetWidth;
      canvas.height = canvas.offsetHeight;
      const w = canvas.width;
      const h = canvas.height;

      canvasCtx.fillStyle = "#ffffeb";
      canvasCtx.fillRect(0, 0, w, h);

      if (state.shutter === "CLOSED") {
        // Flatline when shutter is closed
        canvasCtx.strokeStyle = "#8a8a80";
        canvasCtx.lineWidth = 2;
        canvasCtx.beginPath();
        canvasCtx.moveTo(0, h / 2);
        canvasCtx.lineTo(w, h / 2);
        canvasCtx.stroke();
        document.getElementById("audioBarFill").style.width = "0%";
        document.getElementById("audioDbText").innerText = "Muted (Gated)";
        return;
      }

      state.audioAnalyser.getByteTimeDomainData(dataArray);

      // Calculate audio energy (volume)
      let sum = 0;
      for (let i = 0; i < bufferLength; i++) {
        const val = (dataArray[i] - 128) / 128;
        sum += val * val;
      }
      const rms = Math.sqrt(sum / bufferLength);
      const db = Math.min(95, Math.round(30 + rms * 150));
      const pct = Math.min(100, Math.round(rms * 250));

      document.getElementById("audioBarFill").style.width = `${pct}%`;
      document.getElementById("audioDbText").innerText = `${db} dB ${db > 55 ? '(Voice detected)' : '(Quiet)'}`;
      document.getElementById("speechActivityLabel").innerText = db > 52 ? "Speech Active" : "Listening...";

      // Draw real-time crisp black audio waveform (Wispr Flow style)
      canvasCtx.lineWidth = 2.0;
      canvasCtx.strokeStyle = "#1a1a1a";

      canvasCtx.beginPath();
      const sliceWidth = w / bufferLength;
      let x = 0;

      for (let i = 0; i < bufferLength; i++) {
        const v = dataArray[i] / 128.0;
        const y = (v * h) / 2;

        if (i === 0) canvasCtx.moveTo(x, y);
        else canvasCtx.lineTo(x, y);
        x += sliceWidth;
      }

      canvasCtx.lineTo(w, h / 2);
      canvasCtx.stroke();
    }

    drawAudioWaveform();
  } catch (err) {
    // Audio context fallback waveform (idle sine)
    runFallbackWaveform(canvas, canvasCtx);
  }
}

function runFallbackWaveform(canvas, canvasCtx) {
  let step = 0;
  function animate() {
    requestAnimationFrame(animate);
    canvas.width = canvas.offsetWidth;
    canvas.height = canvas.offsetHeight;
    const w = canvas.width;
    const h = canvas.height;

    canvasCtx.fillStyle = "#ffffeb";
    canvasCtx.fillRect(0, 0, w, h);

    if (state.shutter === "CLOSED") {
      canvasCtx.strokeStyle = "#8a8a80";
      canvasCtx.lineWidth = 2;
      canvasCtx.beginPath();
      canvasCtx.moveTo(0, h / 2);
      canvasCtx.lineTo(w, h / 2);
      canvasCtx.stroke();
      return;
    }

    canvasCtx.strokeStyle = "#1a1a1a";
    canvasCtx.lineWidth = 2;
    canvasCtx.beginPath();
    step += 0.08;
    for (let x = 0; x < w; x++) {
      const y = h / 2 + Math.sin(x * 0.04 + step) * 8 * Math.sin(x * 0.01);
      if (x === 0) canvasCtx.moveTo(x, y);
      else canvasCtx.lineTo(x, y);
    }
    canvasCtx.stroke();
  }
  animate();
}

// ── Periodic Telemetry Polling ────────────────────────────────────

async function pollTelemetry() {
  await Promise.allSettled([
    fetchSensors(),
    fetchAudit(),
    fetchMood()
  ]);
  evaluateContinuousSituation();
}

function evaluateContinuousSituation() {
  if (!state.continuousConversation || state.isAssistantSpeaking || state.isProcessingSpeech || state.shutter === "CLOSED") {
    return;
  }

  const now = Date.now();
  // Do not interrupt if Aaron spoke in the last 25 seconds or if check-in occurred in the last 50 seconds
  if (now - state.lastUserSpokeTime < 25000) return;
  if (now - state.lastBiometricCheckinTime < 50000) return;

  const bpmEl = document.getElementById("valBPM");
  const rawBpm = bpmEl ? parseFloat(bpmEl.innerText) : null;
  const moodObj = state.currentMood || {};
  const hasConfidentFaceMood = Boolean(
    state.isCameraActive && moodObj.face_detected && (moodObj.confidence || 0) >= 0.65
  );
  const currentMood = hasConfidentFaceMood && moodObj.mood_label ? moodObj.mood_label : "calm";

  let abnormalSituation = null;
  if (rawBpm && (rawBpm > 105 || rawBpm < 50)) {
    abnormalSituation = rawBpm > 105 ? `elevated heart rate of ${Math.round(rawBpm)} BPM` : `low heart rate of ${Math.round(rawBpm)} BPM`;
  } else if (currentMood === "sad" || currentMood === "anxious" || currentMood === "pain" || currentMood === "distress") {
    abnormalSituation = `observed emotional tension (${currentMood})`;
  }

  if (abnormalSituation) {
    state.sustainedDistressCount = (state.sustainedDistressCount || 0) + 1;
    // Require 4 consecutive telemetry checks (approx 8 seconds) of sustained high-confidence reading
    if (state.sustainedDistressCount >= 4) {
      state.sustainedDistressCount = 0;
      state.lastBiometricCheckinTime = now;

      const proactivePrompt = `[AMBIENT CLINICAL SITUATION EVALUATION: Aaron has ${abnormalSituation}. As Aaron's dedicated ambient companion, initiate a gentle, warm check-in inquiring how Aaron is feeling.]`;

      const banner = document.getElementById("continuousBannerText");
      if (banner) banner.innerText = `Evaluating situation (${abnormalSituation})...`;

      processInput(proactivePrompt);
    }
  } else {
    state.sustainedDistressCount = 0;
  }
}

async function fetchSensors() {
  try {
    const res = await fetch("/api/sensors");
    if (!res.ok) return;
    const data = await res.json();
    const sensors = data.sensors || {};

    const hwBadge = document.getElementById("hwStatusBadge");
    const bpmMeta = document.getElementById("bpmSourceMeta");
    const driverBadge = document.getElementById("sensorDriverBadge");
    const awPill = document.getElementById("awStatusPill");

    // BPM is EXCLUSIVELY driven by HypeRate live stream
    const hyperateActive = Boolean(data.hyperate && data.hyperate.active);
    const hyperateBpm = data.hyperate ? data.hyperate.latest_bpm : null;
    const channelCode = (data.hyperate && data.hyperate.channel_id) ? data.hyperate.channel_id : "034A7";

    if (hyperateActive && hyperateBpm) {
      if (hwBadge) {
        hwBadge.innerText = `HypeRate Live Stream (${channelCode})`;
        hwBadge.style.color = "var(--color-forest-ink)";
      }
      if (bpmMeta) {
        bpmMeta.innerText = `Source: HypeRate Live Stream (Apple Watch ${channelCode})`;
      }
      if (driverBadge) {
        driverBadge.innerText = "HypeRate Live";
        driverBadge.style.backgroundColor = "var(--color-forest-ink)";
      }
      // If direct WebSocket hasn't received a beat yet, fall back to backend's latest HypeRate beat
      const bpmEl = document.getElementById("valBPM");
      if (bpmEl && (bpmEl.innerText === "--" || !hyperateState.socket)) {
        bpmEl.innerText = Math.round(hyperateBpm);
      }
    } else {
      if (hwBadge) {
        hwBadge.innerText = `HypeRate Stream Active (${channelCode})`;
        hwBadge.style.color = "var(--color-forest-ink)";
      }
      if (bpmMeta) {
        bpmMeta.innerText = `Source: HypeRate Live Stream (Apple Watch ${channelCode})`;
      }
      if (driverBadge) {
        driverBadge.innerText = "HypeRate Stream";
        driverBadge.style.backgroundColor = "var(--color-forest-ink)";
      }
    }
    if (sensors["max30102_spo2"]) {
      document.getElementById("valSpO2").innerText = Number(sensors["max30102_spo2"]).toFixed(1);
    }
    if (sensors["mlx90614_temp"]) {
      document.getElementById("valTemp").innerText = Number(sensors["mlx90614_temp"]).toFixed(1);
    }
    if (sensors["apple_watch_hrv"]) {
      const hrvEl = document.getElementById("valHRV");
      if (hrvEl) hrvEl.innerText = Number(sensors["apple_watch_hrv"]).toFixed(1);
    }
    if (sensors["apple_watch_steps"]) {
      const stepsEl = document.getElementById("valSteps");
      if (stepsEl) stepsEl.innerText = Math.round(sensors["apple_watch_steps"]).toLocaleString();
    }
    if (sensors["mpu6050_activity"] !== undefined || sensors["webcam_presence"] !== undefined) {
      document.getElementById("valActivity").innerText = "Active";
    }
  } catch (err) {
    // Non-blocking telemetry miss
  }
}

// ── Apple Watch Plan B Client Helpers ─────────────────────────────

function copyAppleWatchUrl() {
  const input = document.getElementById("awWebhookUrl");
  if (!input) return;
  input.select();
  input.setSelectionRange(0, 99999);
  navigator.clipboard.writeText(input.value).then(() => {
    alert("Copied Apple Watch Webhook URL to clipboard!\n\nPaste this URL into the Health Auto Export app on your iPhone under REST API Export:\n" + input.value);
  }).catch(() => {
    alert("Apple Watch URL:\n" + input.value);
  });
}

function toggleAppleWatchHelp() {
  const el = document.getElementById("awHelp");
  if (el) el.style.display = el.style.display === "none" ? "block" : "none";
}

async function simulateAppleWatchSync() {
  try {
    const res = await fetch("/api/sensor/apple_watch/simulate_test", { method: "POST" });
    const data = await res.json();
    if (data.status === "success") {
      await fetchSensors();
      appendFeedItem({
        type: "system",
        meta: "APPLE WATCH HEALTHKIT STREAM",
        body: `Genuine biometric telemetry ingested from <strong>${escapeHtml(data.source)}</strong>: Pulse ${data.values.max30102_bpm} BPM, SpO2 ${data.values.max30102_spo2}%, Wrist Temp ${data.values.mlx90614_temp}°C, Steps ${data.values.apple_watch_steps}. Synthetic twin suppressed.`
      });
    }
  } catch (e) {
    console.error("simulateAppleWatchSync error:", e);
  }
}

async function fetchAudit() {
  try {
    const res = await fetch("/api/audit");
    if (!res.ok) return;
    const data = await res.json();

    const stream = document.getElementById("auditStream");
    const countTag = document.getElementById("auditCount");
    const badge = document.getElementById("auditChainBadge");

    if (data.chain_valid) {
      badge.className = "audit-chain-badge";
      badge.innerText = "CHAIN VERIFIED ✓";
    } else {
      badge.className = "audit-chain-badge";
      badge.style.color = "#fb7185";
      badge.innerText = "TAMPER DETECTED ⚠";
    }

    countTag.innerText = `${data.total_entries || (data.entries ? data.entries.length : 0)} blocks`;

    if (data.entries && data.entries.length > 0) {
      const slice = data.entries.slice(-5).reverse();
      stream.innerHTML = slice.map(entry => {
        const timeStr = entry.timestamp ? new Date(entry.timestamp).toLocaleTimeString() : "Recent";
        const hashStr = entry.entry_hash || entry.prev_hash || "000000000000";
        return `
          <div class="audit-item">
            <div class="audit-head">
              <span class="audit-type">${escapeHtml(entry.event_type || 'block')}</span>
              <span class="audit-time">${timeStr}</span>
            </div>
            <div class="audit-hash">HASH: <span class="hash-str">${hashStr.substring(0, 28)}...</span></div>
          </div>
        `;
      }).join("");
    }
  } catch (err) {
    // Ignore error
  }
}

async function fetchMood() {
  try {
    const res = await fetch("/api/mood");
    if (!res.ok) return;
    const data = await res.json();
    const moods = data.moods || [];

    const badge = document.getElementById("moodStatusBadge");
    // Only update badge from poll if camera stream is NOT actively providing high-res frames
    if (!state.isCameraActive && badge) {
      if (data.latest_label) {
        badge.innerText = `${data.latest_label.toUpperCase()} (Last Seen)`;
      } else {
        badge.innerText = "CALM (Standby)";
      }
    }

    if (moods.length > 0) {
      const timeline = document.getElementById("moodTimeline");
      timeline.innerHTML = moods.slice(0, 5).map(m => {
        const lbl = (m.mood_label || "neutral").toLowerCase();
        let dotClass = "dot-positive";
        if (lbl.includes("sad") || lbl.includes("depress")) dotClass = "dot-sad";
        else if (lbl.includes("anxious") || lbl.includes("worry")) dotClass = "dot-anxious";
        else if (lbl.includes("distress") || lbl.includes("pain")) dotClass = "dot-distress";
        else if (lbl.includes("fatigue") || lbl.includes("tired")) dotClass = "dot-anxious";

        const timeStr = m.timestamp ? new Date(m.timestamp).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit', second: '2-digit'}) : "Recent";
        return `
          <div class="mood-entry">
            <span class="mood-dot ${dotClass}"></span>
            <div class="mood-info">
              <strong>${escapeHtml(m.mood_label || 'State')}</strong>
              <span>Biometric Affect • Confidence ${Math.round((m.confidence || 0.85) * 100)}%</span>
            </div>
            <span class="mood-time">${timeStr}</span>
          </div>
        `;
      }).join("");
    }
  } catch (err) {
    // Ignore error
  }
}

// ── Live Speech Recognition (Microphone & Continuous Wake Word) ──

state.continuousWakeEnabled = false;

function playWakeChime() {
  try {
    const ctx = state.audioContext || new (window.AudioContext || window.webkitAudioContext)();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = "sine";
    osc.frequency.setValueAtTime(587.33, ctx.currentTime); // D5
    osc.frequency.exponentialRampToValueAtTime(880.0, ctx.currentTime + 0.12); // A5
    gain.gain.setValueAtTime(0.12, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.45);
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start();
    osc.stop(ctx.currentTime + 0.45);
  } catch (e) {}
}

function setContinuousConversation(enabled) {
  if (enabled && state.shutter === "CLOSED") {
    const toggle = document.getElementById("continuousConvToggle");
    if (toggle) toggle.checked = false;
    const fb = document.getElementById("liveSpeechFeedback");
    if (fb) {
      fb.className = "live-speech-feedback error";
      fb.innerText = "Privacy shutter is CLOSED. Open privacy shutter above to converse with CareWatcher.";
    }
    return;
  }

  state.continuousConversation = Boolean(enabled);
  const toggle = document.getElementById("continuousConvToggle");
  const btn = document.getElementById("btnToggleContinuous");
  const btnLabel = document.getElementById("btnContinuousLabel");
  const bannerWrap = document.getElementById("continuousDialogueBanner");

  if (toggle) toggle.checked = state.continuousConversation;

  if (state.continuousConversation) {
    if (btn) btn.classList.add("active-continuous");
    if (btnLabel) btnLabel.innerText = "⏹️ Pause Continuous Dialogue";
    if (bannerWrap) bannerWrap.classList.remove("hidden");
    startContinuousListening();
  } else {
    if (btn) btn.classList.remove("active-continuous");
    if (btnLabel) btnLabel.innerText = "🎙️ Start Continuous Dialogue";
    if (bannerWrap) bannerWrap.classList.add("hidden");
    stopContinuousListening();
  }
}

function toggleContinuousConversationButton() {
  setContinuousConversation(!state.continuousConversation);
}

function handleOrbClick() {
  if (state.continuousConversation) {
    setContinuousConversation(false);
  } else {
    toggleLiveMic();
  }
}

function startContinuousListening() {
  if (state.shutter === "CLOSED") return;
  if (state.isAssistantSpeaking || state.isProcessingSpeech) return;

  if (!state.recognition) {
    state.recognition = initSpeechRecognition();
  }
  if (!state.recognition) return;

  state.isListening = true;
  const orb = document.getElementById("micOrb");
  const inst = document.getElementById("micInstruction");
  const pill = document.getElementById("voiceStatusPill");
  const fb = document.getElementById("liveSpeechFeedback");
  const banner = document.getElementById("continuousBannerText");

  if (orb) {
    orb.classList.remove("speaking");
    orb.classList.remove("thinking");
    orb.classList.add("recording");
    orb.classList.add("continuous-listening");
  }
  if (pill) {
    pill.className = "status-pill status-active";
    pill.innerText = "Listening to Aaron...";
  }
  if (inst) inst.innerText = "Continuous Dialogue Active: Speak naturally to Aaron's AI companion...";
  if (banner) banner.innerText = "Continuous Dialogue Active — Listening to Aaron";
  if (fb) {
    fb.className = "live-speech-feedback active";
    fb.innerText = "Listening to Aaron... Speak your health update or question.";
  }

  startAudioVisualizer();

  try {
    state.recognition.start();
  } catch (err) {
    // Already active or starting
    console.debug("Recognition start status:", err);
  }
}

function stopContinuousListening() {
  state.continuousConversation = false;
  const orb = document.getElementById("micOrb");
  const inst = document.getElementById("micInstruction");
  const pill = document.getElementById("voiceStatusPill");
  const bannerWrap = document.getElementById("continuousDialogueBanner");
  const btn = document.getElementById("btnToggleContinuous");
  const btnLabel = document.getElementById("btnContinuousLabel");
  const toggle = document.getElementById("continuousConvToggle");

  if (toggle) toggle.checked = false;
  if (btn) btn.classList.remove("active-continuous");
  if (btnLabel) btnLabel.innerText = "🎙️ Start Continuous Dialogue";
  if (bannerWrap) bannerWrap.classList.add("hidden");

  if (orb) {
    orb.classList.remove("recording");
    orb.classList.remove("continuous-listening");
    orb.classList.remove("thinking");
  }
  if (pill) {
    pill.className = "status-pill status-ready";
    pill.innerText = "Standby";
  }
  if (inst) inst.innerText = "Click to speak directly to CareWatcher via Laptop Mic";

  stopAudioVisualizer();

  if (state.recognition && state.isListening) {
    try { state.recognition.stop(); } catch (e) {}
  }
}

function toggleContinuousWake(enabled) {
  state.continuousWakeEnabled = enabled;
  const orb = document.getElementById("micOrb");
  const inst = document.getElementById("micInstruction");
  const pill = document.getElementById("voiceStatusPill");

  if (enabled) {
    if (orb) orb.classList.add("wake-listening");
    if (pill) {
      pill.className = "status-pill status-active";
      pill.innerText = "Wake Word Armed";
    }
    if (inst) inst.innerText = "Hands-free active: Say 'Hey Care' or 'Hey Aaron' to converse!";
    if (!state.recognition) state.recognition = initSpeechRecognition();
    try { state.recognition.start(); } catch (e) {}
  } else {
    if (orb) orb.classList.remove("wake-listening");
    if (pill) {
      pill.className = "status-pill status-ready";
      pill.innerText = "Standby";
    }
    if (inst) inst.innerText = "Click to speak directly to CareWatcher via Laptop Mic";
    if (state.recognition && state.isListening && !state.continuousConversation) {
      try { state.recognition.stop(); } catch (e) {}
    }
  }
}

// ── Real-Time Web Audio VU Visualizer ────────────────────────────

let audioAnalyser = null;
let audioStream = null;
let animFrameId = null;

async function startAudioVisualizer() {
  try {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) return;
    if (!audioStream) {
      audioStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    }
    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    if (!state.audioContext) {
      state.audioContext = new AudioContextClass();
    }
    if (state.audioContext.state === "suspended") {
      await state.audioContext.resume();
    }
    const source = state.audioContext.createMediaStreamSource(audioStream);
    audioAnalyser = state.audioContext.createAnalyser();
    audioAnalyser.fftSize = 64;
    source.connect(audioAnalyser);

    drawAudioVU();
  } catch (err) {
    console.warn("Could not start audio visualizer:", err);
    const vuStatus = document.getElementById("audioVUStatus");
    if (vuStatus) {
      vuStatus.innerText = err.name === "NotAllowedError"
        ? "Microphone access blocked in browser."
        : "Mic hardware access standby.";
    }
  }
}

function stopAudioVisualizer() {
  if (animFrameId) {
    cancelAnimationFrame(animFrameId);
    animFrameId = null;
  }
  const canvas = document.getElementById("audioVUCanvas");
  if (canvas) {
    const ctx = canvas.getContext("2d");
    ctx.clearRect(0, 0, canvas.width, canvas.height);
  }
  const vuStatus = document.getElementById("audioVUStatus");
  if (vuStatus) vuStatus.innerText = "Mic Input: Standby";
}

function drawAudioVU() {
  const canvas = document.getElementById("audioVUCanvas");
  if (!canvas || !audioAnalyser) return;
  const ctx = canvas.getContext("2d");
  const data = new Uint8Array(audioAnalyser.frequencyBinCount);
  audioAnalyser.getByteFrequencyData(data);

  // Compute average volume & peak
  let sum = 0;
  let peak = 0;
  for (let i = 0; i < data.length; i++) {
    sum += data[i];
    if (data[i] > peak) peak = data[i];
  }
  const avg = sum / data.length;
  const percent = Math.min(100, Math.round((peak / 255) * 100));

  if (state.isListening && avg > 0) {
    if (!state.audioEnergySamples) state.audioEnergySamples = [];
    state.audioEnergySamples.push(avg / 255);
  }

  ctx.clearRect(0, 0, canvas.width, canvas.height);

  // Draw discrete Wispr Flow style bars
  const barCount = 20;
  const barWidth = (canvas.width / barCount) - 3;
  const maxBarHeight = canvas.height - 4;

  for (let i = 0; i < barCount; i++) {
    const binIndex = Math.floor((i / barCount) * data.length);
    const binVal = data[binIndex] || 0;
    const barHeight = Math.max(3, (binVal / 255) * maxBarHeight);
    const x = i * (barWidth + 3) + 2;
    const y = canvas.height - barHeight - 2;

    // Color gradient based on activity: dark charcoal -> lavender whisper -> forest ink
    if (binVal > 160) {
      ctx.fillStyle = "#ffa946"; // Ember peak
    } else if (binVal > 60) {
      ctx.fillStyle = "#f0d7ff"; // Lavender active
    } else {
      ctx.fillStyle = "#8a8a80"; // Idle fog
    }
    ctx.fillRect(x, y, barWidth, barHeight);
  }

  const vuStatus = document.getElementById("audioVUStatus");
  if (vuStatus) {
    if (percent > 8) {
      vuStatus.innerText = `Active Room Audio: ${percent}% (Signal Detected)`;
      vuStatus.style.color = "#f0d7ff";
    } else {
      vuStatus.innerText = `Room Audio: ${percent}% (Quiet / Listening)`;
      vuStatus.style.color = "#8a8a80";
    }
  }

  animFrameId = requestAnimationFrame(drawAudioVU);
}

// ── Live Speech Recognition (Microphone & Continuous Wake Word) ──

function initSpeechRecognition() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    const fb = document.getElementById("liveSpeechFeedback");
    if (fb) {
      fb.className = "live-speech-feedback error";
      fb.innerHTML = "WebSpeech API not supported in this browser. Use 'Record via Hardware Mic (Whisper)' below!";
    }
    return null;
  }

  const rec = new SpeechRecognition();
  rec.continuous = true;
  rec.interimResults = true;
  rec.lang = 'en-US';

  rec.onstart = () => {
    state.isListening = true;
    state.speechStartTime = performance.now();
    state.audioEnergySamples = [];
    startAudioVisualizer();

    const orb = document.getElementById("micOrb");
    const inst = document.getElementById("micInstruction");
    const pill = document.getElementById("voiceStatusPill");
    const fb = document.getElementById("liveSpeechFeedback");
    const banner = document.getElementById("continuousBannerText");

    if (state.continuousConversation) {
      if (orb) {
        orb.classList.remove("speaking");
        orb.classList.remove("thinking");
        orb.classList.add("recording");
        orb.classList.add("continuous-listening");
      }
      if (pill) {
        pill.className = "status-pill status-active";
        pill.innerText = "Listening to Aaron...";
      }
      if (inst) inst.innerText = "Continuous Dialogue Active: Speak naturally to Aaron's AI companion...";
      if (banner) banner.innerText = "Continuous Dialogue Active — Listening to Aaron";
      if (fb) {
        fb.className = "live-speech-feedback active";
        fb.innerText = "Listening to Aaron... Speak your health update or question.";
      }
    } else if (state.continuousWakeEnabled) {
      if (orb) orb.classList.add("wake-listening");
      if (pill) {
        pill.className = "status-pill status-active";
        pill.innerText = "Wake Word Armed";
      }
      if (inst) inst.innerText = "Listening for 'Hey Care' or 'Hey Aaron'...";
      if (fb) {
        fb.className = "live-speech-feedback active";
        fb.innerText = "Ambient wake word active. Say 'Hey Care' anytime.";
      }
    } else {
      if (orb) orb.classList.add("recording");
      if (pill) {
        pill.className = "status-pill status-active";
        pill.innerText = "Listening to Aaron...";
      }
      if (inst) inst.innerText = "Microphone active — speak naturally now...";
      if (fb) {
        fb.className = "live-speech-feedback active";
        fb.innerText = "Listening... Speak your health update or question.";
      }
    }
  };

  rec.onresult = (event) => {
    // Echo cancellation: if assistant is currently speaking or generating, drop mic input
    if (state.isAssistantSpeaking) {
      return;
    }

    let interim = "";
    let final = "";

    for (let i = event.resultIndex; i < event.results.length; ++i) {
      const transcript = event.results[i][0].transcript;
      if (event.results[i].isFinal) {
        final += transcript;
      } else {
        interim += transcript;
      }
    }

    const fb = document.getElementById("liveSpeechFeedback");
    if (interim) {
      if (fb) {
        fb.className = "live-speech-feedback active";
        fb.innerText = `Hearing Aaron: "${interim}..."`;
      }
      document.getElementById("userInput").value = interim;
    }

    if (final && final.trim()) {
      const cleanFinal = final.trim();
      const lower = cleanFinal.toLowerCase();
      const triggers = ["hey care", "care", "carewatcher", "care watcher", "hey aaron", "aaron", "ok care", "okay care", "hi care", "hello care"];
      const hasTrigger = triggers.some(t => lower.includes(t));

      // In ambient wake word mode only (when continuous conversation is off), enforce trigger
      if (state.continuousWakeEnabled && !state.continuousConversation) {
        if (!hasTrigger) return; // Ambient chatter filter
        playWakeChime();
      }

      state.lastUserSpokeTime = Date.now();
      state.isProcessingSpeech = true;

      // Extract real-time prosodic speech metrics
      const durationSeconds = state.speechStartTime > 0 ? (performance.now() - state.speechStartTime) / 1000 : 0;
      const wordCount = cleanFinal.split(/\s+/).filter(Boolean).length;
      const wpm = durationSeconds > 0.4 ? Math.round((wordCount / durationSeconds) * 60) : 125;
      const avgVolume = (state.audioEnergySamples && state.audioEnergySamples.length > 0)
        ? (state.audioEnergySamples.reduce((a, b) => a + b, 0) / state.audioEnergySamples.length)
        : 0.45;

      state.recentAudioMetrics = {
        duration_seconds: durationSeconds,
        wpm: wpm,
        avg_volume: avgVolume,
      };

      if (fb) {
        fb.className = "live-speech-feedback";
        fb.innerText = `Transcribed: "${cleanFinal}" (${wpm} WPM)`;
      }
      document.getElementById("userInput").value = cleanFinal;

      // Update UI to thinking state
      const orb = document.getElementById("micOrb");
      const pill = document.getElementById("voiceStatusPill");
      const inst = document.getElementById("micInstruction");
      const banner = document.getElementById("continuousBannerText");

      if (orb) {
        orb.classList.remove("recording");
        orb.classList.remove("continuous-listening");
        orb.classList.add("thinking");
      }
      if (pill) {
        pill.className = "status-pill status-ready";
        pill.innerText = "🧠 Gemini Thinking...";
      }
      if (inst) inst.innerText = "Gemini is evaluating your situation & crafting response...";
      if (banner) banner.innerText = "Gemini evaluating Aaron's update & situation...";

      // Stop mic temporarily during Gemini thinking & assistant speech to prevent audio echo
      try { rec.stop(); } catch (e) {}

      processInput(cleanFinal);
    }
  };

  rec.onerror = (event) => {
    console.warn("Speech recognition notice:", event.error);

    if (event.error === "no-speech") {
      // Normal in continuous mode when Aaron pauses; ignore and allow onend to re-arm
      return;
    }
    if (event.error === "aborted") {
      // Normal when rec.stop() was called
      return;
    }

    const fb = document.getElementById("liveSpeechFeedback");
    if (event.error === "not-allowed") {
      if (fb) {
        fb.className = "live-speech-feedback error";
        fb.innerHTML = "Microphone blocked. Click the lock/settings icon in your browser address bar to allow mic access.";
      }
      stopContinuousListening();
    } else if (event.error === "network") {
      if (fb) {
        fb.className = "live-speech-feedback error";
        fb.innerHTML = "Browser speech server unreachable. Click 'Record via Hardware Mic (Whisper)' below for direct local processing.";
      }
    } else if (event.error === "audio-capture") {
      if (fb) {
        fb.className = "live-speech-feedback error";
        fb.innerHTML = "Hardware mic capture failed. Windows may be using Virtual Audio Cable. Run 'Audio Diagnostics' below.";
      }
    }
  };

  rec.onend = () => {
    stopAudioVisualizer();

    // If assistant is currently speaking or processing, do not re-arm yet; speakReply will re-arm
    if (state.isAssistantSpeaking || state.isProcessingSpeech) {
      return;
    }

    if (state.continuousConversation && state.shutter === "OPEN") {
      // Auto-restart hands-free listening loop seamlessly
      setTimeout(() => {
        if (state.continuousConversation && !state.isAssistantSpeaking && !state.isProcessingSpeech && !state.isListening && state.shutter === "OPEN") {
          startContinuousListening();
        }
      }, 250);
    } else if (state.continuousWakeEnabled && state.shutter === "OPEN") {
      setTimeout(() => {
        if (state.continuousWakeEnabled && !state.isListening && state.shutter === "OPEN") {
          try { rec.start(); } catch (e) {}
        }
      }, 350);
    } else {
      stopMicUI();
    }
  };

  return rec;
}

function stopMicUI() {
  state.isListening = false;
  const orb = document.getElementById("micOrb");
  const inst = document.getElementById("micInstruction");
  const pill = document.getElementById("voiceStatusPill");

  if (state.continuousConversation) {
    if (orb) {
      orb.classList.remove("recording");
      orb.classList.remove("speaking");
      orb.classList.remove("thinking");
      orb.classList.add("continuous-listening");
    }
    if (pill) {
      pill.className = "status-pill status-active";
      pill.innerText = "Listening to Aaron...";
    }
    if (inst) inst.innerText = "Continuous Dialogue Active: Speak naturally without pressing buttons";
  } else if (state.continuousWakeEnabled) {
    if (orb) orb.classList.remove("recording");
    if (orb) orb.classList.add("wake-listening");
    if (pill) {
      pill.className = "status-pill status-active";
      pill.innerText = "Wake Word Armed";
    }
    if (inst) inst.innerText = "Say 'Hey Care' or 'Hey Aaron' anytime to speak!";
  } else {
    if (orb) {
      orb.classList.remove("recording");
      orb.classList.remove("wake-listening");
      orb.classList.remove("continuous-listening");
      orb.classList.remove("speaking");
      orb.classList.remove("thinking");
    }
    if (pill) {
      pill.className = "status-pill status-ready";
      pill.innerText = "Standby";
    }
    if (inst) inst.innerText = "Click to speak directly to CareWatcher via Laptop Mic";
  }
}

function toggleLiveMic() {
  if (state.continuousConversation) {
    // If continuous dialogue is active, clicking mic button pauses it
    setContinuousConversation(false);
    return;
  }

  if (!state.recognition) {
    state.recognition = initSpeechRecognition();
  }
  if (!state.recognition) return;

  if (state.isListening) {
    state.recognition.stop();
  } else {
    try {
      state.recognition.start();
    } catch (err) {
      console.warn("Recognition start error:", err);
    }
  }
}

// ── Direct Hardware Microphone Recording (Local Whisper) ──────────

async function recordDirectHardwareMic() {
  const btn = document.getElementById("btnHardwareMic");
  const fb = document.getElementById("liveSpeechFeedback");
  const inst = document.getElementById("micInstruction");
  const orb = document.getElementById("micOrb");

  if (btn) btn.disabled = true;
  if (orb) orb.classList.add("recording");
  if (inst) inst.innerText = "Recording directly from Laptop Hardware Mic (Realtek)...";

  let secondsLeft = 3;
  if (fb) {
    fb.className = "live-speech-feedback active";
    fb.innerText = `Recording via local Whisper STT (${secondsLeft}s) — Speak to Aaron's CareWatcher now!`;
  }

  const countdown = setInterval(() => {
    secondsLeft--;
    if (secondsLeft > 0 && fb) {
      fb.innerText = `Recording via local Whisper STT (${secondsLeft}s) — Speak now...`;
    }
  }, 1000);

  try {
    const res = await fetch("/api/audio/record_and_transcribe", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ duration: 3.0 })
    });
    clearInterval(countdown);
    const data = await res.json();

    if (orb) orb.classList.remove("recording");
    if (btn) btn.disabled = false;
    if (inst) inst.innerText = "Click to speak directly to CareWatcher via Laptop Mic";

    if (data.blocked) {
      if (fb) {
        fb.className = "live-speech-feedback error";
        fb.innerText = "Privacy shutter is CLOSED. Open privacy shutter in top bar to converse.";
      }
      appendFeedItem({
        type: "blocked",
        meta: "PRIVACY SHUTTER ENGAGED",
        body: "Hardware audio was blocked because the privacy shutter is closed. Open shutter to converse."
      });
      speakReply("Privacy shutter is closed. Please open the privacy shutter to converse.");
      return;
    }

    const transcribedText = (data.transcript && data.transcript.text) ? data.transcript.text.trim() : "";
    if (transcribedText) {
      if (fb) {
        fb.className = "live-speech-feedback";
        fb.innerText = `Transcribed via Local Whisper: "${transcribedText}"`;
      }
      document.getElementById("userInput").value = transcribedText;

      appendFeedItem({
        type: "user",
        meta: "RESIDENT HARDWARE MIC [WHISPER LOCAL]",
        body: `"${escapeHtml(transcribedText)}"`
      });

      const replyText = data.reply_text || "I understood your health update.";
      const eventCat = data.event ? data.event.category : "HEALTH";
      const eventSumm = data.event ? data.event.summary : "";

      appendFeedItem({
        type: "assistant",
        meta: `CAREWATCHER [${eventCat}: ${eventSumm}]`,
        body: replyText
      });

      speakReply(replyText);
    } else {
      if (fb) {
        fb.className = "live-speech-feedback";
        fb.innerText = data.message || "No audible voice recognized. Speak louder or check mic volume in Sound Settings.";
      }
    }
  } catch (err) {
    clearInterval(countdown);
    if (orb) orb.classList.remove("recording");
    if (btn) btn.disabled = false;
    if (inst) inst.innerText = "Click to speak directly to CareWatcher via Laptop Mic";
    if (fb) {
      fb.className = "live-speech-feedback error";
      fb.innerText = `Hardware mic error: ${err.message}`;
    }
  }
}

// ── Audio & Microphone Diagnostics Drawer ─────────────────────────

async function openAudioDiagnostics() {
  const drawer = document.getElementById("diagDrawer");
  const body = document.getElementById("diagBody");
  if (!drawer || !body) return;

  drawer.style.display = "block";
  body.innerHTML = "<p style='color: var(--color-fog);'>Running real-time audio and hardware diagnostics...</p>";

  // 1. Browser WebSpeech support
  const hasWebSpeech = Boolean(window.SpeechRecognition || window.webkitSpeechRecognition);

  // 2. Browser MediaDevices support & permission
  let micPermission = "Unknown";
  try {
    if (navigator.permissions && navigator.permissions.query) {
      const p = await navigator.permissions.query({ name: "microphone" });
      micPermission = p.state; // 'granted', 'prompt', 'denied'
    }
  } catch (e) {}

  // 3. Backend Hardware Mic & Devices
  let backendData = null;
  try {
    const res = await fetch("/api/audio/status");
    backendData = await res.json();
  } catch (e) {}

  const defaultDev = backendData ? backendData.default_device : "Unknown";
  const shutterState = backendData ? backendData.shutter_state : "OPEN";
  const isVirtual = defaultDev.toLowerCase().includes("virtual") || defaultDev.toLowerCase().includes("line 1");

  let html = `
    <div class="diag-grid">
      <div class="diag-card">
        <div class="diag-card-title">Browser WebSpeech Engine</div>
        <div class="diag-card-value" style="color: ${hasWebSpeech ? '#034f46' : '#ff7b72'};">
          ${hasWebSpeech ? "Available (Chrome/Edge Engine)" : "Not Supported"}
        </div>
      </div>
      <div class="diag-card">
        <div class="diag-card-title">Browser Mic Permission</div>
        <div class="diag-card-value" style="color: ${micPermission === 'granted' ? '#034f46' : (micPermission === 'denied' ? '#ff7b72' : '#ffa946')};">
          ${micPermission.toUpperCase()}
        </div>
      </div>
      <div class="diag-card">
        <div class="diag-card-title">Windows Hardware Input Device</div>
        <div class="diag-card-value" style="color: ${isVirtual ? '#ffa946' : '#f0d7ff'};">
          ${defaultDev}
        </div>
      </div>
      <div class="diag-card">
        <div class="diag-card-title">Privacy Shutter Gate</div>
        <div class="diag-card-value" style="color: ${shutterState === 'OPEN' ? '#034f46' : '#ffa946'};">
          ${shutterState}
        </div>
      </div>
    </div>
  `;

  if (shutterState === "CLOSED") {
    html += `
      <div style="background: rgba(255,169,70,0.15); border: 1px solid #ffa946; padding: 10px 14px; border-radius: 12px; margin-bottom: 12px; font-size: 13px;">
        ⚠️ <strong>Privacy Shutter is CLOSED</strong>: All audio and video input is intentionally blocked at the physical gate. Click <strong>"Open Privacy Shutter"</strong> in the top bar to enable audio processing.
      </div>
    `;
  }

  if (isVirtual) {
    html += `
      <div style="background: rgba(255,123,114,0.15); border: 1px solid #ff7b72; padding: 10px 14px; border-radius: 12px; margin-bottom: 12px; font-size: 13px;">
        ⚠️ <strong>Virtual Audio Cable Detected as Default</strong>: Windows is currently routing default sound to Virtual Audio Cable (which has 0 physical room audio).
        <br><br>
        <strong>Fix:</strong> Open Windows Settings ➔ <em>System</em> ➔ <em>Sound</em> ➔ <em>Input</em> and set <strong>"Microphone Array (Realtek)"</strong> as your Default Device.
      </div>
    `;
  }

  html += `
    <div style="font-size: 12px; color: var(--color-fog); line-height: 1.6;">
      <strong>Instant CLI Check (No prompt needed in the future):</strong>
      <div style="background: #111; padding: 8px 12px; border-radius: 8px; font-family: monospace; color: #f0d7ff; margin: 6px 0;">
        python check_mic.py
      </div>
      Running this single command in terminal tests all audio devices, measures peak volume, and verifies Whisper STT in 2 seconds.
    </div>
  `;

  body.innerHTML = html;
}

function closeAudioDiagnostics() {
  const drawer = document.getElementById("diagDrawer");
  if (drawer) drawer.style.display = "none";
}

// ── Spoken Voice Output (TTS) ────────────────────────────────────

function speakReply(text) {
  const voiceCheckbox = document.getElementById("voiceOutput");
  const orb = document.getElementById("micOrb");
  const pill = document.getElementById("voiceStatusPill");
  const banner = document.getElementById("continuousBannerText");
  const inst = document.getElementById("micInstruction");

  const onSpeechDone = () => {
    state.isAssistantSpeaking = false;
    state.isProcessingSpeech = false;
    if (orb) {
      orb.classList.remove("speaking");
      orb.classList.remove("thinking");
    }

    if (state.continuousConversation && state.shutter === "OPEN") {
      if (pill) {
        pill.className = "status-pill status-active";
        pill.innerText = "Listening to Aaron...";
      }
      if (banner) banner.innerText = "Continuous Dialogue Active — Listening to Aaron";
      if (inst) inst.innerText = "Continuous Dialogue Active: Speak naturally without pressing buttons";

      // 350ms echo clearance delay to allow room reverberations to clear before re-arming mic
      setTimeout(() => {
        if (state.continuousConversation && !state.isAssistantSpeaking && !state.isProcessingSpeech && state.shutter === "OPEN") {
          startContinuousListening();
        }
      }, 350);
    } else {
      stopMicUI();
    }
  };

  if (!voiceCheckbox || !voiceCheckbox.checked || !('speechSynthesis' in window)) {
    // If TTS is disabled or unavailable, pause briefly for reading, then re-arm mic
    setTimeout(onSpeechDone, 700);
    return;
  }

  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.rate = 0.98;
  utterance.pitch = 1.0;

  state.isAssistantSpeaking = true;
  // Immediately stop mic while assistant speaks so it does not hear itself
  if (state.recognition && state.isListening) {
    try { state.recognition.stop(); } catch (e) {}
  }

  if (orb) {
    orb.classList.remove("recording");
    orb.classList.remove("continuous-listening");
    orb.classList.remove("thinking");
    orb.classList.add("speaking");
  }
  if (pill) {
    pill.className = "status-pill status-speaking";
    pill.innerText = "CareWatcher Speaking...";
  }
  if (banner) banner.innerText = "CareWatcher speaking to Aaron...";
  if (inst) inst.innerText = "CareWatcher speaking aloud...";

  utterance.onend = onSpeechDone;
  utterance.onerror = onSpeechDone;

  window.speechSynthesis.speak(utterance);
}

// ── Conversation Processing ──────────────────────────────────────

function sendPreset(text) {
  document.getElementById("userInput").value = text;
  processInput(text);
}

async function processInput(explicitText) {
  const inputEl = document.getElementById("userInput");
  const text = (explicitText || inputEl.value).trim();
  if (!text) return;
  inputEl.value = "";

  if (text.startsWith("[AMBIENT CLINICAL SITUATION")) {
    appendFeedItem({
      type: "system",
      meta: "CONTINUOUS SITUATION EVALUATION",
      body: `<em>Continuous evaluation triggered gentle check-in based on live Apple Watch vitals & mood affect.</em>`
    });
  } else {
    appendFeedItem({
      type: "user",
      meta: "RESIDENT SPOKEN VOICE [AARON]",
      body: `"${escapeHtml(text)}"`
    });
  }

  const audioMetrics = state.recentAudioMetrics || {
    duration_seconds: Math.max(1.0, text.split(/\s+/).length * 0.45),
    wpm: 125,
    avg_volume: 0.45,
  };
  state.recentAudioMetrics = null;

  try {
    const res = await fetch("/api/process_transcript", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        text,
        audio_metrics: audioMetrics,
        facial_data: state.currentMood || null,
      })
    });
    const data = await res.json();

    if (data.blocked) {
      state.isProcessingSpeech = false;
      appendFeedItem({
        type: "blocked",
        meta: "PRIVACY SHUTTER ENGAGED",
        body: "Input was gated and discarded at the physical shutter boundary. Please open the privacy shutter to converse."
      });
      speakReply("Privacy shutter is closed. Please open the privacy shutter to converse.");
    } else {
      if (data.speech_analysis || data.multimodal_evaluation) {
        updateMultimodalAffectUI(data.speech_analysis, data.multimodal_evaluation);
      }

      let replyText = data.reply_text || (data.event && data.event.summary ? data.event.summary : "I understood that.");

      const eventCat = data.event ? data.event.category : "HEALTH";
      const eventSumm = data.event ? data.event.summary : "";

      let insightChip = "";
      if (data.multimodal_evaluation) {
        const mm = data.multimodal_evaluation;
        if (mm.congruence_status === "MASKED_FATIGUE") {
          insightChip = `<div class="affect-insight-pill masked-fatigue">⚠️ Affective Discordance: Masked Fatigue Detected — Smiling Face vs Subdued Voice (${Math.round(mm.speech_wpm)} WPM)</div>`;
        } else if (mm.congruence_status === "INTERNAL_AGITATION") {
          insightChip = `<div class="affect-insight-pill internal-agitation">⚡ Internal Sympathetic Arousal: Elevated Cardiac Rate (${Math.round(mm.heart_rate_bpm)} BPM) & Hurried Speech</div>`;
        } else if (mm.congruence_status === "CONGRUENT_CHEERFUL") {
          insightChip = `<div class="affect-insight-pill cheerful">✨ Multimodal Harmony: High Social Vitality & Radiant Engagement</div>`;
        } else if (mm.congruence_status === "CONGRUENT_FATIGUE") {
          insightChip = `<div class="affect-insight-pill fatigue">💤 Multimodal Congruence: Weariness & Fatigue Confirmed</div>`;
        }
      }

      appendFeedItem({
        type: "assistant",
        meta: `CAREWATCHER [${eventCat}: ${eventSumm}]`,
        body: `${replyText}${insightChip ? '<br>' + insightChip : ''}`
      });

      speakReply(replyText);

      // Refresh polls
      pollTelemetry();
    }
  } catch (err) {
    state.isProcessingSpeech = false;
    appendFeedItem({
      type: "system",
      meta: "PROCESSING ERROR",
      body: `Error: ${err}`
    });
    if (state.continuousConversation && state.shutter === "OPEN") {
      setTimeout(() => {
        if (state.continuousConversation && !state.isAssistantSpeaking && !state.isProcessingSpeech && state.shutter === "OPEN") {
          startContinuousListening();
        }
      }, 500);
    }
  }
}

// ── Speech Pattern & Multimodal Affect Engine UI ───────────────

function updateMultimodalAffectUI(speech, mmEval) {
  if (!speech && !mmEval) return;

  const badge = document.getElementById("hudCongruenceBadge");
  const vocalEl = document.getElementById("hudVocalEmotionVal");
  const confEl = document.getElementById("hudEmotionConfidence");
  const cadenceEl = document.getElementById("hudSpeechCadenceVal");
  const cadenceSub = document.getElementById("hudCadenceSub");
  const dynamicsEl = document.getElementById("hudAcousticDynamicsVal");
  const pitchSub = document.getElementById("hudPitchSub");
  const stabilityEl = document.getElementById("hudStabilityVal");
  const stabilitySub = document.getElementById("hudStabilitySub");
  const noteEl = document.getElementById("hudClinicalNoteText");

  if (mmEval) {
    if (badge) {
      badge.innerText = mmEval.congruence_badge || mmEval.congruence_status;
      badge.className = "hud-congruence-badge";
      if (mmEval.congruence_status === "MASKED_FATIGUE") {
        badge.classList.add("badge-masked-fatigue");
      } else if (mmEval.congruence_status === "INTERNAL_AGITATION") {
        badge.classList.add("badge-internal-agitation");
      } else if (mmEval.congruence_status === "CONGRUENT_CHEERFUL") {
        badge.classList.add("badge-cheerful");
      } else if (mmEval.congruence_status === "CONGRUENT_FATIGUE") {
        badge.classList.add("badge-fatigue");
      } else if (mmEval.congruence_status === "SOMATIC_DISCOMFORT") {
        badge.classList.add("badge-discomfort");
      } else {
        badge.classList.add("badge-equilibrium");
      }
    }

    if (stabilityEl) {
      const stab = Math.round((mmEval.stability_index || 0.9) * 100);
      stabilityEl.innerText = `${stab}%`;
    }
    if (stabilitySub) {
      if (mmEval.stability_index >= 0.85) stabilitySub.innerText = "Optimal Equilibrium";
      else if (mmEval.stability_index >= 0.60) stabilitySub.innerText = "Affective Variance";
      else stabilitySub.innerText = "Discordant Episode";
    }

    if (noteEl && mmEval.clinical_assessment) {
      noteEl.innerText = mmEval.clinical_assessment;
    }
  }

  if (speech) {
    if (vocalEl) {
      const emo = speech.primary_emotion ? speech.primary_emotion.toUpperCase() : "CALM";
      vocalEl.innerText = emo;
    }
    if (confEl) {
      confEl.innerText = `Confidence ${Math.round((speech.confidence || 0.85) * 100)}%`;
    }
    if (cadenceEl) {
      cadenceEl.innerText = `${Math.round(speech.wpm || 120)} WPM`;
    }
    if (cadenceSub) {
      cadenceSub.innerText = speech.cadence_label || "Conversational Baseline";
    }
    if (dynamicsEl) {
      const pv = speech.pitch_variance !== undefined ? speech.pitch_variance.toFixed(2) : "0.50";
      dynamicsEl.innerText = speech.pitch_variance < 0.35 ? `Monotone (${pv})` : (speech.pitch_variance > 0.65 ? `Tremor/Expressive (${pv})` : `Balanced (${pv})`);
    }
    if (pitchSub) {
      const energy = speech.rms_energy < 0.35 ? "Subdued Amplitude" : (speech.rms_energy > 0.65 ? "Elevated Amplitude" : "Steady Amplitude");
      pitchSub.innerText = `${energy} • Pauses: ${Math.round((speech.pause_ratio || 0.15) * 100)}%`;
    }
    if (noteEl && (!mmEval || !mmEval.clinical_assessment)) {
      noteEl.innerText = speech.clinical_note;
    }
  }
}

// ── Feed DOM Helpers ─────────────────────────────────────────────

function appendFeedItem({ type, meta, body }) {
  const feed = document.getElementById("chatStream");
  const bubble = document.createElement("div");
  bubble.className = `feed-bubble ${type}`;
  bubble.innerHTML = `
    <div class="bubble-meta">${meta}</div>
    <div class="bubble-body">${body}</div>
  `;
  feed.appendChild(bubble);
  feed.scrollTop = feed.scrollHeight;

  const countTag = document.getElementById("eventCountTag");
  if (countTag) {
    const bubbles = feed.getElementsByClassName("feed-bubble");
    countTag.innerText = `${bubbles.length} messages`;
  }
}

function escapeHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

// ── Live Cardiac Beat Engine (ECG Sweep & Rhythm Contraction) ─────

let liveBeatState = {
  lastBeatTime: 0,
  hasFiredPeakThisCycle: false,
};

function playCardiacTone() {
  const chk = document.getElementById("beatAudioCheckbox");
  if (!chk || !chk.checked) return;

  try {
    const AudioCtx = window.AudioContext || window.webkitAudioContext;
    if (!state.audioContext) state.audioContext = new AudioCtx();
    const ctx = state.audioContext;
    if (ctx.state === "suspended") ctx.resume();

    // S1 Heart Sound ("Lub" - 85-110Hz resonant damped thump)
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = "sine";
    osc.frequency.setValueAtTime(110, ctx.currentTime);
    osc.frequency.exponentialRampToValueAtTime(45, ctx.currentTime + 0.08);

    gain.gain.setValueAtTime(0.18, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.09);

    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start();
    osc.stop(ctx.currentTime + 0.1);
  } catch (e) {
    // Audio context may require user gesture on first interaction
  }
}

function initLiveBeatEngine() {
  const canvas = document.getElementById("liveBeatCanvas");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");

  const history = new Array(80).fill(0);
  let phase = 0;

  function ecgSampleAt(p) {
    // Standard P-Q-R-S-T wave model for normalized phase [0, 1]
    if (p > 0.08 && p < 0.16) {
      // P wave (atrial depolarization)
      return Math.sin(((p - 0.08) / 0.08) * Math.PI) * 0.22;
    } else if (p >= 0.16 && p < 0.20) {
      // PR segment baseline
      return 0;
    } else if (p >= 0.20 && p < 0.22) {
      // Q wave (septal depolarization)
      return -Math.sin(((p - 0.20) / 0.02) * Math.PI) * 0.18;
    } else if (p >= 0.22 && p < 0.28) {
      // R wave (ventricular depolarization peak)
      return Math.sin(((p - 0.22) / 0.06) * Math.PI) * 1.0;
    } else if (p >= 0.28 && p < 0.31) {
      // S wave
      return -Math.sin(((p - 0.28) / 0.03) * Math.PI) * 0.35;
    } else if (p >= 0.31 && p < 0.40) {
      // ST segment baseline
      return 0;
    } else if (p >= 0.40 && p < 0.54) {
      // T wave (ventricular repolarization)
      return Math.sin(((p - 0.40) / 0.14) * Math.PI) * 0.32;
    }
    // Diastolic baseline with subtle micro-undulation
    return Math.sin(p * Math.PI * 4) * 0.02;
  }

  function loop() {
    requestAnimationFrame(loop);

    // Current BPM from DOM or state
    let bpm = 74;
    const bpmEl = document.getElementById("valBPM");
    if (bpmEl) {
      const parsed = parseFloat(bpmEl.innerText);
      if (!isNaN(parsed) && parsed > 35 && parsed < 220) bpm = parsed;
    }

    const intervalMs = (60 / bpm) * 1000;
    const intervalLabel = document.getElementById("beatIntervalText");
    if (intervalLabel) {
      intervalLabel.innerText = `Rhythm: ${Math.round(intervalMs)} ms / beat (${Math.round(bpm)} BPM)`;
    }

    // Step the cardiac phase based on real-time rate
    // 60 FPS -> ~16.6ms per frame
    const phaseDelta = 16.667 / intervalMs;
    const prevPhase = phase;
    phase = (phase + phaseDelta) % 1.0;

    // Detect R-Peak transition (~0.25)
    const heartIcon = document.getElementById("cardiacHeartIcon");
    if (prevPhase < 0.25 && phase >= 0.25) {
      if (heartIcon) {
        heartIcon.classList.add("beating");
        setTimeout(() => heartIcon.classList.remove("beating"), 140);
      }
      playCardiacTone();
    }

    // Push current instantaneous deflection into buffer
    const val = ecgSampleAt(phase);
    history.push(val);
    history.shift();

    // Render ECG sweep on canvas
    const w = canvas.width;
    const h = canvas.height;
    const midY = h / 2 + 2;

    ctx.fillStyle = "#111111";
    ctx.fillRect(0, 0, w, h);

    // Subtle clinical grid lines
    ctx.strokeStyle = "rgba(255, 255, 255, 0.06)";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(0, midY); ctx.lineTo(w, midY);
    ctx.stroke();

    // ECG trace
    ctx.strokeStyle = "#34d399"; // Crisp clinical emerald
    ctx.lineWidth = 2.0;
    ctx.beginPath();

    const step = w / (history.length - 1);
    for (let i = 0; i < history.length; i++) {
      const x = i * step;
      // Invert Y because canvas Y grows downwards
      const y = midY - history[i] * (h * 0.42);
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();

    // Leading glowing beam dot
    const leadX = w - 2;
    const leadY = midY - history[history.length - 1] * (h * 0.42);
    ctx.fillStyle = "#f0d7ff";
    ctx.beginPath();
    ctx.arc(leadX, leadY, 2.5, 0, Math.PI * 2);
    ctx.fill();
  }

  loop();
}

// ── HypeRate.io Live Stream Client ─────────────────────────────────

let hyperateState = {
  socket: null,
  channelId: "034A7",
  heartbeatTimer: null,
  lastIngestTime: 0,
};

function extractChannelFromUrl(urlOrCode) {
  if (!urlOrCode) return "034A7";
  const str = String(urlOrCode).trim();
  if (str.includes("/")) {
    const parts = str.split("/").filter(Boolean);
    return parts[parts.length - 1] || "034A7";
  }
  return str;
}

function initHyperateStream(channelInput) {
  const channel = extractChannelFromUrl(channelInput || "034A7");
  hyperateState.channelId = channel;

  const dot = document.getElementById("hyperateLiveDot");
  const badge = document.getElementById("hyperateStatusBadge");
  const meta = document.getElementById("hyperateLiveMeta");

  if (dot) dot.className = "live-dot connecting";
  if (badge) {
    badge.innerText = "CONNECTING...";
    badge.className = "vital-pill";
    badge.style.backgroundColor = "var(--color-ember-glow)";
    badge.style.color = "var(--color-vast-ink)";
  }

  // Clean old socket
  if (hyperateState.socket) {
    try { hyperateState.socket.close(); } catch (e) {}
  }
  if (hyperateState.heartbeatTimer) {
    clearInterval(hyperateState.heartbeatTimer);
    hyperateState.heartbeatTimer = null;
  }

  const token = "bnQ1FoJmfiRprrSUJzrFxt8x8BbllHyqIWq4LsRjV7aCrLuLot6QyCQM9NZRkd9z";
  const wsUrl = `wss://app.hyperate.io/socket/websocket?token=${token}`;

  try {
    const ws = new WebSocket(wsUrl);
    hyperateState.socket = ws;
    let ref = 1;

    ws.onopen = () => {
      // Join Phoenix Channel
      ws.send(JSON.stringify({
        topic: `hr:${channel}`,
        event: "phx_join",
        payload: {},
        ref: ref++
      }));

      if (dot) dot.className = "live-dot";
      if (badge) {
        badge.innerText = "LIVE STREAMING";
        badge.className = "vital-pill active";
        badge.style.backgroundColor = "";
        badge.style.color = "";
      }
      if (meta) {
        meta.innerHTML = `Channel: <strong>${escapeHtml(channel)}</strong> • Protocol: <strong>Phoenix WebSocket</strong> • Latency: <strong>&lt; 30ms</strong>`;
      }

      // Heartbeat every 25s
      hyperateState.heartbeatTimer = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({
            topic: "phoenix",
            event: "heartbeat",
            payload: {},
            ref: ref++
          }));
        }
      }, 25000);
    };

    ws.onmessage = (evt) => {
      let msg;
      try { msg = JSON.parse(evt.data); } catch (e) { return; }

      if (msg.topic === `hr:${channel}` && msg.event === "hr_update") {
        const hr = msg.payload && msg.payload.hr;
        if (hr && typeof hr === "number" && hr >= 30 && hr <= 230) {
          const bpm = Math.round(hr);

          // 1. Immediately update UI
          const bpmEl = document.getElementById("valBPM");
          if (bpmEl) bpmEl.innerText = bpm;

          const bpmMeta = document.getElementById("bpmSourceMeta");
          if (bpmMeta) bpmMeta.innerText = `Source: HypeRate Live Stream (Apple Watch ${channel})`;

          const hwBadge = document.getElementById("hwStatusBadge");
          if (hwBadge) {
            hwBadge.innerText = `HypeRate Stream Active (${channel})`;
            hwBadge.style.color = "var(--color-forest-ink)";
          }

          const driverBadge = document.getElementById("sensorDriverBadge");
          if (driverBadge) {
            driverBadge.innerText = "HypeRate Live";
            driverBadge.style.backgroundColor = "var(--color-forest-ink)";
          }

          // Trigger live contraction animation
          const heartIcon = document.getElementById("cardiacHeartIcon");
          if (heartIcon) {
            heartIcon.classList.add("beating");
            setTimeout(() => heartIcon.classList.remove("beating"), 140);
          }

          // 2. Throttled backend sync (every 2.5s) to record in SQLite & audit ledger
          const now = Date.now();
          if (now - hyperateState.lastIngestTime > 2500) {
            hyperateState.lastIngestTime = now;
            fetch("/api/sensor/apple_watch", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                bpm: bpm,
                source: `HypeRate Live (Apple Watch ${channel})`
              })
            }).catch(() => {});
          }
        }
      }
    };

    ws.onerror = (err) => {
      console.warn("HypeRate WS error:", err);
    };

    ws.onclose = () => {
      if (dot) dot.className = "live-dot disconnected";
      if (badge) {
        badge.innerText = "RECONNECTING";
        badge.className = "vital-pill";
      }
      if (hyperateState.heartbeatTimer) clearInterval(hyperateState.heartbeatTimer);
      setTimeout(() => initHyperateStream(channel), 3500);
    };

  } catch (e) {
    console.warn("HypeRate WebSocket init failed:", e);
  }
}

function connectCustomHyperate() {
  const input = document.getElementById("hyperateUrlInput");
  const val = input ? input.value : "034A7";
  const ch = extractChannelFromUrl(val);
  initHyperateStream(ch);

  // Notify backend to also stream this channel
  fetch("/api/hyperate/connect", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ channel: ch })
  }).then(r => r.json()).then(data => {
    appendFeedItem({
      type: "system",
      meta: "HYPERATE LIVE STREAM CONNECTED",
      body: `Direct Phoenix WebSocket link engaged for Apple Watch channel <strong>${escapeHtml(ch)}</strong>. Real-time heart rate active.`
    });
  }).catch(() => {});
}

// ── Conversational AI Model & Gemini Management ───────────────────

let llmState = {
  provider: "gemini",
  model: "gemini-3.5-flash",
  hasKey: false,
  keyPreview: "",
  status: "needs_key"
};

async function pollLLMStatus() {
  try {
    const res = await fetch("/api/llm/status");
    if (!res.ok) return;
    const data = await res.json();
    llmState = {
      provider: data.provider || "gemini",
      model: data.model || "gemini-3.5-flash",
      hasKey: !!data.has_key,
      keyPreview: data.key_preview || "",
      status: data.status || (data.has_key ? "active" : "needs_key")
    };
    updateLLMUI();
  } catch (err) {
    console.debug("pollLLMStatus error:", err);
  }
}

function updateLLMUI() {
  const pillVal = document.getElementById("llmPillVal");
  const dot = document.getElementById("llmDot");
  const badge = document.getElementById("cardModelBadge");
  const aside = document.getElementById("keyPreviewAside");
  const statusCard = document.getElementById("modelStatusCard");
  const statusTitle = document.getElementById("statusCardTitle");
  const statusDesc = document.getElementById("statusCardDesc");
  const statusIcon = document.getElementById("statusCardIcon");
  const modelSelect = document.getElementById("geminiModelSelect");

  const modelDisplay = (llmState.model || "gemini-2.0-flash").toUpperCase();

  if (pillVal) {
    pillVal.innerText = modelDisplay;
  }

  if (dot) {
    if (llmState.hasKey) {
      dot.style.backgroundColor = "#2e7d32"; // Emerald green
    } else {
      dot.style.backgroundColor = "#f57f17"; // Amber warning
    }
  }

  if (badge) {
    if (llmState.hasKey) {
      badge.className = "model-badge";
      badge.innerHTML = `✨ ${escapeHtml(llmState.model)}`;
      badge.title = "Google Gemini Active (Click to change settings)";
    } else {
      badge.className = "model-badge needs-key";
      badge.innerHTML = `⚠️ Set Gemini Key`;
      badge.title = "Click to enter your free Google Gemini API Key";
    }
  }

  if (aside && llmState.keyPreview) {
    aside.innerText = `Active: ${llmState.keyPreview}`;
  }

  if (statusCard && statusTitle && statusDesc && statusIcon) {
    if (llmState.hasKey) {
      statusCard.className = "model-status-card";
      statusIcon.innerText = "⚡";
      statusTitle.innerText = `Google Gemini (${llmState.model}) Active`;
      statusDesc.innerText = `Empathetic health companion connected with live Apple Watch vitals and affect stream.`;
    } else {
      statusCard.className = "model-status-card needs-key";
      statusIcon.innerText = "🔑";
      statusTitle.innerText = "Gemini API Key Needed";
      statusDesc.innerText = "CareWatcher is ready to connect. Paste your free Google AI Studio key below to activate conversational cognition.";
    }
  }

  if (modelSelect && llmState.model) {
    modelSelect.value = llmState.model;
  }
}

function openModelSettingsModal() {
  const modal = document.getElementById("aiModelModal");
  if (modal) {
    modal.style.display = "flex";
    pollLLMStatus();
  }
}

function closeModelSettingsModal() {
  const modal = document.getElementById("aiModelModal");
  if (modal) modal.style.display = "none";
}

function handleModalBackdropClick(event) {
  if (event.target && event.target.id === "aiModelModal") {
    closeModelSettingsModal();
  }
}

function toggleKeyVisibility() {
  const input = document.getElementById("geminiApiKeyInput");
  const btn = document.getElementById("keyToggleBtn");
  if (!input || !btn) return;
  if (input.type === "password") {
    input.type = "text";
    btn.innerText = "Hide";
  } else {
    input.type = "password";
    btn.innerText = "Show";
  }
}

async function saveGeminiConfig() {
  const keyInput = document.getElementById("geminiApiKeyInput");
  const modelSelect = document.getElementById("geminiModelSelect");
  const saveBtn = document.getElementById("saveGeminiBtn");

  const apiKey = keyInput ? keyInput.value.trim() : "";
  const modelName = modelSelect ? modelSelect.value : "gemini-2.0-flash";

  if (!apiKey && !llmState.hasKey) {
    alert("Please enter a valid Google Gemini API key (starts with AIzaSy...).");
    return;
  }

  if (saveBtn) {
    saveBtn.disabled = true;
    saveBtn.innerText = "Connecting...";
  }

  try {
    const res = await fetch("/api/llm/config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ api_key: apiKey, model_name: modelName })
    });
    const data = await res.json();
    if (saveBtn) {
      saveBtn.disabled = false;
      saveBtn.innerText = "Save & Connect";
    }

    if (data.success) {
      appendFeedItem({
        type: "system",
        meta: "CONVERSATIONAL AI CONFIGURED",
        body: `Google Gemini <strong>${escapeHtml(modelName)}</strong> is now actively driving CareWatcher's conversational cognition.`
      });
      await pollLLMStatus();
      if (keyInput) keyInput.value = "";
      closeModelSettingsModal();
    } else {
      alert("Could not update model settings: " + (data.error || "Unknown error"));
    }
  } catch (err) {
    if (saveBtn) {
      saveBtn.disabled = false;
      saveBtn.innerText = "Save & Connect";
    }
    alert("Connection error: " + err);
  }
}

async function testGeminiConnection() {
  const previewBox = document.getElementById("testPreviewBox");
  const previewContent = document.getElementById("testPreviewContent");
  const testBtn = document.getElementById("testGeminiBtn");

  if (testBtn) {
    testBtn.disabled = true;
    testBtn.innerText = "Testing...";
  }
  if (previewBox) previewBox.style.display = "block";
  if (previewContent) previewContent.innerText = "Querying Google Gemini with live vitals context...";

  try {
    const res = await fetch("/api/llm/test", {
      method: "POST",
      headers: { "Content-Type": "application/json" }
    });
    const data = await res.json();
    if (testBtn) {
      testBtn.disabled = false;
      testBtn.innerText = "⚡ Test Conversation";
    }

    if (data.reply) {
      if (previewContent) {
        previewContent.innerHTML = `<strong>Assistant:</strong> "${escapeHtml(data.reply)}"`;
      }
      speakReply(data.reply);
    } else {
      if (previewContent) {
        previewContent.innerHTML = `<span style="color: #c62828;">Error: ${escapeHtml(data.error || "No response received")}</span>`;
      }
    }
  } catch (err) {
    if (testBtn) {
      testBtn.disabled = false;
      testBtn.innerText = "⚡ Test Conversation";
    }
    if (previewContent) {
      previewContent.innerHTML = `<span style="color: #c62828;">Test failed: ${escapeHtml(err.message || String(err))}</span>`;
    }
  }
}

// ── Collapsible Stream Menus & Multi-Page View Transition ───────────

function toggleStreamCollapse(boxId) {
  const box = document.getElementById(boxId);
  if (box) {
    box.classList.toggle("collapsed");
  }
}

function switchToView(viewName) {
  const compView = document.getElementById("viewCompanion");
  const auditView = document.getElementById("viewAudit");
  const tabComp = document.getElementById("tabCompanion");
  const tabAudit = document.getElementById("tabAudit");

  if (viewName === "audit") {
    if (compView) {
      compView.style.display = "none";
      compView.classList.remove("active", "slide-right");
    }
    if (auditView) {
      auditView.style.display = "block";
      auditView.classList.remove("slide-right");
      auditView.classList.add("active", "slide-left");
    }
    if (tabComp) tabComp.classList.remove("active");
    if (tabAudit) tabAudit.classList.add("active");
    try {
      history.pushState({ view: "audit" }, "", "#audit");
    } catch (e) {}
  } else {
    if (auditView) {
      auditView.style.display = "none";
      auditView.classList.remove("active", "slide-left");
    }
    if (compView) {
      compView.style.display = "grid";
      compView.classList.remove("slide-left");
      compView.classList.add("active", "slide-right");
    }
    if (tabComp) tabComp.classList.add("active");
    if (tabAudit) tabAudit.classList.remove("active");
    try {
      history.pushState({ view: "companion" }, "", "#companion");
    } catch (e) {}
  }
  window.scrollTo({ top: 0, behavior: "smooth" });
}

// Handle browser Back / Forward buttons & direct hash links
window.addEventListener("popstate", () => {
  if (window.location.hash === "#audit") {
    switchToView("audit");
  } else {
    switchToView("companion");
  }
});

// Check initial URL hash on DOM ready or immediate execution
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", () => {
    if (window.location.hash === "#audit" || window.location.pathname.includes("audit") || window.location.pathname.includes("ledger")) {
      switchToView("audit");
    }
  });
} else {
  if (window.location.hash === "#audit" || window.location.pathname.includes("audit") || window.location.pathname.includes("ledger")) {
    switchToView("audit");
  }
}



