from flask import Flask, send_file, request, jsonify
import uuid

app = Flask(__name__)

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
    data = request.get_json()

    # dummy response (for now)
    return jsonify({
        "session_id": str(uuid.uuid4()),
        "response": {
            "question": "Tell me about yourself."
        }
    })





# ── RUN SERVER ────────────────────────────────
if __name__ == "__main__":
    app.run(debug=True)