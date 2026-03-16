#!/usr/bin/env python3
"""word_layout.py — Per-word X/Y layout for CapCut's build-up subtitle effect.

POSITIONING STRATEGY
--------------------
Instead of estimating font pixel widths (which is fragile), this module
divides the usable screen width proportionally by character count:

    char_unit = USABLE_WIDTH / total_chars_in_line   (including spaces)
    word_center_x = LEFT_MARGIN + (chars_before + word_chars/2) * char_unit

This is font-agnostic: as long as characters are roughly the same width
(which holds for Poppins Bold), the proportional approach avoids overlap.

PHRASE SIZE
-----------
Short phrases (~3 words, ≤ MAX_LINE_CHARS) keep each phrase on a SINGLE line.
No multi-line wrapping — phrases are just small enough to fit.

BUILD-UP EFFECT
---------------
Each word entry keeps:
  start      = word's own timestamp
  end        = phrase end time   ← word persists until phrase is done
  position_x = proportional center of this word on screen
  position_y = base_y (single line per phrase)

Canvas: 1080 × 1920 px (portrait mobile).
Coordinates: 0=left/top, 1=right/bottom; position = CENTER of element.

Usage:
    python utils_py/word_layout.py words.json
    python utils_py/word_layout.py words.json --position_y 0.88 --max-chars 20
    # Output: [{word, start, end, position_x, position_y}, ...]
"""

import json
import re
import sys
import os
import argparse

# ---------------------------------------------------------------------------
# Screen layout constants
# ---------------------------------------------------------------------------
USABLE_WIDTH = 0.84   # normalized width used for text (leaves ~8% margin each side)
LEFT_MARGIN  = (1.0 - USABLE_WIDTH) / 2   # = 0.08

SENTENCE_END = re.compile(r'[.?!…]$')

# Default max chars per phrase — keeps ~3 words on one line without overflow
DEFAULT_MAX_CHARS = 20


# ---------------------------------------------------------------------------
# Phrase grouping — keeps original word dicts, groups into short lines
# ---------------------------------------------------------------------------

def _group_lines(
    words: list[dict],
    max_chars: int = DEFAULT_MAX_CHARS,
    max_gap: float = 0.5,
) -> list[list[dict]]:
    """
    Group words into short phrases (≈3 words / max_chars chars).
    Returns list of groups; each group is a list of original word dicts.
    Breaks on: sentence-ending punctuation, long gap, or char limit reached.
    """
    if not words:
        return []

    lines: list[list[dict]] = []
    current: list[dict] = []
    current_chars = 0

    for w in words:
        word = w.get("word") or w.get("text", "")
        n = len(word)

        if not current:
            current.append(w)
            current_chars = n
            continue

        gap = w["start"] - current[-1]["end"]
        prev_word = current[-1].get("word") or current[-1].get("text", "")
        # +1 for the space between words
        new_chars = current_chars + 1 + n

        ends_sentence = bool(SENTENCE_END.search(prev_word))
        too_long      = new_chars > max_chars
        big_gap       = gap > max_gap

        if ends_sentence or too_long or big_gap:
            lines.append(current)
            current = [w]
            current_chars = n
        else:
            current.append(w)
            current_chars = new_chars

    if current:
        lines.append(current)

    return lines


# ---------------------------------------------------------------------------
# Proportional character-based layout for a single line
# ---------------------------------------------------------------------------

def _layout_line(
    phrase_words: list[dict],
    phrase_end: float,
    base_y: float,
) -> list[dict]:
    """
    Position words on a single horizontal line using character-proportional widths.

    Total chars (including spaces) are mapped linearly to USABLE_WIDTH.
    Each word's center_x = LEFT_MARGIN + (cumulative_chars + n_chars/2) * char_unit.

    Args:
        phrase_words: list of word dicts (with 'word'/'text', 'start', 'end')
        phrase_end:   end time that all words in this phrase share
        base_y:       normalized Y center for this line

    Returns:
        List of dicts: {word, start, end, position_x, position_y}
    """
    texts       = [w.get("word") or w.get("text", "") for w in phrase_words]
    char_counts = [len(t) for t in texts]
    # total includes one space between each adjacent pair
    total_chars = sum(char_counts) + max(0, len(phrase_words) - 1)

    if total_chars == 0:
        return []

    char_unit = USABLE_WIDTH / total_chars

    result: list[dict] = []
    cumulative = 0   # chars consumed so far (words + spaces)

    for entry, n_chars in zip(phrase_words, char_counts):
        center_x = LEFT_MARGIN + (cumulative + n_chars / 2) * char_unit
        result.append({
            "word":       entry.get("word") or entry.get("text", ""),
            "start":      entry["start"],
            "end":        phrase_end,
            "position_x": round(center_x, 4),
            "position_y": round(base_y, 4),
        })
        cumulative += n_chars + 1   # +1 for the space after this word

    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compute_layout(
    words: list[dict],
    base_y: float = 0.88,
    max_chars: int = DEFAULT_MAX_CHARS,
    max_gap: float = 0.5,
) -> list[dict]:
    """
    Full pipeline: group words into short lines → compute proportional positions.

    Returns a flat list of word entries, each with:
      word, start, end (= phrase end), position_x, position_y
    """
    lines = _group_lines(words, max_chars=max_chars, max_gap=max_gap)
    result: list[dict] = []
    for line_words in lines:
        phrase_end = line_words[-1]["end"]
        result.extend(_layout_line(line_words, phrase_end, base_y))
    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Compute per-word positions for the build-up subtitle effect"
    )
    parser.add_argument("words",        help="Path to words JSON file")
    parser.add_argument("--position_y", type=float, default=0.88,
                        help="Normalized Y of text line (0=top, 1=bottom; default: 0.88)")
    parser.add_argument("--max-chars",  type=int,   default=DEFAULT_MAX_CHARS,
                        help=f"Max chars per line/phrase (default: {DEFAULT_MAX_CHARS}; "
                             "increase for longer lines, decrease for shorter)")
    parser.add_argument("--max-gap",    type=float, default=0.5,
                        help="Max silence gap (s) to keep words together (default: 0.5)")
    args = parser.parse_args()

    with open(args.words, encoding="utf-8") as f:
        data = json.load(f)

    entries = compute_layout(
        words     = data,
        base_y    = args.position_y,
        max_chars = args.max_chars,
        max_gap   = args.max_gap,
    )
    print(json.dumps(entries, indent=2, ensure_ascii=False))
