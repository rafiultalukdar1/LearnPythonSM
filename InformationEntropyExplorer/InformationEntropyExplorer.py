
import json
import math
import csv
import io
import zlib
import re
import random
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse


HOST = "127.0.0.1"
PORT = 8006
MAX_INPUT = 100000


# =========================================================
# 1. ANALYSIS ENGINE
# =========================================================

def entropy_of(values):
    if not values:
        return 0.0

    counts = Counter(values)
    total = len(values)

    return -sum(
        (count / total) * math.log2(count / total)
        for count in counts.values()
    )


def get_ngrams(text, size):
    return [
        text[i:i + size]
        for i in range(len(text) - size + 1)
    ]


def get_patterns(text):
    results = []

    for size in (2, 3, 4):
        grams = get_ngrams(text, size)
        counts = Counter(grams)

        for pattern, count in counts.most_common(5):
            if count > 1:
                results.append({
                    "pattern": pattern,
                    "count": count,
                    "size": size
                })

    return sorted(
        results,
        key=lambda x: (x["count"], x["size"]),
        reverse=True
    )[:12]


def get_distribution(text):
    counts = Counter(text)
    total = len(text)
    result = []

    for char, count in counts.most_common(20):
        if char == " ":
            label = "SPACE"
        elif char == "\n":
            label = "NEWLINE"
        elif char == "\t":
            label = "TAB"
        elif char == "\r":
            label = "CR"
        else:
            label = char

        result.append({
            "character": label,
            "count": count,
            "percentage": round(count / total * 100, 2)
        })

    return result


def get_word_analysis(text):
    words = re.findall(r"\b[\w'-]+\b", text.lower())
    counts = Counter(words)

    return {
        "total": len(words),
        "unique": len(counts),
        "repeated": [
            {"word": word, "count": count}
            for word, count in counts.most_common(10)
            if count > 1
        ]
    }


def get_compression(text):
    original = text.encode("utf-8")

    if not original:
        return {
            "original": 0,
            "compressed": 0,
            "saved": 0,
            "ratio": 0
        }

    compressed = zlib.compress(original, level=9)

    original_size = len(original)
    compressed_size = len(compressed)

    return {
        "original": original_size,
        "compressed": compressed_size,
        "saved": round(
            (original_size - compressed_size) / original_size * 100,
            2
        ),
        "ratio": round(compressed_size / original_size * 100, 2)
    }


def analyze(text):
    if not isinstance(text, str):
        raise ValueError("Input must be text.")

    if len(text) > MAX_INPUT:
        raise ValueError(f"Maximum input length is {MAX_INPUT:,} characters.")

    if not text:
        raise ValueError("Please enter some text.")

    total = len(text)
    counts = Counter(text)

    entropy = entropy_of(text)
    unique = len(counts)

    maximum = math.log2(unique) if unique > 1 else 0
    normalized = entropy / maximum * 100 if maximum else 0

    dominant = max(counts.values()) / total * 100

    # Heuristic indicator, not a cryptographic randomness test.
    randomness = min(
        100,
        max(0, normalized * 0.75 + (100 - dominant) * 0.25)
    )

    bigrams = get_ngrams(text, 2)
    trigrams = get_ngrams(text, 3)

    word_data = get_word_analysis(text)
    compression = get_compression(text)

    return {
        "overview": {
            "characters": total,
            "unique": unique,
            "words": word_data["total"],
            "uniqueWords": word_data["unique"],
            "lines": len(text.splitlines()),
            "entropy": round(entropy, 4),
            "maxEntropy": round(maximum, 4),
            "normalized": round(normalized, 2),
            "randomness": round(randomness, 2),
            "predictability": round(100 - randomness, 2),
            "informationBits": round(entropy * total, 2),
            "dominant": round(dominant, 2)
        },
        "ngrams": {
            "bigram": round(entropy_of(bigrams), 4),
            "trigram": round(entropy_of(trigrams), 4),
            "bigramCount": len(set(bigrams)),
            "trigramCount": len(set(trigrams))
        },
        "compression": compression,
        "distribution": get_distribution(text),
        "patterns": get_patterns(text),
        "words": word_data
    }


# =========================================================
# 2. DASHBOARD
# =========================================================

HTML = r"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Information Entropy Explorer</title>

<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Inter:wght@400;500;600;700;800&display=swap');

:root {
    --bg: #0B1020;
    --surface: #111827;
    --surface-2: #151F30;
    --surface-3: #1B2940;
    --border: #26354B;
    --text: #E8EDF5;
    --muted: #8492A9;
    --teal: #2DD4BF;
    --purple: #A78BFA;
    --blue: #38BDF8;
    --green: #4ADE80;
    --orange: #FBBF24;
    --red: #FB7185;
    --radius: 15px;
}

* {
    box-sizing: border-box;
    margin: 0;
}

body {
    background: var(--bg);
    color: var(--text);
    font-family: Inter, sans-serif;
    min-height: 100vh;
}

button, textarea, select {
    font: inherit;
}

button {
    cursor: pointer;
}

.app {
    min-height: 100vh;
}

/* SIDEBAR */

.sidebar {
    width: 245px;
    position: fixed;
    inset: 0 auto 0 0;
    background: #0D1525;
    border-right: 1px solid var(--border);
    padding: 25px 17px;
    display: flex;
    flex-direction: column;
    z-index: 10;
}

.brand {
    display: flex;
    align-items: center;
    gap: 11px;
    padding: 5px 8px 35px;
}

.brand-icon {
    width: 38px;
    height: 38px;
    display: grid;
    place-items: center;
    border-radius: 11px;
    background: #153A3B;
    color: var(--teal);
    font-size: 21px;
    font-weight: 800;
}

