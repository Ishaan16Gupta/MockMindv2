import json
import time
import random

import api_code_editor.groq_service as gq
from speech_portion.stt import listen
from speech_portion.tts import speak
from api_code_editor.problems import PROBLEMS
from api_code_editor.code_runner import(
    is_safe_code,
    run_python_code,
    analyse_complexity
)

def run_coding_interview():
    print("\n" + "═" * 50)
    print("💻 CODING INTERVIEW ROUND")
    print("═" * 50)

    # Pick a problem
    problem = random.choice(PROBLEMS)

    # ── Ask like interviewer ───────────────────
    print(f"\n👨‍💻 Interviewer:")
    print(f"Let's work on a coding problem.\n")

    print(f"Problem: {problem['title']} ({problem['difficulty']})\n")
    print(problem["description"])

    print("\nInput Format:", problem["input_format"])
    print("Output Format:", problem["output_format"])

    print("\nExample Test Cases:")
    for tc in problem["test_cases"][:2]:
        print(f"  Input: {tc['input']} → Output: {tc['expected']}")

    print("\nStarter Code:\n")
    print(problem["starter_code"])

    input("\n👉 Press Enter when you're ready to code...")

    # ── Get user code ──────────────────────────
    print("\n✍️  Paste your solution below")
    print("Type 'END' on a new line to finish:\n")

    lines = []
    while True:
        line = input()
        if line.strip().upper() == "END":
            break
        lines.append(line)

    code = "\n".join(lines)

    # ── Safety check ───────────────────────────
    safe, reason = is_safe_code(code)
    if not safe:
        print(f"\n❌ Code rejected: {reason}")
        return

    # ── Run tests ─────────────────────────────
    print("\n🧪 Running test cases...\n")

    results = []
    passed_count = 0

    for i, tc in enumerate(problem["test_cases"], 1):
        res = run_python_code(code, tc["input"])

        actual = res.get("result")
        error = res.get("error")
        passed = error is None and actual == tc["expected"]

        if passed:
            passed_count += 1

        print(f"Test {i}: {'✅ PASS' if passed else '❌ FAIL'}")
        print(f"  Input: {tc['input']}")
        print(f"  Expected: {tc['expected']}")
        print(f"  Got: {actual}")
        print(f"  Runtime: {res.get('runtime_ms')} ms")

        if error:
            print(f"  Error: {error}")

        print()

        results.append({
            "passed": passed,
            "error": error
        })

    # ── Complexity ─────────────────────────────
    complexity = analyse_complexity(code)

    # ── Summary ────────────────────────────────
    total = len(problem["test_cases"])
    pass_rate = passed_count / total if total else 0

    print("═" * 50)
    print("📊 INTERVIEW SUMMARY")
    print("═" * 50)
    print(f"Passed: {passed_count}/{total}")
    print(f"Pass Rate: {pass_rate * 100:.0f}%")
    print(f"Time Complexity: {complexity['time']}")
    print(f"Space Complexity: {complexity['space']}")

    # Interview-style verdict
    if pass_rate == 1:
        print("\n🟢 Strong hire signal")
    elif pass_rate >= 0.5:
        print("\n🟡 Partial solution — needs improvement")
    else:
        print("\n🔴 Weak solution")

    print("═" * 50)

    # ── AI Analysis ───────────────────────────────
    analysis = analyze_and_generate_questions(problem, code, results)

    if analysis:
        print("\n🤖 AI REVIEW\n")

        review = analysis.get("review", {})
        print("📊 Summary:", review.get("summary", ""))

        print("\n✅ Strengths:")
        for s in review.get("strengths", []):
            print(" •", s)

        print("\n❌ Issues:")
        for i in review.get("issues", []):
            print(" •", i)

        print("\n🧠 Edge Case Questions:")
        for q in analysis.get("edge_case_questions", []):
            print(" •", q)

        print("\n🎯 Follow-up Questions:")
        for q in analysis.get("follow_up_questions", []):
            print(" •", q)

# ── Generate feedback and questions ───────────────────────────────
def analyze_and_generate_questions(problem, code, results):
    import api_code_editor.groq_service as gq
    import json

    prompt = f"""
You are a senior software engineer conducting a coding interview.

Analyze the candidate's solution and respond in STRICT JSON format:

{{
  "review": {{
    "summary": "one sentence overall assessment",
    "strengths": ["strength 1", "strength 2"],
    "issues": ["issue 1", "issue 2"]
  }},
  "edge_case_questions": [
    "question about an edge case",
    "another edge case question"
  ],
  "follow_up_questions": [
    "question about time complexity",
    "question about optimization",
    "question about design improvement"
  ]
}}

Problem:
{problem['title']}

Description:
{problem['description']}

Candidate Code:
{code}

Test Results:
{results}

Instructions:
- Review correctness, logic, and code quality
- Use test results to identify weaknesses
- Ask edge case questions BASED ON THE CODE (not generic)
- Ask realistic follow-up interview questions
- Keep everything concise
- DO NOT include anything outside JSON
"""

    response = gq.call_groq(
        "You are a strict coding interviewer. Only return valid JSON.",
        [{"role": "user", "content": prompt}]
    )

    # Optional: parse safely
    try:
        return response if isinstance(response, dict) else json.loads(response)
    except Exception:
        print("⚠️ Failed to parse response")
        print(response)
        return None


