#!/usr/bin/env python3
"""calc_subtitle_y.py — Groups words into subtitle phrases and assigns position_y per phrase.

Y-axis convention (CapCut API / VectCut):
  0 = bottom of screen   1 = top of screen   (positive Y = upward on screen)

This means:
  - position_y = 0.85 → near top (15% from top)
  - position_y = 0.10 → near bottom (10% from bottom)  ← typical subtitle zone

Phrase height model:
  Each phrase may span multiple visual lines depending on its character count.
  chars_per_line ≈ max chars that fit on one line (~3 average words of 5-6 chars + spaces).

  For a phrase with N estimated lines:
    position_y = base_y + (N - 1) * line_height

  base_y = center Y of a 1-line phrase.
  Multi-line phrases shift upward so their bottom edge stays near base_y.

Usage:
    python utils_py/calc_subtitle_y.py words.json \\
        --base_y 0.10 --line_height 0.06 --chars_per_line 20 \\
        --max-chars 35 --max-gap 0.5
    # Output: [{"text":"...", "start":float, "end":float, "position_y":float}, ...]
"""

import json
import math
import sys
import os
import argparse

sys.path.insert(0, os.path.dirname(__file__))
from group_words import group_words

DEFAULT_BASE_Y        = 0.10   # subtitle zone near bottom (0=bottom, 1=top)
DEFAULT_LINE_HEIGHT   = 0.06   # ~100px on a 1920px screen at font_size 15
DEFAULT_CHARS_PER_LINE = 20    # ~3 words of avg 5-6 chars + spaces per visual line
DEFAULT_MAX_CHARS     = 35
DEFAULT_MAX_GAP       = 0.5


def compute_phrases_with_y(
    words: list,
    base_y: float           = DEFAULT_BASE_Y,
    line_height: float      = DEFAULT_LINE_HEIGHT,
    chars_per_line: int     = DEFAULT_CHARS_PER_LINE,
    max_chars: int          = DEFAULT_MAX_CHARS,
    max_gap: float          = DEFAULT_MAX_GAP,
) -> list:
    """
    Group words into subtitle phrases and assign a per-phrase position_y.

    Returns list of dicts: {text, start, end, position_y}

    position_y calculation:
      n_lines   = ceil(len(phrase_text) / chars_per_line)
      position_y = base_y + (n_lines - 1) * line_height
    """
    phrases = group_words(words, max_chars=max_chars, max_gap=max_gap)

    result = []
    for p in phrases:
        text = p.get("text") or p.get("word", "")
        n_chars = len(text)
        n_lines = max(1, math.ceil(n_chars / chars_per_line))
        position_y = round(base_y + (n_lines - 1) * line_height, 4)
        result.append({
            "text":       text,
            "start":      p["start"],
            "end":        p["end"],
            "position_y": position_y,
        })

    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Group words into subtitle phrases with per-phrase position_y"
    )
    parser.add_argument("words",
                        help="Path to words JSON file")
    parser.add_argument("--base_y",         type=float, default=DEFAULT_BASE_Y,
                        help=f"Y center for 1-line phrases; 0=bottom, 1=top "
                             f"(default: {DEFAULT_BASE_Y})")
    parser.add_argument("--line_height",    type=float, default=DEFAULT_LINE_HEIGHT,
                        help=f"Normalized Y units per visual line "
                             f"(default: {DEFAULT_LINE_HEIGHT})")
    parser.add_argument("--chars_per_line", type=int, default=DEFAULT_CHARS_PER_LINE,
                        help=f"Estimated chars per visual line, ~3 words "
                             f"(default: {DEFAULT_CHARS_PER_LINE})")
    parser.add_argument("--max-chars",      type=int, default=DEFAULT_MAX_CHARS,
                        help=f"Max chars per subtitle phrase (default: {DEFAULT_MAX_CHARS})")
    parser.add_argument("--max-gap",        type=float, default=DEFAULT_MAX_GAP,
                        help=f"Max silence gap (s) to keep words in phrase "
                             f"(default: {DEFAULT_MAX_GAP})")
    args = parser.parse_args()

    with open(args.words, encoding="utf-8") as f:
        data = json.load(f)

    phrases = compute_phrases_with_y(
        words          = data,
        base_y         = args.base_y,
        line_height    = args.line_height,
        chars_per_line = args.chars_per_line,
        max_chars      = args.max_chars,
        max_gap        = args.max_gap,
    )
    print(json.dumps(phrases, indent=2, ensure_ascii=False))