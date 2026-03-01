import os
import base64
import tempfile
import requests
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydub import AudioSegment

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise RuntimeError("GROQ_API_KEY is not set")

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

GROQ_BASE = "https://api.groq.com/openai/v1"

def groq_headers():
    return {
        "Authorization": f"Bearer {GROQ_API_KEY}",
    }

@app.post("/talk")
async def talk(file: UploadFile = File(...)):
    # 1) Save uploaded audio
    data = await file.read()
    with tempfile.NamedTemporaryFile(delete=False, suffix=".m4a") as f:
        f.write(data)
        in_path = f.name

    # Convert to wav (Whisper likes wav)
    wav_path = in_path + ".wav"
    AudioSegment.from_file(in_path).export(wav_path, format="wav")

    # 2) Speech-to-Text (Whisper via Groq)
    with open(wav_path, "rb") as f:
        stt = requests.post(
            f"{GROQ_BASE}/audio/transcriptions",
            headers=groq_headers(),
            files={"file": f},
            data={"model": "whisper-large-v3"},
            timeout=60,
        )
    stt.raise_for_status()
    user_text = stt.json()["text"]

    # 3) LLM reply
    chat = requests.post(
        f"{GROQ_BASE}/chat/completions",
        headers={**groq_headers(), "Content-Type": "application/json"},
        json={
            "model": "llama-3.1-8b-instant",
            "messages": [
                {"role": "system", "content": "You are a helpful voice assistant. Keep replies short and clear."},
                {"role": "user", "content": user_text},
            ],
            "temperature": 0.6,
        },
        timeout=60,
    )
    chat.raise_for_status()
    reply_text = chat.json()["choices"][0]["message"]["content"]

    # 4) Text-to-Speech (simple, fast cloud TTS using a public API)
    # Using ElevenLabs-style free endpoint substitute: StreamElements TTS
    tts = requests.get(
        "https://api.streamelements.com/kappa/v2/speech",
        params={"voice": "Brian", "text": reply_text},
        timeout=60,
    )
    tts.raise_for_status()
    wav_bytes = tts.content

    audio_b64 = base64.b64encode(wav_bytes).decode("utf-8")

    return {
        "text": reply_text,
        "audio_base64": audio_b64,
    }
