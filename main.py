"""
AI Mock Interview – CLI + Voice
Run: python main.py
"""

import json
import time

import api_code_editor.groq_service as gq
from speech_portion.stt import listen
from speech_portion.tts import speak

# ─────────────────────────────────────────────────────────────────────────────
# SYSTEM PROMPT  (mirrors app.py's INTERVIEW_SYSTEM_PROMPT)
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

TOTAL_QUESTIONS = 5

# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def ask_groq(messages: list[dict]) -> dict:
    """Call Groq and return the parsed JSON response."""
    start = time.perf_counter()
    resp = gq.call_groq(INTERVIEW_SYSTEM_PROMPT, messages)
    elapsed = time.perf_counter() - start
    print(f"  [response in {elapsed:.2f}s]")
    return resp


def say(text: str):
    """Print and speak a line."""
    print(f"\n🎙  Interviewer: {text}\n")
    speak(text=text)


def hear() -> str:
    """Listen for candidate speech and return the transcript."""
    print("🎤  Your turn (listening…)")
    transcript = listen()
    print(f"📝  You said: {transcript}\n")
    return transcript


def print_scores(scores: list[float]):
    if not scores:
        return
    avg = sum(scores) / len(scores)
    print("\n" + "═" * 50)
    print("  SESSION SUMMARY")
    print("═" * 50)
    for i, s in enumerate(scores, 1):
        bar = "█" * int(s) + "░" * (10 - int(s))
        print(f"  Q{i}: {bar}  {s:.1f}/10")
    print(f"\n  Average score: {avg:.1f}/10")
    verdict = "Strong hire ✅" if avg >= 7 else ("Consider 🤔" if avg >= 5 else "Not ready ❌")
    print(f"  Verdict: {verdict}")
    print("═" * 50 + "\n")


# ─────────────────────────────────────────────────────────────────────────────
# INTERVIEW SETUP
# ─────────────────────────────────────────────────────────────────────────────

def get_interview_config() -> tuple[str, str, str]:
    """Prompt the user for interview configuration via voice or CLI."""
    print("\n" + "═" * 50)
    print("  MockMind – AI Interview Session")
    print("═" * 50)

    mode = input("Interview mode (behavioral / technical) [behavioral]: ").strip() or "behavioral"
    difficulty = input("Difficulty (Junior / Mid / Senior) [Mid]: ").strip() or "Mid"
    use_resume = input("Paste resume text? (y/N): ").strip().lower()
    resume = ""
    if use_resume == "y":
        resume = input("Resume (one line): ").strip()

    return mode, difficulty, resume


# ─────────────────────────────────────────────────────────────────────────────
# MAIN LOOP
# ─────────────────────────────────────────────────────────────────────────────

def run_interview():
    mode, difficulty, resume = get_interview_config()

    messages: list[dict] = []
    scores: list[float] = []
    question_num = 0

    # ── Start the session ────────────────────────────────────────────────────
    init_content = (
        f"Start a {difficulty} {mode} interview.\n"
        f"Session plan: {total_questions} questions total — "
        f"{cfg['resume_based']} resume-based, "
        f"{cfg['situational']} situational, "
        f"{cfg['technical']} technical.\n"
        f"Depth expectation: {cfg['depth']}.\n"
        f"Generate a follow-up if score is below {cfg['follow_up_threshold']}/10.\n"
        + (f"Candidate resume: {resume[:600]}\n" if resume else "")
        + "Ask question 1."
    )
    
    messages.append({"role": "user", "content": init_content})

    print("\nStarting interview…\n")
    resp = ask_groq(messages)
    messages.append({"role": "assistant", "content": json.dumps(resp)})
    question_num = 1

    say(resp["question"])

    # ── Conversation loop ────────────────────────────────────────────────────
    while True:
        answer = hear()

        next_q = question_num + 1
        is_last = next_q > TOTAL_QUESTIONS

        content = (
            f'Candidate answer: "{answer}"\n\n'
            + (
                f"Evaluate and ask question {next_q} of {TOTAL_QUESTIONS}."
                if not is_last
                else "Evaluate. This was the final question — set session_complete: true."
            )
        )
        messages.append({"role": "user", "content": content})

        resp = ask_groq(messages)
        messages.append({"role": "assistant", "content": json.dumps(resp)})

        # Collect score
        evaluation = resp.get("evaluation")
        if evaluation and evaluation.get("score") is not None:
            score = evaluation["score"]
            scores.append(score)
            print(f"  [Score: {score}/10 | {evaluation.get('competency', '')}]")
            if evaluation.get("feedback"):
                print(f"  [Feedback: {evaluation['feedback']}]")

        question_num = next_q

        # ── Follow-up or next question ───────────────────────────────────────
        if resp.get("should_follow_up") and resp.get("follow_up"):
            say(resp["follow_up"])
            # Collect the follow-up answer and fold it back into the thread
            follow_up_answer = hear()
            messages.append({
                "role": "user",
                "content": f'Follow-up answer: "{follow_up_answer}". Continue to the next question.'
            })
        elif resp.get("question"):
            say(resp["question"])

        # ── Session complete ─────────────────────────────────────────────────
        if resp.get("session_complete"):
            say("That concludes our interview. Thank you for your time!")
            break

        if question_num > TOTAL_QUESTIONS:
            say("That concludes our interview. Thank you for your time!")
            break

    print_scores(scores)


if __name__ == "__main__":
    run_interview()
