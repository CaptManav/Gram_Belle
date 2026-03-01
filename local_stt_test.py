import sounddevice as sd
import numpy as np
import soundfile as sf
from faster_whisper import WhisperModel

SAMPLE_RATE = 16000
DURATION = 5  # seconds

print("🎤 Speak for 5 seconds...")

recording = sd.rec(
    int(DURATION * SAMPLE_RATE),
    samplerate=SAMPLE_RATE,
    channels=1,
    dtype="float32"
)
sd.wait()

sf.write("speech.wav", recording, SAMPLE_RATE)

print("🧠 Loading model...")
model = WhisperModel("base", device="cpu", compute_type="int8")

print("📝 Transcribing...")
segments, info = model.transcribe("speech.wav")

text = ""
for segment in segments:
    text += segment.text

print("\n✅ You said:")
print(text.strip())
