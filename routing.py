from flask import Flask, send_file, request, jsonify, Response
import uuid
import interview_flow
import code_editor
from speech_portion.tts import synthesize
from speech_portion.stt import transcribe_from_bytes

app = Flask(__name__)

# In-memory session store: session_id -> session state dict
SESSIONS: dict = {}

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


# ── API ROUTES ─────────────────────────────────────────────────────────────────

@app.route("/api/interview/start", methods=["POST"])
def start_interview():
    data = request.get_json() or {}
    try:
        session = main.start_session(
            mode       = data.get("mode", "behavioral"),
            difficulty = data.get("difficulty", "Mid"),
            resume     = data.get("resume", ""),
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    session_id = str(uuid.uuid4())
    SESSIONS[session_id] = session
    return jsonify({"session_id": session_id, "response": {"question": session["question"]}})


@app.route("/api/tts", methods=["POST"])
def tts():
    text = (request.get_json() or {}).get("text", "").strip()
    if not text:
        return jsonify({"error": "No text provided"}), 400
    audio_bytes = synthesize(text)
    if audio_bytes is None:
        return jsonify({"error": "TTS synthesis failed"}), 500
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

    if not session_id or session_id not in SESSIONS:
        return jsonify({"error": "Session not found"}), 404
    if not answer:
        return jsonify({"error": "Empty answer"}), 400

    try:
        resp = main.process_answer(
            session      = SESSIONS[session_id],
            answer       = answer,
            question_num = data.get("question_num", 1),
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({"response": resp})


# ── RUN SERVER ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(debug=True)