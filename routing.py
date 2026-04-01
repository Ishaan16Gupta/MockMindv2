from flask import Flask, send_file, request, jsonify
import threading
import uuid
import main
import code_editor

app = Flask(__name__)

# In-memory session store: session_id -> session state dict
SESSIONS: dict = {}

# ── ROUTES ─────────────────────────────────────

# Landing page
@app.route("/")
def landing():
    return send_file("static/landing.html")


# Whiteboard page
@app.route("/whiteboard")
def whiteboard():
    return send_file("static/whiteboard.html")


# Report page
@app.route("/report")
def report():
    return send_file("static/report.html")



@app.route("/api/interview/start", methods=["POST"])
def start_interview():
    
    data = request.get_json() or {}
    print(f"Request: {data} \n") #ran
    mode       = data.get("mode", "behavioral")
    difficulty = data.get("difficulty", "Mid")
    resume     = data.get("resume", "")

    try:
        print("🚀 Starting new interview session...\n")
        session = main.start_session(mode, difficulty, resume)
        print("✅ Session initialized with question:\n", session["question"])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    session_id = str(uuid.uuid4())
    SESSIONS[session_id] = session          # persist state for answer route

    # Launch the full voice interview loop in a background thread so this
    # HTTP response can return immediately (the browser navigates to /whiteboard)
    t = threading.Thread(
        target=main.run_interview,
        args=(session_id, session["cfg"], session["messages"]),
        daemon=True,
    )
    t.start()

    return jsonify({
        "session_id": session_id,
        "response": {
            "question": session["question"]
        }
    })





# ── RUN SERVER ────────────────────────────────
if __name__ == "__main__":
    app.run(debug=True)