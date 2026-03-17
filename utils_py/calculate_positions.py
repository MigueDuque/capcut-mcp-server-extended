#!/usr/bin/env python3
"""Word-by-word position calculator for CapCut subtitle layout.

Given a list of words with timestamps, computes transform_x / transform_y
positions so words flow left-to-right across lines, building downward,
without overlapping. Resets to a new "screen" after max_lines is exceeded.

Coordinate system (CapCut backend — verified):
  transform_x: -1.0 = left edge,   0.0 = center,  1.0 = right edge
  transform_y: -1.0 = bottom edge,  0.0 = center,  1.0 = top edge
  The x,y point of each text element is its geometric CENTER.
  1 unit in X = 540px  (for 1080px screen)
  1 unit in Y = 960px  (for 1920px screen)

Lines build DOWNWARD from anchor_y:
  Line 0 (first line, highest):  transform_y = anchor_y
  Line 1 (below):                transform_y = anchor_y - LINE_HEIGHT_TY
  Line 2:                        transform_y = anchor_y - 2 * LINE_HEIGHT_TY
  ...

When line_index reaches max_lines, the screen clears and the next word
starts a fresh block at anchor_y again.

Alignment modes (--align):
  left   — words start from the left edge of the usable area (original behavior)
  center — each line is centered independently (two-pass algorithm)

Usage:
    python utils_py/calculate_positions.py \\
      --words '[{"word":"Hello","start":0.0,"end":0.5}]' \\
      --screen_width 1080 --screen_height 1920 --font_size 15.0 --align center
"""

import json
import argparse
from collections import defaultdict


