#!/usr/bin/env python3
"""
Validates that all media files referenced in a CapCut draft exist on disk.
Usage: python utils_py/validate_project.py "path/to/draft_content.json"
"""
import json
import sys
import os


def validate_project(draft_path: str) -> dict:
    with open(draft_path, "r", encoding="utf-8") as f:
        d = json.load(f)

    materials = d.get("materials", {})

    results = {
        "valid": True,
        "checked": [],
        "missing": [],
        "found": [],
    }

    # Check all material types that have paths
    for material_type in ["audios", "videos", "images", "stickers"]:
        for item in materials.get(material_type, []):
            path = item.get("path", "").strip()
            if not path:
                continue

            # Normalize path separators
            normalized = path.replace("/", os.sep).replace("\\", os.sep)

            entry = {
                "type": material_type,
                "id": item.get("id"),
                "name": item.get("name", ""),
                "path": normalized,
            }

            results["checked"].append(entry)

            if os.path.exists(normalized):
                results["found"].append(normalized)
            else:
                results["missing"].append(normalized)
                results["valid"] = False

    # Deduplicate
    results["found"] = list(set(results["found"]))
    results["missing"] = list(set(results["missing"]))

    return results


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python utils_py/validate_project.py <path_to_draft_content.json>")
        sys.exit(1)

    result = validate_project(sys.argv[1])

    print(json.dumps(result, indent=2, ensure_ascii=False))

    # Exit with error code if files are missing
    if not result["valid"]:
        print(f"\n⚠ {len(result['missing'])} archivo(s) no encontrado(s):", file=sys.stderr)
        for path in result["missing"]:
            print(f"  - {path}", file=sys.stderr)
        sys.exit(1)
    else:
        print(f"\n✓ Todos los archivos encontrados ({len(result['found'])} únicos)", file=sys.stderr)