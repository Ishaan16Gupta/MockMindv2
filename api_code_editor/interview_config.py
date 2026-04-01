import pdfplumber
import docx
import os

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
    ("resume", "Junior"): {
        "total_questions": 4,
        "resume_based": 3,
        "situational": 1,
        "technical": 0,
        "follow_up_threshold": 6,
        "depth": "walk through past experiences, basic ownership and decisions",
    },
    ("resume", "Mid"): {
        "total_questions": 5,
        "resume_based": 4,
        "situational": 1,
        "technical": 0,
        "follow_up_threshold": 7,
        "depth": "deep dive into past projects, decisions, and ownership",
    },
    ("resume", "Senior"): {
        "total_questions": 6,
        "resume_based": 4,
        "situational": 2,
        "technical": 0,
        "follow_up_threshold": 7,
        "depth": "strategic decisions, leadership, measurable impact from past roles",
    },
}

def parse_resume(file_path: str) -> str:
    ext = os.path.splitext(file_path)[1].lower() 
    if ext=='.pdf':
        with pdfplumber.open(file_path) as pdf:
            return "\n".join(page.extract_text() or "" for page in pdf.pages)
    elif ext in (".docx", ".doc"):
        doc = docx.Document(file_path)
        return "\n".join(para.text for para in doc.paragraphs)
    elif ext==".txt":
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    else : raise ValueError(f"Unsupported file type : {ext}. Supoorted: pdf, doc, docx, txt")

def get_interview_config() -> tuple[str, str, str, str, str]:
    """Prompt the user for interview configuration via voice or CLI."""
    print("\n" + "═" * 50)
    print("  MockMind – AI Interview Session")
    print("═" * 50)

    role = input("Target Role: ").strip() or "Software Engineer" 
    company_type = input("Company Type ").strip() or "FAANG"
    mode = input("Interview mode (behavioral / technical/ resume-based) [behavioral]: ").strip() or "behavioral"
    difficulty = input("Difficulty (Junior / Mid / Senior) [Mid]: ").strip() or "Mid"
    
    resume = ""
    file_path = input("Resume file path (leave blank to skip): ").strip()
    if file_path:
        try:
            resume = parse_resume(file_path)
            print(f"  ✅ Resume parsed ({len(resume)} characters)")
        except Exception as e:
            print(f"  ⚠️  Could not parse resume: {e}")

    return role, company_type, mode, difficulty, resume