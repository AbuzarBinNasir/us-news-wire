#!/usr/bin/env python3
"""
fetch_news.py
Fetches U.S. news RSS feeds, keeps only articles published in the last 24
hours, appends them to news.json without duplicating existing stories, and
removes any stored article older than 7 days.

Run manually:  python scripts/fetch_news.py
Run by GitHub Actions on a daily schedule (see .github/workflows/fetch-news.yml)
"""

import calendar
import json
import hashlib
import os
import sys
import time
from datetime import datetime, timedelta, timezone

import feedparser

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

FEEDS = [
    {"name": "NPR", "url": "https://feeds.npr.org/1001/rss.xml"},
    {"name": "CBS News", "url": "https://www.cbsnews.com/latest/rss/us"},
    {"name": "ABC News", "url": "https://feeds.abcnews.com/abcnews/usheadlines"},
    {"name": "PBS NewsHour", "url": "https://www.pbs.org/newshour/feeds/rss/headlines"},
    {"name": "Fox News", "url": "https://moxie.foxnews.com/google-publisher/us.xml"},
    {"name": "UPI", "url": "https://rss.upi.com/news/tn_us.rss"},
]

DATA_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "news.json")

MAX_AGE_HOURS_FOR_NEW_ITEMS = 24   # only ingest articles published within this window
MAX_AGE_DAYS_TO_KEEP = 7           # prune anything older than this from storage
REQUEST_TIMEOUT = 20


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_existing():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict) and "articles" in data:
                    return data["articles"]
        except (json.JSONDecodeError, OSError):
            pass
    return []


def make_id(link, title):
    """Stable unique id for dedup, based on the article URL (falls back to title)."""
    key = (link or title or "").strip().lower()
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


def entry_published_utc(entry):
    """Return a timezone-aware UTC datetime for an entry, or None if unavailable."""
    for field in ("published_parsed", "updated_parsed"):
        struct = getattr(entry, field, None)
        if struct:
            # feedparser normalizes this struct_time to UTC already
            epoch = calendar.timegm(struct)
            return datetime.fromtimestamp(epoch, tz=timezone.utc)
    return None


def clean_summary(entry):
    summary = getattr(entry, "summary", "") or ""
    # Very light HTML strip so descriptions render cleanly as plain text
    import re
    summary = re.sub(r"<[^>]+>", "", summary)
    summary = summary.replace("&nbsp;", " ").strip()
    if len(summary) > 280:
        summary = summary[:277].rsplit(" ", 1)[0] + "..."
    return summary


def fetch_feed(source_name, url):
    articles = []
    try:
        parsed = feedparser.parse(url, agent="Mozilla/5.0 (compatible; USNewsBot/1.0)")
    except Exception as exc:  # network or parsing failure for one feed shouldn't kill the run
        print(f"  [warn] failed to fetch {source_name}: {exc}", file=sys.stderr)
        return articles

    if getattr(parsed, "bozo", False) and not parsed.entries:
        print(f"  [warn] {source_name} feed returned no usable entries "
              f"({getattr(parsed, 'bozo_exception', 'unknown error')})", file=sys.stderr)
        return articles

    for entry in parsed.entries:
        title = getattr(entry, "title", "").strip()
        link = getattr(entry, "link", "").strip()
        if not title or not link:
            continue

        published_dt = entry_published_utc(entry)
        articles.append({
            "id": make_id(link, title),
            "title": title,
            "link": link,
            "summary": clean_summary(entry),
            "source": source_name,
            "published": published_dt.isoformat() if published_dt else None,
        })

    return articles


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    now = datetime.now(timezone.utc)
    cutoff_new = now - timedelta(hours=MAX_AGE_HOURS_FOR_NEW_ITEMS)
    cutoff_keep = now - timedelta(days=MAX_AGE_DAYS_TO_KEEP)

    existing = load_existing()
    existing_ids = {a["id"] for a in existing}

    print(f"Loaded {len(existing)} existing articles from {DATA_FILE}")

    added = 0
    for feed in FEEDS:
        print(f"Fetching {feed['name']} ...")
        entries = fetch_feed(feed["name"], feed["url"])
        for art in entries:
            if art["id"] in existing_ids:
                continue  # already stored, skip (no duplicates)

            # Only ingest articles published within the last 24 hours.
            # If a feed entry has no publish date, accept it (better to show
            # it than silently drop legitimate breaking news), but tag it
            # with "now" so it doesn't get pruned prematurely.
            if art["published"]:
                pub_dt = datetime.fromisoformat(art["published"])
                if pub_dt < cutoff_new:
                    continue
            else:
                art["published"] = now.isoformat()

            existing.append(art)
            existing_ids.add(art["id"])
            added += 1

    # Prune anything older than MAX_AGE_DAYS_TO_KEEP
    before_prune = len(existing)
    kept = []
    for art in existing:
        try:
            pub_dt = datetime.fromisoformat(art["published"])
        except (TypeError, ValueError):
            pub_dt = now
        if pub_dt >= cutoff_keep:
            kept.append(art)
    pruned = before_prune - len(kept)

    # Sort newest first for convenience (frontend also sorts, but this keeps
    # the raw JSON readable and diff-friendly)
    kept.sort(key=lambda a: a.get("published") or "", reverse=True)

    output = {
        "last_updated": now.isoformat(),
        "articles": kept,
    }

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"Added {added} new articles, pruned {pruned} old articles, "
          f"{len(kept)} total stored.")


if __name__ == "__main__":
    main()
