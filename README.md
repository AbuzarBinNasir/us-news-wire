# The Wire — U.S. News Dashboard

A free, static, single-purpose website with two parts:

1. **The wire feed** — headlines from NPR, CBS News, ABC News, PBS NewsHour,
   Fox News, and UPI, refreshed daily. New stories are added on top of
   older ones, nothing is ever replaced, anything older than 7 days is
   dropped automatically.
2. **The Briefing** — an *original* daily analysis piece (350–500 words)
   about what's actually happening in U.S. news, drafted automatically by
   Claude each day and held back until **you review and approve it**. This
   is the part that makes the site eligible for ad monetization (see
   [Monetizing](#monetizing-this-site) below) — pure aggregated headlines
   generally don't qualify for AdSense or comply with most outlets' RSS
   terms, but original commentary does.

## What's in this folder

```
index.html                          the page itself
style.css                           styling
app.js                              loads news.json + briefings.json and renders them
news.json                           wire feed data (starts empty)
briefings.json                      published briefings only (starts empty)
briefings/                          one .md file per day — drafts + published pieces
requirements.txt                    Python dependency for the fetch script
scripts/fetch_news.py               fetches RSS, dedupes, appends, prunes >7 days
scripts/generate_briefing.py        asks Claude to draft today's original briefing
scripts/build_briefings.py          compiles only *published* briefings into briefings.json
.github/workflows/fetch-news.yml       daily: fetch news + draft a briefing
.github/workflows/build-briefings.yml  on publish: rebuild briefings.json
```

Everything is a static file — there is no server or database. The only
paid component is small, optional, pay-as-you-go usage of the Claude API
for drafting briefings (see cost note below).

---

## Step 1 — Create the GitHub repository

1. Go to [github.com/new](https://github.com/new).
2. Name it anything, e.g. `us-news-wire`. Set it to **Public** (required for
   free GitHub Pages). Don't initialize with a README (you already have one).
3. Click **Create repository**.

## Step 2 — Upload these files

Easiest way (no git command line needed):

1. On your new repo's page, click **"uploading an existing file"** (or
   **Add file → Upload files**).
2. Drag in *all* the files and folders from this delivery, keeping the
   folder structure intact — especially `.github/workflows/fetch-news.yml`
   and `scripts/fetch_news.py`. GitHub's uploader preserves folder paths
   when you drag a whole folder in.
3. Scroll down, add a commit message like "Initial site", click
   **Commit changes**.

(If you prefer git: `git init`, `git add .`, `git commit -m "Initial site"`,
`git remote add origin <your-repo-url>`, `git push -u origin main`.)

## Step 3 — Enable GitHub Pages

1. In your repo, go to **Settings → Pages** (left sidebar).
2. Under **Build and deployment → Source**, choose **Deploy from a branch**.
3. Under **Branch**, choose `main` and folder `/ (root)`. Click **Save**.
4. Wait about 1 minute. GitHub will show your live URL at the top of that
   page, something like:
   `https://YOUR-USERNAME.github.io/us-news-wire/`

The site will load and show "Couldn't load news.json" or an empty state
until you run the fetch at least once — that's step 4.

## Step 4 — Allow the workflow to commit, then run the first fetch

1. Go to **Settings → Actions → General**.
2. Scroll to **Workflow permissions**, select **Read and write permissions**,
   click **Save**. (This lets the daily job commit the updated `news.json`
   back to your repo.)
3. Go to the **Actions** tab at the top of your repo.
4. Click **Fetch US News Daily** in the left list.
5. Click **Run workflow** (dropdown on the right) → **Run workflow**.
6. Wait ~30–60 seconds, refresh — you'll see a green checkmark when it's
   done. It will have committed an updated `news.json` with the last 24
   hours of stories from all six sources.
7. Reload your GitHub Pages URL — the site will now show live stories,
   newest on top.

## Step 5 — Add your Claude API key (for the daily Briefing draft)

The wire feed works without this. This step only enables the AI-drafted
"Briefing" section.

1. Get a key at [console.anthropic.com](https://console.anthropic.com) →
   **Settings → API Keys → Create Key**. New accounts get starter credit;
   after that it's pay-as-you-go and billed to a card you add there.
2. Back in your GitHub repo: **Settings → Secrets and variables → Actions**.
3. Under **Secrets** tab, click **New repository secret**:
   - Name: `ANTHROPIC_API_KEY`
   - Value: paste the key from step 1
4. *(Optional)* Under the **Variables** tab, click **New repository
   variable** to pick a different model:
   - Name: `ANTHROPIC_MODEL`
   - Value: `claude-haiku-4-5-20251001` (default — cheapest, ~$0.15–0.30/month
     for one briefing a day) or `claude-sonnet-5` (higher quality, roughly
     10x the cost, still just a few dollars a month at this volume).

If you skip this step, the workflow still runs fine — it just logs a
warning and skips the briefing, and the wire feed keeps working normally.

## Step 6 — Run the first fetch, then review & publish the briefing

1. Go to **Settings → Actions → General → Workflow permissions →
   Read and write permissions → Save** (same as before — lets the bot commit).
2. **Actions** tab → **Fetch US News Daily** → **Run workflow**. Wait ~1
   minute for the green checkmark.
3. This creates a new file at `briefings/YYYY-MM-DD.md` in your repo with
   `status: draft` — Claude's draft is in there, but it will **not** show
   on your live site yet.
4. Open that file on GitHub (in the `briefings/` folder), click the
   pencil/edit icon:
   - Read Claude's draft. Edit the text however you want, or leave it as is.
   - Change the line `status: draft` to `status: published`.
   - Click **Commit changes**.
5. That commit automatically triggers the **Rebuild Published Briefings**
   workflow, which regenerates `briefings.json`. Within a minute, reload
   your GitHub Pages URL — your reviewed briefing is now live at the top
   of the page.

From now on, every day: a new draft appears in `briefings/`, you open it,
edit if you like, flip `status` to `published`, commit — done. Nothing
publishes without you approving it first.

## Step 7 — Confirm the daily automation

The fetch workflow is already scheduled to run every day at **11:00 UTC**
(around 7:00 AM Eastern) with no action needed from you. Each run:

- Fetches all 6 RSS feeds, keeps only articles from the last 24 hours,
  skips duplicates, removes anything older than 7 days
- Drafts a new `briefings/YYYY-MM-DD.md` (if one for that day doesn't exist yet)
- Commits everything, which republishes the live site automatically

You can change the schedule any time by editing the `cron:` line in
`.github/workflows/fetch-news.yml` (times are in UTC), and trigger either
workflow manually anytime from the **Actions** tab.

## Monetizing this site

A few honest notes, since this determines what will actually work:

- **Pure headline aggregation doesn't qualify for AdSense** — Google's
  policy explicitly flags "aggregated content from other sources" as a
  rejection reason, and most outlets' RSS terms restrict ad placement tied
  to their content. The Briefing section exists specifically to solve
  this: it's original writing, reviewed by a human (you), which is what
  AdSense and most ad networks actually require.
- To apply for **Google AdSense**, build up 15–20+ published Briefings
  first (a few weeks of daily use), add an About page and a Privacy
  Policy page (required — plenty of free generators exist, or ask me to
  build these), then apply at [google.com/adsense](https://www.google.com/adsense).
- Other options that don't require AdSense approval: an email newsletter
  built from your Briefings (Substack/Beehiiv, monetizable via paid
  subscribers later), affiliate links relevant to a news-reading audience,
  or simply using the growing traffic to promote something you already
  own (e.g. your Amazon KDP books).
- Keep editing every draft before publishing — beyond the legal/policy
  reasons, it's also what makes the writing actually good enough that
  people come back daily, which is what any of the above monetization
  paths ultimately depends on.

---

## Customizing

- **Add/remove a source:** edit the `FEEDS` list at the top of
  `scripts/fetch_news.py`, and optionally add a matching color in
  `SOURCE_COLORS` in `app.js`.
- **Change the retention window:** `MAX_AGE_DAYS_TO_KEEP` in
  `scripts/fetch_news.py` (currently 7).
- **Change the "new article" ingestion window:** `MAX_AGE_HOURS_FOR_NEW_ITEMS`
  in `scripts/fetch_news.py` (currently 24).
- **Change the briefing prompt/tone:** edit `SYSTEM_PROMPT` in
  `scripts/generate_briefing.py`.
- **Run locally:** `pip install -r requirements.txt`, then
  `python scripts/fetch_news.py` to update the wire feed, and (with
  `ANTHROPIC_API_KEY` set as an environment variable)
  `python scripts/generate_briefing.py` to draft a briefing, then
  `python scripts/build_briefings.py` after you edit its status to
  `published`. Open `index.html` in a browser (or run
  `python -m http.server` in the folder and visit `localhost:8000`) to preview.

## Notes on the sources

All six feeds are free, publicly documented RSS feeds intended for exactly
this kind of use (personal, non-commercial headline aggregation with links
back to the original publisher). If any single feed goes down or changes
its URL, the fetch script logs a warning for that one source and continues
with the rest — it won't break the whole run.
