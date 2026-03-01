const startBtn = document.getElementById("startBtn");
const stopBtn = document.getElementById("stopBtn");
const statusDot = document.getElementById("statusDot");
const statusText = document.getElementById("statusText");
const userTextEl = document.getElementById("userText");
const botTextEl = document.getElementById("botText");
const timelineEl = document.getElementById("timeline");
const replyAudioEl = document.getElementById("replyAudio");

const TURN_SECONDS = 10;
const TURN_MS = TURN_SECONDS * 1000;
const MIN_AUDIO_BYTES = 1400;

let micStream = null;
let running = false;
let activeRecorder = null;
let hasShownAudioNotice = false;
let lastAudioUrl = null;

function setStatus(message, mode) {
  statusText.textContent = message;
  statusDot.className = "status-dot";
  statusDot.classList.add(`status-${mode}`);
}

function addTimeline(role, text) {
  const item = document.createElement("li");
  const tag = document.createElement("span");
  const body = document.createElement("p");

  tag.className = "timeline-tag";
  body.className = "timeline-text";

  tag.textContent = role;
  body.textContent = text;

  item.appendChild(tag);
  item.appendChild(body);
  timelineEl.prepend(item);
}

function sleep(ms) {
  return new Promise((resolve) => {
    setTimeout(resolve, ms);
  });
}

function pickMimeType() {
  if (!window.MediaRecorder) {
    return "";
  }

  const preferred = [
    "audio/webm;codecs=opus",
    "audio/webm",
    "audio/mp4",
    "audio/ogg;codecs=opus",
    "audio/ogg",
  ];

  for (const mimeType of preferred) {
    if (MediaRecorder.isTypeSupported(mimeType)) {
      return mimeType;
    }
  }
  return "";
}

function mimeToExtension(mimeType) {
  const lowered = (mimeType || "").toLowerCase();
  if (lowered.includes("webm")) {
    return "webm";
  }
  if (lowered.includes("ogg")) {
    return "ogg";
  }
  if (lowered.includes("mp4") || lowered.includes("m4a")) {
    return "m4a";
  }
  if (lowered.includes("wav")) {
    return "wav";
  }
  return "webm";
}

function base64ToBlob(base64Data, mimeType) {
  const binary = atob(base64Data);
  const bytes = new Uint8Array(binary.length);

  for (let i = 0; i < binary.length; i += 1) {
    bytes[i] = binary.charCodeAt(i);
  }
  return new Blob([bytes], { type: mimeType });
}

async function ensureMic() {
  if (micStream) {
    return;
  }

  micStream = await navigator.mediaDevices.getUserMedia({
    audio: {
      echoCancellation: true,
      noiseSuppression: true,
      autoGainControl: true,
    },
  });
}

async function recordTurn(durationMs) {
  const mimeType = pickMimeType();
  const chunks = [];
  const recorder = mimeType
    ? new MediaRecorder(micStream, { mimeType })
    : new MediaRecorder(micStream);

  activeRecorder = recorder;

  const stopped = new Promise((resolve, reject) => {
    recorder.addEventListener("dataavailable", (event) => {
      if (event.data && event.data.size > 0) {
        chunks.push(event.data);
      }
    });

    recorder.addEventListener("error", (event) => {
      reject(event.error || new Error("Recording failed."));
    });

    recorder.addEventListener("stop", () => {
      const finalMimeType = recorder.mimeType || mimeType || "audio/webm";
      resolve({
        blob: new Blob(chunks, { type: finalMimeType }),
        mimeType: finalMimeType,
      });
    });
  });

  setStatus(`Listening... (${TURN_SECONDS}s turn)`, "listening");
  recorder.start(250);
  const endedBy = await Promise.race([
    sleep(durationMs).then(() => "timer"),
    stopped.then(() => "stopped"),
  ]);

  if (endedBy === "timer" && recorder.state !== "inactive") {
    recorder.stop();
  }

  const result = await stopped;
  if (activeRecorder === recorder) {
    activeRecorder = null;
  }
  return result;
}

