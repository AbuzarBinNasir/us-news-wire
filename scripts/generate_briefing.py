#!/usr/bin/env python3
"""
generate_briefing.py
Reads today's stored headlines from news.json and asks Claude to draft an
ORIGINAL analysis piece (not a rewrite/summary of any single article) about
what's happening in U.S. news today. The draft is saved to
briefings/YYYY-MM-DD.md with status: draft — it will NOT appear on the live
site until a human opens the file, reviews/edits the text, and changes
status to "published".

Requires the ANTHROPIC_API_KEY environment variable (set as a GitHub Actions
secret — see README.md). If it's missing, this script logs a warning and
exits without failing the workflow, so the news fetch still succeeds.
"""

import json
import os
import re
import sys
import urllib.request
import urllib.error
from datetime import datetime, timedelta, timezone

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NEWS_FILE = os.path.join(REPO_ROOT, "news.json")
BRIEFINGS_DIR = os.path.join(REPO_ROOT, "briefings")

MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")
API_KEY = os.environ.get("ANTHROPIC_API_KEY")
API_URL = "https://api.anthropic.com/v1/messages"

SYSTEM_PROMPT = """You are a U.S. news editorial writer producing one short daily briefing.

Rules:
- Write ORIGINAL analysis and commentary. Do not copy or closely paraphrase any
  sentence from the source headlines/summaries provided — use them only as raw
  facts to synthesize your own independent write-up.
- Identify the 2-4 most significant U.S. stories from the list and explain why
  they matter, how they connect, and what to watch next. Add genuine
  perspective and context, not just a recap.
- Neutral, factual tone. Do not take a partisan side on contested political
  topics; where a topic is contested, note the different perspectives fairly.
- Length: 350-500 words, in 3-5 short paragraphs.
- Output format EXACTLY as follows, with no markdown formatting, no headers,
  no bullet points, and nothing before or after it:

TITLE: <a short original headline for the briefing, under 12 words>
BODY:
<paragraph 1>

<paragraph 2>

<paragraph 3>
"""


def load_todays_headlines():
    if not os.path.exists(NEWS_FILE):
        return []
    with open(NEWS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    items = []
    for art in data.get("articles", []):
        pub = art.get("published")
        try:
            pub_dt = datetime.fromisoformat(pub) if pub else None
        except ValueError:
            pub_dt = None
        if pub_dt and pub_dt >= cutoff:
            items.append(art)
    return items


def call_claude(headlines):
    lines = [f"- [{a['source']}] {a['title']}: {a.get('summary', '')}" for a in headlines]
    user_content = "Today's U.S. headlines:\n" + "\n".join(lines)

    payload = {
        "model": MODEL,
        "max_tokens": 900,
        "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": user_content}],
    }

    req = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-api-key": API_KEY,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=60) as resp:
        result = json.loads(resp.read().decode("utf-8"))

    text_blocks = [b["text"] for b in result.get("content", []) if b.get("type") == "text"]
    return "\n".join(text_blocks).strip()


def parse_response(raw):
    title_match = re.search(r"TITLE:\s*(.+)", raw)
    body_match = re.search(r"BODY:\s*(.+)", raw, re.DOTALL)
    title = title_match.group(1).strip() if title_match else "Today's U.S. News Briefing"
    body = body_match.group(1).strip() if body_match else raw.strip()
    return title, body


def write_draft(date_key, title, body):
    os.makedirs(BRIEFINGS_DIR, exist_ok=True)
    path = os.path.join(BRIEFINGS_DIR, f"{date_key}.md")

    if os.path.exists(path):
        print(f"briefings/{date_key}.md already exists — leaving it untouched "
              f"(don't want to overwrite a draft you may already be editing).")
        return

    front_matter = (
        "---\n"
        f"date: {date_key}\n"
        f"title: {title}\n"
        "status: draft\n"
        "---\n\n"
    )
    with open(path, "w", encoding="utf-8") as f:
        f.write(front_matter + body + "\n")
    print(f"Wrote draft: briefings/{date_key}.md")


def main():
    if not API_KEY:
        print("[warn] ANTHROPIC_API_KEY not set — skipping briefing generation. "
              "See README.md to add it as a repo secret.", file=sys.stderr)
        return

    headlines = load_todays_headlines()
    if not headlines:
        print("[info] No headlines from the last 24 hours yet — skipping briefing "
              "(run fetch_news.py first).")
        return

    date_key = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    briefing_path = os.path.join(BRIEFINGS_DIR, f"{date_key}.md")
    if os.path.exists(briefing_path):
        print(f"briefings/{date_key}.md already exists — skipping generation.")
        return

    try:
        raw = call_claude(headlines)
    except urllib.error.HTTPError as e:
        print(f"[error] Claude API request failed: {e.code} {e.read().decode('utf-8', 'ignore')}",
              file=sys.stderr)
        return
    except Exception as e:
        print(f"[error] Claude API request failed: {e}", file=sys.stderr)
        return

    title, body = parse_response(raw)
    write_draft(date_key, title, body)


if __name__ == "__main__":
    main()