.brand-name {
    font-size: 15px;
    font-weight: 800;
    letter-spacing: -.5px;
}

.brand-name span {
    color: var(--teal);
}

.nav-label {
    font-size: 9px;
    letter-spacing: 1.7px;
    color: #64738A;
    padding: 0 11px;
    margin: 20px 0 10px;
}

.nav-item {
    width: 100%;
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px;
    margin-bottom: 5px;
    border-radius: 9px;
    border: 1px solid transparent;
    background: transparent;
    color: var(--muted);
    font-size: 12px;
    text-align: left;
    transition: .2s;
}

.nav-item:hover {
    background: var(--surface-2);
    color: var(--text);
}

.nav-item.active {
    background: #15333A;
    color: var(--teal);
    border-color: #20504E;
}

.nav-icon {
    width: 19px;
    text-align: center;
    font-size: 16px;
}

.sidebar-footer {
    margin-top: auto;
    border-top: 1px solid var(--border);
    padding: 18px 8px 0;
    color: var(--muted);
    font-size: 10px;
    line-height: 2;
}

.online-dot {
    color: var(--green);
}

/* MAIN */

.main {
    margin-left: 245px;
    padding: 28px 36px 45px;
    max-width: 1800px;
}

.topbar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 15px;
    margin-bottom: 28px;
}

.eyebrow {
    font-family: 'DM Mono', monospace;
    color: var(--teal);
    font-size: 10px;
    letter-spacing: 2px;
    margin-bottom: 9px;
}

h1 {
    font-size: clamp(24px, 3vw, 34px);
    letter-spacing: -1.3px;
}

.subtitle {
    color: var(--muted);
    font-size: 12px;
    margin-top: 9px;
    line-height: 1.7;
}

.top-actions {
    display: flex;
    gap: 9px;
    align-items: center;
}

.engine-status {
    border: 1px solid var(--border);
    background: var(--surface);
    border-radius: 30px;
    padding: 10px 14px;
    color: var(--green);
    font-size: 10px;
    white-space: nowrap;
}

/* BUTTONS */

.btn {
    border: 1px solid var(--border);
    background: var(--surface-2);
    color: var(--text);
    border-radius: 8px;
    padding: 10px 14px;
    font-size: 11px;
    font-weight: 700;
    transition: .2s;
}

.btn:hover {
    border-color: var(--teal);
    transform: translateY(-1px);
}

.btn-primary {
    background: var(--teal);
    color: #06231F;
    border-color: var(--teal);
}

.btn-primary:hover {
    background: #5EEAD4;
}

.btn:disabled {
    opacity: .5;
    cursor: not-allowed;
    transform: none;
}

/* PAGE TABS */

.page {
    display: none;
    animation: appear .25s ease;
}

.page.active {
    display: block;
}

@keyframes appear {
    from { opacity: 0; transform: translateY(5px); }
    to { opacity: 1; transform: translateY(0); }
}

.page-heading {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 15px;
    margin-bottom: 18px;
}

.page-heading h2 {
    font-size: 16px;
}

.page-heading p {
    color: var(--muted);
    font-size: 11px;
    margin-top: 6px;
}

/* CARDS */

.card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 21px;
    min-width: 0;
}

.card-title {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 10px;
    font-size: 13px;
    font-weight: 700;
    margin-bottom: 18px;
}

.card-subtitle {
    color: var(--muted);
    font-size: 10px;
    font-weight: 400;
}

.metrics {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 14px;
    margin-bottom: 18px;
}

.metric {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 18px;
    position: relative;
    overflow: hidden;
}

.metric::after {
    content: "";
    position: absolute;
    width: 65px;
    height: 65px;
    border-radius: 50%;
    right: -30px;
    bottom: -35px;
    background: var(--metric-color, var(--teal));
    opacity: .09;
    filter: blur(5px);
}

.metric-label {
    font-size: 10px;
    color: var(--muted);
    letter-spacing: .5px;
}

.metric-value {
    font-family: 'DM Mono', monospace;
    font-size: 27px;
    margin: 15px 0 7px;
    color: var(--metric-color, var(--teal));
}

.metric-note {
    font-size: 10px;
    color: var(--muted);
}

/* INPUT */

.workspace {
    display: grid;
    grid-template-columns: 1.15fr .85fr;
    gap: 16px;
    margin-bottom: 17px;
}

textarea {
    display: block;
    width: 100%;
    min-height: 215px;
    resize: vertical;
    background: #0B1424;
    border: 1px solid var(--border);
    color: var(--text);
    border-radius: 10px;
    padding: 16px;
    outline: none;
    font: 12px/1.8 'DM Mono', monospace;
    transition: .2s;
}

textarea:focus {
    border-color: var(--teal);
    box-shadow: 0 0 0 3px #2DD4BF12;
}

textarea::placeholder {
    color: #65748B;
}

.input-toolbar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
    margin-top: 13px;
}

.toolbar-left, .toolbar-right {
    display: flex;
    align-items: center;
    gap: 7px;
    flex-wrap: wrap;
}

.select {
    background: var(--surface-2);
    color: var(--text);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 9px;
    font-size: 10px;
    outline: none;
}

.char-count {
    color: var(--muted);
    font-size: 10px;
}

/* PROFILE */

.profile-item {
    padding: 15px;
    background: #0D1728;
    border: 1px solid var(--border);
    border-radius: 10px;
    margin-bottom: 11px;
}

.profile-head {
    display: flex;
    justify-content: space-between;
    font-size: 11px;
    margin-bottom: 11px;
}

