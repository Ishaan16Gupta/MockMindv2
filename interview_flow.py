"""
AI Mock Interview – CLI + Voice
Run: python main.py
"""

import json
import time
import random

import api_code_editor.groq_service as gq
from api_code_editor.interview_config import INTERVIEW_CONFIG, get_interview_config
from api_code_editor.problems import PROBLEMS
from speech_portion.stt import listen
from speech_portion.tts import speak

import sys
sys.path.append('nlp_confidence_checker')
from nlp_analysis import analyze

# ─────────────────────────────────────────────────────────────────────────────
# SYSTEM PROMPT  (merged with coding instructions)
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

CODING QUESTIONS — IMPORTANT:
- When you are given a coding problem (marked with [CODING PROBLEM]), you MUST use that exact problem as-is. Do NOT invent a different problem.
- For coding questions, set "requires_code_editor": true in your response.
- The "question" field for a coding problem must be a SHORT SPOKEN INTRO ONLY — 2-3 sentences max, e.g. "Alright, let's move to a coding problem. I've loaded it into the panel on your left — take a moment to read through it and let me know when you're ready." Do NOT recite the title, description, constraints, or examples in the question field — those are already displayed in the problem panel on the candidate's screen
- When evaluating a coding answer, you will receive the test results — evaluate based on correctness, complexity, and code quality from those results.
- ONLY mention syntax errors if they are explicitly present in the test results (i.e., the "error" field is not null).
- If no runtime or syntax error is present, DO NOT claim syntax issues.

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
  "requires_code_editor": false,
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


def _pick_problems(cfg: dict) -> list[dict]:
    """Pick `cfg['technical']` problems from the PROBLEMS bank without replacement."""
    count = cfg.get("technical", 0)
    if count == 0:
        return []
    pool = list(PROBLEMS)
    random.shuffle(pool)
    return pool[:count]


