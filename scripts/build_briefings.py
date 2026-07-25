#!/usr/bin/env python3
"""
build_briefings.py
Scans briefings/*.md for files with status: published in their front matter
and compiles them into briefings.json, which the site actually reads.
Draft files (status: draft) are ignored entirely, so nothing you haven't
approved ever appears on the live page.

Runs automatically (via .github/workflows/build-briefings.yml) whenever you
edit a file in briefings/ and push/commit the change — e.g. flipping
"status: draft" to "status: published" after you've reviewed the AI's draft.

Can also be run locally: python scripts/build_briefings.py
"""

import json
import os
import re

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BRIEFINGS_DIR = os.path.join(REPO_ROOT, "briefings")
OUTPUT_FILE = os.path.join(REPO_ROOT, "briefings.json")

FRONT_MATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)


def parse_file(path):
    with open(path, "r", encoding="utf-8") as f:
        raw = f.read()

    match = FRONT_MATTER_RE.match(raw)
    if not match:
        return None

    front_matter_block, body = match.groups()
    meta = {}
    for line in front_matter_block.splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        meta[key.strip()] = value.strip()

    return {
        "date": meta.get("date", ""),
        "title": meta.get("title", "Untitled Briefing"),
        "status": meta.get("status", "draft"),
        "body": body.strip(),
    }


def main():
    if not os.path.isdir(BRIEFINGS_DIR):
        print("No briefings/ directory yet — nothing to build.")
        briefings = []
    else:
        briefings = []
        for filename in sorted(os.listdir(BRIEFINGS_DIR)):
            if not filename.endswith(".md"):
                continue
            parsed = parse_file(os.path.join(BRIEFINGS_DIR, filename))
            if not parsed:
                print(f"[warn] couldn't parse front matter in {filename}, skipping")
                continue
            if parsed["status"].lower() == "published":
                briefings.append(parsed)

    briefings.sort(key=lambda b: b["date"], reverse=True)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump({"briefings": briefings}, f, indent=2, ensure_ascii=False)

    print(f"Built briefings.json with {len(briefings)} published briefing(s).")


if __name__ == "__main__":
    main()
