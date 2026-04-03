import requests
import sounddevice as sd
import numpy as np
import tempfile
import os
import time
from dotenv import load_dotenv

# ==============================
# CONFIG
# ==============================
load_dotenv(override=True)
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY_tts")

# Voice options (Deepgram Aura engine)
# Female: aura-asteria-en, aura-luna-en, aura-stella-en, aura-athena-en, aura-hera-en
# Male  : aura-orion-en, aura-arcas-en, aura-perseus-en, aura-angus-en, aura-helios-en, aura-zeus-en
DEFAULT_VOICE  = "aura-asteria-en"

# Audio format sent to Deepgram: mp3 | wav | ogg | flac
DEFAULT_FORMAT = "mp3"

# Playback speed multiplier (0.5 – 2.0); mirrors the HTML slider default of 0.75
DEFAULT_SPEED  = 1

# Max characters accepted (mirrors HTML maxlength="2000")
MAX_CHARS = 2000

# Whether to save the audio file after playback
SAVE_AUDIO = False
SAVE_DIR   = "."          # folder to save to when SAVE_AUDIO=True

# ==============================
# TEXT-TO-SPEECH (Deepgram Aura)
# ==============================

def synthesize(
    text: str,
    voice:  str   = DEFAULT_VOICE,
    format: str   = DEFAULT_FORMAT,
    speed:  float = DEFAULT_SPEED,
) -> bytes | None:
    """
    Send *text* to Deepgram's TTS endpoint and return raw audio bytes.
    Returns None on failure.

    Mirrors the synthesize() function in deepgram-tts.html.
    """

    text = text.strip()

    if not text:
        print("❌ No text provided.")
        return None

    if len(text) > MAX_CHARS:
        print(f"❌ Text exceeds {MAX_CHARS} character limit ({len(text)} chars).")
        return None

    print(f"🗣️  Synthesizing  |  voice={voice}  format={format}  speed={speed}×")
    print(f"📝 Text preview  : {text[:80]}{'…' if len(text) > 80 else ''}")

    url = f"https://api.deepgram.com/v1/speak?model={voice}&encoding={format}"

    headers = {
        "Authorization": f"Token {DEEPGRAM_API_KEY}",
        "Content-Type":  "application/json",
    }

    payload = {"text": text}

    start_time = time.time()

    try:
        response = requests.post(url, headers=headers, json=payload)
    except requests.RequestException as exc:
        print(f"❌ Network error: {exc}")
        return None

    latency = (time.time() - start_time) * 1000

    if not response.ok:
        try:
            err = response.json()
            msg = err.get("err_msg") or err.get("message") or f"HTTP {response.status_code}"
        except Exception:
            msg = f"HTTP {response.status_code}"
        print(f"❌ TTS failed: {msg}")
        return None

    audio_bytes = response.content
    size_kb     = len(audio_bytes) / 1024

    print(f"✅ Audio received |  {size_kb:.1f} KB")
    print(f"⚡ TTS Latency   :  {latency:.2f} ms")

    return audio_bytes


# ==============================
# PLAYBACK
# ==============================

def play_audio(audio_bytes: bytes, format: str = DEFAULT_FORMAT, speed: float = DEFAULT_SPEED):
    """
    Write audio to a temp file, decode with soundfile, then play via sounddevice.
    Speed is applied by resampling the playback sample-rate (simple time-stretch).

    Mirrors the setupPlayer / togglePlay logic in deepgram-tts.html.
    """
    try:
        import soundfile as sf
    except ImportError:
        print("⚠️  soundfile not installed — install it with: pip install soundfile")
        _play_fallback(audio_bytes, format)
        return

    suffix = f".{format}"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name

    try:
        data, samplerate = sf.read(tmp_path, dtype="float32")

        # Apply speed by adjusting the effective sample rate
        effective_rate = int(samplerate * speed)

        print(f"▶️  Playing audio  |  duration≈{len(data)/samplerate:.2f}s  "
              f"sr={samplerate}  speed={speed}×")

        sd.play(data, samplerate=effective_rate)
        sd.wait()  # block until playback finishes

        print("⏹️  Playback complete.")

    except Exception as exc:
        print(f"❌ Playback error: {exc}")
    finally:
        os.remove(tmp_path)


def _play_fallback(audio_bytes: bytes, format: str):
    """Last-resort: open audio with the OS default player."""
    import subprocess, sys
    suffix = f".{format}"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name
    print(f"🎵 Opening with system player: {tmp_path}")
    if sys.platform == "darwin":
        subprocess.call(["open", tmp_path])
    elif sys.platform.startswith("linux"):
        subprocess.call(["xdg-open", tmp_path])
    elif sys.platform == "win32":
        os.startfile(tmp_path)


# ==============================
# SAVE AUDIO
# ==============================

def save_audio(audio_bytes: bytes, voice: str, format: str, save_dir: str = SAVE_DIR) -> str:
    """
    Save audio bytes to disk and return the file path.
    Mirrors the Download Audio button in deepgram-tts.html.
    """
    filename = f"speech_{voice}.{format}"
    filepath = os.path.join(save_dir, filename)
    with open(filepath, "wb") as f:
        f.write(audio_bytes)
    print(f"💾 Saved to: {filepath}  ({len(audio_bytes)/1024:.1f} KB)")
    return filepath


# ==============================
# MAIN ENTRY POINT
# ==============================

def speak(
    text:   str,
    voice:  str   = DEFAULT_VOICE,
    format: str   = DEFAULT_FORMAT,
    speed:  float = DEFAULT_SPEED,
    save:   bool  = SAVE_AUDIO,
) -> str | None:
    """
    High-level convenience function:
      1. Synthesize speech via Deepgram
      2. Play it back immediately
      3. Optionally save to disk

    Returns the saved file path (str) if save=True, else None.

    Integration hook for stt.py:
        from tts import speak
        speak(transcribed_text)
    """
    audio_bytes = synthesize(text, voice=voice, format=format, speed=speed)
    if audio_bytes is None:
        return None

    play_audio(audio_bytes, format=format, speed=speed)

    if save:
        return save_audio(audio_bytes, voice=voice, format=format)

    return None


# ==============================
# STANDALONE DEMO
# ==============================

if __name__ == "__main__":
    sample_text = (
        "Hello! This is a text-to-speech test using the Deepgram Aura engine. "
        "You can change the voice, format, and speed in the config section at the top."
    )

    speak(
        text   = sample_text,
        voice  = DEFAULT_VOICE,
        format = DEFAULT_FORMAT,
        speed  = DEFAULT_SPEED,
        save   = SAVE_AUDIO,
    )
