import threading
import queue
import numpy as np
import sounddevice as sd
import gradio as gr

from faster_whisper import WhisperModel
from brain_gemini import reply  # your Groq wrapper
from TTS.api import TTS

# ================== CONFIG ==================
SAMPLE_RATE = 16000
BLOCKSIZE = 1024
SILENCE_SEC = 0.6       # silence duration to end an utterance
VAD_THRESH = 0.01       # energy threshold for speech
WHISPER_MODEL = "base"  # change to "small"/"tiny" for speed
# ============================================

# Initialize GPU models (CUDA already verified on your system)
asr = WhisperModel(WHISPER_MODEL, device="cuda", compute_type="float16")
tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2", gpu=True)
tts = tts.to("cuda")

audio_q = queue.Queue()
stop_flag = threading.Event()

def audio_callback(indata, frames, time_info, status):
    if status:
        print(status)
    audio_q.put(indata.copy())

def record_until_silence():
    """Record audio chunks until sustained silence is detected."""
    frames = []
    silence_count = 0
    max_silence_blocks = int((SILENCE_SEC * SAMPLE_RATE) / BLOCKSIZE)

    while not stop_flag.is_set():
        try:
            chunk = audio_q.get(timeout=0.1)
        except queue.Empty:
            continue

        mono = np.mean(chunk, axis=1)
        energy = np.mean(np.abs(mono))
        frames.append(mono)

        if energy < VAD_THRESH:
            silence_count += 1
        else:
            silence_count = 0

        if silence_count >= max_silence_blocks and len(frames) > 5:
            break

    if not frames:
        return None

    audio = np.concatenate(frames)
    return audio.astype(np.float32)

def transcribe(audio):
    segments, _ = asr.transcribe(audio, beam_size=1)
    text = "".join(seg.text for seg in segments).strip()
    return text

# pick a default speaker once
# Get speakers from the underlying model (XTTS is multi-speaker)
speakers = getattr(tts.synthesizer.tts_model, "speakers", None)
DEFAULT_SPEAKER = speakers[0] if speakers and len(speakers) > 0 else None

REF_VOICE = "speech.wav"
LANG = "en"

               # or "hi", "en-us", etc.

def speak(text):
    wav = tts.tts(text, speaker_wav=REF_VOICE, language=LANG)
    sd.play(wav, samplerate=tts.synthesizer.output_sample_rate)
    sd.wait()




def loop_worker():
    """Continuous hands-free loop. Yields (transcript, replies) for Gradio streaming."""
    stop_flag.clear()
    transcript_log = ""
    reply_log = ""

    with sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=1,
        blocksize=BLOCKSIZE,
        callback=audio_callback,
    ):
        while not stop_flag.is_set():
            audio = record_until_silence()
            if stop_flag.is_set():
                break
            if audio is None or len(audio) < SAMPLE_RATE * 0.2:
                continue

            user_text = transcribe(audio)
            if not user_text:
                continue

            transcript_log += f"🧑 You: {user_text}\n"
            yield transcript_log, reply_log

            bot_text = reply(user_text)
            reply_log += f"🤖 Bot: {bot_text}\n"
            yield transcript_log, reply_log

            speak(bot_text)

    yield transcript_log, reply_log

def stop():
    stop_flag.set()
    return gr.update(), gr.update()

with gr.Blocks(title="Grambelle – Continuous Voice") as demo:
    gr.Markdown(
        "## 🎤 Grambelle (Hands‑Free Continuous Voice)\n"
        "Click **Start Conversation**, talk, pause to send. Hit **Stop** to end."
    )

    with gr.Row():
        start_btn = gr.Button("▶️ Start Conversation", variant="primary")
        stop_btn = gr.Button("⏹️ Stop", variant="stop")

    transcript_box = gr.Textbox(label="Transcript", lines=10)
    reply_box = gr.Textbox(label="Replies", lines=10)

    start_btn.click(loop_worker, outputs=[transcript_box, reply_box])
    stop_btn.click(stop, outputs=[transcript_box, reply_box])

if __name__ == "__main__":
    demo.queue().launch()
