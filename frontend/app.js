// DOM Elements
const orbBtn = document.getElementById("orbBtn");
const orbGlow = document.getElementById("orbGlow");
const statusDot = document.getElementById("statusDot");
const statusText = document.getElementById("statusText");
const timelineEl = document.getElementById("timeline");
const replyAudioEl = document.getElementById("replyAudio");

// Sidebars & Overlay
const settingsSidebar = document.getElementById("settingsSidebar");
const feedbackSidebar = document.getElementById("feedbackSidebar");
const settingsToggleBtn = document.getElementById("settingsToggleBtn");
const feedbackToggleBtn = document.getElementById("feedbackToggleBtn");
const settingsCloseBtn = document.getElementById("settingsCloseBtn");
const feedbackCloseBtn = document.getElementById("feedbackCloseBtn");
const sidebarsOverlay = document.getElementById("sidebarsOverlay");
const feedbackDot = document.getElementById("feedbackDot");

// Dashboard Elements
const dashboardEmptyState = document.getElementById("dashboardEmptyState");
const dashboardContent = document.getElementById("dashboardContent");
const cardRoast = document.getElementById("cardRoast");
const cardOriginal = document.getElementById("cardOriginal");
const cardCorrection = document.getElementById("cardCorrection");
const cardExplanation = document.getElementById("cardExplanation");
const cardChallenge = document.getElementById("cardChallenge");

// Settings
const resetSessionBtn = document.getElementById("resetSessionBtn");
const darkModeToggle = document.getElementById("darkModeToggle");
const vadThresholdInput = document.getElementById("vadThreshold");
const vadThresholdVal = document.getElementById("vadThresholdVal");
const silenceDurationInput = document.getElementById("silenceDuration");
const silenceDurationVal = document.getElementById("silenceDurationVal");
const ttsSpeedInput = document.getElementById("ttsSpeed");
const ttsSpeedVal = document.getElementById("ttsSpeedVal");

// State Variables
let running = false;
let micStream = null;
let audioCtx = null;
let analyser = null;
let micSource = null;
let mediaRecorder = null;
let audioChunks = [];
let isSpeaking = false;
let speechDetected = false;
let silenceStart = null;
let vadAnimationId = null;

// Configuration Defaults
let vadThreshold = parseFloat(vadThresholdInput.value);
let silenceDuration = parseInt(silenceDurationInput.value);
let ttsSpeed = parseFloat(ttsSpeedInput.value);

// Session Management
let sessionId = sessionStorage.getItem("gram_belle_session_id");
if (!sessionId) {
  sessionId = "session_" + Math.random().toString(36).substring(2, 11);
  sessionStorage.setItem("gram_belle_session_id", sessionId);
}

// ----------------------------------------------------
// Sidebar Navigation & Toggle Controls
// ----------------------------------------------------

function openSidebar(sidebar) {
  sidebar.classList.add("open");
  sidebarsOverlay.classList.add("visible");
}

function closeAllSidebars() {
  settingsSidebar.classList.remove("open");
  feedbackSidebar.classList.remove("open");
  sidebarsOverlay.classList.remove("visible");
}

settingsToggleBtn.addEventListener("click", () => {
  if (settingsSidebar.classList.contains("open")) {
    closeAllSidebars();
  } else {
    closeAllSidebars();
    openSidebar(settingsSidebar);
  }
});

feedbackToggleBtn.addEventListener("click", () => {
  if (feedbackSidebar.classList.contains("open")) {
    closeAllSidebars();
  } else {
    closeAllSidebars();
    openSidebar(feedbackSidebar);
    // Clear notification dot when feedback is viewed
    feedbackDot.style.display = "none";
  }
});

settingsCloseBtn.addEventListener("click", closeAllSidebars);
feedbackCloseBtn.addEventListener("click", closeAllSidebars);
sidebarsOverlay.addEventListener("click", closeAllSidebars);

// ----------------------------------------------------
// Settings & Theme Preferences
// ----------------------------------------------------

// Load and handle Dark Theme
const savedTheme = localStorage.getItem("theme") || "light";
if (savedTheme === "dark") {
  document.body.classList.add("dark-theme");
  darkModeToggle.checked = true;
}

darkModeToggle.addEventListener("change", (e) => {
  if (e.target.checked) {
    document.body.classList.add("dark-theme");
    localStorage.setItem("theme", "dark");
  } else {
    document.body.classList.remove("dark-theme");
    localStorage.setItem("theme", "light");
  }
});

