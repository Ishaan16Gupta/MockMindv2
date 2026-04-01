INTERVIEW_CONFIG = {
    ("behavioral", "Junior"): {
        "total_questions": 4,
        "resume_based": 2,
        "situational": 2,
        "technical": 0,
        "follow_up_threshold": 6,   # score below this triggers follow-up
        "depth": "surface-level, focus on basics and simple past experiences",
    },
    ("behavioral", "Mid"): {
        "total_questions": 5,
        "resume_based": 2,
        "situational": 2,
        "technical": 1,
        "follow_up_threshold": 7,
        "depth": "moderate depth, expect STAR format and ownership",
    },
    ("behavioral", "Senior"): {
        "total_questions": 6,
        "resume_based": 2,
        "situational": 2,
        "technical": 2,
        "follow_up_threshold": 7,
        "depth": "deep dive, expect leadership, ambiguity handling, and strategic thinking",
    },
    ("technical", "Junior"): {
        "total_questions": 5,
        "resume_based": 1,
        "situational": 0,
        "technical": 4,
        "follow_up_threshold": 6,
        "depth": "fundamentals only, basic DSA, no system design",
    },
    ("technical", "Mid"): {
        "total_questions": 6,
        "resume_based": 1,
        "situational": 1,
        "technical": 4,
        "follow_up_threshold": 7,
        "depth": "moderate DSA, one system design concept, past project deep-dive",
    },
    ("technical", "Senior"): {
        "total_questions": 7,
        "resume_based": 2,
        "situational": 1,
        "technical": 4,
        "follow_up_threshold": 7,
        "depth": "hard DSA, full system design, architecture trade-offs, leadership scenarios",
    },
}

def get_interview_config() -> tuple[str, str, str]:
    """Prompt the user for interview configuration via voice or CLI."""
    print("\n" + "═" * 50)
    print("  MockMind – AI Interview Session")
    print("═" * 50)

    mode = input("Interview mode (behavioral / technical) [behavioral]: ").strip() or "behavioral"
    difficulty = input("Difficulty (Junior / Mid / Senior) [Mid]: ").strip() or "Mid"
    use_resume = input("Paste resume text? (y/N): ").strip().lower()
    cfg=INTERVIEW_CONFIG.get((mode,difficulty),INTERVIEW_CONFIG[("behavioral", "Mid")])
    total_questions = cfg["total_questions"]
    resume = ""
    if use_resume == "y":
        resume = input("Resume (one line): ").strip()

    return mode, difficulty, resume