.profile-head strong {
    color: var(--teal);
    font-family: 'DM Mono', monospace;
}

.progress {
    height: 6px;
    border-radius: 10px;
    background: #26354B;
    overflow: hidden;
}

.progress-fill {
    width: 0%;
    height: 100%;
    border-radius: inherit;
    background: linear-gradient(90deg, var(--teal), var(--purple));
    transition: width .5s ease;
}

.profile-desc {
    color: var(--muted);
    font-size: 10px;
    line-height: 1.6;
    margin-top: 9px;
}

.insight {
    padding: 13px;
    background: #142D2D;
    border: 1px solid #24534D;
    border-radius: 9px;
    color: #A7F3D0;
    font-size: 11px;
    line-height: 1.7;
}

/* CHARTS */

.two-col {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
    margin-bottom: 17px;
}

canvas {
    width: 100%;
    height: 245px;
    display: block;
}

.chart-legend {
    display: flex;
    gap: 14px;
    flex-wrap: wrap;
    color: var(--muted);
    font-size: 10px;
    margin-top: 10px;
}

.legend-dot {
    display: inline-block;
    width: 7px;
    height: 7px;
    border-radius: 50%;
    margin-right: 5px;
}

/* TABLE */

.table-wrap {
    overflow-x: auto;
}

table {
    width: 100%;
    border-collapse: collapse;
    font-size: 11px;
    white-space: nowrap;
}

th, td {
    text-align: left;
    padding: 13px 10px;
    border-bottom: 1px solid var(--border);
}

th {
    color: var(--muted);
    font-size: 9px;
    letter-spacing: .7px;
    font-weight: 600;
}

td {
    color: #D8E1EF;
}

td.value {
    color: var(--teal);
    font-family: 'DM Mono', monospace;
}

.empty {
    color: var(--muted);
    font-size: 11px;
    padding: 17px 0;
}

/* PATTERNS */

.pattern-list {
    display: grid;
    gap: 9px;
}

.pattern-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    padding: 12px;
    border-radius: 9px;
    background: #182438;
    border: 1px solid var(--border);
}

.pattern-code {
    color: var(--purple);
    font: 12px 'DM Mono', monospace;
    overflow-wrap: anywhere;
}

.pattern-meta {
    color: var(--muted);
    font-size: 10px;
    white-space: nowrap;
}

/* COMPARISON */

.compare-inputs {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 14px;
    margin-bottom: 15px;
}

.compare-result {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 14px;
    margin-top: 16px;
}

.compare-box {
    background: #0D1728;
    border: 1px solid var(--border);
    border-radius: 11px;
    padding: 18px;
}

.compare-box h3 {
    font-size: 12px;
    margin-bottom: 17px;
}

.compare-number {
    font: 26px 'DM Mono', monospace;
    color: var(--teal);
    margin-bottom: 8px;
}

.compare-label {
    font-size: 10px;
    color: var(--muted);
}

.winner {
    color: var(--green);
    font-size: 10px;
    margin-top: 14px;
}

/* COMPRESSION */

.compression-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 12px;
    margin-bottom: 17px;
}

.compression-item {
    background: #0D1728;
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 17px;
}

.compression-item small {
    color: var(--muted);
    font-size: 9px;
    letter-spacing: .5px;
}

.compression-item strong {
    display: block;
    font: 22px 'DM Mono', monospace;
    margin-top: 11px;
    color: var(--teal);
}

/* INFO */

.info-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 12px;
}

.info-card {
    padding: 15px;
    background: #0D1728;
    border: 1px solid var(--border);
    border-radius: 10px;
}

.info-card small {
    color: var(--muted);
    font-size: 9px;
}

.info-card strong {
    display: block;
    margin-top: 9px;
    font: 20px 'DM Mono', monospace;
}

/* TOAST / LOADING */

.toast {
    position: fixed;
    right: 25px;
    bottom: 25px;
    z-index: 50;
    background: #1B2B40;
    border: 1px solid var(--border);
    padding: 13px 17px;
    border-radius: 9px;
    font-size: 11px;
    opacity: 0;
    transform: translateY(10px);
    transition: .2s;
    pointer-events: none;
}

.toast.show {
    opacity: 1;
    transform: translateY(0);
}

.loading {
    opacity: .6;
    pointer-events: none;
}

/* RESPONSIVE */

@media(max-width: 1150px) {
    .sidebar { width: 210px; }
    .main { margin-left: 210px; padding: 25px 20px; }
    .metrics { grid-template-columns: repeat(2, 1fr); }
}

@media(max-width: 850px) {
    .workspace, .two-col { grid-template-columns: 1fr; }
    .topbar { align-items: flex-start; }
    .engine-status { display: none; }
}

@media(max-width: 600px) {
    .sidebar {
        position: static;
        width: 100%;
        height: auto;
        padding: 12px;
        border-right: 0;
        border-bottom: 1px solid var(--border);
    }

    .brand { padding: 4px 6px 12px; }
    .nav-label, .sidebar-footer { display: none; }

    .sidebar nav {
        display: flex;
        overflow-x: auto;
        gap: 5px;
    }

    .nav-item {
        width: auto;
        min-width: max-content;
        margin: 0;
        padding: 10px;
    }

    .main {
        margin: 0;
        padding: 22px 13px;
    }

    .topbar { flex-direction: column; }
    .metrics { gap: 9px; }
    .metric { padding: 14px; }
    .metric-value { font-size: 23px; }
    .compare-inputs, .compare-result { grid-template-columns: 1fr; }
    .compression-grid { grid-template-columns: 1fr; }
    .info-grid { grid-template-columns: 1fr 1fr; }
}
</style>
</head>

