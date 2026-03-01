import os
import base64
import tempfile
from pathlib import Path
import requests
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
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
BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR / "frontend"

FORMAT_BY_SUFFIX = {
    ".wav": "wav",
    ".mp3": "mp3",
    ".m4a": "mp4",
    ".mp4": "mp4",
    ".ogg": "ogg",
    ".webm": "webm",
    ".flac": "flac",
}

SUFFIX_BY_CONTENT_TYPE = {
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
    "audio/mpeg": ".mp3",
    "audio/mp3": ".mp3",
    "audio/mp4": ".m4a",
    "audio/aac": ".m4a",
    "audio/ogg": ".ogg",
    "audio/webm": ".webm",
    "video/webm": ".webm",
    "audio/flac": ".flac",
}

if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

def groq_headers():
    return {
        "Authorization": f"Bearer {GROQ_API_KEY}",
    }

def resolve_suffix(upload: UploadFile) -> str:
    suffix = Path(upload.filename or "").suffix.lower()
    if suffix in FORMAT_BY_SUFFIX:
        return suffix

    content_type = (upload.content_type or "").split(";")[0].strip().lower()
    return SUFFIX_BY_CONTENT_TYPE.get(content_type, ".webm")

def ensure_wav(in_path: str, in_suffix: str) -> str:
    input_format = FORMAT_BY_SUFFIX.get(in_suffix)
    fd, wav_path = tempfile.mkstemp(suffix=".wav")
    os.close(fd)

    audio = AudioSegment.from_file(in_path, format=input_format)
    audio.export(wav_path, format="wav")
    return wav_path

@app.get("/")
def home():
    index_path = FRONTEND_DIR / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="Frontend file not found.")
    return FileResponse(index_path)

@app.get("/health")
def health():
    return {"ok": True}

@app.post("/talk")
async def talk(file: UploadFile = File(...)):
    in_path = None
    wav_path = None

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Uploaded audio file is empty.")

    in_suffix = resolve_suffix(file)

    try:
        # 1) Save uploaded audio
        with tempfile.NamedTemporaryFile(delete=False, suffix=in_suffix) as src_file:
            src_file.write(data)
            in_path = src_file.name

        # Convert to wav (Whisper likes wav)
        wav_path = ensure_wav(in_path, in_suffix)

        # 2) Speech-to-Text (Whisper via Groq)
        with open(wav_path, "rb") as wav_file:
            stt = requests.post(
                f"{GROQ_BASE}/audio/transcriptions",
                headers=groq_headers(),
                files={"file": ("speech.wav", wav_file, "audio/wav")},
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
            "transcript": user_text,
            "text": reply_text,
            "audio_base64": audio_b64,
        }

    except requests.RequestException as exc:
        detail = str(exc)
        if getattr(exc, "response", None) is not None and exc.response is not None:
            detail = f"{detail}. {exc.response.text[:280]}"
        raise HTTPException(status_code=502, detail=f"Upstream API error: {detail}") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Audio pipeline failed: {exc}") from exc
    finally:
        for path in [in_path, wav_path]:
            if path and os.path.exists(path):
                os.remove(path)