async function speakWithBrowser(text) {
  const cleaned = (text || "").trim();
  if (!cleaned || !("speechSynthesis" in window) || !("SpeechSynthesisUtterance" in window)) {
    return false;
  }

  setStatus("Speaking (browser fallback)...", "speaking");
  const voices = window.speechSynthesis.getVoices();
  const preferred = voices.find((voice) => /^en(-|_)/i.test(voice.lang)) || voices[0];

  return new Promise((resolve) => {
    const utterance = new SpeechSynthesisUtterance(cleaned);
    if (preferred) {
      utterance.voice = preferred;
    }
    utterance.rate = 1;
    utterance.pitch = 1;
    utterance.volume = 1;

    utterance.onend = () => resolve(true);
    utterance.onerror = () => resolve(false);

    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(utterance);
  });
}

async function playReply(payload, replyText) {
  if (payload.audio_base64) {
    const replyBlob = base64ToBlob(payload.audio_base64, "audio/wav");
    if (lastAudioUrl) {
      URL.revokeObjectURL(lastAudioUrl);
    }
    lastAudioUrl = URL.createObjectURL(replyBlob);
    replyAudioEl.src = lastAudioUrl;

    setStatus("Speaking...", "speaking");
    await new Promise((resolve) => {
      replyAudioEl.onended = () => resolve();
      replyAudioEl.onerror = () => resolve();
      replyAudioEl.play().catch(() => resolve());
    });
    return;
  }

  const spoke = await speakWithBrowser(replyText);
  if (!spoke && payload.audio_error) {
    if (!hasShownAudioNotice) {
      addTimeline("Audio", payload.audio_error);
      hasShownAudioNotice = true;
    }
  }
}

async function processTurn(audioBlob, mimeType) {
  setStatus("Transcribing and thinking...", "working");

  const extension = mimeToExtension(mimeType);
  const formData = new FormData();
  formData.append("file", audioBlob, `voice.${extension}`);

  const response = await fetch("/talk", {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const details = (await response.text()).slice(0, 280);
    throw new Error(`Server returned ${response.status}. ${details}`);
  }

  const payload = await response.json();
  const transcript = (payload.transcript || payload.user_text || "").trim();
  const replyText = (payload.text || "").trim();

  if (!transcript) {
    addTimeline("System", "No speech detected in this turn.");
    return;
  }

  userTextEl.classList.remove("placeholder");
  userTextEl.textContent = transcript;

  botTextEl.classList.remove("placeholder");
  botTextEl.textContent = replyText || "No response text returned.";

  addTimeline("You", transcript);
  addTimeline("Assistant", replyText || "No response text returned.");

  await playReply(payload, replyText);
}

function setControls(isRunning) {
  startBtn.disabled = isRunning;
  stopBtn.disabled = !isRunning;
  startBtn.classList.toggle("running", isRunning);
}

async function conversationLoop() {
  while (running) {
    let turnRecording;
    try {
      turnRecording = await recordTurn(TURN_MS);
    } catch (error) {
      addTimeline("Error", error.message || "Recording failed.");
      setStatus("Recording failed.", "error");
      running = false;
      break;
    }

    if (!running) {
      break;
    }

    if (!turnRecording || !turnRecording.blob || turnRecording.blob.size < MIN_AUDIO_BYTES) {
      addTimeline("System", "Too little audio captured. Listening again.");
      continue;
    }

    try {
      await processTurn(turnRecording.blob, turnRecording.mimeType);
    } catch (error) {
      addTimeline("Error", error.message || "Turn failed.");
      setStatus("Turn failed. Retrying...", "error");
      await sleep(600);
    }
  }

  setControls(false);
  setStatus("Idle", "idle");
}

async function startConversation() {
  if (running) {
    return;
  }

  try {
    await ensureMic();
  } catch (error) {
    setStatus("Microphone access failed.", "error");
    addTimeline("Error", "Microphone permission was denied.");
    return;
  }

  running = true;
  setControls(true);
  addTimeline("System", "Continuous conversation started.");
  conversationLoop();
}

function stopConversation() {
  running = false;
  setStatus("Stopping...", "working");

  if (activeRecorder && activeRecorder.state !== "inactive") {
    activeRecorder.stop();
  }

  if ("speechSynthesis" in window) {
    window.speechSynthesis.cancel();
  }

  if (!replyAudioEl.paused) {
    replyAudioEl.pause();
  }
}

startBtn.addEventListener("click", () => {
  startConversation();
});

stopBtn.addEventListener("click", () => {
  stopConversation();
});

window.addEventListener("beforeunload", () => {
  stopConversation();
  if (micStream) {
    for (const track of micStream.getTracks()) {
      track.stop();
    }
  }
});

setControls(false);
setStatus("Idle", "idle");
