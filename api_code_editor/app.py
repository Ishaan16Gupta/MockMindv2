"""
AI Mock Interview System
Backend: Flask + Groq API
Run: python app.py
"""

import os
import json
import uuid
import ast
import re
import sys
import time
try:
    import resource
except ImportError:
    resource = None
import subprocess
import tempfile
import textwrap
from flask import Flask, request, jsonify, session, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
from groq_service import call_groq, get_model_name

load_dotenv()

app = Flask(__name__, static_folder="static")
app.secret_key = os.getenv("SECRET_KEY")
CORS(app, supports_credentials=True)

# ── In-memory session store (replace with Redis in production) ────────────────
sessions = {}


# ─────────────────────────────────────────────────────────────────────────────
# PROMPTS
# ─────────────────────────────────────────────────────────────────────────────

INTERVIEW_SYSTEM_PROMPT = """You are an expert senior technical interviewer at a top-tier technology company.

Rules:
- Ask ONE clear interview question at a time
- Evaluate answers using a rubric (clarity, depth, specificity, STAR for behavioural)
- Generate follow-up questions when answers score below 7
- Be professional, encouraging, and precise
- Never reveal scores or rubric to candidate

ALWAYS respond in this exact JSON format (no markdown, no extra text):
{
  "question": "the question text",
  "evaluation": {
    "score": 7.5,
    "strengths": ["strength 1", "strength 2"],
    "weaknesses": ["weakness 1"],
    "competency": "Communication",
    "feedback": "brief constructive sentence"
  },
  "follow_up": "targeted follow-up question or null",
  "should_follow_up": false,
  "model_hint": "one thing a strong answer includes",
  "session_complete": false
}

On the FIRST message set evaluation to null. Keep questions sharp. Probe for depth."""


CODE_REVIEW_PROMPT = """You are an expert software engineer reviewing a coding interview submission.

ALWAYS respond in this exact JSON format (no markdown, no extra text):
{
  "summary": "one sentence verdict",
  "code_score": 8.0,
  "correctness_score": 9.0,
  "style_score": 7.0,
  "complexity": {
    "time": "O(n)",
    "space": "O(n)",
    "explanation": "brief explanation"
  },
  "strengths": ["strength 1"],
  "issues": ["issue 1"],
  "follow_up_questions": [
    "What is the time complexity?",
    "How would you handle edge cases?",
    "Can you think of a more efficient approach?"
  ],
  "optimized_approach": "brief description of optimal solution",
  "interviewer_verdict": "hire"
}"""


def get_session(session_id):
    """Get or create session data."""
    if session_id not in sessions:
        sessions[session_id] = {"messages": [], "scores": [], "question_num": 0}
    return sessions[session_id]


# ─────────────────────────────────────────────────────────────────────────────
# CODE ANALYSIS
# ─────────────────────────────────────────────────────────────────────────────

BLOCKED_IMPORTS = {
    "os", "sys", "subprocess", "shutil", "socket", "urllib",
    "requests", "http", "ftplib", "smtplib", "importlib",
    "ctypes", "multiprocessing", "threading",
}

BLOCKED_PATTERNS = [
    r"__import__\s*\(",
    r"\beval\s*\(",
    r"\bexec\s*\(",
    r"\bcompile\s*\(",
    r"\bopen\s*\(",
]

def is_safe_code(code):
    for pattern in BLOCKED_PATTERNS:
        if re.search(pattern, code):
            return False, f"Blocked pattern: {pattern}"
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return False, f"Syntax error: {e}"
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = (
                [a.name for a in node.names]
                if isinstance(node, ast.Import)
                else [node.module or ""]
            )
            for name in names:
                if name.split(".")[0] in BLOCKED_IMPORTS:
                    return False, f"Blocked import: {name}"
    return True, ""


