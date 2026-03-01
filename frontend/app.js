const recordBtn = document.getElementById("recordBtn");
const statusDot = document.getElementById("statusDot");
const statusText = document.getElementById("statusText");
const userTextEl = document.getElementById("userText");
const botTextEl = document.getElementById("botText");
const timelineEl = document.getElementById("timeline");
const replyAudioEl = document.getElementById("replyAudio");
const apiBaseInput = document.getElementById("apiBaseUrl");

let mediaRecorder = null;
let audioChunks = [];
let micStream = null;
let isRecording = false;
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

function normalizeBaseUrl() {
  const raw = apiBaseInput.value.trim();
  if (!raw) {
    return "";
  }
  return raw.replace(/\/+$/, "");
}

function buildEndpoint(path) {
  const base = normalizeBaseUrl();
  return base ? `${base}${path}` : path;
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

function resetMic() {
  if (micStream) {
    for (const track of micStream.getTracks()) {
      track.stop();
    }
  }

  micStream = null;
  mediaRecorder = null;
  audioChunks = [];
}

async function sendRecording(audioBlob, mimeType) {
  setStatus("Sending audio...", "working");

  const extension = mimeToExtension(mimeType);
  const formData = new FormData();
  formData.append("file", audioBlob, `voice.${extension}`);

  const response = await fetch(buildEndpoint("/talk"), {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const details = (await response.text()).slice(0, 200);
    throw new Error(`Server returned ${response.status}. ${details}`);
  }

  const payload = await response.json();
  const transcript = (payload.transcript || payload.user_text || "").trim();
  const replyText = (payload.text || "").trim();

  userTextEl.classList.remove("placeholder");
  userTextEl.textContent = transcript || "Voice message sent.";

  botTextEl.classList.remove("placeholder");
  botTextEl.textContent = replyText || "No text response was returned.";

  addTimeline("You", transcript || "Voice message sent.");
  addTimeline("Assistant", replyText || "No response text.");

  if (payload.audio_base64) {
    const replyBlob = base64ToBlob(payload.audio_base64, "audio/wav");
    if (lastAudioUrl) {
      URL.revokeObjectURL(lastAudioUrl);
    }
    lastAudioUrl = URL.createObjectURL(replyBlob);
    replyAudioEl.src = lastAudioUrl;
    await replyAudioEl.play().catch(() => null);
  }

  setStatus("Done. Ready for next message.", "idle");
}

async function startRecording() {
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia || !window.MediaRecorder) {
    setStatus("This browser does not support audio recording.", "error");
    return;
  }

  try {
    micStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const mimeType = pickMimeType();
    mediaRecorder = mimeType
      ? new MediaRecorder(micStream, { mimeType })
      : new MediaRecorder(micStream);

    audioChunks = [];
    mediaRecorder.addEventListener("dataavailable", (event) => {
      if (event.data && event.data.size > 0) {
        audioChunks.push(event.data);
      }
    });

    mediaRecorder.addEventListener("stop", async () => {
      const finalMimeType = mimeType || mediaRecorder.mimeType || "audio/webm";
      const audioBlob = new Blob(audioChunks, { type: finalMimeType });

      try {
        await sendRecording(audioBlob, finalMimeType);
      } catch (error) {
        console.error(error);
        setStatus(error.message || "Failed to process recording.", "error");
        addTimeline("Error", error.message || "Failed to process recording.");
      } finally {
        recordBtn.disabled = false;
        resetMic();
      }
    });

    mediaRecorder.start(250);
    isRecording = true;
    recordBtn.textContent = "Stop and Send";
    recordBtn.classList.add("recording");
    setStatus("Recording... click again to send.", "recording");
  } catch (error) {
    console.error(error);
    resetMic();
    setStatus("Microphone access failed.", "error");
  }
}

function stopRecording() {
  if (!mediaRecorder || mediaRecorder.state === "inactive") {
    return;
  }

  isRecording = false;
  recordBtn.disabled = true;
  recordBtn.textContent = "Start Recording";
  recordBtn.classList.remove("recording");
  setStatus("Finalizing capture...", "working");
  mediaRecorder.stop();
}

recordBtn.addEventListener("click", async () => {
  if (isRecording) {
    stopRecording();
    return;
  }

  await startRecording();
});

setStatus("Idle", "idle");
