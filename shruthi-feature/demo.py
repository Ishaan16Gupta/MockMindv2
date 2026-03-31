"""
MockMind NLP Demo

Runs the 3-step NLP pipeline on a realistic speech-to-text transcript
and prints the structured output.
"""

import json
from nlp_analysis import analyze

# ── Sample raw speech-to-text transcript ─────────────────────────────────────
# This simulates what you'd receive from a speech-to-text converter like
# ElevenLabs, Whisper, Deepgram, etc. — messy, unpunctuated, full of fillers.

raw_transcript = (
    "um okay so like I think what I'd do is uh I'd use a hash map "
    "you know to store the the values as I go and then um for each "
    "element I I would check if the complement exists in the hash map "
    "right so basically the time complexity is like O(n) because uh "
    "there's a loop and we we just go through the array once I think "
    "maybe it's O(n) yeah I'm not sure but I believe this handles "
    "most cases sort of like a two pass thing honestly"
)

# ── Run the pipeline ──────────────────────────────────────────────────────────
result = analyze(raw_transcript)

# ── Print the output ──────────────────────────────────────────────────────────
print(json.dumps(result, indent=2, ensure_ascii=False))
