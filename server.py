import os
import base64
import tempfile
import time
import threading
import inspect
from pathlib import Path

import requests
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from brain import reply, clear_session_history

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise RuntimeError("GROQ_API_KEY is not set")

def env_float(name: str, default: float) -> float:
    raw = os.getenv(name, str(default)).strip()
    try:
        return float(raw)
    except Exception:
        return default

STREAMELEMENTS_API_KEY = os.getenv("STREAMELEMENTS_API_KEY", "").strip()
USE_LOCAL_XTTS = os.getenv("USE_LOCAL_XTTS", "1").strip().lower() not in {"0", "false", "no"}
XTTS_LANGUAGE = os.getenv("XTTS_LANGUAGE", "en").strip() or "en"
XTTS_PRELOAD_ON_START = os.getenv("XTTS_PRELOAD_ON_START", "1").strip().lower() not in {"0", "false", "no"}
XTTS_SPEED = max(0.8, min(2.0, env_float("XTTS_SPEED", 1.2)))

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

ALLOWED_AUDIO_SUFFIXES = {
    ".wav",
    ".mp3",
    ".m4a",
    ".mp4",
    ".ogg",
    ".webm",
    ".flac",
    ".mpeg",
    ".mpga",
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

_xtts_lock = threading.Lock()
_xtts_model = None
_xtts_speaker = None
_xtts_init_error = ""
_xtts_supports_speed = False

def groq_headers():
    return {
        "Authorization": f"Bearer {GROQ_API_KEY}",
    }

def resolve_suffix(upload: UploadFile) -> str:
    suffix = Path(upload.filename or "").suffix.lower()
    if suffix in ALLOWED_AUDIO_SUFFIXES:
        return suffix

    content_type = (upload.content_type or "").split(";")[0].strip().lower()
    return SUFFIX_BY_CONTENT_TYPE.get(content_type, ".webm")

def safe_unlink(path: str, retries: int = 8, delay_sec: float = 0.2) -> None:
    """
    Windows can keep temp files locked briefly after ffmpeg/pydub work completes.
    Retry unlink a few times before giving up.
    """
    for attempt in range(retries):
        try:
            os.remove(path)
            return
        except FileNotFoundError:
            return
        except PermissionError:
            if attempt == retries - 1:
                return
            time.sleep(delay_sec)

def format_request_error(exc: requests.RequestException) -> str:
    detail = str(exc)
    if getattr(exc, "response", None) is not None and exc.response is not None:
        detail = f"{detail}. {exc.response.text[:280]}"
    return detail

def clean_text_for_tts(text: str) -> str:
    cleaned = text
    for ch in ["*", "_", "#", "`"]:
        cleaned = cleaned.replace(ch, "")
    return cleaned.strip()

def get_xtts():
    global _xtts_model, _xtts_speaker, _xtts_init_error, _xtts_supports_speed

    if not USE_LOCAL_XTTS:
        return None, "", "Local XTTS is disabled (USE_LOCAL_XTTS=0)."

    if _xtts_model is not None:
        return _xtts_model, _xtts_speaker, ""

    if _xtts_init_error:
        return None, "", _xtts_init_error

    with _xtts_lock:
        if _xtts_model is not None:
            return _xtts_model, _xtts_speaker, ""

        if _xtts_init_error:
            return None, "", _xtts_init_error

        try:
            import torch
            from TTS.api import TTS
            from TTS.tts.models.xtts import XttsAudioConfig
            from TTS.tts.configs.xtts_config import XttsConfig

            # Keep compatibility with newer torch safe deserialization defaults.
            torch.serialization.add_safe_globals([XttsAudioConfig, XttsConfig])

            has_cuda = torch.cuda.is_available()
            if not has_cuda:
                _xtts_init_error = "Local XTTS requires CUDA GPU, but CUDA is not available."
                return None, "", _xtts_init_error

            model = TTS("tts_models/multilingual/multi-dataset/xtts_v2", gpu=True)
            model = model.to("cuda")
            speaker_manager = model.synthesizer.tts_model.speaker_manager
            speaker = list(speaker_manager.speakers.keys())[0]
            _xtts_supports_speed = "speed" in inspect.signature(model.tts_to_file).parameters

            _xtts_model = model
            _xtts_speaker = speaker
            return _xtts_model, _xtts_speaker, ""
        except Exception as exc:
            _xtts_init_error = f"Local XTTS init failed: {exc}"
            return None, "", _xtts_init_error

def synthesize_local_xtts(reply_text: str) -> tuple[str, str]:
    model, speaker, err = get_xtts()
    if err:
        return "", err

    out_fd, out_path = tempfile.mkstemp(suffix=".wav")
    os.close(out_fd)

    try:
        tts_kwargs = {
            "text": clean_text_for_tts(reply_text),
            "file_path": out_path,
            "speaker": speaker,
            "language": XTTS_LANGUAGE,
        }
        if _xtts_supports_speed:
            tts_kwargs["speed"] = XTTS_SPEED

        model.tts_to_file(**tts_kwargs)
        with open(out_path, "rb") as audio_file:
            wav_bytes = audio_file.read()

        if not wav_bytes:
            return "", "Local XTTS returned empty audio."

        return base64.b64encode(wav_bytes).decode("utf-8"), ""
    except Exception as exc:
        return "", f"Local XTTS synthesis failed: {exc}"
    finally:
        safe_unlink(out_path)

async def synthesize_edge_tts(reply_text: str) -> tuple[str, str]:
    try:
        import edge_tts
        
        voice = "en-US-EmmaNeural"
        communicate = edge_tts.Communicate(clean_text_for_tts(reply_text), voice)
        
        out_fd, out_path = tempfile.mkstemp(suffix=".mp3")
        os.close(out_fd)
        
        try:
            await communicate.save(out_path)
            with open(out_path, "rb") as audio_file:
                mp3_bytes = audio_file.read()
            if not mp3_bytes:
                return "", "Edge TTS returned empty audio."
            return base64.b64encode(mp3_bytes).decode("utf-8"), ""
        finally:
            safe_unlink(out_path)
    except Exception as exc:
        return "", f"Edge TTS synthesis failed: {exc}"

def synthesize_tts(reply_text: str) -> tuple[str, str]:
    """
    Fallback legacy StreamElements cloud TTS.
    """
    if not STREAMELEMENTS_API_KEY:
        return "", "Cloud TTS disabled: missing STREAMELEMENTS_API_KEY."

    try:
        tts = requests.get(
            "https://api.streamelements.com/kappa/v2/speech",
            headers={
                "Authorization": f"Bearer {STREAMELEMENTS_API_KEY}",
                "x-api-key": STREAMELEMENTS_API_KEY,
            },
            params={"voice": "Brian", "text": reply_text},
            timeout=60,
        )
        tts.raise_for_status()
        wav_bytes = tts.content
        if not wav_bytes:
            return "", "TTS provider returned empty audio."
        return base64.b64encode(wav_bytes).decode("utf-8"), ""
    except requests.RequestException as exc:
        return "", f"TTS unavailable: {format_request_error(exc)}"

def preload_xtts_background() -> None:
    if not USE_LOCAL_XTTS or not XTTS_PRELOAD_ON_START:
        return

    def _worker():
        get_xtts()

    threading.Thread(target=_worker, name="xtts-preload", daemon=True).start()

@app.get("/")
def home():
    index_path = FRONTEND_DIR / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="Frontend file not found.")
    return FileResponse(index_path)

