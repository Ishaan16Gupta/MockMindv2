from flask import Flask, send_file, request, jsonify, Response
import uuid
import traceback
import interview_flow
import code_editor
from speech_portion.tts import synthesize
from speech_portion.stt import transcribe_from_bytes

app = Flask(__name__)

# In-memory session store: session_id -> session state dict
SESSIONS: dict = {}


def _json_safe(value):
    """Recursively convert values to JSON-safe primitives."""
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(v) for v in value]
    return str(value)

# ── PAGE ROUTES ────────────────────────────────────────────────────────────────

@app.route("/")
def landing():
    return send_file("static/landing.html")

@app.route("/whiteboard")
def whiteboard():
    return send_file("static/whiteboard.html")

@app.route("/report")
def report():
    return send_file("static/report.html")


@app.route("/Camera_analyser/script.js")
def camera_analyser_script():
    return send_file("Camera_analyser/script.js", mimetype="application/javascript")


# ── API ROUTES ─────────────────────────────────────────────────────────────────

@app.route("/api/interview/start", methods=["POST"])
def start_interview():
    data = request.get_json() or {}
    try:
        session = interview_flow.start_session(
            role = data.get("role", "Software Engineer"),
            company_type = data.get("company_type", "FAANG"),
            mode       = data.get("mode", "behavioral"),
            difficulty = data.get("difficulty", "Mid"),
            resume     = data.get("resume", ""),
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    session_id = str(uuid.uuid4())
    SESSIONS[session_id] = session
    return jsonify({
        "session_id": session_id,
        "response": {
            "question": session["question"],
            "total_questions": session["total_questions"]
        }
    })


@app.route("/api/tts", methods=["POST"])
def tts():
    import datetime
    text = (request.get_json() or {}).get("text", "").strip()
    timestamp = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
    print(f"[{timestamp}] 🎙 [MODEL SPEAKING] TTS requested: {text[:80]}{'...' if len(text) > 80 else ''}")
    if not text:
        return jsonify({"error": "No text provided"}), 400
    audio_bytes = synthesize(text)
    if audio_bytes is None:
        print(f"[{timestamp}] ✗ TTS synthesis failed")
        return jsonify({"error": "TTS synthesis failed"}), 500
    print(f"[{timestamp}] ✓ TTS audio generated ({len(audio_bytes)} bytes)")
    return Response(audio_bytes, mimetype="audio/mpeg")


@app.route("/api/stt", methods=["POST"])
def stt():
    if not request.data:
        return jsonify({"error": "No audio data received"}), 400
    transcript = transcribe_from_bytes(request.data, request.content_type or "audio/webm")
    return jsonify({"transcript": transcript})


@app.route("/api/interview/answer", methods=["POST"])
def interview_answer():
    data       = request.get_json() or {}
    session_id = data.get("session_id")
    answer     = data.get("answer", "").strip()
    camera_confidence = data.get("camera_confidence", None)
    try:
        question_num = int(data.get("question_num", 1))
    except (TypeError, ValueError):
        question_num = 1

    if not session_id or session_id not in SESSIONS:
        return jsonify({"error": "Session not found"}), 404
    if not answer:
        return jsonify({"error": "Empty answer"}), 400

    try:
        resp = interview_flow.process_answer(
            session      = SESSIONS[session_id],
            answer       = answer,
            question_num = question_num,
            camera_confidence = camera_confidence,
        )
        resp = _json_safe(resp)
    except Exception as e:
        print("[ERROR] /api/interview/answer failed")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

    return jsonify({"response": resp})


# ── RUN SERVER ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(debug=True)