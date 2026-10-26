import json
import sqlite3
from difflib import SequenceMatcher
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
from datetime import datetime

HOST = "127.0.0.1"
PORT = 8000
DB = "findora.db"

CATEGORIES = [
    "Electronics", "Wallet & Money", "Keys", "Documents",
    "Bags", "Clothing", "Accessories", "Pets", "Other"
]


# ==================== DATABASE ====================

def database():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row

    conn.execute("""
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_type TEXT NOT NULL,
            title TEXT NOT NULL,
            category TEXT NOT NULL,
            description TEXT NOT NULL,
            location TEXT NOT NULL,
            contact TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()
    return conn


def get_items():
    with database() as conn:
        return [dict(row) for row in conn.execute(
            "SELECT * FROM items ORDER BY id DESC"
        ).fetchall()]


def add_item(data):
    with database() as conn:
        conn.execute("""
            INSERT INTO items
            (item_type, title, category, description,
             location, contact, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            data["item_type"], data["title"], data["category"],
            data["description"], data["location"], data["contact"],
            datetime.now().strftime("%d %b %Y, %I:%M %p")
        ))


def delete_item(item_id):
    with database() as conn:
        conn.execute("DELETE FROM items WHERE id = ?", (item_id,))


# ==================== SMART MATCHING ====================

def similarity(a, b):
    return SequenceMatcher(
        None, a.lower().strip(), b.lower().strip()
    ).ratio()


def match_score(a, b):
    if a["item_type"] == b["item_type"]:
        return 0

    category = (
        35 if a["category"].lower() == b["category"].lower() else 0
    )
    location = similarity(a["location"], b["location"]) * 25
    title = similarity(a["title"], b["title"]) * 25
    description = similarity(
        a["description"], b["description"]
    ) * 15

    return round(min(100, category + location + title + description))


def get_matches(item, items):
    results = []

    for other in items:
        if other["id"] == item["id"]:
            continue

        score = match_score(item, other)

        if score >= 25:
            results.append({
                "item": other,
                "score": score
            })

    return sorted(
        results, key=lambda x: x["score"], reverse=True
    )


def make_payload():
    items = get_items()
    matched_ids = set()

    for item in items:
        matches = get_matches(item, items)
        if matches:
            matched_ids.add(item["id"])

    return {
        "items": items,
        "stats": {
            "total": len(items),
            "lost": sum(i["item_type"] == "Lost" for i in items),
            "found": sum(i["item_type"] == "Found" for i in items),
            "matched": len(matched_ids)
        },
        "categories": CATEGORIES
    }

# ==================== WEB INTERFACE ====================

PAGE = r"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Findora | Smart Lost & Found</title>

<style>
:root {
    --bg: #0b0b0e;
    --panel: #141418;
    --panel2: #1d1d23;
    --orange: #ff7b24;
    --orange2: #ffa052;
    --text: #f6f6f8;
    --muted: #92929e;
    --border: #2b2b33;
    --green: #4de0a0;
    --red: #ff7777;
}

* { box-sizing: border-box; }

body {
    margin: 0;
    background: var(--bg);
    color: var(--text);
    font: 14px/1.5 Inter, system-ui, Arial, sans-serif;
}

button, input, select, textarea { font: inherit; }
button { cursor: pointer; }

nav {
    height: 72px;
    padding: 0 6%;
    display: flex;
    align-items: center;
    justify-content: space-between;
    border-bottom: 1px solid var(--border);
    background: #0e0e11;
}

.logo {
    font-size: 26px;
    font-weight: 850;
    letter-spacing: -1.4px;
}

.logo span { color: var(--orange); }

.nav-right {
    display: flex;
    align-items: center;
    gap: 9px;
    color: var(--muted);
    font-size: 11px;
    letter-spacing: 1px;
}

.status-dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: var(--green);
    box-shadow: 0 0 12px #4de0a077;
}

.container {
    width: min(1200px, 92%);
    margin: 32px auto 60px;
}