// Update Sliders in UI
vadThresholdInput.addEventListener("input", (e) => {
  vadThreshold = parseFloat(e.target.value);
  vadThresholdVal.textContent = vadThreshold.toFixed(3);
});

silenceDurationInput.addEventListener("input", (e) => {
  silenceDuration = parseInt(e.target.value);
  silenceDurationVal.textContent = silenceDuration + "ms";
});

ttsSpeedInput.addEventListener("input", (e) => {
  ttsSpeed = parseFloat(e.target.value);
  ttsSpeedVal.textContent = ttsSpeed.toFixed(1) + "x";
});

// Reset Session
resetSessionBtn.addEventListener("click", async () => {
  if (confirm("Are you sure you want to clear Gram Belle's memory for this session?")) {
    try {
      await fetch(`/reset?session_id=${sessionId}`, { method: "POST" });
      timelineEl.innerHTML = '<li class="timeline-empty-state">Memory reset. Start speaking to log new transcripts.</li>';
      dashboardEmptyState.style.display = "flex";
      dashboardContent.style.display = "none";
      addTimelineItem("sys", "Memory cleared.");
      closeAllSidebars();
    } catch (err) {
      alert("Failed to reset session: " + err.message);
    }
  }
});

// ----------------------------------------------------
// Helper Functions
// ----------------------------------------------------

function setOrbState(state) {
  orbBtn.className = "glass-bubble-orb";
  statusDot.className = "pulse-dot";
  orbGlow.className = "orb-glow-layer";
  
  if (state === "idle") {
    orbBtn.classList.add("orb-idle");
    statusDot.classList.add("state-idle");
    orbGlow.classList.add("state-idle");
    statusText.textContent = "Click bubble to start";
  } else if (state === "listening") {
    orbBtn.classList.add("orb-recording");
    statusDot.classList.add("state-listening");
    orbGlow.classList.add("state-listening");
    statusText.textContent = "Listening... speak now";
  } else if (state === "working") {
    orbBtn.classList.add("orb-working");
    statusDot.classList.add("state-working");
    orbGlow.classList.add("state-working");
    statusText.textContent = "Thinking and analyzing...";
  } else if (state === "speaking") {
    orbBtn.classList.add("orb-speaking");
    statusDot.classList.add("state-speaking");
    orbGlow.classList.add("state-speaking");
    statusText.textContent = "Gram Belle speaking";
  } else if (state === "error") {
    orbBtn.classList.add("orb-idle");
    statusDot.classList.add("state-error");
    orbGlow.classList.add("state-idle");
    statusText.textContent = "Error. Click to retry.";
  }
}

function addTimelineItem(role, text) {
  const empty = timelineEl.querySelector(".timeline-empty-state");
  if (empty) empty.remove();

  const li = document.createElement("li");
  li.className = `role-${role}`;

  const meta = document.createElement("div");
  meta.className = "timeline-meta";
  meta.textContent = role === "user" ? "You" : role === "bot" ? "Gram Belle" : "System";

  const content = document.createElement("div");
  content.className = "timeline-content";
  content.textContent = text;

  li.appendChild(meta);
  li.appendChild(content);
  timelineEl.appendChild(li);

  // Scroll
  const container = timelineEl.parentElement;
  container.scrollTop = container.scrollHeight;
}

function getSelectedTtsEngine() {
  const selected = document.querySelector('input[name="tts_engine"]:checked');
  return selected ? selected.value : "browser";
}

function base64ToBlob(base64Data, mimeType) {
  const binary = atob(base64Data);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) {
    bytes[i] = binary.charCodeAt(i);
  }
  return new Blob([bytes], { type: mimeType });
}

// ----------------------------------------------------
// Voice Activity Detection (VAD) Loop
// ----------------------------------------------------

