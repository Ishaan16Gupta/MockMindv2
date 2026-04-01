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
- If the score is below 6, you MUST ask a follow-up question (this is non-optional) — set should_follow_up: true and populate the follow_up field
- Be professional, encouraging, and precise
- Never reveal scores or rubric to candidate
- After every answer (except the first question), speak a natural 1-2 sentence verbal reaction
  acknowledging what the candidate said and briefly noting what was strong or what could be
  improved — as a real interviewer would. This goes in the "transition" field.

ALWAYS respond in this exact JSON format (no markdown, no extra text):
{
  "question": "the question text",
  "transition": "natural spoken acknowledgement of the previous answer before asking next question, or null on the first turn",
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

On the FIRST message set evaluation and transition to null. Keep questions sharp. Probe for depth."""

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
    question_num = 1

    # ── Start the session ────────────────────────────────────────────────────
    init_content = (
        f"Start a {difficulty} {mode} interview."
        + (f" Candidate resume: {resume[:600]}" if resume else "")
        + f" Ask question {question_num} of {TOTAL_QUESTIONS}."
    )
    messages.append({"role": "user", "content": init_content})

    print("\nStarting interview…\n")
    print(f"Asking Q{question_num}")

    resp = ask_groq(messages)
    messages.append({"role": "assistant", "content": json.dumps(resp)})

    print("[say] first question")
    say(resp["question"])

    # ── Conversation loop ────────────────────────────────────────────────────
    while True:
        # Hear answer
        answer = hear()

    # Handle empty input (prevents infinite loop)
        if not answer.strip() or answer.strip().lower() == "[no speech detected]":
            if question_num == TOTAL_QUESTIONS:
                print("[say] no response → ending interview")
                say("No response detected. Ending interview.")
                break
            else:
                print("[say] didn't catch → retry")
                say("I didn't catch that. Please try again.")
                continue

        is_last_question = question_num == TOTAL_QUESTIONS

        # ── Step 1: Evaluate answer ───────────────────────────────────────────
        content = (
            f'Candidate answer: "{answer}"\n\n'
            + (
                "Evaluate the answer. If it is weak, incomplete, or incorrect, ask a follow-up question."
                if not is_last_question
                else "Evaluate. This was the final question."
            )
        )
        messages.append({"role": "user", "content": content})

        resp = ask_groq(messages)
        messages.append({"role": "assistant", "content": json.dumps(resp)})

        # ── Collect score ─────────────────────────────────────────────────────
        evaluation = resp.get("evaluation")
        score = None
        if evaluation and evaluation.get("score") is not None:
            score = evaluation["score"]
            scores.append(score)
            print(f"  [Score: {score}/10 | {evaluation.get('competency', '')}]")

        # ── Speak transition ──────────────────────────────────────────────────
        transition = resp.get("transition")
        if transition:
            print("[say] transition")
            say(transition)

        # ── FOLLOW-UP FLOW ────────────────────────────────────────────────────
        # Decide whether to follow up based on LLM flag OR low score.
        # If we decide to follow up but the LLM left follow_up null, we force
        # a second Groq call to generate the follow-up question ourselves.
        should_follow = resp.get("should_follow_up") or (score is not None and score < 6)

        if should_follow and not is_last_question:
            follow_up_question = resp.get("follow_up")

            # LLM failed to provide one → generate it explicitly
            if not follow_up_question:
                print("  [Follow-up: LLM didn't provide one — generating]")
                messages.append({
                    "role": "user",
                    "content": (
                        f'The candidate gave a weak answer: "{answer}". '
                        "Ask a single targeted follow-up question to probe deeper. "
                        "Respond in the same JSON format. Set evaluation to null."
                    )
                })
                fu_resp = ask_groq(messages)
                messages.append({"role": "assistant", "content": json.dumps(fu_resp)})
                follow_up_question = fu_resp.get("follow_up") or fu_resp.get("question")

            print("  [Follow-up triggered]")
            print("[say] follow-up question")
            say(follow_up_question)
            follow_up_answer = hear()

            if not follow_up_answer.strip() or follow_up_answer.strip().lower() == "[no speech detected]":
                print("[say] no response → moving on")
                say("No response detected. Moving to next question.")

            # Ask Groq for the next main question after the follow-up
            messages.append({
                "role": "user",
                "content": (
                    f'Follow-up answer: "{follow_up_answer}". '
                    f"Now ask question {question_num + 1} of {TOTAL_QUESTIONS}. Do NOT evaluate."
                )
            })
            resp = ask_groq(messages)
            messages.append({"role": "assistant", "content": json.dumps(resp)})

            fu_transition = resp.get("transition")
            if fu_transition:
                print("[say] follow-up transition")
                say(fu_transition)

        else:
            # ── No follow-up → ask next question directly ─────────────────────
            if not is_last_question:
                messages.append({
                    "role": "user",
                    "content": f"Generate question {question_num + 1} of {TOTAL_QUESTIONS}. Do NOT evaluate."
                })
                resp = ask_groq(messages)
                messages.append({"role": "assistant", "content": json.dumps(resp)})

        # ── Move to next question ─────────────────────────────────────────────
        if not is_last_question:
            question_num += 1

        # FIX 2: Backend controls termination
        if question_num > TOTAL_QUESTIONS:
            print("[say] closing")
            say("That concludes our interview. Thank you for your time!")
            break

        # ── Speak next question ──────────────────────────────────────────────
        if resp.get("question"):
            print("[say] next main question")
            say(resp["question"])

    print_scores(scores)

if __name__ == "__main__":
    run_interview()