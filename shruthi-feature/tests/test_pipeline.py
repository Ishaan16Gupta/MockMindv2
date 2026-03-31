"""
Tests for the MockMind NLP analysis pipeline (Steps 1, 2, 3).
"""

import json
import pytest

from nlp_analysis.pipeline import analyze, analyze_to_json
from nlp_analysis.transcript_cleaner import clean_transcript
from nlp_analysis.filler_analyzer import analyze_fillers
from nlp_analysis.confidence_scorer import score_confidence


# ── Sample data ───────────────────────────────────────────────────────────────

MESSY_TRANSCRIPT = (
    "um so like I think what I'd do is uh I'd use a hash map "
    "you know to store the the values as I go and then um for each "
    "element I I would check if the complement right so basically "
    "the time complexity is like O(n) because there's a loop "
    "I think maybe it's O(n) I'm not sure but I believe this handles "
    "most cases sort of like honestly"
)


# ═══════════════════════════════════════════════════════════════════════════════
# Step 1 — Transcript Cleaner
# ═══════════════════════════════════════════════════════════════════════════════

class TestTranscriptCleaner:
    def test_removes_filler_sounds(self):
        result = clean_transcript("um so I think uh the answer is hmm yes")
        words = result.lower().split()
        assert "uh" not in words
        assert "hmm" not in words

    def test_removes_stutters(self):
        result = clean_transcript("I I think this this is the answer")
        assert "I I" not in result
        assert "this this" not in result

    def test_preserves_meaningful_content(self):
        result = clean_transcript("I would use a hash map to store values")
        assert "hash" in result.lower()
        assert "store" in result.lower()
        assert "values" in result.lower()

    def test_adds_punctuation(self):
        result = clean_transcript("I would use a hash map then I check the complement")
        assert any(c in result for c in ".!?")

    def test_capitalises_sentences(self):
        result = clean_transcript("i think we should use recursion")
        assert result[0].isupper()

    def test_empty_input(self):
        assert clean_transcript("") == ""
        assert clean_transcript("   ") == ""

    def test_only_fillers(self):
        result = clean_transcript("um uh hmm ah er")
        assert len(result.strip()) <= 5

    def test_real_words_survive_filler_removal(self):
        # "um" inside "umbrella" should NOT be removed
        result = clean_transcript("the umbrella approach works well")
        assert "umbrella" in result.lower()


# ═══════════════════════════════════════════════════════════════════════════════
# Step 2 — Filler Analyzer
# ═══════════════════════════════════════════════════════════════════════════════

class TestFillerAnalyzer:
    def test_counts_unambiguous_fillers(self):
        result = analyze_fillers("Basically I would use a hash map you know for storage")
        assert result["count"] > 0
        assert "basically" in result["breakdown"] or "you know" in result["breakdown"]

    def test_rate_per_minute_is_float(self):
        result = analyze_fillers("Um I would use a hash map you know for storage")
        assert isinstance(result["rate_per_minute"], float)
        assert result["rate_per_minute"] >= 0

    def test_top_three_has_at_most_three(self):
        result = analyze_fillers(
            "Like I think like this is like sort of the answer "
            "you know basically you know it works"
        )
        assert len(result["top_three"]) <= 3
        assert isinstance(result["top_three"], list)

    def test_top_three_ordered_by_frequency(self):
        result = analyze_fillers(
            "like like like you know you know basically"
        )
        if len(result["top_three"]) >= 2:
            top = result["top_three"][0]
            second = result["top_three"][1]
            assert result["breakdown"].get(top, 0) >= result["breakdown"].get(second, 0)

    def test_no_fillers_in_clean_sentence(self):
        result = analyze_fillers("The time complexity of binary search is O(log n).")
        assert result["count"] == 0
        assert result["top_three"] == []

    def test_empty_input(self):
        result = analyze_fillers("")
        assert result["count"] == 0
        assert result["rate_per_minute"] == 0.0

    def test_breakdown_is_dict(self):
        result = analyze_fillers("Um I basically you know want to use a stack")
        assert isinstance(result["breakdown"], dict)

    def test_like_as_verb_not_counted(self):
        # "I like" — like is a verb here, not a filler
        result = analyze_fillers("I like this data structure very much")
        assert result["breakdown"].get("like", 0) == 0

    def test_like_as_filler_counted(self):
        # "it's like the answer" — like is a filler here
        result = analyze_fillers("it's like the right approach")
        assert result["breakdown"].get("like", 0) >= 1


# ═══════════════════════════════════════════════════════════════════════════════
# Step 3 — Confidence Scorer
# ═══════════════════════════════════════════════════════════════════════════════