.hero {
    padding: 40px;
    border: 1px solid #4b2b19;
    border-radius: 20px;
    background:
        radial-gradient(ellipse at 90% 0%, #48230f 0%, transparent 45%),
        linear-gradient(120deg, #1b1511, #121215 70%);
}

.eyebrow {
    color: var(--orange);
    font-size: 11px;
    font-weight: 800;
    letter-spacing: 2px;
    text-transform: uppercase;
}

h1 {
    margin: 13px 0;
    font-size: clamp(32px, 5vw, 48px);
    line-height: 1.12;
    letter-spacing: -1.8px;
}

h1 span { color: var(--orange); }

.hero p {
    max-width: 570px;
    color: #aaaab4;
    line-height: 1.9;
}

.hero-bottom {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 12px;
    margin-top: 24px;
}

.primary, .secondary, .filter-btn {
    border: 1px solid transparent;
    border-radius: 9px;
    padding: 12px 16px;
    font-weight: 750;
    transition: .2s;
}

.primary {
    background: var(--orange);
    color: #17100a;
}

.primary:hover {
    background: var(--orange2);
    transform: translateY(-1px);
}

.secondary {
    background: #202025;
    color: var(--text);
    border-color: var(--border);
}

.secondary:hover { border-color: var(--orange); }

.stats {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 14px;
    margin: 22px 0 32px;
}

.stat {
    padding: 20px;
    border: 1px solid var(--border);
    border-radius: 14px;
    background: var(--panel);
}

.stat-top {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
}

.stat-label {
    color: var(--muted);
    font-size: 11px;
    letter-spacing: 1px;
}

.stat-icon {
    display: grid;
    place-items: center;
    width: 34px;
    height: 34px;
    border-radius: 10px;
    background: #ff7b2419;
    color: var(--orange);
}

.stat-number {
    margin-top: 12px;
    font-size: 31px;
    font-weight: 850;
}

.workspace {
    display: grid;
    grid-template-columns: 330px minmax(0, 1fr);
    gap: 24px;
    align-items: start;
}

.panel {
    padding: 22px;
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 16px;
}

.panel h2 { margin: 0 0 5px; font-size: 19px; }

.muted {
    color: var(--muted);
    font-size: 12px;
}

label {
    display: block;
    margin: 16px 0 7px;
    color: #c9c9d0;
    font-size: 12px;
    font-weight: 650;
}

input, select, textarea {
    width: 100%;
    padding: 12px;
    color: var(--text);
    background: #0c0c0f;
    border: 1px solid #303038;
    border-radius: 9px;
    outline: none;
}

input:focus, select:focus, textarea:focus {
    border-color: var(--orange);
    box-shadow: 0 0 0 3px #ff7b2218;
}

textarea { min-height: 85px; resize: vertical; }
option { background: #17171c; }

.full { width: 100%; margin-top: 19px; }

.toolbar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
    margin-bottom: 18px;
}

.toolbar h2 { margin: 0; font-size: 23px; }

.search {
    display: flex;
    gap: 9px;
    margin-bottom: 13px;
}

.search input { flex: 1; min-width: 0; }

.search button {
    padding: 0 17px;
    background: var(--orange);
    border: 0;
    border-radius: 9px;
    color: #17100a;
    font-weight: 800;
}

.filters {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 9px;
    margin-bottom: 18px;
}

.filters select { min-width: 0; }

.results-note {
    display: flex;
    justify-content: space-between;
    margin-bottom: 13px;
    color: var(--muted);
    font-size: 12px;
}

.item-list {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 14px;
}

.item-card {
    min-width: 0;
    padding: 17px;
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 14px;
    transition: .2s;
    animation: appear .25s ease both;
}

.item-card:hover {
    border-color: #704021;
    transform: translateY(-3px);
}

@keyframes appear {
    from { opacity: 0; transform: translateY(6px); }
    to { opacity: 1; transform: translateY(0); }
}

.card-top {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 7px;
    margin-bottom: 14px;
}

.badge {
    padding: 5px 9px;
    border-radius: 6px;
    font-size: 10px;
    font-weight: 850;
    letter-spacing: .5px;
}

.badge.lost { color: var(--red); background: #391b20; }
.badge.found { color: var(--green); background: #123126; }

.category {
    color: var(--muted);
    font-size: 10px;
    text-align: right;
}

.item-card h3 {
    margin: 0 0 8px;
    font-size: 17px;
    overflow-wrap: anywhere;
}

.description {
    min-height: 40px;
    color: #a5a5b0;
    font-size: 12px;
    line-height: 1.7;
    overflow-wrap: anywhere;
}

.details {
    display: grid;
    gap: 8px;
    margin-top: 15px;
    padding-top: 13px;
    border-top: 1px solid var(--border);
    color: #c4c4cc;
    font-size: 11px;
    overflow-wrap: anywhere;
}

.match {
    margin-top: 13px;
    padding: 11px;
    background: #2b1b10;
    border: 1px solid #53331d;
    border-radius: 10px;
}

.match-head {
    display: flex;
    justify-content: space-between;
    gap: 8px;
    color: var(--orange2);
    font-size: 10px;
    font-weight: 850;
}

.progress {
    height: 5px;
    margin: 9px 0;
    overflow: hidden;
    border-radius: 5px;
    background: #48301f;
}

.progress div {
    height: 100%;
    background: var(--orange);
    border-radius: inherit;
    transition: width .4s;
}

.match-name {
    color: #f0d0b6;
    font-size: 12px;
    overflow-wrap: anywhere;
}

.match-meta {
    margin-top: 5px;
    color: #b8a18e;
    font-size: 11px;
    overflow-wrap: anywhere;
}

.card-actions {
    display: flex;
    gap: 7px;
    margin-top: 13px;
}

.card-actions button {
    flex: 1;
    padding: 8px;
    border: 1px solid var(--border);
    border-radius: 7px;
    background: #1c1c21;
    color: #dedee5;
    font-size: 11px;
}

.card-actions button:hover {
    border-color: var(--orange);
    color: var(--orange);
}

.empty {
    grid-column: 1 / -1;
    padding: 42px 20px;
    border: 1px dashed #393940;
    border-radius: 14px;
    color: var(--muted);
    text-align: center;
    line-height: 2;
}

.empty strong { color: var(--text); }

.toast {
    position: fixed;
    right: 22px;
    bottom: 22px;
    z-index: 10;
    max-width: calc(100% - 44px);
    padding: 14px 18px;
    border: 1px solid #3d684f;
    border-radius: 10px;
    background: #14271c;
    color: #a3f4c4;
    box-shadow: 0 12px 35px #0006;
    opacity: 0;
    transform: translateY(10px);
    pointer-events: none;
    transition: .25s;
}

.toast.show {
    opacity: 1;
    transform: translateY(0);
}

.modal {
    position: fixed;
    inset: 0;
    z-index: 20;
    display: none;
    place-items: center;
    padding: 20px;
    background: #000b;
}

.modal.show { display: grid; }

.modal-box {
    width: min(500px, 100%);
    max-height: 85vh;
    overflow: auto;
    padding: 24px;
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 16px;
}

.modal-head {
    display: flex;
    justify-content: space-between;
    gap: 12px;
    align-items: center;
}

.modal-head h2 { margin: 0; font-size: 21px; }

.close-btn {
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 7px 11px;
    background: var(--panel2);
    color: var(--text);
}

#modal-content {
    color: #c7c7cf;
    line-height: 1.9;
    overflow-wrap: anywhere;
}

footer {
    padding: 25px;
    border-top: 1px solid var(--border);
    color: #777780;
    text-align: center;
    font-size: 12px;
}

@media (max-width: 950px) {
    .workspace { grid-template-columns: 1fr; }
}

@media (max-width: 650px) {
    nav { padding: 0 4%; }
    .nav-right { font-size: 9px; }
    .container { width: 92%; margin-top: 20px; }
    .hero { padding: 25px; }
    .stats { grid-template-columns: repeat(2, 1fr); gap: 9px; }
    .stat { padding: 14px; }
    .stat-number { font-size: 25px; }
    .item-list { grid-template-columns: 1fr; }
    .toolbar h2 { font-size: 20px; }
}

@media (prefers-reduced-motion: reduce) {
    *, *::before, *::after {
        animation-duration: .01ms !important;
        transition-duration: .01ms !important;
    }
}
</style>
</head>

<body>
<nav>
    <div class="logo">find<span>ora.</span></div>
    <div class="nav-right"><span class="status-dot"></span> SMART MATCHING ACTIVE</div>
</nav>

<main class="container">
    <section class="hero">
        <div class="eyebrow">A smarter way to reconnect</div>
        <h1>Lost something?<br>Let's bring it <span>home.</span></h1>
        <p>
            Report lost belongings, discover potential matches, and help
            people reconnect with the things that matter.
        </p>
        <div class="hero-bottom">
            <button class="primary" onclick="focusForm()">＋ Report an Item</button>
            <button class="secondary" onclick="resetFilters()">Explore Reports ↗</button>
        </div>
    </section>

    <section class="stats">
        <div class="stat">
            <div class="stat-top"><span class="stat-label">TOTAL REPORTS</span><span class="stat-icon">▦</span></div>
            <div class="stat-number" id="stat-total">0</div>
        </div>
        <div class="stat">
            <div class="stat-top"><span class="stat-label">LOST ITEMS</span><span class="stat-icon">⌕</span></div>
            <div class="stat-number" id="stat-lost">0</div>
        </div>
        <div class="stat">
            <div class="stat-top"><span class="stat-label">FOUND ITEMS</span><span class="stat-icon">✓</span></div>
            <div class="stat-number" id="stat-found">0</div>
        </div>
        <div class="stat">
            <div class="stat-top"><span class="stat-label">POTENTIAL MATCHES</span><span class="stat-icon">✦</span></div>
            <div class="stat-number" id="stat-matched">0</div>
        </div>
    </section>

    <section class="workspace">
        <aside class="panel" id="report-panel">
            <h2>＋ Report an Item</h2>
            <p class="muted">Provide details to help find a match.</p>

            <form id="report-form">
                <label for="item_type">Report Type</label>
                <select id="item_type" name="item_type" required>
                    <option value="Lost">I lost something</option>
                    <option value="Found">I found something</option>
                </select>

                <label for="title">Item Name</label>
                <input id="title" name="title" maxlength="100"
                       placeholder="e.g. Black leather wallet" required>

                <label for="category">Category</label>
                <select id="category" name="category" required>
                    __CATEGORY_OPTIONS__
                </select>

                <label for="location">Location</label>
                <input id="location" name="location" maxlength="150"
                       placeholder="e.g. Dhanmondi, Dhaka" required>

                <label for="description">Description</label>
                <textarea id="description" name="description" maxlength="1000"
                          placeholder="Color, brand, identifying details..." required></textarea>

                <label for="contact">Contact Information</label>
                <input id="contact" name="contact" maxlength="150"
                       placeholder="Email or phone number" required>

                <button class="primary full" id="submit-btn" type="submit">
                    Submit Report →
                </button>
            </form>
        </aside>

        <section>
            <div class="toolbar">
                <div>
                    <h2>Explore Reports</h2>
                    <span class="muted">Find what you're looking for.</span>
                </div>
                <span class="count" id="result-count">0 items</span>
            </div>

            <div class="search">
                <input id="search" placeholder="⌕  Search items, locations...">
                <button onclick="clearSearch()" type="button">Clear</button>
            </div>

            <div class="filters">
                <select id="type-filter" aria-label="Filter by report type">
                    <option value="All">All report types</option>
                    <option value="Lost">Lost only</option>
                    <option value="Found">Found only</option>
                </select>
                <select id="category-filter" aria-label="Filter by category">
                    <option value="All">All categories</option>
                    __CATEGORY_OPTIONS__
                </select>
                <select id="sort-filter" aria-label="Sort reports">
                    <option value="newest">Newest first</option>
                    <option value="oldest">Oldest first</option>
                    <option value="az">Name A–Z</option>
                    <option value="match">Best match first</option>
                </select>
                <select id="match-filter" aria-label="Filter potential matches">
                    <option value="All">All match statuses</option>
                    <option value="Matched">Has a potential match</option>
                    <option value="Unmatched">No potential match</option>
                </select>
            </div>

            <div class="results-note">
                <span id="live-note">Live results</span>
                <span>Powered by Findora Engine</span>
            </div>

            <div class="item-list" id="item-list">
                <div class="empty">Loading reports...</div>
            </div>
        </section>
    </section>
</main>

<footer>Findora Engine · Built with Python · Helping lost belongings find their way home.</footer>

<div class="toast" id="toast" role="status"></div>

<div class="modal" id="modal" onclick="closeModalOutside(event)">
    <div class="modal-box">
        <div class="modal-head">
            <h2 id="modal-title">Item Details</h2>
            <button class="close-btn" onclick="closeModal()">✕</button>
        </div>
        <div id="modal-content"></div>
    </div>
</div>

<script>
let items = [];
let toastTimer;

const $ = id => document.getElementById(id);

function notify(message) {
    const toast = $("toast");
    toast.textContent = message;
    toast.classList.add("show");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toast.classList.remove("show"), 2800);
}

function safe(value) {
    return String(value ?? "").replace(/[&<>"']/g, char => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;"
    })[char]);
}

async function request(url, options = {}) {
    const response = await fetch(url, options);
    const data = await response.json();

    if (!response.ok || !data.ok) {
        throw new Error(data.error || "Something went wrong.");
    }

    return data;
}

function updateStats(stats) {
    for (const key of ["total", "lost", "found", "matched"]) {
        $("stat-" + key).textContent = stats[key];
    }
}

function matchesFor(item) {
    const candidates = items
        .filter(other => other.id !== item.id)
        .filter(other => other.item_type !== item.item_type)
        .map(other => ({ item: other, score: score(item, other) }))
        .filter(result => result.score >= 25)
        .sort((a, b) => b.score - a.score);

    return candidates;
}

function similarity(a, b) {
    a = a.toLowerCase().trim();
    b = b.toLowerCase().trim();

    if (!a || !b) return 0;
    if (a === b) return 1;

    const matrix = Array.from({length: a.length + 1}, () =>
        Array(b.length + 1).fill(0)
    );

    for (let i = 0; i <= a.length; i++) matrix[i][0] = i;
    for (let j = 0; j <= b.length; j++) matrix[0][j] = j;

    for (let i = 1; i <= a.length; i++) {
        for (let j = 1; j <= b.length; j++) {
            matrix[i][j] = Math.min(
                matrix[i - 1][j] + 1,
                matrix[i][j - 1] + 1,
                matrix[i - 1][j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1)
            );
        }
    }

    return 1 - matrix[a.length][b.length] / Math.max(a.length, b.length);
}

function score(a, b) {
    const category = a.category.toLowerCase() === b.category.toLowerCase()
        ? 35 : 0;
    const location = similarity(a.location, b.location) * 25;
    const title = similarity(a.title, b.title) * 25;
    const description = similarity(a.description, b.description) * 15;

    return Math.round(Math.min(100, category + location + title + description));
}

function renderCard(item) {
    const matches = matchesFor(item);
    const best = matches[0];
    const type = item.item_type.toLowerCase();

    let matchHTML = "";

    if (best) {
        matchHTML = `
        <div class="match">
            <div class="match-head">
                <span>✦ POTENTIAL MATCH</span>
                <span>${best.score}%</span>
            </div>
            <div class="progress"><div style="width:${best.score}%"></div></div>
            <div class="match-name">${safe(best.item.title)} · ${safe(best.item.item_type)}</div>
            <div class="match-meta">📍 ${safe(best.item.location)}</div>
            <div class="match-meta">Contact: ${safe(best.item.contact)}</div>
            <div class="card-actions">
                <button onclick="viewItem(${best.item.id})">View match</button>
            </div>
        </div>`;
    }

    return `
    <article class="item-card">
        <div class="card-top">
            <span class="badge ${type}">${safe(item.item_type)}</span>
            <span class="category">${safe(item.category)}</span>
        </div>
        <h3>${safe(item.title)}</h3>
        <div class="description">${safe(item.description)}</div>
        <div class="details">
            <div>📍 &nbsp;${safe(item.location)}</div>
            <div>✉ &nbsp;${safe(item.contact)}</div>
            <div>◷ &nbsp;${safe(item.created_at)}</div>
        </div>
        ${matchHTML}
        <div class="card-actions">
            <button onclick="viewItem(${item.id})">View details</button>
            <button onclick="removeItem(${item.id})">Delete</button>
        </div>
    </article>`;
}

function renderItems() {
    const query = $("search").value.toLowerCase().trim();
    const type = $("type-filter").value;
    const category = $("category-filter").value;
    const matchFilter = $("match-filter").value;
    const sort = $("sort-filter").value;

    let filtered = items.filter(item => {
        const searchable = [
            item.title, item.category, item.description,
            item.location, item.contact
        ].join(" ").toLowerCase();

        if (query && !searchable.includes(query)) return false;
        if (type !== "All" && item.item_type !== type) return false;
        if (category !== "All" && item.category !== category) return false;

        const hasMatch = matchesFor(item).length > 0;
        if (matchFilter === "Matched" && !hasMatch) return false;
        if (matchFilter === "Unmatched" && hasMatch) return false;

        return true;
    });

    if (sort === "newest") filtered.sort((a, b) => b.id - a.id);
    if (sort === "oldest") filtered.sort((a, b) => a.id - b.id);
    if (sort === "az") filtered.sort((a, b) => a.title.localeCompare(b.title));
    if (sort === "match") {
        filtered.sort((a, b) =>
            (matchesFor(b)[0]?.score || 0) - (matchesFor(a)[0]?.score || 0)
        );
    }

    $("result-count").textContent = `${filtered.length} item${filtered.length !== 1 ? "s" : ""}`;
    $("live-note").textContent = query ? `Results for "${query}"` : "Live results";

    $("item-list").innerHTML = filtered.length
        ? filtered.map(renderCard).join("")
        : `<div class="empty">
            <div style="font-size:32px">⌕</div>
            <strong>No reports found</strong><br>
            Try changing your filters or submit a new report.
          </div>`;
}

async function loadItems() {
    try {
        const data = await request("/api/items");
        items = data.items;
        updateStats(data.stats);
        renderItems();
    } catch (error) {
        $("item-list").innerHTML =
            `<div class="empty">${safe(error.message)}<br>Try refreshing the page.</div>`;
    }
}

$("report-form").addEventListener("submit", async event => {
    event.preventDefault();

    const button = $("submit-btn");
    button.disabled = true;
    button.textContent = "Submitting...";

    const data = Object.fromEntries(new FormData(event.target).entries());

    try {
        await request("/api/items", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify(data)
        });

        event.target.reset();
        await loadItems();
        notify("Your report was added successfully.");
    } catch (error) {
        notify(error.message);
    } finally {
        button.disabled = false;
        button.textContent = "Submit Report →";
    }
});