@app.get("/health")
def health():
    return {"ok": True}

@app.on_event("startup")
def startup_event():
    preload_xtts_background()

@app.post("/reset")
def reset_session(session_id: str = "default"):
    clear_session_history(session_id)
    return {"ok": True}

@app.post("/talk")
async def talk(
    file: UploadFile = File(...),
    session_id: str = "default",
    tts_engine: str = "browser"
):
    in_path = None
    t0 = time.perf_counter()

    data = await file.read()
    await file.close()
    if not data:
        raise HTTPException(status_code=400, detail="Uploaded audio file is empty.")

    in_suffix = resolve_suffix(file)

    try:
        # 1) Save uploaded audio
        with tempfile.NamedTemporaryFile(delete=False, suffix=in_suffix) as src_file:
            src_file.write(data)
            in_path = src_file.name

        # 2) Speech-to-Text (Whisper via Groq)
        content_type = (file.content_type or "application/octet-stream").split(";")[0].strip().lower()
        with open(in_path, "rb") as source_audio:
            stt = requests.post(
                f"{GROQ_BASE}/audio/transcriptions",
                headers=groq_headers(),
                files={"file": (f"speech{in_suffix}", source_audio, content_type)},
                data={"model": "whisper-large-v3"},
                timeout=60,
            )
        stt.raise_for_status()
        user_text = stt.json()["text"]
        t_stt = time.perf_counter()

        # 3) LLM reply
        response_data = reply(user_text, session_id)
        t_llm = time.perf_counter()

        roast = response_data.get("roast", "")
        correction = response_data.get("correction", "")
        challenge = response_data.get("challenge", "")

        # Build text to speak (excluding explanation to keep voice output punchy)
        read_parts = []
        if roast:
            read_parts.append(roast)
        if correction:
            read_parts.append(f"You should say: {correction}")
        if challenge:
            read_parts.append(challenge)
        tts_text = " ".join(read_parts)

        # 4) Text-to-Speech
        audio_b64 = ""
        audio_error = ""
        audio_mime = ""

        if tts_engine == "browser":
            # Browser will synthesize text on the client side using Web Speech API
            pass
        elif tts_engine == "edge_tts":
            audio_b64, audio_error = await synthesize_edge_tts(tts_text)
            audio_mime = "audio/mpeg"
        elif tts_engine == "local_xtts":
            audio_b64, audio_error = synthesize_local_xtts(tts_text)
            audio_mime = "audio/wav"
        else:
            # Server default fallback
            audio_b64, audio_error = synthesize_tts(tts_text)
            audio_mime = "audio/wav"

        t_tts = time.perf_counter()

        print(
            f"[talk] stt={t_stt - t0:.2f}s "
            f"llm={t_llm - t_stt:.2f}s "
            f"tts={t_tts - t_llm:.2f}s "
            f"total={t_tts - t0:.2f}s "
            f"engine={tts_engine} "
            f"reply_chars={len(tts_text)}"
        )

        return {
            "transcript": user_text,
            "roast": roast,
            "original_error": response_data.get("original_error", ""),
            "correction": correction,
            "explanation": response_data.get("explanation", ""),
            "challenge": challenge,
            "audio_base64": audio_b64,
            "audio_mime": audio_mime,
            "audio_error": audio_error,
        }

    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"Upstream API error: {format_request_error(exc)}") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Audio pipeline failed: {exc}") from exc
    finally:
        if in_path and os.path.exists(in_path):
            safe_unlink(in_path)
