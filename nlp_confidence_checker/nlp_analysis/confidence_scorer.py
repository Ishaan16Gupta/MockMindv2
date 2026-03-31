"""
Step 3 — Confidence scoring.

Scans every sentence for hedging language (low confidence) and assertive
language (high confidence).  Produces a 0-10 score and records every
sentence that contains a hedge as a "low confidence moment".
"""

from __future__ import annotations

import re
from typing import Any

import spacy

# ---------------------------------------------------------------------------
# Phrase lists (case-insensitive matching via compiled patterns)
# ---------------------------------------------------------------------------

HEDGE_PHRASES = [
    "I think",
    "I believe",
    "maybe",
    "possibly",
    "I'm not sure but",
    "could be",
    "might be",
    "I guess",
    "something like",
    "I don't know if",
    "not 100% sure",
    "I feel like",
]

ASSERTIVE_PHRASES = [
    "This is",
    "The solution is",
    "We need to",
    "This will",
    "The time complexity is",
    "This approach works because",
    "The reason is",
    "This handles",
    "We can",
    "This ensures",
]

_HEDGE_PATTERNS = [
    re.compile(r"\b" + re.escape(p) + r"\b", re.IGNORECASE)
    for p in HEDGE_PHRASES
]

_ASSERT_PATTERNS = [
    re.compile(r"\b" + re.escape(p) + r"\b", re.IGNORECASE)
    for p in ASSERTIVE_PHRASES
]

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
# Helpers
# ---------------------------------------------------------------------------

def _sentence_has_pattern(sentence: str, patterns: list[re.Pattern]) -> bool:
    """Return True if *any* pattern matches inside the sentence."""
    return any(p.search(sentence) for p in patterns)


def _count_pattern_hits(text: str, patterns: list[re.Pattern]) -> int:
    """Count total pattern matches across all patterns in the text."""
    return sum(len(p.findall(text)) for p in patterns)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def score_confidence(cleaned_transcript: str) -> dict[str, Any]:
    """
    Main entry point for Step 3.

    Parameters
    ----------
    cleaned_transcript : str
        Output of Step 1.

    Returns
    -------
    dict with keys: score, hedge_count, assert_count, low_confidence_moments
    """
    if not cleaned_transcript or not cleaned_transcript.strip():
        return {
            "score": 5.0,
            "hedge_count": 0,
            "assert_count": 0,
            "low_confidence_moments": [],
        }

    nlp = _get_nlp()
    doc = nlp(cleaned_transcript)

    hedge_count = 0
    assert_count = 0
    low_confidence_moments: list[str] = []

    for sent in doc.sents:
        sentence = sent.text.strip()
        if not sentence:
            continue

        sent_hedges = _count_pattern_hits(sentence, _HEDGE_PATTERNS)
        sent_asserts = _count_pattern_hits(sentence, _ASSERT_PATTERNS)

        hedge_count += sent_hedges
        assert_count += sent_asserts

        # Record entire sentence if it contained any hedge
        if sent_hedges > 0:
            low_confidence_moments.append(sentence)

    total = hedge_count + assert_count
    if total == 0:
        score = 5.0
    else:
        score = round((assert_count / total) * 10, 1)

    return {
        "score": score,
        "hedge_count": hedge_count,
        "assert_count": assert_count,
        "low_confidence_moments": low_confidence_moments,
    }