function startVadLoop() {
  const bufferLength = analyser.frequencyBinCount;
  const dataArray = new Uint8Array(bufferLength);
  
  isSpeaking = false;
  speechDetected = false;
  silenceStart = null;

  function checkAudio() {
    if (!running) return;

    analyser.getByteTimeDomainData(dataArray);
    
    // Calculate RMS energy
    let sum = 0;
    for (let i = 0; i < bufferLength; i++) {
      let dev = (dataArray[i] - 128) / 128;
      sum += dev * dev;
    }
    const rms = Math.sqrt(sum / bufferLength);

    // Dynamic scale feedback for Frutiger Aero Bubble Orb
    if (running && mediaRecorder && mediaRecorder.state === "recording") {
      const scale = 1 + rms * 3.8;
      const opacity = Math.min(0.9, 0.25 + rms * 5);
      orbBtn.style.transform = `scale(${scale})`;
      orbGlow.style.transform = `scale(${scale * 1.35})`;
      orbGlow.style.opacity = `${opacity}`;
    }

    const now = Date.now();
    if (rms > vadThreshold) {
      if (!isSpeaking) {
        isSpeaking = true;
        speechDetected = true;
      }
      silenceStart = null;
    } else {
      if (isSpeaking) {
        if (!silenceStart) {
          silenceStart = now;
        } else if (now - silenceStart > silenceDuration) {
          isSpeaking = false;
          silenceStart = null;
          stopAndProcessTurn();
          return;
        }
      }
    }

    vadAnimationId = requestAnimationFrame(checkAudio);
  }

  checkAudio();
}

function stopVadLoop() {
  if (vadAnimationId) {
    cancelAnimationFrame(vadAnimationId);
    vadAnimationId = null;
  }
  orbBtn.style.transform = "";
  orbGlow.style.transform = "";
  orbGlow.style.opacity = "";
}

// ----------------------------------------------------
// Audio Recording & API Calls
// ----------------------------------------------------

async function ensureMic() {
  if (!micStream) {
    micStream = await navigator.mediaDevices.getUserMedia({
      audio: {
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
      },
    });
  }

  if (!audioCtx) {
    audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    analyser = audioCtx.createAnalyser();
    analyser.fftSize = 512;
    micSource = audioCtx.createMediaStreamSource(micStream);
    micSource.connect(analyser);
  }
}

async function startRecordingTurn() {
  if (!running) return;

  try {
    await ensureMic();
    audioChunks = [];
    
    let mimeType = "audio/webm";
    if (MediaRecorder.isTypeSupported("audio/webm;codecs=opus")) {
      mimeType = "audio/webm;codecs=opus";
    } else if (MediaRecorder.isTypeSupported("audio/mp4")) {
      mimeType = "audio/mp4";
    }

    mediaRecorder = new MediaRecorder(micStream, { mimeType });
    
    mediaRecorder.ondataavailable = (event) => {
      if (event.data && event.data.size > 0) {
        audioChunks.push(event.data);
      }
    };

    mediaRecorder.onstop = () => {
      stopVadLoop();
      if (!running) return;

      const audioBlob = new Blob(audioChunks, { type: mimeType });
      if (speechDetected && audioBlob.size > 2000) {
        processTurn(audioBlob, mimeType);
      } else {
        addTimelineItem("sys", "No speech detected. Listening again...");
        startRecordingTurn();
      }
    };

    setOrbState("listening");
    mediaRecorder.start(200);
    startVadLoop();

  } catch (err) {
    console.error("Mic access failed:", err);
    addTimelineItem("sys", "Microphone access failed: " + err.message);
    stopConversation();
    setOrbState("error");
  }
}

function stopAndProcessTurn() {
  if (mediaRecorder && mediaRecorder.state === "recording") {
    mediaRecorder.stop();
  }
}