# ── API ENTRY POINTS FOR INTERVIEW FLOW ─────────────────────────────────────

def get_problem() -> dict:
    """Return a random problem for the frontend to display."""
    problem = random.choice(PROBLEMS)
    return problem


def analyze_code_submission(problem: dict, code: str, results: list) -> dict:
    """
    Sends code + test results to Groq and returns a structured analysis.
    Returns: { "summary": str, "strengths": [...], "issues": [...] }
    """
    prompt = f"""
You are a senior software engineer reviewing a coding interview submission.

Problem: {problem['title']}
Description: {problem['description']}

Candidate Code:
{code}

Test Results:
{json.dumps(results, indent=2)}

Respond ONLY in this JSON format, no extra text:
{{
  "summary": "one sentence overall assessment",
  "strengths": ["strength 1", "strength 2"],
  "issues": ["issue 1", "issue 2"]
}}

- Base strengths and issues on the actual code and test results
- If no issues, write "None" in issues list
- ONLY mention syntax errors if explicitly present in test results
- If no error is present, DO NOT claim syntax issues
- Keep everything concise
"""
    response = gq.call_groq(
        "You are a strict coding interviewer. Only return valid JSON.",
        [{"role": "user", "content": prompt}]
    )
    try:
        return response if isinstance(response, dict) else json.loads(response)
    except Exception:
        print("⚠️ Failed to parse analysis response")
        return {"summary": "Could not analyze.", "strengths": [], "issues": []}


def generate_coding_followup(problem: dict, code: str, analysis: dict) -> str:
    """
    Given the analysis of a submission, generates one targeted follow-up question.
    Returns: a single follow-up question string.
    """
    prompt = f"""
You are conducting a coding interview. The candidate just submitted a solution.

Problem: {problem['title']}

Their code:
{code}

Your analysis of their solution:
{json.dumps(analysis, indent=2)}

Ask ONE specific follow-up question. It should probe:
- A weakness or edge case you identified in their code, OR
- Their understanding of the time/space complexity of their approach, OR
- How they would improve or scale their solution

Return ONLY the question as a plain string. No JSON, no preamble.
"""
    response = gq.call_groq(
        "You are a strict coding interviewer. Ask one sharp follow-up question.",
        [{"role": "user", "content": prompt}]
    )
    if isinstance(response, dict):
        return response.get("question") or response.get("text") or str(response)
    return str(response).strip()


def run_coding_round(code: str, problem: dict = None) -> dict:
    """API entry point: evaluate submitted code and return results as a dict.

    Args:
        code:    the candidate's submitted code
        problem: the exact problem dict that was shown to the candidate.
                 If None, a random problem is picked.
    """
    if problem is None:
        problem = random.choice(PROBLEMS)

    safe, reason = is_safe_code(code)
    if not safe:
        return {"error": reason, "problem": problem["title"]}

    results = []
    passed_count = 0
    for tc in problem["test_cases"]:
        res = run_python_code(code, tc["input"])
        passed = res.get("error") is None and res.get("result") == tc["expected"]
        if passed:
            passed_count += 1
        results.append({
            "passed": passed,
            "input": tc["input"],
            "expected": tc["expected"],
            "got": res.get("result"),
            "runtime_ms": res.get("runtime_ms"),
            "error": res.get("error"),
        })

    total = len(problem["test_cases"])
    complexity = analyse_complexity(code)
    analysis = analyze_code_submission(problem, code, results)
    follow_up = generate_coding_followup(problem, code, analysis)

    return {
        "problem": problem["title"],
        "difficulty": problem["difficulty"],
        "passed": passed_count,
        "total": total,
        "pass_rate": passed_count / total if total else 0,
        "complexity": complexity,
        "results": results,
        "analysis": analysis,
        "follow_up_question": follow_up,
    }


def problem_description(problem) -> dict:
    """Return a clean problem description for the frontend."""
    return {
        "title": problem["title"],
        "difficulty": problem["difficulty"],
        "description": problem["description"],
        "input_format": problem["input_format"],
        "output_format": problem["output_format"],
        "test_cases": problem["test_cases"][:2],  # only show examples
        "starter_code": problem["starter_code"],
    }



if __name__ == "__main__":
    mode = input("\nMode (voice / coding): ").strip().lower()

    if mode == "coding":
        run_coding_interview()

    