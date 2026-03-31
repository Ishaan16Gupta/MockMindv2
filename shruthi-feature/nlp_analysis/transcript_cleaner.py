"""
Step 1 — Clean the transcript.

Normalizes raw speech-to-text output:
- Removes standalone filler sounds (uh, um, hmm, ah, er)
- Fixes punctuation via spaCy sentence segmentation
- Removes word-level repetitions ("I I think" → "I think")
- Splits run-on sentences at natural boundaries
- Preserves all meaningful content — never summarizes
"""

import re
import spacy

# ---------------------------------------------------------------------------
# Lazy-loaded spaCy model (shared across modules)
# ---------------------------------------------------------------------------
_nlp = None


def _get_nlp():
    """Return a cached spaCy English model."""
    global _nlp
    if _nlp is None:
        _nlp = spacy.load("en_core_web_sm")
    return _nlp


# Standalone filler sounds to strip (case-insensitive, whole-word only).
_FILLER_SOUNDS = {"uh", "um", "hmm", "ah", "er", "uhh", "umm", "hmm", "ahh"}

# Pattern that matches one or more filler sounds separated by optional commas/spaces.
_FILLER_PATTERN = re.compile(
    r"\b(?:" + "|".join(re.escape(f) for f in _FILLER_SOUNDS) + r")\b",
    re.IGNORECASE,
)


def _remove_filler_sounds(text: str) -> str:
    """Remove standalone filler sounds while preserving meaningful words."""
    # Remove fillers that are standalone (surrounded by word boundaries)
    cleaned = _FILLER_PATTERN.sub("", text)
    # Collapse multiple spaces / stray commas left behind
    cleaned = re.sub(r"\s*,\s*,+", ",", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    return cleaned.strip()


def _remove_stutters(text: str) -> str:
    """Remove immediate word-level repetitions: 'I I think' → 'I think'."""
    # Match a word repeated 2+ times in a row (case-insensitive).
    return re.sub(
        r"\b(\w+)(?:\s+\1\b)+",
        r"\1",
        text,
        flags=re.IGNORECASE,
    )


def _fix_punctuation_and_split(text: str) -> str:
    """Use spaCy to split into proper sentences with correct punctuation."""
    nlp = _get_nlp()
    doc = nlp(text)

    sentences = []
    for sent in doc.sents:
        s = sent.text.strip()
        if not s:
            continue

        # Capitalize the first letter
        s = s[0].upper() + s[1:] if len(s) > 1 else s.upper()

        # Ensure sentence ends with punctuation
        if s and s[-1] not in ".!?":
            s += "."

        sentences.append(s)

    return " ".join(sentences)


def _collapse_spacing(text: str) -> str:
    """Final pass to normalise whitespace and remove stray punctuation artefacts."""
    text = re.sub(r"\s+([.,!?])", r"\1", text)   # space before punctuation
    text = re.sub(r"([.,!?]){2,}", r"\1", text)   # doubled punctuation
    text = re.sub(r"\s{2,}", " ", text)            # multiple spaces
    return text.strip()


def clean_transcript(raw_transcript: str) -> str:
    """
    Main entry point for Step 1.

    Takes raw speech-to-text output and returns a cleaned, properly
    punctuated transcript with filler sounds and stutters removed.
    All meaningful content is preserved.
    """
    if not raw_transcript or not raw_transcript.strip():
        return ""

    text = raw_transcript.strip()

    # 1. Remove standalone filler sounds
    text = _remove_filler_sounds(text)

    # 2. Remove stutters / immediate word repetitions
    text = _remove_stutters(text)

    # 3. Fix punctuation and split into sentences
    text = _fix_punctuation_and_split(text)

    # 4. Final spacing cleanup
    text = _collapse_spacing(text)

    return text
