import sounddevice as sd
import numpy as np
import requests
import tempfile
import os
import time
from scipy.io.wavfile import write

# ==============================
# CONFIG
# ==============================

DEEPGRAM_API_KEY = os.environ.get("6b8bfb83f948ba8b960ca4b10421e7d1c7b22fbf")

SAMPLE_RATE = 16000
CHANNELS = 1

SILENCE_THRESHOLD = 0.01   # sensitivity (lower = more sensitive)
SILENCE_DURATION = 2     # seconds of silence before stopping
MAX_DURATION = 20          # max recording time (safety)

# Mic-level debug output
MIC_LEVEL_DEBUG = True
MIC_LEVEL_PRINT_EVERY = 0.2  # seconds

# ==============================
# AUDIO RECORDING WITH SILENCE DETECTION
# ==============================

def listen():
    print("🎤 Listening... (speak now)")

    audio_buffer = []
    silence_start = None
    start_time = time.time()
    last_debug_print = 0.0

    def audio_callback(indata, frames, time_info, status):
        nonlocal silence_start, last_debug_print

        volume = np.linalg.norm(indata) / len(indata)

        audio_buffer.append(indata.copy())

        if MIC_LEVEL_DEBUG:
            now = time.time()
            if now - last_debug_print >= MIC_LEVEL_PRINT_EVERY:
                level = min(60, int(volume * 3000))
                meter = "#" * level
                print(
                    f"🔊 mic={volume:.5f} thr={SILENCE_THRESHOLD:.5f} |{meter}",
                    flush=True,
                )
                last_debug_print = now

        if status:
            print(f"⚠️ audio status: {status}", flush=True)

        # Detect silence
        if volume < SILENCE_THRESHOLD:
            if silence_start is None:
                silence_start = time.time()
        else:
            silence_start = None

    with sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        callback=audio_callback
    ):
        while True:
            time.sleep(0.1)

            # Stop if silence persists
            if silence_start and (time.time() - silence_start > SILENCE_DURATION):
                print("🛑 Silence detected, stopping...")
                break

            # Safety timeout
            if time.time() - start_time > MAX_DURATION:
                print("⏱️ Max duration reached, stopping...")
                break

    # Combine audio chunks
    audio = np.concatenate(audio_buffer, axis=0)

    return transcribe(audio)


# ==============================
# TRANSCRIPTION (Deepgram)
# ==============================

def transcribe(audio):
    print("🧠 Processing speech...")

    # Save temp WAV file
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_file:
        write(temp_file.name, SAMPLE_RATE, audio)
        file_path = temp_file.name

    url = "https://api.deepgram.com/v1/listen?model=nova-2&punctuate=true"

    headers = {
        "Authorization": f"Token {DEEPGRAM_API_KEY}",
        "Content-Type": "audio/wav"
    }

    start_time = time.time()

    with open(file_path, "rb") as f:
        response = requests.post(url, headers=headers, data=f)

    latency = (time.time() - start_time) * 1000

    os.remove(file_path)

    try:
        data = response.json()
        text = data["results"]["channels"][0]["alternatives"][0]["transcript"]
    except:
        text = ""

    print(f"📝 Transcript: {text if text else '[No speech detected]'}")
    print(f"⚡ STT Latency: {latency:.2f} ms")

    return text