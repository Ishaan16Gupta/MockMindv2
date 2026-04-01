from flask import Flask, send_file, request, jsonify, Response
import uuid
import traceback
import interview_flow
import code_editor
from speech_portion.tts import synthesize
from speech_portion.stt import transcribe_from_bytes
from api_code_editor.code_runner import is_safe_code, run_python_code, analyse_complexity

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


def _normalize_code_submission(code: str) -> str:
    """Normalize pasted code so fenced snippets and chat artifacts still run."""
    if not code:
        return ""

    text = (
        str(code)
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .replace("\u00a0", " ")
    )

    # Strip common zero-width characters that get copied from chat apps.
    text = "".join(ch for ch in text if ch not in {"\u200b", "\u200c", "\u200d", "\ufeff"})

    stripped = text.strip()
    if stripped.startswith("```") and stripped.endswith("```"):
        lines = stripped.split("\n")
        if lines:
            lines = lines[1:-1]
        text = "\n".join(lines)

    # Remove a single leading fence language tag when code is pasted as a bare block.
    text = text.lstrip("\n")
    if text.lower().startswith(("python\n", "py\n", "javascript\n", "js\n", "java\n", "cpp\n", "c++\n", "typescript\n", "ts\n")):
        text = text.split("\n", 1)[1] if "\n" in text else ""

    # Remove quote markers from chat responses.
    text = "\n".join(line[2:] if line.startswith("> ") else line[1:] if line.startswith(">") else line for line in text.split("\n"))

    lines = text.split("\n")
    non_empty = [line for line in lines if line.strip()]
    if non_empty:
        leading_indents = []
        for line in non_empty:
            indent = len(line) - len(line.lstrip(" \t"))
            if indent > 0:
                leading_indents.append(indent)
        if leading_indents and len(leading_indents) == len(non_empty):
            dedent_by = min(leading_indents)
            if dedent_by > 0:
                lines = [line[dedent_by:] if len(line) >= dedent_by else line for line in lines]

    return "\n".join(lines).strip("\n")

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


@app.route("/api/code/run", methods=["POST"])
def run_code():
    data = request.get_json() or {}
    code = _normalize_code_submission(data.get("code", ""))
    test_cases = data.get("test_cases", [])

    if not code.strip():
        return jsonify({"error": "No code provided"}), 400
    if not isinstance(test_cases, list) or not test_cases:
        return jsonify({"error": "No test cases provided"}), 400

    safe, reason = is_safe_code(code)
    if not safe:
        return jsonify({"error": f"Code blocked: {reason}"}), 400

    results = []
    for i, test_case in enumerate(test_cases, 1):
        execution = run_python_code(code, test_case.get("input"), data.get("time_limit_ms", 3000))
        actual = execution.get("result")
        error = execution.get("error")
        expected = test_case.get("expected")
        passed = error is None and actual == expected

        results.append({
            "label": test_case.get("label", f"Test {i}"),
            "input": test_case.get("input"),
            "expected": expected,
            "actual": actual,
            "passed": passed,
            "runtime_ms": execution.get("runtime_ms", 0),
            "error": error,
        })

    complexity = analyse_complexity(code)
    pass_count = sum(1 for result in results if result["passed"])
    total = len(results)

    return jsonify({
        "results": results,
        "complexity": complexity,
        "all_passed": pass_count == total,
        "pass_rate": round(pass_count / total, 2) if total else 0,
    })


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