<body>

<div class="app">

<aside class="sidebar">

    <div class="brand">
        <div class="brand-icon">∿</div>
        <div class="brand-name">ENTROPY<span>.</span></div>
    </div>

    <div class="nav-label">ANALYTICS</div>

    <nav>
        <button class="nav-item active" data-page="overview">
            <span class="nav-icon">◈</span> Overview
        </button>
        <button class="nav-item" data-page="patterns">
            <span class="nav-icon">⌁</span> Pattern Explorer
        </button>
        <button class="nav-item" data-page="compression">
            <span class="nav-icon">▤</span> Compression Lab
        </button>
        <button class="nav-item" data-page="compare">
            <span class="nav-icon">⇄</span> Compare Lab
        </button>
        <button class="nav-item" data-page="density">
            <span class="nav-icon">◉</span> Information Density
        </button>
    </nav>

    <div class="sidebar-footer">
        INFORMATION THEORY LAB<br>
        VERSION 2.0.0<br>
        <span class="online-dot">● ENGINE ONLINE</span>
    </div>

</aside>


<main class="main">

<header class="topbar">
    <div>
        <div class="eyebrow">DATA SCIENCE / INFORMATION THEORY</div>
        <h1>Information Entropy Explorer</h1>
        <p class="subtitle">
            Measure uncertainty. Discover hidden patterns.
            Understand how information behaves.
        </p>
    </div>

    <div class="top-actions">
        <span class="engine-status">● SYSTEM READY</span>
        <button class="btn" onclick="exportJSON()">↓ Export JSON</button>
    </div>
</header>


<!-- =====================================================
     OVERVIEW PAGE
===================================================== -->

<section class="page active" id="page-overview">

    <div class="metrics">

        <div class="metric" style="--metric-color:var(--teal)">
            <div class="metric-label">SHANNON ENTROPY</div>
            <div class="metric-value" id="entropy">0.000</div>
            <div class="metric-note">Bits per character</div>
        </div>

        <div class="metric" style="--metric-color:var(--purple)">
            <div class="metric-label">RANDOMNESS ESTIMATE</div>
            <div class="metric-value" id="randomness">0%</div>
            <div class="metric-note">Heuristic indicator</div>
        </div>

        <div class="metric" style="--metric-color:var(--blue)">
            <div class="metric-label">UNIQUE SYMBOLS</div>
            <div class="metric-value" id="unique">0</div>
            <div class="metric-note">Distinct characters</div>
        </div>

        <div class="metric" style="--metric-color:var(--green)">
            <div class="metric-label">INFORMATION CONTENT</div>
            <div class="metric-value" id="bits">0</div>
            <div class="metric-note">Estimated total bits</div>
        </div>

    </div>


    <div class="workspace">

        <div class="card">
            <div class="card-title">
                <span>Input Data Explorer</span>
                <span class="card-subtitle">TEXT ANALYZER</span>
            </div>

            <textarea id="input" maxlength="100000"
placeholder="Paste or type your data here...">Information theory measures uncertainty in data. Repeated patterns make information more predictable. Random sequences usually contain more uncertainty than repeated sequences. Entropy helps us understand how information is distributed.</textarea>

            <div class="input-toolbar">
                <div class="toolbar-left">
                    <select class="select" id="preset" onchange="loadPreset()">
                        <option value="">Choose sample data</option>
                        <option value="english">Natural English</option>
                        <option value="repeated">Repeated pattern</option>
                        <option value="binary">Binary sequence</option>
                        <option value="random">Random-like data</option>
                        <option value="numbers">Numeric sequence</option>
                    </select>
                    <span class="char-count" id="charCount">0 characters</span>
                </div>

                <div class="toolbar-right">
                    <button class="btn" onclick="clearInput()">Clear</button>
                    <button class="btn btn-primary" id="analyzeBtn" onclick="analyze()">Analyze ↗</button>
                </div>
            </div>
        </div>


        <div class="card">
            <div class="card-title">
                <span>Information Profile</span>
                <span class="card-subtitle">LIVE METRICS</span>
            </div>

            <div class="profile-item">
                <div class="profile-head">
                    <span>Normalized Entropy</span>
                    <strong id="normalized">0%</strong>
                </div>
                <div class="progress">
                    <div class="progress-fill" id="entropyBar"></div>
                </div>
                <p class="profile-desc">
                    Entropy relative to the maximum possible entropy
                    of the observed character set.
                </p>
            </div>

            <div class="profile-item">
                <div class="profile-head">
                    <span>Predictability Estimate</span>
                    <strong id="predictability">0%</strong>
                </div>
                <div class="progress">
                    <div class="progress-fill" id="predictBar"></div>
                </div>
                <p class="profile-desc">
                    Inverse of the heuristic randomness estimate.
                </p>
            </div>

            <div class="insight" id="insight">
                Enter some data to discover its information profile.
            </div>

        </div>

    </div>


    <div class="two-col">

        <div class="card">
            <div class="card-title">
                <span>Character Distribution</span>
                <span class="card-subtitle">TOP 20 SYMBOLS</span>
            </div>
            <canvas id="distributionChart"></canvas>
            <div class="chart-legend">
                <span><i class="legend-dot" style="background:var(--teal)"></i>Frequency</span>
                <span><i class="legend-dot" style="background:var(--blue)"></i>Distribution</span>
            </div>
        </div>

        <div class="card">
            <div class="card-title">
                <span>Quick Statistics</span>
                <span class="card-subtitle">DATA SUMMARY</span>
            </div>

            <div class="info-grid">
                <div class="info-card">
                    <small>CHARACTERS</small>
                    <strong id="totalChars">0</strong>
                </div>
                <div class="info-card">
                    <small>WORDS</small>
                    <strong id="wordCount">0</strong>
                </div>
                <div class="info-card">
                    <small>LINES</small>
                    <strong id="lineCount">0</strong>
                </div>
                <div class="info-card">
                    <small>UNIQUE WORDS</small>
                    <strong id="uniqueWords">0</strong>
                </div>
                <div class="info-card">
                    <small>DOMINANT SYMBOL</small>
                    <strong id="dominant">0%</strong>
                </div>
                <div class="info-card">
                    <small>MAX ENTROPY</small>
                    <strong id="maxEntropy">0</strong>
                </div>
            </div>
        </div>

    </div>