def run_python_code(code, test_input, time_limit_ms=3000):
    """Run code in sandboxed subprocess."""
    serialized = json.dumps(test_input)
    harness = textwrap.dedent(f"""
import json, sys
{code}

_input = json.loads('''{serialized}''')
_func = None
for _name, _val in list(globals().items()):
    if callable(_val) and not _name.startswith('_'):
        _func = _val
        break

if _func is None:
    print(json.dumps({{"error": "No callable function found", "result": None}}))
    sys.exit(0)

try:
    if isinstance(_input, list):
        _result = _func(*_input)
    elif isinstance(_input, dict):
        _result = _func(**_input)
    else:
        _result = _func(_input)
    print(json.dumps({{"result": _result, "error": None}}))
except Exception as e:
    print(json.dumps({{"result": None, "error": str(e)}}))
""")

    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
        f.write(harness)
        tmp = f.name

    try:
        timeout = min(time_limit_ms / 1000.0, 5.0)
        start = time.perf_counter()

        def set_limits():
            try:
                if resource:
                    resource.setrlimit(resource.RLIMIT_AS, (128*1024*1024, 128*1024*1024))
            except Exception:
                pass

        proc = subprocess.run(
            [sys.executable, tmp],
            capture_output=True, text=True,
            timeout=timeout,
            preexec_fn=set_limits if os.name != "nt" else None,
        )
        elapsed = (time.perf_counter() - start) * 1000

        if proc.returncode != 0 and not proc.stdout.strip():
            return {"result": None, "error": proc.stderr[:300], "runtime_ms": elapsed}

        try:
            data = json.loads(proc.stdout.strip())
            data["runtime_ms"] = round(elapsed, 2)
            return data
        except Exception:
            return {"result": proc.stdout.strip(), "error": None, "runtime_ms": round(elapsed, 2)}

    except subprocess.TimeoutExpired:
        return {"result": None, "error": f"Time limit exceeded ({time_limit_ms}ms)", "runtime_ms": time_limit_ms}
    finally:
        os.unlink(tmp)


