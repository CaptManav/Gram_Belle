# Gram_Belle

Voice-first AI assistant experiments using Groq, Whisper, and XTTS.

This repository currently contains Python prototypes for:
- speech-to-text (local and API-based),
- LLM replies through Groq,
- text-to-speech playback,
- a FastAPI `/talk` endpoint,
- and a Gradio hands-free conversation loop.

## Project Structure

- `server.py`: FastAPI API that accepts uploaded audio and returns `{text, audio_base64}`.
- `brain_gemini.py`: Groq chat wrapper (`llama-3.1-8b-instant`) and system prompt.
- `ui.py`: Gradio continuous voice interface (VAD-like loop + local Whisper + XTTS).
- `agent_v1.py`: local loop version of voice chat (record -> transcribe -> reply -> speak).
- `local_stt_test.py`: quick local Whisper transcription test (CPU).
- `stt_test.py`: OpenAI Whisper API transcription test.
- `tts_test.py`: basic `pyttsx3` text-to-speech test.
- `mic_test.py`: microphone speech activity detection test (`webrtcvad`).

## Requirements

- Python 3.10+ (recommended)
- FFmpeg installed (needed by `pydub` in `server.py`)
- Working microphone/speaker device
- NVIDIA CUDA setup if you want GPU acceleration for Whisper/XTTS

## Environment Variables

Create a `.env` file in the project root:

```env
GROQ_API_KEY=your_groq_api_key_here
```

`brain_gemini.py` and `server.py` expect `GROQ_API_KEY`.

## Setup

1. Create and activate a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2. Install packages:

```powershell
pip install fastapi uvicorn requests pydub python-multipart
pip install groq python-dotenv
pip install gradio numpy sounddevice soundfile webrtcvad
pip install faster-whisper
pip install TTS torch
pip install openai pyttsx3
```

Note: depending on your machine, `torch`, `TTS`, and `faster-whisper` may need specific CUDA/CPU wheels.

## Run

### 1) FastAPI server

```powershell
uvicorn server:app --reload --host 0.0.0.0 --port 8000
```

Open the frontend at:
- `http://127.0.0.1:8000/`

Endpoint:
- `POST /talk` with multipart field `file` (audio input).

Example request:

```bash
curl -X POST "http://127.0.0.1:8000/talk" \
  -F "file=@speech.wav"
```

### 2) Gradio continuous voice app

```powershell
python ui.py
```

Notes:
- `ui.py` uses `REF_VOICE = "speech.wav"` as speaker reference for XTTS.
- If that file is missing, create/provide a valid reference clip.

### 3) Local loop assistant

```powershell
python agent_v1.py
```

## Quick Tests

```powershell
python mic_test.py
python local_stt_test.py
python stt_test.py
python tts_test.py
```

## Known Notes

- The current assistant personality is defined in `brain_gemini.py` (`SYSTEM_PROMPT`).
- `server.py` uses Groq Whisper for STT and a public StreamElements endpoint for TTS output.
- Generated audio files (`*.wav`) and `.env` are ignored by Git.
