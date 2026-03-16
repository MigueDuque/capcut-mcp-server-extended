#!/usr/bin/env python3
"""End-to-end pipeline: words.json → subtitles merged into existing draft.

Combines grouping/layout + add_words_to_draft into a single execution with
parallelized API calls (ThreadPoolExecutor), reducing N×3 sequential
requests to ~3 batched rounds.

Steps:
  1. Compute entries (word-by-word, phrase, or build-up)
  2. Create temp VectCutAPI draft
  3. Add all entries in parallel  (ThreadPoolExecutor, max_workers=8)
  4. Save temp draft → read draft_info.json from VECTCUT_DRAFT_DIR
  5. Merge text tracks + materials into target draft_content.json (in-place)
  6. Backup original before first write (draft_content.json.bak_words)

Modes:
  --word-by-word  (default) — one element per word, centered, position_y fixed
  --no-buildup              — one element per phrase, position_y adjusted per line count
  --buildup                 — build-up horizontal layout (legacy)

Usage:
    python utils_py/edit_draft_pipeline.py \\
        --draft "C:/path/to/draft_content.json" \\
        --words "C:/path/to/words.json" \\
        [--style      defaultTypeWhite] \\
        [--animation  popInUpper | none] \\
        [--position_x 0.5] \\
        [--position_y 0.10]

Env vars:
    CAPCUT_API_URL    (default: http://localhost:9001)
    VECTCUT_DRAFT_DIR (default: C:/smart_cut/capcut-mcp)
"""

import json
import os
import sys
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed

# Import shared helpers from sibling modules (no repeated definitions)
sys.path.insert(0, os.path.dirname(__file__))
from group_words import group_words                          # phrase grouping logic
from word_layout import compute_layout                       # build-up word positioning
from calc_subtitle_y import compute_phrases_with_y           # phrase grouping + per-phrase Y
from add_words_to_draft import STYLES, api_post, wait_for_file  # API helpers + style presets

VECTCUT_DIR  = os.environ.get("VECTCUT_DRAFT_DIR", "C:/smart_cut/capcut-mcp")
KF_OFFSET    = 13 / 30   # popInUpper: 13 frames @ 30 fps ≈ 0.433 s
KF_Y_OFFSET  = 0.03      # fall distance: start this many units above final position


# ---------------------------------------------------------------------------
# Single-entry worker (runs in thread pool)
# ---------------------------------------------------------------------------

