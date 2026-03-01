import sounddevice as sd
import webrtcvad
import queue
import time

SAMPLE_RATE = 16000
FRAME_DURATION = 30  # ms
FRAME_SIZE = int(SAMPLE_RATE * FRAME_DURATION / 1000)

vad = webrtcvad.Vad(2)  # 0 = chill, 3 = aggressive
audio_queue = queue.Queue()

def callback(indata, frames, time_info, status):
    if status:
        print(status)
    audio_queue.put(bytes(indata))

print("🎤 Listening... Speak something. Ctrl+C to stop.")

stream = sd.RawInputStream(
    samplerate=SAMPLE_RATE,
    blocksize=FRAME_SIZE,
    dtype="int16",
    channels=1,
    callback=callback
)

stream.start()

speaking = False
last_voice_time = time.time()

try:
    while True:
        frame = audio_queue.get()
        is_speech = vad.is_speech(frame, SAMPLE_RATE)

        if is_speech:
            if not speaking:
                print("🟢 Speech detected")
                speaking = True
            last_voice_time = time.time()

        else:
            if speaking and time.time() - last_voice_time > 0.6:
                print("🔴 Speech ended")
                speaking = False

except KeyboardInterrupt:
    print("\n🛑 Stopped.")
    stream.stop()
    stream.close()
