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
    VECTCUT_DRAFT_DIR (default: C:/capcut_project/capcut-mcp-back)
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
from calculate_positions import calculate_positions           # word-by-word XY layout

VECTCUT_DIR  = os.environ.get("VECTCUT_DRAFT_DIR", "C:/capcut_project/capcut-mcp-back")
KF_OFFSET    = 5 / 30    # popInUpper: 5 frames @ 30 fps ≈ 0.167 s — controls position drop timing
KF_FADE_DUR  = 0.2       # Fade_In intro animation duration — 5 frames @ 30 fps (fast, subtitle-style)
KF_Y_OFFSET  = 0.04      # slide distance in transform units [-1,1]: element starts this far ABOVE final pos (y+ = up)


# ---------------------------------------------------------------------------
# Single-entry worker (runs in thread pool)
# ---------------------------------------------------------------------------

def _add_entry(draft_id: str, index: int, entry: dict,
               style_params: dict, animation: str | None,
               position_x: float, position_y: float,
               fade_duration: float = KF_FADE_DUR) -> tuple[int, bool, str | None]:
    """Add one word/phrase as text + keyframes. Returns (index, ok, error_msg).

    If entry contains 'position_x' / 'position_y' keys (from word_layout),
    those override the global defaults.
    """
    text  = (entry.get("word") or entry.get("text", "")).upper()
    start = float(entry["start"])
    end   = float(entry["end"])
    track = f"w_{index}"

    # transform_x/y from calculate_positions ([-1,1] space) override global defaults
    px = entry.get("transform_x", entry.get("position_x", position_x))
    py = entry.get("transform_y", entry.get("position_y", position_y))

    add_text_payload: dict = {
        "draft_id":    draft_id,
        "text":        text,
        "start":       start,
        "end":         end,
        "transform_x": px,
        "transform_y": py,
        "track_name":  track,
        **style_params,
    }
    if animation == "popInUpper":
        # Fade-in via CapCut's native Text_intro animation (KFTypeAlpha is not
        # supported on text segments — native animation is the correct path).
        add_text_payload["intro_animation"] = "Fade_In"
        add_text_payload["intro_duration"]  = fade_duration

    r = api_post("/add_text", add_text_payload)
    if not r.get("success"):
        return (index, False, f"add_text: {r.get('error')}")

    if animation == "popInUpper":
        t0, t1 = start, start + KF_OFFSET
        # Position Y: element starts KF_Y_OFFSET above final position and falls down
        r2 = api_post("/add_video_keyframe", {
            "draft_id":       draft_id,
            "track_name":     track,
            "property_types": ["position_y", "position_y"],
            "times":          [t0, t1],
            "values":         [str(round(py + KF_Y_OFFSET, 4)), str(py)],
        })
        if not r2.get("success"):
            return (index, False, f"kf_pos_y: {r2.get('error')}")

    return (index, True, None)


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def run_pipeline(
    draft_path:     str | None = None,
    words:          list = (),
    style:          str       = "defaultTypeWhite",
    animation:      str | None = "popInUpper",
    position_x:     float = 0.0,
    position_y:     float = -0.4,
    max_chars:      int   = 35,
    max_gap:        float = 0.5,
    max_workers:    int   = 8,
    buildup:        bool  = False,
    word_by_word:   bool  = True,
    line_height:    float = 0.06,
    chars_per_line: int   = 20,
    screen_width:   int   = 1080,
    screen_height:  int   = 1920,
    font_size:      float = 15.0,
    fade_duration:  float = KF_FADE_DUR,
    draft_folder:   str | None = None,
) -> dict:
    """position_x/y are in transform units [-1,1]: 0=center, -1=bottom/left, 1=top/right."""

    if style not in STYLES:
        raise ValueError(f"Unknown style '{style}'. Available: {list(STYLES)}")

    # Step 1 — compute entries
    if word_by_word:
        # Word-by-word mode: use calculate_positions for per-word XY layout
        positioned = calculate_positions(
            words         = words,
            screen_width  = screen_width,
            screen_height = screen_height,
            font_size     = font_size,
            anchor_y      = position_y,
        )
        entries = positioned
        print(
            f"[pipeline] word-by-word: {len(entries)} words "
            f"({screen_width}x{screen_height}, font={font_size})",
            flush=True,
        )
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
    r = api_post("/create_draft", {"width": screen_width, "height": screen_height})
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
                draft_id, i, p, style_params, animation, position_x, position_y, fade_duration
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

    # Step 6 — extract text tracks (named w_N) and their materials from temp draft
    text_tracks = [
        t for t in source.get("tracks", [])
        if t.get("name", "").startswith("w_")
    ]

    # Collect material_id and extra_material_refs (animations, etc.)
    used_ids  = set()
    extra_refs = set()
    for t in text_tracks:
        for seg in t.get("segments", []):
            used_ids.add(seg.get("material_id"))
            for ref in seg.get("extra_material_refs", []):
                extra_refs.add(ref)

    src_texts = [
        m for m in source.get("materials", {}).get("texts", [])
        if m.get("id") in used_ids
    ]
    src_anims = [
        m for m in source.get("materials", {}).get("material_animations", [])
        if m.get("id") in extra_refs
    ]

    # Step 7a — new-draft mode: copy temp folder to draft_folder
    if draft_folder is not None and draft_path is None:
        import shutil
        dest = os.path.join(draft_folder, draft_id)
        if os.path.exists(dest):
            shutil.rmtree(dest)
        shutil.copytree(os.path.dirname(source_path), dest)
        mode = "word_by_word" if word_by_word else ("buildup" if buildup else "phrases")
        return {
            "draft_id":            draft_id,
            "entries_added":       len(entries),
            "source_words":        len(words),
            "text_tracks_merged":  len(text_tracks),
            "materials_merged":    len(src_texts) + len(src_anims),
            "errors":              len(errors),
            "mode":                mode,
        }

    # Step 7b — merge mode: inject into existing draft_content.json
    with open(draft_path, encoding="utf-8") as f:
        target = json.load(f)

    bak_path = draft_path + ".bak_words"
    if not os.path.exists(bak_path):
        with open(bak_path, "w", encoding="utf-8") as f:
            json.dump(target, f, ensure_ascii=False)

    target.setdefault("tracks", []).extend(text_tracks)
    target.setdefault("materials", {}).setdefault("texts", []).extend(src_texts)
    target.setdefault("materials", {}).setdefault("material_animations", []).extend(src_anims)

    with open(draft_path, "w", encoding="utf-8") as f:
        json.dump(target, f, ensure_ascii=False)

    mode = "word_by_word" if word_by_word else ("buildup" if buildup else "phrases")
    return {
        "entries_added":       len(entries),
        "source_words":        len(words),
        "text_tracks_merged":  len(text_tracks),
        "materials_merged":    len(src_texts) + len(src_anims),
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
    parser.add_argument("--draft",        default=None,   help="Path to draft_content.json (merge mode)")
    parser.add_argument("--draft_folder", default=None,   help="CapCut drafts directory; creates a new project (no --draft needed)")
    parser.add_argument("--words",        required=True,  help="Path to words JSON file, or inline JSON string")
    parser.add_argument("--style",       default="defaultTypeWhite", choices=list(STYLES))
    parser.add_argument("--animation",   default="popInUpper",
                        help="popInUpper | none  (default: popInUpper)")
    parser.add_argument("--position_x",     type=float, default=0.0,
                        help="transform_x center for fallback (word-by-word uses auto layout); -1=left 0=center 1=right (default: 0.0)")
    parser.add_argument("--position_y",     type=float, default=-0.4,
                        help="anchor_y: transform_y of first subtitle line; -1=bottom 0=center 1=top (default: -0.4)")
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
    parser.add_argument("--screen_width",   type=int,   default=1080,
                        help="Screen width in px for position calculation (default: 1080)")
    parser.add_argument("--screen_height",  type=int,   default=1920,
                        help="Screen height in px for position calculation (default: 1920)")
    parser.add_argument("--font_size",      type=float, default=15.0,
                        help="Font size for character-width estimation (default: 15.0)")
    parser.add_argument("--fade_duration",  type=float, default=KF_FADE_DUR,
                        help="Fade_In intro animation duration in seconds (default: 0.167 = 5 frames @ 30fps)")
    args = parser.parse_args()

    if args.draft is None and args.draft_folder is None:
        parser.error("Provide --draft (merge mode) or --draft_folder (new draft mode)")

    # Accept inline JSON string or path to file
    if args.words.strip().startswith("["):
        words = json.loads(args.words)
    else:
        with open(args.words, encoding="utf-8") as f:
            words = json.load(f)

    result = run_pipeline(
        draft_path     = args.draft,
        draft_folder   = args.draft_folder,
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
        screen_width   = args.screen_width,
        screen_height  = args.screen_height,
        font_size      = args.font_size,
        fade_duration  = args.fade_duration,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))