def _add_entry(draft_id: str, index: int, entry: dict,
               style_params: dict, animation: str | None,
               position_x: float, position_y: float) -> tuple[int, bool, str | None]:
    """Add one word/phrase as text + keyframes. Returns (index, ok, error_msg).

    If entry contains 'position_x' / 'position_y' keys (from word_layout),
    those override the global defaults.
    """
    text  = (entry.get("word") or entry.get("text", "")).upper()
    start = float(entry["start"])
    end   = float(entry["end"])
    track = f"w_{index}"

    px = entry.get("position_x", position_x)
    py = entry.get("position_y", position_y)

    r = api_post("/add_text", {
        "draft_id":   draft_id,
        "text":       text,
        "start":      start,
        "end":        end,
        "position_x": px,
        "position_y": py,
        "track_name": track,
        **style_params,
    })
    if not r.get("success"):
        return (index, False, f"add_text: {r.get('error')}")

    if animation == "popInUpper":
        t0, t1 = start, start + KF_OFFSET
        for prop, vals in [
            ("alpha",      ["0",                    "1"]),
            ("position_y", [str(py + KF_Y_OFFSET),  str(py)]),
        ]:
            r2 = api_post("/add_video_keyframe", {
                "draft_id":       draft_id,
                "track_name":     track,
                "property_types": [prop, prop],
                "times":          [t0, t1],
                "values":         vals,
            })
            if not r2.get("success"):
                return (index, False, f"kf_{prop}: {r2.get('error')}")

    return (index, True, None)


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def run_pipeline(
    draft_path:     str,
    words:          list,
    style:          str       = "defaultTypeWhite",
    animation:      str | None = "popInUpper",
    position_x:     float = 0.5,
    position_y:     float = 0.10,
    max_chars:      int   = 35,
    max_gap:        float = 0.5,
    max_workers:    int   = 8,
    buildup:        bool  = False,
    word_by_word:   bool  = True,
    line_height:    float = 0.06,
    chars_per_line: int   = 20,
) -> dict:

    if style not in STYLES:
        raise ValueError(f"Unknown style '{style}'. Available: {list(STYLES)}")

    # Step 1 — compute entries
    if word_by_word:
        # Word-by-word mode: one element per word, centered, fixed position_y
        entries = [
            {
                "text":       (w.get("word") or w.get("text", "")),
                "start":      w["start"],
                "end":        w["end"],
                "position_y": position_y,
            }
            for w in words
        ]
        print(f"[pipeline] word-by-word: {len(entries)} words", flush=True)
    elif buildup:
        # Build-up mode: per-word positions, words persist until phrase ends
        entries = compute_layout(words, base_y=position_y,
                                 max_chars=max_chars, max_gap=max_gap)
        print(f"[pipeline] buildup layout: {len(words)} words → {len(entries)} entries", flush=True)
    else:
        # Phrase mode: one text element per phrase, position_y adjusted per line count
        entries = compute_phrases_with_y(
            words, base_y=position_y, line_height=line_height,
            chars_per_line=chars_per_line, max_chars=max_chars, max_gap=max_gap,
        )
        print(f"[pipeline] grouped {len(words)} words → {len(entries)} phrases", flush=True)

    style_params = STYLES[style]

    # Step 2 — create temp text-only draft
    r = api_post("/create_draft", {"width": 1080, "height": 1920})
    if not r.get("success"):
        raise RuntimeError(f"create_draft failed: {r.get('error')}")
    draft_id = r["output"]["draft_id"]
    print(f"[pipeline] temp draft: {draft_id}", flush=True)

    # Step 3 — add all entries in parallel
    errors: list[str] = []
    done   = 0
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {
            pool.submit(
                _add_entry,
                draft_id, i, p, style_params, animation, position_x, position_y
            ): i
            for i, p in enumerate(entries)
        }
        for fut in as_completed(futures):
            idx, ok, msg = fut.result()
            if ok:
                done += 1
                print(f"  [{done}/{len(entries)}] ok", flush=True)
            else:
                errors.append(f"[{idx}] {msg}")
                print(f"  [{idx}] ERR: {msg}", file=sys.stderr, flush=True)

    # Step 4 — save temp draft and wait for file
    api_post("/save_draft", {"draft_id": draft_id})
    source_path = os.path.join(VECTCUT_DIR, draft_id, "draft_info.json")
    if not wait_for_file(source_path):
        raise FileNotFoundError(f"Temp draft_info.json not found: {source_path}")

    with open(source_path, encoding="utf-8") as f:
        source = json.load(f)

    # Step 5 — backup + read target
    with open(draft_path, encoding="utf-8") as f:
        target = json.load(f)

    bak_path = draft_path + ".bak_words"
    if not os.path.exists(bak_path):
        with open(bak_path, "w", encoding="utf-8") as f:
            json.dump(target, f, ensure_ascii=False)

    # Step 6 — merge text tracks (named w_N) and their materials
    text_tracks = [
        t for t in source.get("tracks", [])
        if t.get("name", "").startswith("w_")
    ]
    target.setdefault("tracks", []).extend(text_tracks)

    used_ids = {
        seg.get("material_id")
        for t in text_tracks
        for seg in t.get("segments", [])
    }
    src_texts = [
        m for m in source.get("materials", {}).get("texts", [])
        if m.get("id") in used_ids
    ]
    target.setdefault("materials", {}).setdefault("texts", []).extend(src_texts)

    with open(draft_path, "w", encoding="utf-8") as f:
        json.dump(target, f, ensure_ascii=False)

    mode = "word_by_word" if word_by_word else ("buildup" if buildup else "phrases")
    return {
        "entries_added":       len(entries),
        "source_words":        len(words),
        "text_tracks_merged":  len(text_tracks),
        "materials_merged":    len(src_texts),
        "errors":              len(errors),
        "mode":                mode,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Words → phrases → subtitles on existing CapCut draft (parallelized)"
    )
    parser.add_argument("--draft",       required=True,  help="Path to draft_content.json")
    parser.add_argument("--words",       required=True,  help="Path to words JSON file")
    parser.add_argument("--style",       default="defaultTypeWhite", choices=list(STYLES))
    parser.add_argument("--animation",   default="popInUpper",
                        help="popInUpper | none  (default: popInUpper)")
    parser.add_argument("--position_x",     type=float, default=0.5)
    parser.add_argument("--position_y",     type=float, default=0.10,
                        help="Base Y for 1-line phrases; 0=bottom, 1=top (default: 0.10)")
    parser.add_argument("--max-chars",      type=int,   default=35)
    parser.add_argument("--max-gap",        type=float, default=0.5)
    parser.add_argument("--max-workers",    type=int,   default=8,
                        help="Parallel API workers (default: 8)")
    parser.add_argument("--line-height",    type=float, default=0.06,
                        help="Y units per visual line for multi-line Y adjustment (default: 0.06)")
    parser.add_argument("--chars-per-line", type=int,   default=20,
                        help="Estimated chars per visual line, ~3 words (default: 20)")
    parser.add_argument("--word-by-word",   action="store_true",  default=True,
                        help="Word-by-word mode: one element per word, centered (default)")
    parser.add_argument("--no-word-by-word", action="store_false", dest="word_by_word",
                        help="Disable word-by-word mode (use phrase or build-up instead)")
    parser.add_argument("--buildup",        action="store_true", default=False,
                        help="Build-up mode: per-word horizontal layout (requires --no-word-by-word)")
    parser.add_argument("--no-buildup",     action="store_false", dest="buildup",
                        help="Phrase mode: one element per phrase with Y adjustment (requires --no-word-by-word)")
    args = parser.parse_args()

    with open(args.words, encoding="utf-8") as f:
        words = json.load(f)

    result = run_pipeline(
        draft_path     = args.draft,
        words          = words,
        style          = args.style,
        animation      = args.animation if args.animation != "none" else None,
        position_x     = args.position_x,
        position_y     = args.position_y,
        max_chars      = args.max_chars,
        max_gap        = args.max_gap,
        max_workers    = args.max_workers,
        word_by_word   = args.word_by_word,
        buildup        = args.buildup,
        line_height    = args.line_height,
        chars_per_line = args.chars_per_line,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))