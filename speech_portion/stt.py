import sounddevice as sd
import numpy as np
import requests
import tempfile
import os
import time
from scipy.io.wavfile import write
from dotenv import load_dotenv

# ==============================
# CONFIG
# ==============================
load_dotenv(override=True)
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY_stt")

SAMPLE_RATE = 16000
CHANNELS = 1

SILENCE_THRESHOLD = 0.005   # sensitivity (lower = more sensitive)
SILENCE_DURATION = 1.4      # seconds of silence before stopping
MAX_DURATION = 20           # max recording time (safety)

# Mic-level debug output
MIC_LEVEL_DEBUG = True
MIC_LEVEL_PRINT_EVERY = 0.2  # seconds

# ==============================
# AUDIO RECORDING WITH SILENCE DETECTION
# ==============================

def listen():
    print("🎤 Listening... (speak now)")
    print("🔧 sounddevice default input:", sd.default.device)
    print("🖥️ available devices:")
    for i, dev in enumerate(sd.query_devices()):
        if "input" in dev["name"].lower() or dev["max_input_channels"] > 0:
            print(f"  [{i}] {dev['name']} chans={dev['max_input_channels']}" )

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

    if len(audio_buffer) == 0:
        print("⚠️ no audio frames captured, likely mic issue")
        return ""

    # Combine audio chunks
    audio = np.concatenate(audio_buffer, axis=0)

    # If audio contains very low energy, still send it to Deepgram for best guess
    max_val = np.max(np.abs(audio)) if audio.size > 0 else 0
    print(f"🔊 captured audio max amplitude={max_val:.6f}")

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
        print("🧾 Deepgram results:", data.get("results"))
        text = data["results"]["channels"][0]["alternatives"][0]["transcript"]
        confidence = data["results"]["channels"][0]["alternatives"][0].get("confidence")
        print(f"   transcript confidence: {confidence}")
    except Exception as e:
        print(f"❌ Deepgram JSON error: {e}")
        print("   response status", response.status_code)
        print("   response text", response.text)
        text = ""

    if not text or text.strip() == "":
        # if nothing is detected, dump additional fields if available for debugging
        if data and "channels" in data.get("results", {}).get("channels", [{}])[0]:
            print("   Deepgram channels detail:", data.get("results", {}).get("channels"))

    print(f"📝 Transcript: {text if text else '[No speech detected]'}")
    print(f"⚡ STT Latency: {latency:.2f} ms")

    return text


# ==============================
# BYTES ENTRY POINT  (called by Flask /api/stt)
# ==============================

def transcribe_from_bytes(audio_bytes: bytes, content_type: str = "audio/webm") -> str:
    """Accept raw audio bytes (from a browser MediaRecorder blob), write to a
    temp file with the correct extension, and return the Deepgram transcript.

    This is the programmatic entry point used by the Flask route so that
    routing.py stays simple.

    Args:
        audio_bytes:  raw audio blob from the browser
        content_type: MIME type, e.g. 'audio/webm' or 'audio/wav'

    Returns:
        Transcript string, or empty string if nothing was heard.
    """
    import tempfile

    ext = ".webm" if "webm" in content_type else ".wav"
    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name

    try:
        url = f"https://api.deepgram.com/v1/listen?model=nova-2&punctuate=true"
        headers = {
            "Authorization": f"Token {DEEPGRAM_API_KEY}",
            "Content-Type": content_type,
        }
        start_time = time.time()
        with open(tmp_path, "rb") as f:
            response = requests.post(url, headers=headers, data=f)
        latency = (time.time() - start_time) * 1000

        try:
            data = response.json()
            text = data["results"]["channels"][0]["alternatives"][0]["transcript"]
        except Exception:
            text = ""

        print(f"📝 Transcript: {text if text else '[No speech detected]'}")
        print(f"⚡ STT Latency: {latency:.2f} ms")
        return text
    finally:
        os.remove(tmp_path)