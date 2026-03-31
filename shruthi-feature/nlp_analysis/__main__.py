"""
CLI entry point.

Usage:
    python3 -m nlp_analysis --transcript "um so I think I'd use a hash map..."
    python3 -m nlp_analysis --transcript-file answer.txt
"""

import argparse

from nlp_analysis.pipeline import analyze_to_json


def main():
    parser = argparse.ArgumentParser(
        description="MockMind NLP — analyse interview transcript confidence"
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--transcript", type=str, help="Raw transcript text (inline)")
    group.add_argument("--transcript-file", type=str, help="Path to a transcript file")

    parser.add_argument("--compact", action="store_true", help="Compact JSON output")

    args = parser.parse_args()

    if args.transcript_file:
        with open(args.transcript_file) as f:
            transcript = f.read()
    else:
        transcript = args.transcript

    print(analyze_to_json(transcript, indent=None if args.compact else 2))


if __name__ == "__main__":
    main()
