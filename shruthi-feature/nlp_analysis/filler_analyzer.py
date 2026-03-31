"""
Step 2 — Filler word analysis.

Scans the *cleaned* transcript for filler words and phrases.
Uses spaCy POS tagging for context-aware detection of ambiguous
fillers like "like", "so", and "right".

Returns total count, rate per minute (at 130 wpm), per-filler
breakdown, and the top 3 most frequent fillers.
"""

from __future__ import annotations

import re
from typing import Any

import spacy

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SPEAKING_PACE_WPM = 130

# Unambiguous fillers — always count when matched as whole words.
_UNAMBIGUOUS_FILLERS = [
    "um", "uh", "you know", "basically", "sort of",
    "kind of", "literally", "honestly", "I mean",
]

# Ambiguous fillers — need POS / context checks.
_AMBIGUOUS_FILLERS = ["like", "right", "so"]

# All fillers (for reporting order).
ALL_FILLERS = _UNAMBIGUOUS_FILLERS + _AMBIGUOUS_FILLERS

# Pre-compiled patterns for unambiguous fillers (case-insensitive, word boundary).
_UNAMBIGUOUS_PATTERNS = {
    filler: re.compile(r"\b" + re.escape(filler) + r"\b", re.IGNORECASE)
    for filler in _UNAMBIGUOUS_FILLERS
}

# ---------------------------------------------------------------------------
# spaCy model (lazy singleton)
# ---------------------------------------------------------------------------
_nlp = None


def _get_nlp():
    global _nlp
    if _nlp is None:
        _nlp = spacy.load("en_core_web_sm")
    return _nlp


# ---------------------------------------------------------------------------
# Context-aware detection for ambiguous fillers
# ---------------------------------------------------------------------------

def _count_filler_like(doc) -> int:
    """
    Count 'like' used as a filler vs. meaningful verb/preposition.

    Heuristic: 'like' is a filler when it is NOT:
      - A verb (POS=VERB): "I like hashmaps"
      - A preposition/conjunction introducing a comparison (POS=ADP/SCONJ):
        "works like a queue"
    Anything else (INTJ, ADV, or spaCy's uncertain tag) → filler.
    """
    count = 0
    for token in doc:
        if token.lower_ == "like":
            if token.pos_ not in ("VERB", "ADP", "SCONJ"):
                count += 1
    return count


def _count_filler_so(doc) -> int:
    """
    Count 'so' used as a filler vs. meaningful conjunction/adverb.

    Heuristic: 'so' at the start of a sentence (or after a comma) and
    tagged as an adverb or conjunction is likely a filler.  When it
    modifies an adjective ("so large") it's meaningful.
    """
    count = 0
    for token in doc:
        if token.lower_ == "so":
            # "so" modifying an adjective → meaningful ("so large")
            if token.head.pos_ == "ADJ" and token.dep_ == "advmod":
                continue
            # "so that" → meaningful conjunction
            if token.i + 1 < len(doc) and doc[token.i + 1].lower_ == "that":
                continue
            # sentence-initial or post-comma "so" → filler
            if token.i == 0 or token.is_sent_start or (
                token.i > 0 and doc[token.i - 1].text == ","
            ):
                count += 1
    return count


def _count_filler_right(doc) -> int:
    """
    Count 'right' used as a filler / tag question vs. adjective.

    Heuristic: 'right' is a filler when used as a discourse marker —
    typically sentence-final or followed by comma/question mark.
    When it precedes a noun ("right approach") it's an adjective.
    """
    count = 0
    for token in doc:
        if token.lower_ == "right":
            # Adjective usage: "the right answer"
            if token.pos_ == "ADJ" and token.dep_ in ("amod", "attr"):
                continue
            # Noun-modifying position
            if token.i + 1 < len(doc) and doc[token.i + 1].pos_ == "NOUN":
                continue
            # Direction usage
            if token.i > 0 and doc[token.i - 1].lower_ in ("turn", "go", "move"):
                continue
            count += 1
    return count


_AMBIGUOUS_COUNTERS = {
    "like": _count_filler_like,
    "so": _count_filler_so,
    "right": _count_filler_right,
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def analyze_fillers(cleaned_transcript: str) -> dict[str, Any]:
    """
    Main entry point for Step 2.

    Parameters
    ----------
    cleaned_transcript : str
        The output of Step 1 (cleaned transcript).

    Returns
    -------
    dict with keys: count, rate_per_minute, breakdown, top_three
    """
    if not cleaned_transcript or not cleaned_transcript.strip():
        return {
            "count": 0,
            "rate_per_minute": 0.0,
            "breakdown": {},
            "top_three": [],
        }

    nlp = _get_nlp()
    doc = nlp(cleaned_transcript)

    breakdown: dict[str, int] = {}

    # 1. Count unambiguous fillers via regex
    for filler, pattern in _UNAMBIGUOUS_PATTERNS.items():
        n = len(pattern.findall(cleaned_transcript))
        if n > 0:
            breakdown[filler] = n

    # 2. Count ambiguous fillers via spaCy POS context
    for filler, counter_fn in _AMBIGUOUS_COUNTERS.items():
        n = counter_fn(doc)
        if n > 0:
            breakdown[filler] = n

    total = sum(breakdown.values())

    # Rate per minute: total fillers / (word_count / speaking_pace)
    word_count = len(cleaned_transcript.split())
    if word_count > 0:
        minutes = word_count / SPEAKING_PACE_WPM
        rate = round(total / minutes, 1) if minutes > 0 else 0.0
    else:
        rate = 0.0

    # Top 3 by frequency (descending), ties broken alphabetically
    sorted_fillers = sorted(
        breakdown.items(), key=lambda x: (-x[1], x[0])
    )
    top_three = [f for f, _ in sorted_fillers[:3]]

    return {
        "count": total,
        "rate_per_minute": rate,
        "breakdown": breakdown,
        "top_three": top_three,
    }
