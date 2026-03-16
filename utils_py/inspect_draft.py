#!/usr/bin/env python3
"""
Inspects a CapCut draft_content.json and prints a structured summary as JSON.
Usage: python utils_py/inspect_draft.py "path/to/draft_content.json"
"""
import json
import sys

def inspect_draft(draft_path: str) -> dict:
    with open(draft_path, "r", encoding="utf-8") as f:
        d = json.load(f)

    # Duration and fps
    duration_us = d.get("duration", 0)
    fps = d.get("fps", 30)
    duration_sec = duration_us / 1_000_000

    # Tracks
    tracks_summary = []
    for track in d.get("tracks", []):
        tracks_summary.append({
            "type": track.get("type"),
            "segment_count": len(track.get("segments", [])),
            "segments": [
                {
                    "id": seg.get("id"),
                    "start_sec": seg.get("target_timerange", {}).get("start", 0) / 1_000_000,
                    "duration_sec": seg.get("target_timerange", {}).get("duration", 0) / 1_000_000,
                }
                for seg in track.get("segments", [])
            ]
        })

    # Materials
    materials = d.get("materials", {})

    audios = [
        {
            "id": a.get("id"),
            "path": a.get("path"),
            "name": a.get("name"),
        }
        for a in materials.get("audios", [])
        if a.get("path")
    ]

    # Deduplicate audios by path
    seen_paths = set()
    unique_audios = []
    for a in audios:
        if a["path"] not in seen_paths:
            seen_paths.add(a["path"])
            unique_audios.append(a)

    videos = [
        {
            "id": v.get("id"),
            "path": v.get("path"),
            "name": v.get("name"),
        }
        for v in materials.get("videos", [])
        if v.get("path")
    ]

    # Deduplicate videos by path
    seen_paths = set()
    unique_videos = []
    for v in videos:
        if v["path"] not in seen_paths:
            seen_paths.add(v["path"])
            unique_videos.append(v)

    return {
        "duration_sec": round(duration_sec, 3),
        "fps": fps,
        "tracks": tracks_summary,
        "audio_materials": unique_audios,
        "video_materials": unique_videos,
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python utils_py/inspect_draft.py <path_to_draft_content.json>")
        sys.exit(1)

    result = inspect_draft(sys.argv[1])
    print(json.dumps(result, indent=2, ensure_ascii=False))