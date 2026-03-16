#!/usr/bin/env python3
"""Groups word-level timestamps into phrase-level subtitle entries.

Words are merged into a phrase until one of these conditions breaks the group:
  - Adding the next word would exceed --max-chars characters
  - The gap between the previous word end and the next word start exceeds --max-gap seconds
  - A sentence-ending punctuation is detected (. ? ! …)

Output: JSON list of {"text": "...", "start": float, "end": float}

Usage:
    python utils_py/group_words.py words.json
    python utils_py/group_words.py words.json --max-chars 40 --max-gap 0.6
    echo '[...]' | python utils_py/group_words.py -
"""

import json
import re
import sys
import argparse

SENTENCE_END = re.compile(r'[.?!…]$')


def group_words(words: list, max_chars: int = 35, max_gap: float = 0.5) -> list:
    phrases = []
    current: list = []

    for w in words:
        word = w.get("word") or w.get("text", "")

        if current:
            current_text = " ".join(c["_w"] for c in current)
            new_text = current_text + " " + word
            gap = w["start"] - current[-1]["end"]

            # Break phrase on: too long, big gap, or sentence-ending punctuation
            if len(new_text) > max_chars or gap > max_gap or SENTENCE_END.search(current[-1]["_w"]):
                phrases.append({
                    "text": current_text,
                    "start": current[0]["start"],
                    "end": current[-1]["end"],
                })
                current = []

        current.append({"_w": word, "start": w["start"], "end": w["end"]})

    if current:
        phrases.append({
            "text": " ".join(c["_w"] for c in current),
            "start": current[0]["start"],
            "end": current[-1]["end"],
        })

    return phrases


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Group word timestamps into subtitle phrases")
    parser.add_argument("input", help="JSON file with word list, or '-' for stdin")
    parser.add_argument("--max-chars", type=int, default=35,
                        help="Max characters per phrase (default: 35)")
    parser.add_argument("--max-gap",   type=float, default=0.5,
                        help="Max silence gap in seconds to keep words in same phrase (default: 0.5)")
    args = parser.parse_args()

    if args.input == "-":
        words = json.load(sys.stdin)
    else:
        with open(args.input, encoding="utf-8") as f:
            words = json.load(f)

    phrases = group_words(words, max_chars=args.max_chars, max_gap=args.max_gap)
    print(json.dumps(phrases, ensure_ascii=False, indent=2))