def calculate_positions(
    words: list,
    screen_width:  int   = 1080,
    screen_height: int   = 1920,
    font_size:     float = 15.0,
    margin_x_px:   float = 80.0,
    anchor_y:      float = -0.4,
    max_lines:     int   = 3,
    align:         str   = "center",
) -> list:
    """Return a list of positioned word entries.

    Each output entry contains all input fields plus:
      transform_x  – horizontal center in transform units [-1, 1]
      transform_y  – vertical   center in transform units [-1, 1]
      line         – 0-based line index within the current screen
      clear_before – True if this word starts a fresh screen
    """
    # -----------------------------------------------------------------------
    # Calibration constants
    # -----------------------------------------------------------------------
    PX_PER_TX = screen_width  / 2.0   # 540 px per tx unit (for 1080px screen)
    PX_PER_TY = screen_height / 2.0   # 960 px per ty unit (for 1920px screen)

    # Character-width estimation: Poppins Bold all-caps at font_size=15
    # calibrated so ~5-6 words fit per usable line width.
    SAFETY_FACTOR  = 2.0
    CHAR_WIDTH_PX  = font_size * 1.9 * SAFETY_FACTOR
    SPACE_WIDTH_PX = font_size * 1.5

    # Line height in transform_y units (lines go downward = negative direction)
    WORD_HEIGHT_PX = font_size * 8
    LINE_HEIGHT_TY = WORD_HEIGHT_PX / PX_PER_TY

    # -----------------------------------------------------------------------
    # Usable area in transform units
    # -----------------------------------------------------------------------
    usable_width_px = screen_width - 2.0 * margin_x_px  # e.g. 920px for 1080 - 2*80
    usable_width_tx = usable_width_px / PX_PER_TX         # e.g. 1.704 tx
    left_edge_tx    = -(usable_width_tx / 2.0)            # e.g. -0.852 tx

    # -----------------------------------------------------------------------
    # Pass 1 — Layout: determine line membership and word metrics.
    # transform_x is NOT assigned here.
    # -----------------------------------------------------------------------
    intermediate = []
    cursor_tx    = left_edge_tx
    line_index   = 0
    screen_block = 0
    need_clear   = False

    for w in words:
        word_text     = (w.get("word") or w.get("text", "")).strip().upper()
        word_width_tx = len(word_text) * CHAR_WIDTH_PX / PX_PER_TX

        is_first = (cursor_tx == left_edge_tx)
        space_tx = 0.0 if is_first else (SPACE_WIDTH_PX / PX_PER_TX)

        # Would this word overflow the usable area?
        right_edge_tx = cursor_tx + space_tx + word_width_tx
        if not is_first and right_edge_tx > left_edge_tx + usable_width_tx:
            # Wrap to next line
            line_index += 1
            cursor_tx   = left_edge_tx
            space_tx    = 0.0

            if line_index >= max_lines:
                # Exceeded max_lines → start fresh screen on this word
                line_index   = 0
                screen_block += 1
                need_clear   = True

        # Store the cursor position before advancing (used for left-align tx)
        left_cursor = cursor_tx
        ty = anchor_y - (line_index * LINE_HEIGHT_TY)

        intermediate.append({
            "w":            w,
            "word_text":    word_text,
            "word_width_tx": word_width_tx,
            "space_tx":     space_tx,
            "line_index":   line_index,
            "screen_block": screen_block,
            "ty":           ty,
            "need_clear":   need_clear,
            "left_cursor":  left_cursor,
        })

        cursor_tx  += space_tx + word_width_tx
        need_clear  = False

    # -----------------------------------------------------------------------
    # Pass 2 — Assign transform_x
    # -----------------------------------------------------------------------
    if align == "center":
        # Group word indices by (screen_block, line_index)
        line_groups: dict = defaultdict(list)
        for idx, item in enumerate(intermediate):
            key = (item["screen_block"], item["line_index"])
            line_groups[key].append(idx)

        # For each line, compute total width then assign centered tx values
        tx_values: dict[int, float] = {}
        for indices in line_groups.values():
            # Total line width: first word has space_tx=0, rest include their space
            line_width_tx = sum(
                intermediate[i]["space_tx"] + intermediate[i]["word_width_tx"]
                for i in indices
            )
            cursor = -(line_width_tx / 2.0)
            for i in indices:
                item = intermediate[i]
                tx = cursor + item["space_tx"] + item["word_width_tx"] / 2.0
                cursor += item["space_tx"] + item["word_width_tx"]
                tx_values[i] = tx

        result = [
            {
                **{k: v for k, v in item["w"].items() if k not in ("word", "text", "start", "end")},
                "word":         item["word_text"],
                "start":        float(item["w"]["start"]),
                "end":          float(item["w"]["end"]),
                "transform_x":  round(tx_values[idx], 4),
                "transform_y":  round(item["ty"], 4),
                "line":         item["line_index"],
                "clear_before": item["need_clear"],
            }
            for idx, item in enumerate(intermediate)
        ]

    else:  # left — original behavior
        result = [
            {
                **{k: v for k, v in item["w"].items() if k not in ("word", "text", "start", "end")},
                "word":         item["word_text"],
                "start":        float(item["w"]["start"]),
                "end":          float(item["w"]["end"]),
                "transform_x":  round(item["left_cursor"] + item["space_tx"] + item["word_width_tx"] / 2.0, 4),
                "transform_y":  round(item["ty"], 4),
                "line":         item["line_index"],
                "clear_before": item["need_clear"],
            }
            for item in intermediate
        ]

    # -----------------------------------------------------------------------
    # Accumulation pass: all words in a screen share the same end time so
    # they stay visible together until the screen clears.
    # Block boundary = word with clear_before=True.
    # Each block's end = start of the first word of the next block.
    # Last block's end = original end of its last word + 1.5 s.
    # -----------------------------------------------------------------------
    boundaries = [i for i, r in enumerate(result) if r["clear_before"]] + [len(result)]
    prev = 0
    for boundary in boundaries:
        if boundary < len(result):
            shared_end = result[boundary]["start"]
        else:
            shared_end = float(words[-1]["end"]) + 1.5
        for i in range(prev, boundary):
            result[i]["end"] = shared_end
        # Advance start of last word in block by 0.2 s so it appears slightly earlier
        result[boundary - 1]["start"] = max(0, result[boundary - 1]["start"] - 0.2)
        prev = boundary

    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Calculate word positions for CapCut word-by-word subtitle layout"
    )
    parser.add_argument(
        "--words", required=True,
        help="JSON string with [{word,start,end}] or path to a JSON file",
    )
    parser.add_argument("--screen_width",  type=int,   default=1080)
    parser.add_argument("--screen_height", type=int,   default=1920)
    parser.add_argument("--font_size",     type=float, default=15.0)
    parser.add_argument("--margin_x_px",   type=float, default=80.0,
                        help="Horizontal margin in pixels (default: 80)")
    parser.add_argument("--anchor_y",      type=float, default=-0.4,
                        help="transform_y of the first line; -1=bottom 0=center 1=top (default: -0.4)")
    parser.add_argument("--max_lines",     type=int,   default=4,
                        help="Lines before clearing the screen (default: 4)")
    parser.add_argument("--align",         default="center", choices=["left", "center"],
                        help="Horizontal alignment: left (original) or center (default: center)")
    args = parser.parse_args()

    try:
        words = json.loads(args.words)
    except json.JSONDecodeError:
        with open(args.words, encoding="utf-8") as f:
            words = json.load(f)

    result = calculate_positions(
        words         = words,
        screen_width  = args.screen_width,
        screen_height = args.screen_height,
        font_size     = args.font_size,
        margin_x_px   = args.margin_x_px,
        anchor_y      = args.anchor_y,
        max_lines     = args.max_lines,
        align         = args.align,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