async function removeItem(id) {
    const item = items.find(item => item.id === id);
    if (!item) return;

    if (!confirm(`Delete "${item.title}" from the reports?`)) return;

    try {
        await request(`/api/items/${id}`, {method: "DELETE"});
        await loadItems();
        notify("Report deleted.");
    } catch (error) {
        notify(error.message);
    }
}

function viewItem(id) {
    const item = items.find(item => item.id === id);
    if (!item) return;

    $("modal-title").textContent = item.title;
    $("modal-content").innerHTML = `
        <p><strong>Type:</strong> ${safe(item.item_type)}</p>
        <p><strong>Category:</strong> ${safe(item.category)}</p>
        <p><strong>Description:</strong><br>${safe(item.description)}</p>
        <p><strong>Location:</strong><br>${safe(item.location)}</p>
        <p><strong>Contact:</strong><br>${safe(item.contact)}</p>
        <p><strong>Reported:</strong><br>${safe(item.created_at)}</p>
    `;

    $("modal").classList.add("show");
}

function closeModal() {
    $("modal").classList.remove("show");
}

function closeModalOutside(event) {
    if (event.target === $("modal")) closeModal();
}

function clearSearch() {
    $("search").value = "";
    renderItems();
    $("search").focus();
}

function resetFilters() {
    $("search").value = "";
    $("type-filter").value = "All";
    $("category-filter").value = "All";
    $("sort-filter").value = "newest";
    $("match-filter").value = "All";
    renderItems();
}

