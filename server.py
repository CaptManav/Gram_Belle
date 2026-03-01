import os
import base64
import tempfile
import time
import threading
from pathlib import Path

import requests
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from brain_gemini import reply

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise RuntimeError("GROQ_API_KEY is not set")

STREAMELEMENTS_API_KEY = os.getenv("STREAMELEMENTS_API_KEY", "").strip()
USE_LOCAL_XTTS = os.getenv("USE_LOCAL_XTTS", "1").strip().lower() not in {"0", "false", "no"}
XTTS_LANGUAGE = os.getenv("XTTS_LANGUAGE", "en").strip() or "en"

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
    global _xtts_model, _xtts_speaker, _xtts_init_error

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

            last_error = None
            for use_gpu in [torch.cuda.is_available(), False]:
                try:
                    model = TTS("tts_models/multilingual/multi-dataset/xtts_v2", gpu=use_gpu)
                    if use_gpu:
                        model = model.to("cuda")

                    speaker_manager = model.synthesizer.tts_model.speaker_manager
                    speaker = list(speaker_manager.speakers.keys())[0]

                    _xtts_model = model
                    _xtts_speaker = speaker
                    return _xtts_model, _xtts_speaker, ""
                except Exception as exc:
                    last_error = exc
                    if not use_gpu:
                        break

            _xtts_init_error = f"Local XTTS init failed: {last_error}"
            return None, "", _xtts_init_error
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
        model.tts_to_file(
            text=clean_text_for_tts(reply_text),
            file_path=out_path,
            speaker=speaker,
            language=XTTS_LANGUAGE,
        )
        with open(out_path, "rb") as audio_file:
            wav_bytes = audio_file.read()

        if not wav_bytes:
            return "", "Local XTTS returned empty audio."

        return base64.b64encode(wav_bytes).decode("utf-8"), ""
    except Exception as exc:
        return "", f"Local XTTS synthesis failed: {exc}"
    finally:
        safe_unlink(out_path)


def synthesize_tts(reply_text: str) -> tuple[str, str]:
    """
    Return (audio_base64, audio_error).
    If TTS fails, return empty audio with a human-readable error.
    """
    audio_b64, audio_error = synthesize_local_xtts(reply_text)
    if audio_b64:
        return audio_b64, ""

    # Optional cloud fallback when local XTTS is unavailable.
    if not STREAMELEMENTS_API_KEY:
        return "", audio_error or "Cloud TTS disabled: missing STREAMELEMENTS_API_KEY."

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
            fallback_error = "TTS provider returned empty audio."
            if audio_error:
                fallback_error = f"{audio_error} | {fallback_error}"
            return "", fallback_error
        return base64.b64encode(wav_bytes).decode("utf-8"), ""
    except requests.RequestException as exc:
        cloud_error = f"TTS unavailable: {format_request_error(exc)}"
        if audio_error:
            cloud_error = f"{audio_error} | {cloud_error}"
        return "", cloud_error


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

        # 3) LLM reply - identical path used by agent_v1.py
        reply_text = reply(user_text)

        # 4) Text-to-Speech (best-effort)
        audio_b64, audio_error = synthesize_tts(reply_text)

        return {
            "transcript": user_text,
            "text": reply_text,
            "audio_base64": audio_b64,
            "audio_error": audio_error,
        }

    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"Upstream API error: {format_request_error(exc)}") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Audio pipeline failed: {exc}") from exc
    finally:
        for path in [in_path]:
            if path and os.path.exists(path):
                safe_unlink(path)