</section>


<!-- =====================================================
     PATTERN EXPLORER
===================================================== -->

<section class="page" id="page-patterns">

    <div class="page-heading">
        <div>
            <h2>Pattern Explorer</h2>
            <p>Explore repeated sequences and frequent words.</p>
        </div>
        <button class="btn btn-primary" onclick="analyze()">Refresh Analysis ↗</button>
    </div>

    <div class="two-col">

        <div class="card">
            <div class="card-title">
                <span>Repeated Character Sequences</span>
                <span class="card-subtitle">N-GRAMS</span>
            </div>
            <div class="pattern-list" id="patterns">
                <div class="empty">Analyze some data first.</div>
            </div>
        </div>

        <div class="card">
            <div class="card-title">
                <span>Frequent Words</span>
                <span class="card-subtitle">WORD FREQUENCY</span>
            </div>
            <div class="pattern-list" id="frequentWords">
                <div class="empty">Analyze some data first.</div>
            </div>
        </div>

    </div>

    <div class="card">
        <div class="card-title">
            <span>N-gram Entropy</span>
            <span class="card-subtitle">SEQUENCE UNCERTAINTY</span>
        </div>

        <div class="info-grid">
            <div class="info-card">
                <small>BIGRAM ENTROPY</small>
                <strong id="bigram">0</strong>
            </div>
            <div class="info-card">
                <small>TRIGRAM ENTROPY</small>
                <strong id="trigram">0</strong>
            </div>
            <div class="info-card">
                <small>UNIQUE BIGRAMS</small>
                <strong id="bigramCount">0</strong>
            </div>
        </div>
    </div>

</section>


<!-- =====================================================
     COMPRESSION LAB
===================================================== -->

<section class="page" id="page-compression">

    <div class="page-heading">
        <div>
            <h2>Compression Lab</h2>
            <p>Compare original data with actual zlib compression.</p>
        </div>
        <button class="btn btn-primary" onclick="analyze()">Calculate ↗</button>
    </div>

    <div class="card">
        <div class="card-title">
            <span>Compression Report</span>
            <span class="card-subtitle">ZLIB LEVEL 9</span>
        </div>

        <div class="compression-grid">
            <div class="compression-item">
                <small>ORIGINAL SIZE</small>
                <strong id="originalSize">0 B</strong>
            </div>
            <div class="compression-item">
                <small>COMPRESSED SIZE</small>
                <strong id="compressedSize" style="color:var(--blue)">0 B</strong>
            </div>
            <div class="compression-item">
                <small>SIZE SAVED</small>
                <strong id="saved" style="color:var(--green)">0%</strong>
            </div>
        </div>

        <div class="profile-item">
            <div class="profile-head">
                <span>Compression Ratio</span>
                <strong id="ratio">0%</strong>
            </div>
            <div class="progress">
                <div class="progress-fill" id="compressionBar"></div>
            </div>
            <p class="profile-desc" id="compressionNote">
                Run an analysis to calculate the compression ratio.
            </p>
        </div>

        <div class="insight" id="compressionInsight">
            Compression results will appear here.
        </div>
    </div>

</section>


<!-- =====================================================
     COMPARE LAB
===================================================== -->

<section class="page" id="page-compare">

    <div class="page-heading">
        <div>
            <h2>Compare Lab</h2>
            <p>Analyze two datasets and compare their uncertainty.</p>
        </div>
    </div>

    <div class="card">

        <div class="compare-inputs">
            <div>
                <div class="card-title">Dataset A</div>
                <textarea id="compareA" style="min-height:180px">AAAAAAAAAAAAAAAAAAAAAAAAAAAA</textarea>
            </div>

            <div>
                <div class="card-title">Dataset B</div>
                <textarea id="compareB" style="min-height:180px">The quick brown fox jumps over the lazy dog.</textarea>
            </div>
        </div>

        <button class="btn btn-primary" onclick="compareData()">Compare Datasets ↗</button>

        <div class="compare-result" id="compareResult">
            <div class="compare-box">
                <h3>DATASET A</h3>
                <div class="compare-number">—</div>
                <div class="compare-label">Waiting for comparison</div>
            </div>
            <div class="compare-box">
                <h3>DATASET B</h3>
                <div class="compare-number">—</div>
                <div class="compare-label">Waiting for comparison</div>
            </div>
        </div>

        <div class="insight" id="compareInsight" style="margin-top:14px">
            Compare two datasets to see which contains more uncertainty.
        </div>

    </div>

</section>


<!-- =====================================================
     INFORMATION DENSITY
===================================================== -->