function focusForm() {
    $("report-panel").scrollIntoView({behavior: "smooth", block: "start"});
    $("title").focus({preventScroll: true});
}

["search", "type-filter", "category-filter", "sort-filter", "match-filter"]
    .forEach(id => {
        $(id).addEventListener(id === "search" ? "input" : "change", renderItems);
    });

loadItems();
</script>
</body>
</html>
"""

# ==================== API SERVER ====================

class FindoraHandler(BaseHTTPRequestHandler):

    def send_json(self, data, status=200):
        content = json.dumps(data).encode("utf-8")

        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(content)

    def send_html(self, content):
        data = content.encode("utf-8")

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def read_json(self):
        length = int(self.headers.get("Content-Length", "0"))

        if length <= 0 or length > 20000:
            raise ValueError("Invalid request size.")

        return json.loads(self.rfile.read(length).decode("utf-8"))

    def do_GET(self):
        path = urlparse(self.path).path

        if path == "/":
            options = "".join(
                f'<option value="{escape(category, quote=True)}">'
                f'{escape(category)}</option>'
                for category in CATEGORIES
            )
            self.send_html(PAGE.replace("__CATEGORY_OPTIONS__", options))
            return

        if path == "/api/items":
            items = get_items()
            matched_ids = {
                item["id"]
                for item in items
                if get_matches(item, items)
            }

            stats = {
                "total": len(items),
                "lost": sum(i["item_type"] == "Lost" for i in items),
                "found": sum(i["item_type"] == "Found" for i in items),
                "matched": len(matched_ids)
            }

            self.send_json({"ok": True, "items": items, "stats": stats})
            return

        self.send_json({"ok": False, "error": "Endpoint not found."}, 404)

    def do_POST(self):
        if urlparse(self.path).path != "/api/items":
            self.send_json({"ok": False, "error": "Endpoint not found."}, 404)
            return

        try:
            data = self.read_json()

            fields = {
                "item_type": 10,
                "title": 100,
                "category": 60,
                "description": 1000,
                "location": 150,
                "contact": 150
            }

            clean = {
                key: str(data.get(key, "")).strip()[:limit]
                for key, limit in fields.items()
            }

            if clean["item_type"] not in ("Lost", "Found"):
                raise ValueError("Choose Lost or Found.")

            if clean["category"] not in CATEGORIES:
                raise ValueError("Choose a valid category.")

            if not all(clean.values()):
                raise ValueError("Please complete all fields.")

            add_item(clean)
            self.send_json({"ok": True, "message": "Report added."}, 201)

        except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as error:
            self.send_json({"ok": False, "error": str(error)}, 400)

    def do_DELETE(self):
        path = urlparse(self.path).path
        prefix = "/api/items/"

        if not path.startswith(prefix):
            self.send_json({"ok": False, "error": "Endpoint not found."}, 404)
            return

        try:
            item_id = int(path[len(prefix):])

            if item_id <= 0:
                raise ValueError

            with database() as conn:
                exists = conn.execute(
                    "SELECT id FROM items WHERE id = ?", (item_id,)
                ).fetchone()

            if not exists:
                self.send_json({"ok": False, "error": "Report not found."}, 404)
                return

            delete_item(item_id)
            self.send_json({"ok": True, "message": "Report deleted."})

        except ValueError:
            self.send_json({"ok": False, "error": "Invalid item ID."}, 400)

    def log_message(self, format, *args):
        print(f"[Findora] {args[0]}")


# ==================== RUN APPLICATION ====================

if __name__ == "__main__":

    database().close()

    server = None

    try:
        server = ThreadingHTTPServer((HOST, PORT), FindoraHandler)

        print("=" * 48)
        print("  FINDORA ENGINE")
        print(f"  Open: http://{HOST}:{PORT}")
        print("  Press Ctrl+C to stop")
        print("=" * 48)

        server.serve_forever()

    except KeyboardInterrupt:
        print("\nFindora stopped.")

    except OSError as error:
        print(f"Server could not start: {error}")

    finally:
        if server:
            server.server_close()
