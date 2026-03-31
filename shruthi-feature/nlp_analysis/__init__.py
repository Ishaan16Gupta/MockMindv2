"""
MockMind NLP Analysis Module

Analyses student interview transcripts (from speech-to-text) for:
  - Step 1: Transcript cleaning (removes filler sounds, fixes punctuation)
  - Step 2: Filler word analysis (um, like, you know, etc.)
  - Step 3: Confidence scoring (hedging vs assertive language)

Usage:
    from nlp_analysis import analyze
    result = analyze(transcript)
"""

from nlp_analysis.pipeline import analyze

__all__ = ["analyze"]