def analyse_complexity(code):
    """AST-based complexity heuristics."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return {"time": "Unknown", "space": "Unknown", "confidence": "low"}

    # Loop depth
    def max_loop_depth(node, depth=0):
        if isinstance(node, (ast.For, ast.While)):
            depth += 1
        return max([depth] + [max_loop_depth(c, depth) for c in ast.iter_child_nodes(node)])

    loop_depth = max_loop_depth(tree)
    has_recursion = any(
        code.count(node.name) > 1
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    )
    has_sort = bool(re.search(r"\b(sorted|\.sort\b|heapq)", code))
    allocs = sum(1 for n in ast.walk(tree) if isinstance(n, (ast.List, ast.Dict, ast.Set)))

    if loop_depth == 0 and not has_recursion:
        time_c = "O(1)"
    elif loop_depth == 1 and not has_sort:
        time_c = "O(n)"
    elif loop_depth >= 2:
        time_c = "O(n²)"
    elif has_sort:
        time_c = "O(n log n)"
    elif has_recursion:
        time_c = "O(n)"
    else:
        time_c = "O(n)"

    space_c = "O(1)" if allocs == 0 else "O(n)"

    return {
        "time": time_c,
        "space": space_c,
        "confidence": "high" if loop_depth <= 2 and not has_recursion else "medium",
    }


# ─────────────────────────────────────────────────────────────────────────────
# ROUTES — Interview
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/api/interview/start", methods=["POST"])
def start_interview():
    data       = request.json
    session_id = str(uuid.uuid4())
    mode       = data.get("mode", "behavioral")
    difficulty = data.get("difficulty", "Mid")
    resume     = data.get("resume", "")

    sess = get_session(session_id)

    init_content = (
        f"Start a {difficulty} {mode} interview."
        + (f" Candidate resume: {resume[:600]}" if resume else "")
        + " Ask question 1 of 5."
    )
    sess["messages"].append({"role": "user", "content": init_content})
    print(sess["messages"])

    try:
        resp = call_groq(INTERVIEW_SYSTEM_PROMPT, sess["messages"])
        # start1 = time.perf_counter()
        sess["messages"].append({"role": "assistant", "content": json.dumps(resp)})
        sess["question_num"] = 1
        return jsonify({"session_id": session_id, "response": resp})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    # finally:
    #     print((time.perf_counter() - start1) * 1000)


@app.route("/api/interview/answer", methods=["POST"])
def submit_answer():
    data       = request.json
    session_id = data.get("session_id")
    answer     = data.get("answer", "")
    next_q     = data.get("question_num", 1) + 1

    sess = get_session(session_id)

    content = (
        f'Candidate answer: "{answer}"\n\n'
        + (f"Evaluate and ask question {next_q} of 5." if next_q <= 5
           else "Evaluate. This was the final question — set session_complete: true.")
    )
    sess["messages"].append({"role": "user", "content": content})
    print(sess["messages"])

    try:
        resp = call_groq(INTERVIEW_SYSTEM_PROMPT, sess["messages"])
        sess["messages"].append({"role": "assistant", "content": json.dumps(resp)})
        if resp.get("evaluation") and resp["evaluation"].get("score") is not None:
            sess["scores"].append(resp["evaluation"]["score"])
        sess["question_num"] = next_q
        return jsonify({"response": resp, "scores": sess["scores"]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ─────────────────────────────────────────────────────────────────────────────
# ROUTES — Code Analysis
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/api/code/run", methods=["POST"])
def run_code():
    data       = request.json
    code       = data.get("code", "")
    test_cases = data.get("test_cases", [])

    safe, reason = is_safe_code(code)
    if not safe:
        return jsonify({"error": f"Code blocked: {reason}"}), 400

    results = []
    for i, tc in enumerate(test_cases):
        result = run_python_code(code, tc["input"], data.get("time_limit_ms", 3000))
        actual   = result.get("result")
        error    = result.get("error")
        passed   = error is None and actual == tc["expected"]
        results.append({
            "label":      tc.get("label", f"Test {i+1}"),
            "input":      tc["input"],
            "expected":   tc["expected"],
            "actual":     actual,
            "passed":     passed,
            "runtime_ms": result.get("runtime_ms", 0),
            "error":      error,
        })

    complexity = analyse_complexity(code)
    all_passed = bool(results) and all(r["passed"] for r in results)
    pass_rate  = sum(1 for r in results if r["passed"]) / len(results) if results else 0

    return jsonify({
        "results":    results,
        "complexity": complexity,
        "all_passed": all_passed,
        "pass_rate":  round(pass_rate, 2),
    })


@app.route("/api/code/review", methods=["POST"])
def review_code():
    data         = request.json
    problem      = data.get("problem", {})
    code         = data.get("code", "")
    test_results = data.get("test_results", [])

    passed = sum(1 for r in test_results if r.get("passed"))
    total  = len(test_results)

    user_msg = (
        f"Problem: {problem.get('title', 'Unknown')}\n"
        f"Description: {problem.get('description', '')}\n\n"
        f"Code:\n```python\n{code}\n```\n\n"
        f"Tests: {passed}/{total} passed\n"
        f"Details: {json.dumps([{'label': r['label'], 'passed': r['passed'], 'error': r.get('error')} for r in test_results])}\n\n"
        "Analyse code quality, complexity, and generate 3 follow-up interview questions."
    )

    try:
        resp = call_groq(CODE_REVIEW_PROMPT, [{"role": "user", "content": user_msg}], temperature=0.4)
        return jsonify(resp)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ─────────────────────────────────────────────────────────────────────────────
# STATIC FILES
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory("static", "index.html")

@app.route("/<path:path>")
def static_files(path):
    return send_from_directory("static", path)


if __name__ == "__main__":
    print("Starting AI Interview System...")
    print(f"Using model: {get_model_name()}")
    print("Open http://localhost:5000 in your browser")
    app.run(debug=True, port=5000)