<section class="page" id="page-density">

    <div class="page-heading">
        <div>
            <h2>Information Density</h2>
            <p>Inspect character frequency and sequence-level information.</p>
        </div>
        <button class="btn btn-primary" onclick="analyze()">Refresh ↗</button>
    </div>

    <div class="card" style="margin-bottom:17px">
        <div class="card-title">
            <span>Character Frequency Table</span>
            <span class="card-subtitle">SORTABLE DATA</span>
        </div>

        <div class="table-wrap">
            <table>
                <thead>
                    <tr>
                        <th>CHARACTER</th>
                        <th>COUNT</th>
                        <th>FREQUENCY</th>
                        <th>VISUAL DISTRIBUTION</th>
                    </tr>
                </thead>
                <tbody id="distributionTable">
                    <tr><td colspan="4" class="empty">Analyze data first.</td></tr>
                </tbody>
            </table>
        </div>
    </div>

    <div class="two-col">
        <div class="card">
            <div class="card-title">Information Density</div>
            <div class="info-grid">
                <div class="info-card">
                    <small>ENTROPY / CHAR</small>
                    <strong id="densityEntropy">0</strong>
                </div>
                <div class="info-card">
                    <small>TOTAL BITS</small>
                    <strong id="densityBits">0</strong>
                </div>
                <div class="info-card">
                    <small>UNIQUE SYMBOLS</small>
                    <strong id="densityUnique">0</strong>
                </div>
            </div>
        </div>

        <div class="card">
            <div class="card-title">Word Frequency</div>
            <div class="pattern-list" id="densityWords">
                <div class="empty">Analyze data first.</div>
            </div>
        </div>
    </div>

</section>


<footer style="text-align:center;color:var(--muted);font-size:10px;margin-top:35px;line-height:2">
    INFORMATION ENTROPY EXPLORER · PYTHON ANALYTICS ENGINE · VERSION 2.0
    <br>
    Randomness score is a heuristic indicator, not a cryptographic randomness test.
</footer>

</main>
</div>

<div class="toast" id="toast"></div>


<script>
const $ = id => document.getElementById(id);

let latest = null;
let toastTimer = null;

const presets = {
    english:
        "Information theory measures uncertainty in data. Repeated patterns make information more predictable. Random sequences usually contain more uncertainty than repeated sequences. Entropy helps us understand how information is distributed.",

    repeated:
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",

    binary:
        "01010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101",

    random:
        "q7!M2#xP9@vL4$zK8&nR5*wT1^bY6%hJ3!sD0@fG9#uA2&cE7*oI4^pW8%",

    numbers:
        "123456789012345678901234567890123456789012345678901234567890"
};


/* =====================================================
   NAVIGATION
===================================================== */

document.querySelectorAll(".nav-item").forEach(button => {
    button.addEventListener("click", () => {
        document.querySelectorAll(".nav-item").forEach(item =>
            item.classList.remove("active")
        );

        document.querySelectorAll(".page").forEach(page =>
            page.classList.remove("active")
        );

        button.classList.add("active");

        const page = button.dataset.page;
        $("page-" + page).classList.add("active");

        if (page === "density" && latest) {
            drawChart(latest.distribution);
        }
    });
});


/* =====================================================
   TOAST
===================================================== */

function toast(message) {
    const element = $("toast");
    element.textContent = message;
    element.classList.add("show");

    clearTimeout(toastTimer);

    toastTimer = setTimeout(() => {
        element.classList.remove("show");
    }, 2500);
}


/* =====================================================
   INPUT
===================================================== */

function updateCount() {
    const value = $("input").value;

    $("charCount").textContent =
        value.length.toLocaleString() + " / 100,000 characters";
}

$("input").addEventListener("input", updateCount);

function loadPreset() {
    const selected = $("preset").value;

    if (!selected) return;

    $("input").value = presets[selected];
    updateCount();
    analyze();
}

function clearInput() {
    $("input").value = "";
    updateCount();
    latest = null;
    resetDashboard();
    toast("Input cleared");
}

function resetDashboard() {
    const ids = [
        "entropy", "randomness", "unique", "bits",
        "normalized", "predictability", "totalChars",
        "wordCount", "lineCount", "uniqueWords",
        "dominant", "maxEntropy", "bigram", "trigram",
        "bigramCount", "originalSize", "compressedSize",
        "saved", "ratio", "densityEntropy", "densityBits",
        "densityUnique"
    ];

    ids.forEach(id => $(id).textContent = "0");

    ["entropyBar", "predictBar", "compressionBar"].forEach(id => {
        $(id).style.width = "0%";
    });

    $("patterns").innerHTML = '<div class="empty">Analyze some data first.</div>';
    $("frequentWords").innerHTML = '<div class="empty">Analyze some data first.</div>';
    $("densityWords").innerHTML = '<div class="empty">Analyze some data first.</div>';
    $("distributionTable").innerHTML = '<tr><td colspan="4" class="empty">Analyze data first.</td></tr>';

    drawChart([]);
}


/* =====================================================
   ANALYSIS API
===================================================== */

async function analyze() {
    const text = $("input").value;

    if (!text) {
        toast("Please enter some data first.");
        return;
    }

    const button = $("analyzeBtn");
    button.disabled = true;
    button.textContent = "Analyzing...";

    try {
        const response = await fetch("/api/analyze", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({text})
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || "Analysis failed");
        }

        latest = data;
        render(data);
        toast("Analysis completed");

    } catch (error) {
        toast(error.message);
    } finally {
        button.disabled = false;
        button.textContent = "Analyze ↗";
    }
}


/* =====================================================
   RENDER
===================================================== */

