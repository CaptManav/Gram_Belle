import os
import time
import tempfile
import subprocess
import torch

# 🔓 Fix PyTorch 2.6+ checkpoint safety for XTTS
from TTS.tts.models.xtts import XttsAudioConfig
from TTS.tts.configs.xtts_config import XttsConfig
torch.serialization.add_safe_globals([XttsAudioConfig, XttsConfig])

import sounddevice as sd
import soundfile as sf
from faster_whisper import WhisperModel
from TTS.api import TTS

from brain_gemini import reply

print("🎤 Loading XTTS model (GPU)...")
tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2", gpu=True)
tts = tts.to("cuda")
print("✅ XTTS ready.")



# ✅ Pick a valid built-in speaker automatically
# 🔎 Get a valid speaker ID from XTTS internals
speaker_manager = tts.synthesizer.tts_model.speaker_manager
DEFAULT_SPEAKER = list(speaker_manager.speakers.keys())[0]
print("🎙️ Using speaker:", DEFAULT_SPEAKER)

SAMPLE_RATE = 16000
DURATION = 10  # seconds to speak each turn

print("🧠 Loading Whisper model...")
model = WhisperModel("base", device="cuda", compute_type="float16")
print("✅ Model ready.")

def clean_text(t):
    for ch in ["*", "_", "#", "`"]:
        t = t.replace(ch, "")
    return t.strip()

def speak(text):
    print("🤖:", text)
    text = clean_text(text)

    out_path = "xtts_out.wav"

    tts.tts_to_file(
        text=text,
        file_path=out_path,
        speaker=DEFAULT_SPEAKER,  # ✅ ALWAYS valid
        language="en"
    )

    data, sr = sf.read(out_path)
    sd.play(data, sr)
    sd.wait()

# Greet once
speak("Hello. I'm ready. Talk to me.")

while True:
    print("\n🎤 Speak now...")

    recording = sd.rec(
        int(DURATION * SAMPLE_RATE),
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="float32"
    )
    sd.wait()

    sf.write("speech.wav", recording, SAMPLE_RATE)

    print("📝 Transcribing...")
    segments, info = model.transcribe("speech.wav")

    user_text = ""
    for segment in segments:
        user_text += segment.text

    user_text = user_text.strip()
    print("🧪 RAW TEXT:", repr(user_text))

    if len(user_text) < 3:
        print("🤷 Didn't catch anything useful.")
        continue

    print("🧑 You said:", user_text)

    response = reply(user_text)
    speak(response)

def run_agent(text: str):
    # TODO: replace these with your existing steps:
    # 1) LLM reply (Groq)
    # 2) (Optional) TTS with XTTS on GPU
    # For now, return text so the app works end-to-end.

    from brain_gemini import reply
    return reply(text)
