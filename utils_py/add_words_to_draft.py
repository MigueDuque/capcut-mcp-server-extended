#!/usr/bin/env python3
"""Add word/phrase subtitle overlays to an EXISTING CapCut draft_content.json.

Workflow:
  1. Create a text-only temp draft via VectCutAPI
  2. Add each word/phrase as styled, animated text
  3. Save — VectCutAPI writes draft_info.json to VECTCUT_DRAFT_DIR
  4. Merge text tracks + materials from the temp draft into the target draft_content.json
  5. Backup the original (skipped if backup already exists)

Usage:
    python utils_py/add_words_to_draft.py \\
        --draft  "C:/path/to/draft_content.json" \\
        --words  '[{"word":"Hola","start":0.5,"end":1.0},...]' \\
        [--style  defaultTypeWhite] \\
        [--animation  popInUpper] \\
        [--position_x 0.5] \\
        [--position_y 0.85]

    Words can also be phrases (using "text" key instead of "word"):
        --words '[{"text":"Hola mundo","start":0.5,"end":2.0},...]'

Env vars:
    CAPCUT_API_URL   VectCutAPI base URL    (default: http://localhost:9001)
    VECTCUT_DRAFT_DIR  Dir where API saves drafts (default: C:/smart_cut/capcut-mcp)
"""

import json
import os
import sys
import time
import argparse
import urllib.request

API_URL         = os.environ.get("CAPCUT_API_URL",    "http://localhost:9001")
VECTCUT_DIR     = os.environ.get("VECTCUT_DRAFT_DIR", "C:/smart_cut/capcut-mcp")

# ---------------------------------------------------------------------------
# Typography presets (mirrors src/presets/typography.ts)
# ---------------------------------------------------------------------------
STYLES = {
    "defaultTypeWhite": {
        "font": "Poppins_Bold", "font_size": 15, "font_color": "#ecebeb",
        "border_width": 40, "border_color": "#000000",
        "shadow_enabled": True,  "shadow_color": "#000000",
        "shadow_alpha": 0.25, "shadow_blur": 23, "shadow_distance": 10, "shadow_angle": -70,
    },
    "defaultTypeBlack": {
        "font": "Poppins_Bold", "font_size": 15, "font_color": "#000000",
        "border_width": 0, "border_color": "#000000",
        "shadow_enabled": False, "shadow_color": "#000000",
        "shadow_alpha": 0, "shadow_blur": 0, "shadow_distance": 0, "shadow_angle": 0,
    },
    "defaultTypeRed": {
        "font": "Poppins_Bold", "font_size": 15, "font_color": "#aa1a1a",
        "border_width": 0, "border_color": "#000000",
        "shadow_enabled": False, "shadow_color": "#000000",
        "shadow_alpha": 0, "shadow_blur": 0, "shadow_distance": 0, "shadow_angle": 0,
    },
}

