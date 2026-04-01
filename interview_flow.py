"""
AI Mock Interview – CLI + Voice
Run: python main.py
"""

import json
import time

import api_code_editor.groq_service as gq
from api_code_editor.interview_config import INTERVIEW_CONFIG, get_interview_config
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
    import datetime
    timestamp = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
    print(f"\n[{timestamp}] 🎙 [MODEL SPEAKING] Interviewer: {text}\n")
    speak(text=text)
    print(f"[{timestamp}] ✓ Speech finished")


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

# ─────────────────────────────────────────────────────────────────────────────
# API ENTRY POINT  (called by Flask routing.py)
# ─────────────────────────────────────────────────────────────────────────────

def start_session(role: str, company_type: str, mode: str, difficulty: str, resume: str = "") -> dict:
    """Start an interview session and return the first question + state.

    This is the programmatic entry point used by the Flask API route.
    It runs the Groq call for question 1 and returns everything the
    route handler needs to build its JSON response.

    Returns:
        {
            "question": str,           # first interview question
            "messages": list[dict],    # full message history so far
            "cfg": dict,               # interview config dict
            "total_questions": int,
            "question_num": int,       # always 1
        }
    """
    cfg = INTERVIEW_CONFIG.get(
        (mode, difficulty),
        INTERVIEW_CONFIG[("behavioral", "Mid")]
    )
    TOTAL_QUESTIONS = cfg["total_questions"]

    init_content = (
        f"Start a {difficulty} {mode} interview.\n"
        f"Target role: {role} at a {company_type} company.\n"
        f"Tailor questions to what {company_type} companies typically ask {role} candidates.\n"
        f"Session plan: {TOTAL_QUESTIONS} questions total — "
        f"{cfg['resume_based']} resume-based, "
        f"{cfg['situational']} situational, "
        f"{cfg['technical']} technical.\n"
        f"Depth expectation: {cfg['depth']}.\n"
        f"Generate a follow-up if score is below {cfg['follow_up_threshold']}/10.\n"
        + (f"Candidate resume:\n{resume[:2000]}\n" if resume else "")
        + "Ask question 1."
    )
    print(f"Init content: {init_content}\n")

    messages: list[dict] = [{"role": "user", "content": init_content}]
    resp = ask_groq(messages)
    print(f"Response: {resp}\n")
    messages.append({"role": "assistant", "content": json.dumps(resp)})

    return {
        "question": resp["question"],
        "messages": messages,
        "cfg": cfg,
        "total_questions": TOTAL_QUESTIONS,
        "question_num": 1,
    }


def process_answer(session: dict, answer: str, question_num: int) -> dict:
    """Evaluate a candidate's answer and return the next interviewer response.

    This is the programmatic entry point used by POST /api/interview/answer.
    It handles the full evaluation → optional follow-up generation → next
    question flow, keeping routing.py simple.

    Enforces: only ONE follow-up per main question, then moves to next question.

    Args:
        session:      the session dict stored in SESSIONS (mutated in-place)
        answer:       the candidate's answer text
        question_num: 1-based index of the question being answered

    Returns:
        The Groq response dict, enriched with:
          - follow_up populated if LLM omitted it but a follow-up is needed
          - question populated with next question (if not last)
          - transition with natural acknowledgement
          - session_complete = True when this was the last question
    """
    messages       = session["messages"]
    cfg            = session["cfg"]
    total          = cfg["total_questions"]
    is_last        = question_num >= total

    # Initialize tracking dict if not present
    if "follow_ups_asked" not in session:
        session["follow_ups_asked"] = set()

    # Check if we've already asked a follow-up for THIS question
    already_asked_followup = question_num in session["follow_ups_asked"]

    content = (
        f'Candidate answer: "{answer}"\n\n'
        + (
            "Evaluate the answer. If it is weak, incomplete, or incorrect, ask a follow-up question."
            if not is_last
            else "Evaluate. This was the final question. Set session_complete to true."
        )
    )
    messages.append({"role": "user", "content": content})
    resp = ask_groq(messages)
    messages.append({"role": "assistant", "content": json.dumps(resp)})

    # Follow-up: trigger if LLM flagged it OR score is low
    # BUT ONLY if we haven't already asked a follow-up for this question
    evaluation    = resp.get("evaluation") or {}
    raw_score     = evaluation.get("score")
    score         = None
    if raw_score is not None:
        try:
            score = float(raw_score)
        except (TypeError, ValueError):
            print(f"[warn] Non-numeric score from model: {raw_score!r}")
    print(f"score: {score}")
    should_follow = (
        resp.get("should_follow_up") or 
        (score is not None and score < cfg["follow_up_threshold"])
    ) and not already_asked_followup

    if should_follow and not is_last and not resp.get("follow_up"):
        messages.append({
            "role": "user",
            "content": (
                f'The candidate gave a weak answer: "{answer}". '
                "Ask a single targeted follow-up question to probe deeper. "
                "Respond in the same JSON format. Set evaluation to null."
            ),
        })
        print(f"\n[Follow-up for Q{question_num}: generating]\n")
        fu_resp = ask_groq(messages)
        messages.append({"role": "assistant", "content": json.dumps(fu_resp)})
        resp["follow_up"]      = fu_resp.get("follow_up") or fu_resp.get("question")
        resp["should_follow_up"] = True
        session["follow_ups_asked"].add(question_num)
    elif should_follow and not is_last and resp.get("follow_up"):
        # Model already provided a follow-up; still mark this question as handled.
        session["follow_ups_asked"].add(question_num)

    # After a follow-up has been answered (detected by: already_asked_followup + not should_follow),
    # we need to ask for the next main question
    elif already_asked_followup and not resp.get("should_follow_up") and not is_last:
        print(f"\n[After follow-up for Q{question_num}: requesting next question]\n")
        messages.append({
            "role": "user",
            "content": f"Now ask question {question_num + 1} of {total}. Do NOT evaluate."
        })
        next_resp = ask_groq(messages)
        messages.append({"role": "assistant", "content": json.dumps(next_resp)})
        # Merge next question + transition into response
        resp["question"] = next_resp.get("question")
        resp["transition"] = next_resp.get("transition") or resp.get("transition")

    if is_last:
        resp["session_complete"] = True

    session["question_num"] = question_num + 1
    return resp


# ─────────────────────────────────────────────────────────────────────────────
# MAIN LOOP
# ─────────────────────────────────────────────────────────────────────────────

def run_interview(session_id: str, cfg: dict, messages: list[dict]):
    """Run the full interview conversation loop.

    Picks up where start_session() left off — the first question has already
    been fetched and spoken, so this loop starts by listening for the
    candidate's first answer.
    """
    TOTAL_QUESTIONS = cfg["total_questions"]
    scores: list[float] = []
    question_num = 1

    # The first question was already asked by start_session(); speak it now
    # so the candidate hears it before we start listening.
    first_q = json.loads(messages[-1]["content"])["question"]
    print("\nStarting interview…\n")
    print("[say] first question")
    say(first_q)

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

        # Backend controls termination
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
    # Standalone CLI mode: get config from terminal, then run
    role, company_type, mode, difficulty, resume = get_interview_config()
    session = start_session(role, company_type, mode, difficulty, resume)
    run_interview(
        session_id="cli-session",
        cfg=session["cfg"],
        messages=session["messages"],
    )