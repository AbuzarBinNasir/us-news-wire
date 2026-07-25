// The Wire — frontend renderer
// Loads news.json (produced by scripts/fetch_news.py) and renders it as a
// day-grouped feed, newest day and newest story first. Purely static: no
// build step, no backend, works on GitHub Pages as-is.

const DATA_URL = "news.json";
const BRIEFINGS_URL = "briefings.json";

// Distinct accent color per source, used for the card's left rule and the
// source label. Anything not listed falls back to the CSS default (navy).
const SOURCE_COLORS = {
  "NPR": "#2B4570",
  "CBS News": "#8A1F2D",
  "ABC News": "#1E5C42",
  "PBS NewsHour": "#5B4B8A",
  "Fox News": "#0F4C81",
  "UPI": "#946A1F",
};

let allArticles = [];
let activeSource = "all";

function timeAgo(iso) {
  if (!iso) return "";
  const then = new Date(iso).getTime();
  const diffMin = Math.round((Date.now() - then) / 60000);
  if (diffMin < 1) return "just now";
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.round(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  const diffDay = Math.round(diffHr / 24);
  return `${diffDay}d ago`;
}

function dayLabel(dateKey) {
  const today = new Date();
  const todayKey = dateKey === today.toISOString().slice(0, 10);
  const yesterday = new Date(today);
  yesterday.setDate(today.getDate() - 1);
  const yesterdayKey = dateKey === yesterday.toISOString().slice(0, 10);

  const d = new Date(dateKey + "T00:00:00");
  const formatted = d.toLocaleDateString(undefined, {
    weekday: "long", month: "long", day: "numeric", year: "numeric",
  });

  if (todayKey) return { text: `Today — ${formatted}`, isNew: true };
  if (yesterdayKey) return { text: `Yesterday — ${formatted}`, isNew: false };
  return { text: formatted, isNew: false };
}

function groupByDay(articles) {
  const groups = new Map();
  for (const art of articles) {
    if (!art.published) continue;
    const key = art.published.slice(0, 10); // YYYY-MM-DD (UTC date of publish)
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(art);
  }
  // Sort day keys descending, and articles within each day descending
  const sortedKeys = [...groups.keys()].sort((a, b) => (a < b ? 1 : -1));
  for (const key of sortedKeys) {
    groups.get(key).sort((a, b) => (a.published < b.published ? 1 : -1));
  }
  return sortedKeys.map((key) => ({ key, items: groups.get(key) }));
}

function renderSourceChips(articles) {
  const bar = document.getElementById("filter-bar");
  const sources = [...new Set(articles.map((a) => a.source))].sort();

  sources.forEach((source) => {
    const btn = document.createElement("button");
    btn.className = "filter-chip";
    btn.dataset.source = source;
    btn.textContent = source;
    bar.appendChild(btn);
  });

  bar.addEventListener("click", (e) => {
    const btn = e.target.closest(".filter-chip");
    if (!btn) return;
    activeSource = btn.dataset.source;
    [...bar.querySelectorAll(".filter-chip")].forEach((c) =>
      c.classList.toggle("is-active", c === btn)
    );
    render();
  });
}

function render() {
  const feed = document.getElementById("feed");
  feed.innerHTML = "";

  const filtered = activeSource === "all"
    ? allArticles
    : allArticles.filter((a) => a.source === activeSource);

  if (filtered.length === 0) {
    feed.innerHTML = `<div class="state-message">No stories in the last 7 days for this source yet. Check back after the next daily update.</div>`;
    return;
  }

  const groups = groupByDay(filtered);

  for (const group of groups) {
    const label = dayLabel(group.key);

    const section = document.createElement("section");
    section.className = "day-group";

    const dateline = document.createElement("div");
    dateline.className = "day-dateline";
    dateline.innerHTML = `<span>${label.text}</span>${label.isNew ? '<span class="badge-new">New</span>' : ""}`;
    section.appendChild(dateline);

    group.items.forEach((art, i) => {
      const card = document.createElement("a");
      card.className = "article-card";
      card.href = art.link;
      card.target = "_blank";
      card.rel = "noopener noreferrer";
      card.style.setProperty("--source-color", SOURCE_COLORS[art.source] || "");
      card.style.animationDelay = `${Math.min(i, 8) * 30}ms`;

      card.innerHTML = `
        <div class="article-meta">
          <span class="source-pill">${escapeHtml(art.source)}</span>
          <span>·</span>
          <span>${timeAgo(art.published)}</span>
        </div>
        <h2 class="article-title">${escapeHtml(art.title)}</h2>
        ${art.summary ? `<p class="article-summary">${escapeHtml(art.summary)}</p>` : ""}
      `;
      section.appendChild(card);
    });

    feed.appendChild(section);
  }
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str || "";
  return div.innerHTML;
}

function setMasthead(lastUpdated) {
  const dateEl = document.getElementById("masthead-date");
  const updatedEl = document.getElementById("last-updated");
  const now = new Date();
  dateEl.textContent = now.toLocaleDateString(undefined, {
    weekday: "short", month: "short", day: "numeric", year: "numeric",
  }).toUpperCase();
  updatedEl.textContent = lastUpdated ? timeAgo(lastUpdated) : "never yet";
}

function formatBriefingDate(dateKey) {
  if (!dateKey) return "";
  const d = new Date(dateKey + "T00:00:00");
  return d.toLocaleDateString(undefined, {
    weekday: "long", month: "long", day: "numeric", year: "numeric",
  });
}

function renderBriefings(briefings) {
  const section = document.getElementById("briefing-section");

  if (!briefings || briefings.length === 0) {
    section.innerHTML = `
      <div class="briefing-card">
        <div class="briefing-eyebrow">The Briefing</div>
        <div class="briefing-empty">No editorial briefing published yet. One is drafted automatically each day for review — see README.md to publish it.</div>
      </div>`;
    return;
  }

  const [latest, ...older] = briefings;
  const bodyHtml = latest.body
    .split(/\n\s*\n/)
    .map((p) => `<p>${escapeHtml(p.trim())}</p>`)
    .join("");

  let archiveHtml = "";
  if (older.length > 0) {
    const items = older.map((b) => {
      const p = b.body.split(/\n\s*\n/).map((para) => `<p>${escapeHtml(para.trim())}</p>`).join("");
      return `
        <div class="briefing-archive-item">
          <p class="briefing-date">${formatBriefingDate(b.date)}</p>
          <h3 class="briefing-title">${escapeHtml(b.title)}</h3>
          <div class="briefing-body">${p}</div>
        </div>`;
    }).join("");
    archiveHtml = `
      <details class="briefing-archive">
        <summary>Past briefings (${older.length})</summary>
        ${items}
      </details>`;
  }

  section.innerHTML = `
    <div class="briefing-card">
      <div class="briefing-eyebrow">The Briefing</div>
      <p class="briefing-date">${formatBriefingDate(latest.date)}</p>
      <h2 class="briefing-title">${escapeHtml(latest.title)}</h2>
      <div class="briefing-body">${bodyHtml}</div>
    </div>
    ${archiveHtml}
  `;
}

async function init() {
  try {
    const res = await fetch(DATA_URL, { cache: "no-store" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    allArticles = data.articles || [];
    setMasthead(data.last_updated);
    renderSourceChips(allArticles);
    render();

    try {
      const briefRes = await fetch(BRIEFINGS_URL, { cache: "no-store" });
      const briefData = briefRes.ok ? await briefRes.json() : { briefings: [] };
      renderBriefings(briefData.briefings || []);
    } catch (briefErr) {
      renderBriefings([]); // briefings.json not present yet — show empty state, don't break the page
    }
  } catch (err) {
    document.getElementById("feed").innerHTML =
      `<div class="state-message">Couldn't load news.json (${err.message}). ` +
      `If you just set this up, run the fetch script once — see README.md.</div>`;
    setMasthead(null);
  }
}

init();