# popInUpper: starts 0.05 units above final position (falls down), fades in over 13 frames
KF_FRAMES   = 13
KF_FPS      = 30
KF_OFFSET   = KF_FRAMES / KF_FPS   # ≈ 0.433 s


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def api_post(endpoint: str, data: dict) -> dict:
    body = json.dumps(data).encode("utf-8")
    req  = urllib.request.Request(
        f"{API_URL}{endpoint}", data=body,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def wait_for_file(path: str, retries: int = 10, delay: float = 0.4) -> bool:
    for _ in range(retries):
        if os.path.exists(path):
            return True
        time.sleep(delay)
    return False


# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------

def add_words_to_draft(
    draft_path:  str,
    words:       list,
    style:       str  = "defaultTypeWhite",
    animation:   str  = "popInUpper",
    position_x:  float = 0.5,
    position_y:  float = 0.85,
) -> dict:
    """
    Inserts subtitle overlays into an existing draft_content.json.
    Returns a summary dict.
    """
    if style not in STYLES:
        raise ValueError(f"Unknown style '{style}'. Available: {list(STYLES)}")

    style_params = STYLES[style]

    # ------------------------------------------------------------------
    # Step 1 — create text-only temp draft
    # ------------------------------------------------------------------
    r = api_post("/create_draft", {"width": 1080, "height": 1920})
    if not r.get("success"):
        raise RuntimeError(f"create_draft failed: {r.get('error')}")
    draft_id = r["output"]["draft_id"]

    # ------------------------------------------------------------------
    # Step 2 — add each entry as styled + animated text
    # ------------------------------------------------------------------
    errors = []
    for i, entry in enumerate(words):
        text  = entry.get("word") or entry.get("text", "")
        start = entry["start"]
        end   = entry["end"]
        track = f"w_{i}"

        r = api_post("/add_text", {
            "draft_id": draft_id,
            "text": text,
            "start": start,
            "end": end,
            "position_x": position_x,
            "position_y": position_y,
            "track_name": track,
            **style_params,
        })
        if not r.get("success"):
            errors.append(f"add_text[{i}] '{text}': {r.get('error')}")
            continue

        if animation == "popInUpper":
            t0, t1 = start, start + KF_OFFSET
            # fade-in
            r2 = api_post("/add_video_keyframe", {
                "draft_id": draft_id, "track_name": track,
                "property_types": ["alpha", "alpha"],
                "times": [t0, t1], "values": ["0", "1"],
            })
            if not r2.get("success"):
                errors.append(f"kf_alpha[{i}]: {r2.get('error')}")

            # fall from above (positive offset = higher in CapCut keyframe space)
            r3 = api_post("/add_video_keyframe", {
                "draft_id": draft_id, "track_name": track,
                "property_types": ["position_y", "position_y"],
                "times": [t0, t1],
                "values": [str(position_y + 0.03), str(position_y)],
            })
            if not r3.get("success"):
                errors.append(f"kf_pos_y[{i}]: {r3.get('error')}")

    if errors:
        print(f"[add_words_to_draft] Warnings ({len(errors)}):", file=sys.stderr)
        for e in errors[:5]:
            print(f"  {e}", file=sys.stderr)

    # ------------------------------------------------------------------
    # Step 3 — save temp draft to VECTCUT_DIR
    # ------------------------------------------------------------------
    api_post("/save_draft", {"draft_id": draft_id})

    source_path = os.path.join(VECTCUT_DIR, draft_id, "draft_info.json")
    if not wait_for_file(source_path):
        raise FileNotFoundError(f"Temp draft not found after save: {source_path}")

    with open(source_path, encoding="utf-8") as f:
        source = json.load(f)

    # ------------------------------------------------------------------
    # Step 4 — read target draft and backup
    # ------------------------------------------------------------------
    with open(draft_path, encoding="utf-8") as f:
        target = json.load(f)

    bak_path = draft_path + ".bak_words"
    if not os.path.exists(bak_path):
        with open(bak_path, "w", encoding="utf-8") as f:
            json.dump(target, f, ensure_ascii=False)

    # ------------------------------------------------------------------
    # Step 5 — merge text tracks
    # Text tracks in VectCutAPI drafts are named w_N — select only those.
    # ------------------------------------------------------------------
    text_tracks = [
        t for t in source.get("tracks", [])
        if t.get("name", "").startswith("w_")
    ]
    target.setdefault("tracks", []).extend(text_tracks)

    # ------------------------------------------------------------------
    # Step 6 — merge text materials
    # ------------------------------------------------------------------
    # Collect material IDs referenced by our text tracks
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

    # ------------------------------------------------------------------
    # Step 7 — write back
    # ------------------------------------------------------------------
    with open(draft_path, "w", encoding="utf-8") as f:
        json.dump(target, f, ensure_ascii=False)

    return {
        "temp_draft_id": draft_id,
        "entries_added": len(words),
        "text_tracks_merged": len(text_tracks),
        "materials_merged": len(src_texts),
        "warnings": len(errors),
    }


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Add subtitle overlays to an existing CapCut draft_content.json"
    )
    parser.add_argument("--draft",      required=True,
                        help="Path to target draft_content.json")
    parser.add_argument("--words",      required=True,
                        help="JSON string or path to .json file with word/phrase list")
    parser.add_argument("--style",      default="defaultTypeWhite",
                        choices=list(STYLES),
                        help="Typography style preset (default: defaultTypeWhite)")
    parser.add_argument("--animation",  default="popInUpper",
                        help="Animation preset: popInUpper | none (default: popInUpper)")
    parser.add_argument("--position_x", type=float, default=0.5)
    parser.add_argument("--position_y", type=float, default=0.85)
    args = parser.parse_args()

    # Parse words — accept JSON string or path to file
    if args.words.strip().startswith("["):
        words = json.loads(args.words)
    else:
        with open(args.words, encoding="utf-8") as f:
            words = json.load(f)

    result = add_words_to_draft(
        draft_path  = args.draft,
        words       = words,
        style       = args.style,
        animation   = args.animation if args.animation != "none" else None,
        position_x  = args.position_x,
        position_y  = args.position_y,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))