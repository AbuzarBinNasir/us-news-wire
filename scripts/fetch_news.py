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
import re
import sys
import time
import urllib.request
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


def extract_image(entry):
    """Pull a representative image URL for the article, if the feed provides
    one. Publishers include these in RSS specifically so aggregators can
    display them alongside the headline (same purpose as the headline/link
    itself), so we just use the URL directly rather than hosting our own copy."""
    # 1. Media RSS thumbnail (used by NPR, PBS, and others)
    thumb = getattr(entry, "media_thumbnail", None)
    if thumb and isinstance(thumb, list) and thumb[0].get("url"):
        return thumb[0]["url"]

    # 2. Media RSS content (image or thumbnail medium)
    media = getattr(entry, "media_content", None)
    if media and isinstance(media, list):
        for m in media:
            if m.get("medium") == "image" or (m.get("type", "").startswith("image")):
                if m.get("url"):
                    return m["url"]

    # 3. Standard RSS enclosure tag (used by CBS News, Fox News, UPI)
    for enc in getattr(entry, "enclosures", []) or []:
        if enc.get("type", "").startswith("image") and enc.get("href"):
            return enc["href"]
        if enc.get("type", "").startswith("image") and enc.get("url"):
            return enc["url"]

    # 4. Fall back to the first <img> tag embedded in the raw summary HTML
    raw_summary = getattr(entry, "summary", "") or ""
    match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', raw_summary)
    if match:
        return match.group(1)

    return None


OG_IMAGE_RE = re.compile(
    r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
    re.IGNORECASE,
)
OG_IMAGE_RE_ALT = re.compile(
    r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
    re.IGNORECASE,
)


def fetch_og_image(article_url):
    """Fallback when the RSS entry itself has no image: fetch the article
    page and read its og:image meta tag (the same image the publisher shows
    when the link is shared on social media). Best-effort only — any
    failure here is silently ignored so it never breaks the main run."""
    try:
        req = urllib.request.Request(
            article_url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; USNewsBot/1.0)"},
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            # Only read the first ~60KB — og:image is always in <head>, no
            # need to download the full page
            html = resp.read(60_000).decode("utf-8", errors="ignore")
        match = OG_IMAGE_RE.search(html) or OG_IMAGE_RE_ALT.search(html)
        return match.group(1) if match else None
    except Exception:
        return None


def clean_summary(entry):
    summary = getattr(entry, "summary", "") or ""
    # Very light HTML strip so descriptions render cleanly as plain text
    summary = re.sub(r"<[^>]+>", "", summary)
    summary = summary.replace("&nbsp;", " ").strip()
    if len(summary) > 280:
        summary = summary[:277].rsplit(" ", 1)[0] + "..."
    return summary


def fetch_feed(source_name, url, existing_ids):
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

        article_id = make_id(link, title)
        image = extract_image(entry)

        # Only worth the extra page fetch for articles we don't already have
        # stored and that had no image in the feed itself.
        if not image and article_id not in existing_ids:
            image = fetch_og_image(link)

        published_dt = entry_published_utc(entry)
        articles.append({
            "id": article_id,
            "title": title,
            "link": link,
            "summary": clean_summary(entry),
            "source": source_name,
            "published": published_dt.isoformat() if published_dt else None,
            "image": image,
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
        entries = fetch_feed(feed["name"], feed["url"], existing_ids)
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