async function processTurn(audioBlob, mimeType) {
  setOrbState("working");
  
  const ext = mimeType.includes("mp4") ? "m4a" : mimeType.includes("ogg") ? "ogg" : "webm";
  const formData = new FormData();
  formData.append("file", audioBlob, `voice.${ext}`);

  const engine = getSelectedTtsEngine();

  try {
    const response = await fetch(`/talk?session_id=${sessionId}&tts_engine=${engine}`, {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      throw new Error(`Server status ${response.status}`);
    }

    const payload = await response.json();
    
    if (!payload.transcript || !payload.transcript.trim()) {
      addTimelineItem("sys", "No speech detected in query.");
      startRecordingTurn();
      return;
    }

    // Timeline Logging
    addTimelineItem("user", payload.transcript);
    addTimelineItem("bot", payload.roast);

    // Update Dashboard Analysis
    dashboardEmptyState.style.display = "none";
    dashboardContent.style.display = "flex";
    cardRoast.textContent = `"${payload.roast}"`;
    
    let hasCorrection = false;
    if (payload.original_error) {
      cardOriginal.textContent = payload.original_error;
      cardOriginal.parentElement.style.display = "flex";
      hasCorrection = true;
    } else {
      cardOriginal.parentElement.style.display = "none";
    }

    if (payload.correction) {
      cardCorrection.textContent = payload.correction;
      cardCorrection.parentElement.style.display = "flex";
      hasCorrection = true;
    } else {
      cardCorrection.parentElement.style.display = "none";
    }

    cardExplanation.textContent = payload.explanation || "Your grammar was flawless. Absolutely unimpressed.";
    cardChallenge.textContent = payload.challenge || "Move on.";

    // Trigger Notification badge if right sidebar is closed
    if (hasCorrection && !feedbackSidebar.classList.contains("open")) {
      feedbackDot.style.display = "inline-block";
    }

    // Play TTS response
    await playTTS(payload);

  } catch (err) {
    console.error("Pipeline turn error:", err);
    addTimelineItem("sys", "Failed to get reply: " + err.message);
    setOrbState("error");
    running = false;
  }
}

// ----------------------------------------------------
// TTS Outputs
// ----------------------------------------------------

async function playTTS(payload) {
  if (!running) return;
  setOrbState("speaking");

  const engine = getSelectedTtsEngine();

  if (engine === "browser") {
    await speakWithBrowser(payload.roast, payload.correction, payload.challenge);
  } else {
    if (payload.audio_base64) {
      const mime = payload.audio_mime || "audio/wav";
      const blob = base64ToBlob(payload.audio_base64, mime);
      const url = URL.createObjectURL(blob);
      replyAudioEl.src = url;

      await new Promise((resolve) => {
        replyAudioEl.onended = () => {
          URL.revokeObjectURL(url);
          resolve();
        };
        replyAudioEl.onerror = () => {
          URL.revokeObjectURL(url);
          resolve();
        };
        replyAudioEl.play().catch(resolve);
      });
    } else {
      console.warn("TTS base64 missing, falling back to browser synthesis.");
      await speakWithBrowser(payload.roast, payload.correction, payload.challenge);
    }
  }

  // Next loop turn
  if (running) {
    startRecordingTurn();
  } else {
    setOrbState("idle");
  }
}

function speakWithBrowser(roast, correction, challenge) {
  return new Promise((resolve) => {
    if (!("speechSynthesis" in window)) {
      resolve();
      return;
    }

    let text = roast || "";
    if (correction) {
      text += `. You should say: ${correction}.`;
    }
    if (challenge) {
      text += ` ${challenge}`;
    }

    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = ttsSpeed;
    
    const voices = window.speechSynthesis.getVoices();
    const preferred = voices.find((v) => v.lang.startsWith("en-US") && v.name.includes("Google")) ||
                      voices.find((v) => v.lang.startsWith("en-")) ||
                      voices[0];
    
    if (preferred) {
      utterance.voice = preferred;
    }

    utterance.onend = () => resolve();
    utterance.onerror = () => resolve();

    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(utterance);
  });
}

// ----------------------------------------------------
// Conversation Setup Activators
// ----------------------------------------------------

async function startConversation() {
  if (running) return;
  running = true;
  addTimelineItem("sys", "Gram Belle listening. Start speaking.");
  startRecordingTurn();
}

function stopConversation() {
  running = false;
  stopVadLoop();
  
  if (mediaRecorder && mediaRecorder.state !== "inactive") {
    mediaRecorder.stop();
  }

  if ("speechSynthesis" in window) {
    window.speechSynthesis.cancel();
  }

  if (!replyAudioEl.paused) {
    replyAudioEl.pause();
  }

  setOrbState("idle");
  addTimelineItem("sys", "Gram Belle stopped.");
}

// Click listener
orbBtn.addEventListener("click", () => {
  if (!running) {
    startConversation();
  } else {
    stopConversation();
  }
});

// Cache browser voices
if ("speechSynthesis" in window) {
  window.speechSynthesis.getVoices();
}

// Check server status (e.g. if local XTTS is enabled)
async function checkServerStatus() {
  try {
    const res = await fetch("/status");
    if (res.ok) {
      const data = await res.json();
      if (!data.local_xtts_enabled) {
        // Find the Local XTTS radio option container and hide it
        const xttsRadio = document.querySelector('input[name="tts_engine"][value="local_xtts"]');
        if (xttsRadio) {
          const optionContainer = xttsRadio.closest('label');
          if (optionContainer) {
            optionContainer.style.display = "none";
          }
        }
      }
    }
  } catch (err) {
    console.warn("Failed to fetch server status:", err);
  }
}
checkServerStatus();