def _coding_problem_snippet(problem: dict) -> str:
    """Format a problem dict into a string for injection into the LLM prompt."""
    return (
        f"[CODING PROBLEM]\n"
        f"Title: {problem['title']} ({problem['difficulty']})\n"
        f"Description: {problem['description']}\n"
        f"Input: {problem['input_format']}\n"
        f"Output: {problem['output_format']}\n"
        f"Example: Input={problem['test_cases'][0]['input']} → Output={problem['test_cases'][0]['expected']}\n"
        f"Starter code:\n{problem['starter_code']}"
    )


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

    Returns:
        {
            "question": str,           # first interview question
            "messages": list[dict],    # full message history so far
            "cfg": dict,               # interview config dict
            "total_questions": int,
            "question_num": int,       # always 1
            "transcripts": list,       # transcript history for NLP analysis
            "camera_confidences": list, # camera confidence scores
            "requires_code_editor": bool, # whether first question needs code editor
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

    # Pick coding problems if this is a technical interview
    problems = _pick_problems(cfg)
    
    return {
        "question": resp["question"],
        "requires_code_editor": resp.get("requires_code_editor", False),
        "messages": messages,
        "cfg": cfg,
        "total_questions": TOTAL_QUESTIONS,
        "question_num": 1,
        "mode": mode,
        "transcripts": [],
        "camera_confidences": [],
        "problems": problems,
        "problem_index": 0,
    }


def process_answer(session: dict, answer: str, question_num: int, camera_confidence: float = None) -> dict:
    """Evaluate a candidate's answer and return the next interviewer response.

    Handles both behavioral and coding questions. For coding:
    1. Detects if this answer is for a coding problem
    2. Evaluates using run_coding_round 
    3. Includes analysis in response

    Args:
        session:      the session dict stored in SESSIONS (mutated in-place)
        answer:       the candidate's answer text (code for coding questions)
        question_num: 1-based index of the question being answered
        camera_confidence: confidence score from camera analysis (0-10)

    Returns:
        The Groq response dict, enriched with:
          - coding_result/coding_analysis (if coding question)
          - nlp_report: NLP analysis with camera confidence
          - requires_code_editor: whether next question needs editor
          - session_complete: True when this was the last question
    """
    messages      = session["messages"]
    cfg           = session["cfg"]
    total         = cfg["total_questions"]
    is_last       = question_num >= total

    # Initialize tracking if not present
    if "follow_ups_asked" not in session:
        session["follow_ups_asked"] = set()
    if "transcripts" not in session:
        session["transcripts"] = []
    if "camera_confidences" not in session:
        session["camera_confidences"] = []

    already_asked_followup = question_num in session["follow_ups_asked"]

    # ── DETECT IF THIS ANSWER IS FOR A CODING QUESTION ────────────────────────
    active_coding_problem = session.get("active_coding_problem")
    is_coding_answer = active_coding_problem is not None

    coding_result  = None
    analysis       = None
    coding_followup = None

    if is_coding_answer:
        from code_editor import run_coding_round

        problem = active_coding_problem
        result  = run_coding_round(answer, problem=problem)

        coding_result   = result
        analysis        = result.get("analysis")
        coding_followup = result.get("follow_up_question")

        analysis_snippet = ""
        if analysis:
            analysis_snippet = (
                f'\nCode analysis: summary="{analysis.get("summary", "")}", '
                f'strengths={analysis.get("strengths", [])}, '
                f'issues={analysis.get("issues", [])}, '
                f'complexity="{analysis.get("complexity_note", "")}"'
            )

        content = (
            f'Candidate submitted code for "{problem["title"]}".\n'
            f'Test results: {json.dumps(coding_result)}'
            f'{analysis_snippet}\n\n'
            + (
                "Briefly acknowledge the submission using the analysis — 2 sentences max. "
                "This is the final question. Set session_complete to true."
                if is_last else
                "Briefly acknowledge the submission using the analysis — 2 sentences max. "
                "Do NOT ask a follow-up question yet."
            )
        )
        session["active_coding_problem"] = None
        session["transcripts"].append(answer[:500])  # Store truncated code for NLP

        if coding_followup and not is_last:
            session["pending_coding_followup"] = {
                "question": coding_followup,
                "question_num": question_num,
            }

    else:
        content = (
            f'Candidate answer: "{answer}"\n\n'
            + (
                "Evaluate the answer. If it is weak, incomplete, or incorrect, ask a follow-up question."
                if not is_last
                else "Evaluate. This was the final question. Set session_complete to true."
            )
        )
        session["transcripts"].append(answer)

    if camera_confidence is not None:
        session["camera_confidences"].append(camera_confidence)

    messages.append({"role": "user", "content": content})
    resp = ask_groq(messages)
    messages.append({"role": "assistant", "content": json.dumps(resp)})

    # ── Attach coding result + analysis to response ────────────────────────────
    if coding_result is not None:
        resp["coding_result"] = coding_result
    if analysis is not None:
        resp["coding_analysis"] = analysis

    # ── INJECT PENDING CODING FOLLOW-UP (overrides normal follow-up logic) ─────
    pending_fu = session.pop("pending_coding_followup", None)
    if pending_fu and not is_last:
        resp["follow_up"]        = pending_fu["question"]
        resp["should_follow_up"] = True
        session["follow_ups_asked"].add(question_num)
        session["question_num"]  = question_num + 1
        return resp

    # ── FOLLOW-UP: trigger if LLM flagged OR score is low ──────────────────────
    # BUT ONLY if we haven't already asked a follow-up for this question
    evaluation = resp.get("evaluation") or {}
    raw_score  = evaluation.get("score")
    score      = None
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
        resp["follow_up"]        = fu_resp.get("follow_up") or fu_resp.get("question")
        resp["should_follow_up"] = True
        session["follow_ups_asked"].add(question_num)
    elif should_follow and not is_last and resp.get("follow_up"):
        session["follow_ups_asked"].add(question_num)

    # ── ENFORCE: move to next question after follow-up ────────────────────────
    elif already_asked_followup and not is_last:
        print(f"\n[After follow-up for Q{question_num}: moving to next question]\n")
        next_q_num = question_num + 1
        next_problem, next_problem_snippet = _get_next_problem_for_prompt(session, cfg, next_q_num)
        next_prompt = f"Now ask question {next_q_num} of {total}. Do NOT evaluate."
        if next_problem_snippet:
            next_prompt += f"\n\nUse this exact coding problem:\n{next_problem_snippet}"
        messages.append({"role": "user", "content": next_prompt})
        next_resp = ask_groq(messages)
        messages.append({"role": "assistant", "content": json.dumps(next_resp)})
        resp["question"]             = next_resp.get("question")
        resp["transition"]           = next_resp.get("transition") or resp.get("transition")
        resp["requires_code_editor"] = next_resp.get("requires_code_editor", False)
        resp["should_follow_up"]     = False
        resp["follow_up"]            = None

    # ── If no follow-up: ask next question ──────────────────────────────────────
    elif not should_follow and not already_asked_followup and not is_last:
        next_q_num = question_num + 1
        next_problem, next_problem_snippet = _get_next_problem_for_prompt(session, cfg, next_q_num)
        next_prompt = f"Generate question {next_q_num} of {total}. Do NOT evaluate."
        if next_problem_snippet:
            next_prompt += f"\n\nUse this exact coding problem:\n{next_problem_snippet}"
        messages.append({"role": "user", "content": next_prompt})
        next_resp = ask_groq(messages)
        messages.append({"role": "assistant", "content": json.dumps(next_resp)})
        resp["question"]             = next_resp.get("question")
        resp["transition"]           = next_resp.get("transition") or resp.get("transition")
        resp["requires_code_editor"] = next_resp.get("requires_code_editor", False)

    # ── Run NLP analysis on combined transcripts ─────────────────────────────────
    combined_transcript = " ".join(session["transcripts"])
    nlp_result = analyze(combined_transcript)
    camera_scores = session["camera_confidences"]
    if camera_scores:
        avg_camera = sum(camera_scores) / len(camera_scores)
        nlp_result["camera_confidence"] = avg_camera
    else:
        nlp_result["camera_confidence"] = None
    resp["nlp_report"] = nlp_result

    if is_last:
        resp["session_complete"] = True

    session["question_num"] = question_num + 1
    return resp


def _get_next_problem_for_prompt(session: dict, cfg: dict, next_q_num: int) -> tuple:
    """
    Returns (problem_dict, snippet_str) if the next question is a coding question.
    Promotes pending_coding_problem -> active_coding_problem.
    Returns (None, None) otherwise.
    """
    total = cfg["total_questions"]
    technical_count = cfg.get("technical", 0)
    if technical_count == 0:
        return None, None

    non_technical = total - technical_count
    coding_q_numbers = list(range(non_technical + 1, total + 1))

    if next_q_num in coding_q_numbers:
        problem = session.get("pending_coding_problem")
        if problem:
            session["active_coding_problem"] = problem
            session.pop("pending_coding_problem", None)
            return problem, _coding_problem_snippet(problem)

    return None, None


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