class TestConfidenceScorer:
    def test_detects_hedging_reduces_score(self):
        result = score_confidence(
            "I think this might work. Maybe we could use a hash map. "
            "I'm not sure but it could be O(n)."
        )
        assert result["hedge_count"] > 0
        assert result["score"] < 10.0
        assert len(result["low_confidence_moments"]) > 0

    def test_detects_assertions_raise_score(self):
        result = score_confidence(
            "The solution is to use a hash map. This handles all cases. "
            "The time complexity is O(n). This approach works because we scan once."
        )
        assert result["assert_count"] > 0
        assert result["score"] > 5.0

    def test_no_signals_returns_default(self):
        result = score_confidence("A hash map stores key-value pairs.")
        assert result["score"] == 5.0
        assert result["hedge_count"] == 0
        assert result["assert_count"] == 0

    def test_all_hedging_gives_low_score(self):
        result = score_confidence(
            "I think maybe this could be the answer. I guess it might be O(n). "
            "I believe it could work possibly."
        )
        assert result["score"] < 3.0

    def test_low_confidence_moments_are_sentences(self):
        result = score_confidence(
            "I think this works. The solution is correct. Maybe it's O(n)."
        )
        # low_confidence_moments should contain the hedging sentences verbatim
        for moment in result["low_confidence_moments"]:
            assert isinstance(moment, str)
            assert len(moment) > 0

    def test_score_is_between_0_and_10(self):
        result = score_confidence(
            "I think I'm not sure maybe could be possibly I guess."
        )
        assert 0.0 <= result["score"] <= 10.0

    def test_empty_input(self):
        result = score_confidence("")
        assert result["score"] == 5.0
        assert result["hedge_count"] == 0
        assert result["assert_count"] == 0

    def test_mixed_signals(self):
        result = score_confidence(
            "The solution is a hash map. I think the complexity is O(n). "
            "This handles duplicates. Maybe the space is O(n) too."
        )
        assert result["hedge_count"] > 0
        assert result["assert_count"] > 0
        assert 0.0 <= result["score"] <= 10.0


# ═══════════════════════════════════════════════════════════════════════════════
# Full Pipeline — End to End
# ═══════════════════════════════════════════════════════════════════════════════

class TestFullPipeline:
    def test_returns_correct_top_level_keys(self):
        result = analyze(MESSY_TRANSCRIPT)
        assert set(result.keys()) == {"cleaned_transcript", "filler_words", "confidence"}

    def test_filler_words_structure(self):
        result = analyze(MESSY_TRANSCRIPT)
        fw = result["filler_words"]
        assert "count" in fw
        assert "rate_per_minute" in fw
        assert "breakdown" in fw
        assert "top_three" in fw
        assert isinstance(fw["count"], int)
        assert isinstance(fw["rate_per_minute"], float)
        assert isinstance(fw["breakdown"], dict)
        assert isinstance(fw["top_three"], list)

    def test_confidence_structure(self):
        result = analyze(MESSY_TRANSCRIPT)
        conf = result["confidence"]
        assert "score" in conf
        assert "hedge_count" in conf
        assert "assert_count" in conf
        assert "low_confidence_moments" in conf
        assert isinstance(conf["score"], float)
        assert isinstance(conf["low_confidence_moments"], list)

    def test_cleaned_transcript_is_string(self):
        result = analyze(MESSY_TRANSCRIPT)
        assert isinstance(result["cleaned_transcript"], str)
        assert len(result["cleaned_transcript"]) > 0

    def test_json_output_is_valid(self):
        output = analyze_to_json(MESSY_TRANSCRIPT)
        parsed = json.loads(output)
        assert isinstance(parsed, dict)
        assert "cleaned_transcript" in parsed

    def test_empty_transcript(self):
        result = analyze("")
        assert result["cleaned_transcript"] == ""
        assert result["filler_words"]["count"] == 0
        assert result["confidence"]["score"] == 5.0

    def test_clean_confident_transcript(self):
        transcript = (
            "The solution is to use a hash map. "
            "The time complexity is O(n) because we scan the array once. "
            "This approach works because hash map lookups are O(1). "
            "This handles all edge cases including duplicates."
        )
        result = analyze(transcript)
        assert result["filler_words"]["count"] == 0
        assert result["confidence"]["score"] > 5.0

    def test_highly_uncertain_transcript(self):
        transcript = (
            "um I think maybe I'd use like a hash map you know "
            "I'm not sure but possibly it could be O(n) I guess"
        )
        result = analyze(transcript)
        assert result["filler_words"]["count"] > 0
        assert result["confidence"]["score"] < 5.0