function render(data) {
    const o = data.overview;
    const c = data.compression;

    $("entropy").textContent = o.entropy.toFixed(3);
    $("randomness").textContent = o.randomness + "%";
    $("unique").textContent = o.unique;
    $("bits").textContent = o.informationBits.toLocaleString();

    $("normalized").textContent = o.normalized + "%";
    $("predictability").textContent = o.predictability + "%";

    $("entropyBar").style.width = o.normalized + "%";
    $("predictBar").style.width = o.predictability + "%";

    $("totalChars").textContent = o.characters.toLocaleString();
    $("wordCount").textContent = o.words.toLocaleString();
    $("lineCount").textContent = o.lines.toLocaleString();
    $("uniqueWords").textContent = o.uniqueWords;
    $("dominant").textContent = o.dominant + "%";
    $("maxEntropy").textContent = o.maxEntropy.toFixed(3);

    $("bigram").textContent = data.ngrams.bigram;
    $("trigram").textContent = data.ngrams.trigram;
    $("bigramCount").textContent = data.ngrams.bigramCount;

    $("originalSize").textContent = formatBytes(c.original);
    $("compressedSize").textContent = formatBytes(c.compressed);
    $("saved").textContent = c.saved + "%";
    $("ratio").textContent = c.ratio + "%";

    $("compressionBar").style.width =
        Math.min(Math.max(c.ratio, 0), 100) + "%";

    $("compressionNote").textContent =
        c.saved > 0
            ? `The compressed data is ${c.saved}% smaller than the original.`
            : "Compression overhead made this result larger than the original.";

    $("compressionInsight").textContent =
        c.saved > 0
            ? "This data benefited from zlib compression. Repeated structures can often be encoded more compactly."
            : "This dataset did not compress efficiently. Small or high-variation data can gain extra compression overhead.";

    $("densityEntropy").textContent = o.entropy.toFixed(4);
    $("densityBits").textContent = o.informationBits.toLocaleString();
    $("densityUnique").textContent = o.unique;

    let message = "";

    if (o.normalized > 75) {
        message = "High normalized entropy: the observed symbols have a relatively even distribution.";
    } else if (o.normalized > 40) {
        message = "Moderate normalized entropy: your data has a mix of dominant and less frequent symbols.";
    } else {
        message = "Low normalized entropy: a small number of symbols dominate your data.";
    }

    $("insight").textContent = message;

    renderPatterns(data.patterns);
    renderWords(data.words.repeated);
    renderDistribution(data.distribution);
    drawChart(data.distribution);
}

function formatBytes(bytes) {
    if (bytes < 1024) return bytes + " B";
    return (bytes / 1024).toFixed(2) + " KB";
}

function escapeHTML(value) {
    return String(value).replace(/[&<>"']/g, char => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#039;"
    })[char]);
}


/* =====================================================
   PATTERN EXPLORER
===================================================== */

function renderPatterns(patterns) {
    if (!patterns.length) {
        $("patterns").innerHTML =
            '<div class="empty">No repeated sequences found.</div>';
        return;
    }

    $("patterns").innerHTML = patterns.map(item => `
        <div class="pattern-row">
            <code class="pattern-code">${escapeHTML(item.pattern)}</code>
            <span class="pattern-meta">
                ${item.count} occurrences · ${item.size}-gram
            </span>
        </div>
    `).join("");
}

function renderWords(words) {
    const html = words.length
        ? words.map(item => `
            <div class="pattern-row">
                <span class="pattern-code">${escapeHTML(item.word)}</span>
                <span class="pattern-meta">${item.count} times</span>
            </div>
        `).join("")
        : '<div class="empty">No repeated words found.</div>';

    $("frequentWords").innerHTML = html;
    $("densityWords").innerHTML = html;
}


/* =====================================================
   DISTRIBUTION
===================================================== */

function renderDistribution(items) {
    $("distributionTable").innerHTML = items.map(item => `
        <tr>
            <td>${escapeHTML(item.character)}</td>
            <td>${item.count}</td>
            <td class="value">${item.percentage}%</td>
            <td style="min-width:130px">
                <div class="progress">
                    <div class="progress-fill" style="width:${item.percentage}%"></div>
                </div>
            </td>
        </tr>
    `).join("");
}


/* =====================================================
   CHART
===================================================== */

function drawChart(items) {
    const canvas = $("distributionChart");
    if (!canvas) return;

    const width = Math.max(canvas.clientWidth, 250);
    const height = 245;
    const dpr = window.devicePixelRatio || 1;

    canvas.width = width * dpr;
    canvas.height = height * dpr;

    const ctx = canvas.getContext("2d");
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, width, height);

    const pad = {left: 35, right: 10, top: 12, bottom: 38};
    const chartW = width - pad.left - pad.right;
    const chartH = height - pad.top - pad.bottom;

    ctx.font = "10px Inter";
    ctx.fillStyle = "#8492A9";
    ctx.strokeStyle = "#26354B";
    ctx.lineWidth = 1;

    for (let i = 0; i <= 4; i++) {
        const y = pad.top + chartH * i / 4;

        ctx.beginPath();
        ctx.moveTo(pad.left, y);
        ctx.lineTo(width - pad.right, y);
        ctx.stroke();

        ctx.fillText((100 - i * 25) + "%", 0, y + 3);
    }

    if (!items.length) return;

    const max = Math.max(...items.map(x => x.percentage), 1);
    const gap = Math.max(4, Math.min(9, chartW / 70));
    const barW = Math.max(
        4,
        (chartW - gap * items.length) / items.length
    );

    items.forEach((item, index) => {
        const x = pad.left + index * (barW + gap);
        const barH = item.percentage / max * chartH;
        const y = pad.top + chartH - barH;

        const gradient = ctx.createLinearGradient(0, y, 0, height);
        gradient.addColorStop(0, "#2DD4BF");
        gradient.addColorStop(1, "#38BDF8");

        ctx.fillStyle = gradient;
        ctx.beginPath();
        ctx.roundRect(x, y, barW, barH, 4);
        ctx.fill();

        ctx.fillStyle = "#8492A9";
        ctx.textAlign = "center";

        const label = item.character.length > 5
            ? item.character.slice(0, 4)
            : item.character;

        ctx.fillText(label, x + barW / 2, height - 13);
    });

    ctx.textAlign = "left";
}

