#!/usr/bin/env python3
"""
backfill_images.py
One-time (or run-whenever-you-like) helper: goes through every article
already stored in news.json that has no image yet, and tries to fetch one
via each article's og:image tag — same fallback fetch_news.py now uses
automatically for new articles.

Run manually:  python scripts/backfill_images.py
Or trigger it from GitHub Actions → "Backfill Missing Images" → Run workflow.

Safe to re-run any time — it only touches articles that still have no image.
"""

import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_news import fetch_og_image, DATA_FILE  # reuse the same fetch logic

DELAY_BETWEEN_REQUESTS = 0.5  # seconds — be polite to the source sites


def main():
    if not os.path.exists(DATA_FILE):
        print("No news.json found — nothing to backfill.")
        return

    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    articles = data.get("articles", [])
    missing = [a for a in articles if not a.get("image")]

    if not missing:
        print("Every stored article already has an image. Nothing to do.")
        return

    print(f"Found {len(missing)} article(s) with no image — fetching...")

    updated = 0
    for i, art in enumerate(missing, 1):
        image = fetch_og_image(art["link"])
        if image:
            art["image"] = image
            updated += 1
            print(f"  [{i}/{len(missing)}] found image for: {art['title'][:60]}")
        else:
            print(f"  [{i}/{len(missing)}] no image available for: {art['title'][:60]}")
        time.sleep(DELAY_BETWEEN_REQUESTS)

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"\nDone. Added images to {updated} of {len(missing)} articles that were missing one.")


if __name__ == "__main__":
    main()
