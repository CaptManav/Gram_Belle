import os
import sounddevice as sd
import numpy as np
import soundfile as sf
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI()

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

print("🧠 Transcribing...")

audio_file = open("speech.wav", "rb")

transcript = client.audio.transcriptions.create(
    file=audio_file,
    model="whisper-1"
)

print("📝 You said:")
print(transcript.text)