window.addEventListener("resize", () => {
    if (latest) drawChart(latest.distribution);
});


/* =====================================================
   COMPARE LAB
===================================================== */

async function compareData() {
    const a = $("compareA").value;
    const b = $("compareB").value;

    if (!a || !b) {
        toast("Both datasets are required.");
        return;
    }

    try {
        const response = await fetch("/api/compare", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({a, b})
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || "Comparison failed");
        }

        const A = data.a.overview;
        const B = data.b.overview;

        $("compareResult").innerHTML = `
            <div class="compare-box">
                <h3>DATASET A</h3>
                <div class="compare-number">${A.entropy.toFixed(4)}</div>
                <div class="compare-label">Bits per character</div>
                <div class="compare-label" style="margin-top:10px">
                    ${A.characters} characters · ${A.unique} unique symbols
                </div>
            </div>

            <div class="compare-box">
                <h3>DATASET B</h3>
                <div class="compare-number" style="color:var(--purple)">
                    ${B.entropy.toFixed(4)}
                </div>
                <div class="compare-label">Bits per character</div>
                <div class="compare-label" style="margin-top:10px">
                    ${B.characters} characters · ${B.unique} unique symbols
                </div>
            </div>
        `;

        const difference = Math.abs(A.entropy - B.entropy).toFixed(4);

        let conclusion;

        if (A.entropy > B.entropy) {
            conclusion = `Dataset A has higher character entropy by ${difference} bits per character.`;
        } else if (B.entropy > A.entropy) {
            conclusion = `Dataset B has higher character entropy by ${difference} bits per character.`;
        } else {
            conclusion = "Both datasets have equal character entropy.";
        }

        $("compareInsight").textContent =
            conclusion + " Higher entropy means greater uncertainty in the observed character distribution.";

        toast("Comparison completed");

    } catch (error) {
        toast(error.message);
    }
}


/* =====================================================
   EXPORT
===================================================== */

function exportJSON() {
    if (!latest) {
        toast("Analyze data before exporting.");
        return;
    }

    downloadFile(
        JSON.stringify(latest, null, 2),
        "entropy-report.json",
        "application/json"
    );
}

function exportCSV() {
    if (!latest) {
        toast("Analyze data before exporting.");
        return;
    }

    const rows = [
        ["Character", "Count", "Percentage"],
        ...latest.distribution.map(item => [
            item.character,
            item.count,
            item.percentage
        ])
    ];

    const csv = rows.map(row =>
        row.map(value =>
            '"' + String(value).replace(/"/g, '""') + '"'
        ).join(",")
    ).join("\n");

    downloadFile(csv, "character-distribution.csv", "text/csv");
}

function downloadFile(content, filename, type) {
    const blob = new Blob([content], {type});
    const url = URL.createObjectURL(blob);

    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    link.click();

    URL.revokeObjectURL(url);
    toast("Report exported");
}


/* =====================================================
   INITIALIZATION
===================================================== */

updateCount();

window.addEventListener("load", () => {
    analyze();
});
</script>

</body>
</html>
"""


# =========================================================
# 3. HTTP API SERVER
# =========================================================

class EntropyHandler(BaseHTTPRequestHandler):

    def send_json(self, data, status=200):
        body = json.dumps(data).encode("utf-8")

        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def read_payload(self):
        length = int(self.headers.get("Content-Length", 0))

        if length > 500000:
            raise ValueError("Request payload is too large.")

        return json.loads(self.rfile.read(length))

    def do_GET(self):
        path = urlparse(self.path).path

        if path != "/":
            self.send_json({"error": "Route not found."}, 404)
            return

        body = HTML.encode("utf-8")

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        path = urlparse(self.path).path

        try:
            payload = self.read_payload()

            if path == "/api/analyze":
                result = analyze(payload.get("text", ""))
                self.send_json(result)
                return

            if path == "/api/compare":
                result_a = analyze(payload.get("a", ""))
                result_b = analyze(payload.get("b", ""))

                self.send_json({
                    "a": result_a,
                    "b": result_b
                })
                return

            self.send_json({"error": "Route not found."}, 404)

        except (ValueError, TypeError, json.JSONDecodeError) as error:
            self.send_json({"error": str(error)}, 400)

        except Exception:
            self.send_json({"error": "Unexpected server error."}, 500)

    def log_message(self, format, *args):
        print("[SERVER]", format % args)


# =========================================================
# 4. APPLICATION ENTRY POINT
# =========================================================

if __name__ == "__main__":

    server = ThreadingHTTPServer((HOST, PORT), EntropyHandler)

    print("\n" + "=" * 55)
    print("       INFORMATION ENTROPY EXPLORER 2.0")
    print("=" * 55)
    print(f"\n  Dashboard : http://{HOST}:{PORT}")
    print("  Engine    : SHANNON ENTROPY")
    print("  Compression: ZLIB")
    print("  API       : ANALYZE + COMPARE")
    print("  Status    : RUNNING")
    print("\n  Press CTRL + C to stop the server.")
    print("=" * 55 + "\n")

    try:
        server.serve_forever()

    except KeyboardInterrupt:
        print("\nServer stopped.")

    finally:
        server.server_close()
