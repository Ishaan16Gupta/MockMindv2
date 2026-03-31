"""
Pipeline orchestrator — Steps 1, 2, and 3.

Takes raw speech-to-text transcript and returns a structured dict with:
  - cleaned_transcript : cleaned, punctuated text
  - filler_words       : counts, rate per minute, top 3 fillers
  - confidence         : score (0-10), hedge/assert counts, shaky moments

Usage:
    from nlp_analysis import analyze
    result = analyze(raw_transcript)
"""

from __future__ import annotations

import json
from typing import Any

from nlp_analysis.transcript_cleaner import clean_transcript
from nlp_analysis.filler_analyzer import analyze_fillers
from nlp_analysis.confidence_scorer import score_confidence


def analyze(transcript: str) -> dict[str, Any]:
    """
    Run the NLP analysis pipeline on a raw speech-to-text transcript.

    Parameters
    ----------
    transcript : str
        Raw transcript string from a speech-to-text converter.

    Returns
    -------
    dict with keys: cleaned_transcript, filler_words, confidence
    """
    # Step 1 — Clean the raw STT output
    cleaned = clean_transcript(transcript)

    # Step 2 — Count filler words
    filler_result = analyze_fillers(cleaned)

    # Step 3 — Score confidence
    confidence_result = score_confidence(cleaned)

    return {
        "cleaned_transcript": cleaned,
        "filler_words": filler_result,
        "confidence": confidence_result,
    }


def analyze_to_json(transcript: str, indent: int | None = 2) -> str:
    """Same as analyze() but returns a JSON string instead of a dict."""
    return json.dumps(analyze(transcript), indent=indent, ensure_ascii=False)
