
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse
from datetime import datetime
import sqlite3
import json

# =========================================================
# CONFIGURATION
# =========================================================

HOST = "127.0.0.1"
PORT = 8007
DB_NAME = "counterfactual_world.db"


# =========================================================
# WORLD MODEL
# =========================================================

VARIABLES = [
    {
        "id": "education",
        "name": "Education",
        "value": 70,
        "weight": 0.24,
        "color": "#32C6B5"
    },
    {
        "id": "technology",
        "name": "Technology",
        "value": 65,
        "weight": 0.20,
        "color": "#5799F5"
    },
    {
        "id": "economy",
        "name": "Economy",
        "value": 60,
        "weight": 0.22,
        "color": "#E9A34A"
    },
    {
        "id": "healthcare",
        "name": "Healthcare",
        "value": 75,
        "weight": 0.18,
        "color": "#9B7CE8"
    },
    {
        "id": "environment",
        "name": "Environment",
        "value": 55,
        "weight": 0.16,
        "color": "#8AC66D"
    }
]

RELATIONSHIPS = [
    {"source": "education", "target": "technology", "strength": 0.80},
    {"source": "education", "target": "economy", "strength": 0.70},
    {"source": "technology", "target": "economy", "strength": 0.75},
    {"source": "technology", "target": "healthcare", "strength": 0.55},
    {"source": "economy", "target": "healthcare", "strength": 0.65},
    {"source": "environment", "target": "healthcare", "strength": 0.60},
    {"source": "economy", "target": "environment", "strength": -0.45},
    {"source": "education", "target": "environment", "strength": 0.35}
]


# =========================================================
# DATABASE
# =========================================================

def get_db():
    connection = sqlite3.connect(DB_NAME)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database():
    with get_db() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS simulations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scenario TEXT NOT NULL,
                variable TEXT NOT NULL,
                old_value REAL,
                new_value REAL,
                baseline REAL,
                counterfactual REAL,
                impact REAL,
                created_at TEXT
            )
        """)


# =========================================================
# SIMULATION ENGINE
# =========================================================

def clamp(value, minimum=0, maximum=100):
    return max(minimum, min(maximum, value))


def calculate_world(values):
    total_weight = sum(v["weight"] for v in VARIABLES)

    base_score = sum(
        values[v["id"]] * v["weight"]
        for v in VARIABLES
    ) / total_weight

    interaction = 0

    for relation in RELATIONSHIPS:
        source = values[relation["source"]]
        target = values[relation["target"]]

        interaction += (
            ((source - 50) / 50)
            * ((target - 50) / 50)
            * relation["strength"]
            * 3
        )

    return round(clamp(base_score + interaction), 2)


def simulate(variable_id, new_value, scenario):
    selected = next(
        (v for v in VARIABLES if v["id"] == variable_id),
        None
    )

    if selected is None:
        raise ValueError("Invalid variable selected.")

    new_value = float(new_value)

    if not 0 <= new_value <= 100:
        raise ValueError("Value must be between 0 and 100.")

    baseline_values = {
        v["id"]: v["value"]
        for v in VARIABLES
    }

    alternative_values = baseline_values.copy()

    old_value = baseline_values[variable_id]
    alternative_values[variable_id] = new_value

    baseline = calculate_world(baseline_values)
    counterfactual = calculate_world(alternative_values)

    impact = round(counterfactual - baseline, 2)

    direct_effect = round(
        (new_value - old_value) * selected["weight"],
        2
    )

    connected = []

    for relation in RELATIONSHIPS:
        if relation["source"] == variable_id:
            other_id = relation["target"]
        elif relation["target"] == variable_id:
            other_id = relation["source"]
        else:
            continue

        other = next(
            v for v in VARIABLES if v["id"] == other_id
        )

        connected.append({
            "variable": other["name"],
            "strength": relation["strength"],
            "direction": (
                "Positive"
                if relation["strength"] > 0
                else "Negative"
            )
        })

    if impact > 0:
        status = "Positive Impact"
    elif impact < 0:
        status = "Negative Impact"
    else:
        status = "No Significant Change"

    return {
        "scenario": scenario,
        "variable": selected["name"],
        "variable_id": variable_id,
        "old_value": old_value,
        "new_value": new_value,
        "baseline": baseline,
        "counterfactual": counterfactual,
        "impact": impact,
        "direct_effect": direct_effect,
        "status": status,
        "connected": connected
    }


# =========================================================
# FRONTEND
# =========================================================

HTML = r"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">

<title>Counterfactual | World Simulator</title>

<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Space+Grotesk:wght@400;500;600;700&display=swap');

:root {
    --bg: #101315;
    --sidebar: #0a0d0f;
    --panel: #191e22;
    --panel-hover: #20272b;
    --border: #303a40;
    --text: #eef3f3;
    --muted: #89949b;
    --teal: #32c6b5;
    --blue: #5799f5;
    --orange: #e9a34a;
    --red: #e56c76;
    --green: #72c78c;
}

* {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
}

body {
    background: var(--bg);
    color: var(--text);
    font-family: 'DM Sans', sans-serif;
    overflow-x: hidden;
}

button, input, select {
    font: inherit;
}

button {
    cursor: pointer;
}

.app {
    min-height: 100vh;
    width: 100%;
}

/* SIDEBAR */

.sidebar {
    width: 76px;
    height: 100vh;
    position: fixed;
    left: 0;
    top: 0;
    z-index: 10;
    background: var(--sidebar);
    border-right: 1px solid var(--border);
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 15px 7px;
}

.logo {
    width: 43px;
    height: 43px;
    border-radius: 13px;
    background: var(--teal);
    color: #071816;
    display: grid;
    place-items: center;
    font-size: 25px;
    font-weight: 700;
    margin-bottom: 32px;
}

.side-btn {
    width: 58px;
    min-height: 58px;
    background: transparent;
    border: none;
    color: var(--muted);
    border-radius: 11px;
    margin-bottom: 9px;
    font-size: 20px;
    transition: .2s;
}

.side-btn span {
    display: block;
    font-size: 9px;
    margin-top: 5px;
}

.side-btn:hover,
.side-btn.active {
    color: var(--teal);
    background: #1d2c2d;
}

/* MAIN */

.main {
    margin-left: 76px;
    width: calc(100% - 76px);
    min-width: 0;
}

.topbar {
    height: 66px;
    padding: 0 26px;
    background: #14191c;
    border-bottom: 1px solid var(--border);
    display: flex;
    align-items: center;
    justify-content: space-between;
    position: sticky;
    top: 0;
    z-index: 5;
    gap: 15px;
}

.top-title {
    font: 700 17px 'Space Grotesk', sans-serif;
    letter-spacing: 1px;
}

.top-title span {
    color: var(--teal);
}

.top-right {
    display: flex;
    align-items: center;
    gap: 12px;
}

.workspace {
    padding: 10px 15px;
    border-radius: 8px;
    border: 1px solid var(--border);
    background: var(--panel);
    color: var(--muted);
    font-size: 10px;
}

.live {
    color: var(--green);
    background: #1b3026;
    border-radius: 20px;
    padding: 9px 13px;
    font-size: 10px;
}

/* CONTENT */

.content {
    width: 100%;
    max-width: 1600px;
    margin: auto;
    padding: 26px;
}

.page {
    display: none;
    width: 100%;
    min-width: 0;
}

.page.active {
    display: block;
}

.page-heading {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 15px;
    margin-bottom: 24px;
}

.page-heading h1 {
    font: 600 clamp(21px, 2vw, 28px) 'Space Grotesk', sans-serif;
}

.page-heading p {
    color: var(--muted);
    font-size: 12px;
    margin-top: 7px;
    line-height: 1.6;
}

.btn {
    border: 1px solid var(--border);
    background: var(--panel-hover);
    color: var(--text);
    padding: 11px 16px;
    border-radius: 8px;
    font-size: 11px;
    transition: .2s;
}

.btn:hover {
    border-color: var(--teal);
}

.btn.primary {
    background: var(--teal);
    color: #081a18;
    border-color: var(--teal);
    font-weight: 700;
    box-shadow: 0 4px 18px #32c6b51c;
}

.btn.primary:hover {
    transform: translateY(-2px);
    box-shadow: 0 7px 22px #32c6b52c;
}

/* STATISTICS */

.stats {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 15px;
    margin-bottom: 18px;
}

.stat-card {
    min-width: 0;
    padding: 20px;
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 12px;
    transition: .2s;
}

.stat-card:hover {
    transform: translateY(-3px);
    border-color: var(--teal);
}

.stat-top {
    display: flex;
    justify-content: space-between;
    color: var(--muted);
    font-size: 10px;
    gap: 5px;
}

.stat-icon {
    color: var(--teal);
    font-size: 17px;
}

.stat-number {
    font: 600 clamp(23px, 2.3vw, 30px) 'Space Grotesk', sans-serif;
    margin-top: 16px;
}

.stat-foot {
    color: var(--muted);
    font-size: 10px;
    margin-top: 6px;
}

/* PANELS */

.workspace-grid {
    display: grid;
    grid-template-columns: minmax(0, 1.65fr) minmax(280px, .85fr);
    gap: 18px;
    align-items: stretch;
}

.panel {
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 12px;
    overflow: hidden;
    min-width: 0;
    box-shadow: 0 8px 30px #00000015;
}

.panel-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    min-height: 60px;
    padding: 16px 19px;
    border-bottom: 1px solid var(--border);
}

.panel-head h3 {
    font: 600 13px 'Space Grotesk', sans-serif;
}

.panel-head small {
    color: var(--muted);
    font-size: 9px;
}

/* GRAPH */

.graph-wrap {
    width: 100%;
    height: 430px;
    position: relative;
    background:
        radial-gradient(circle at 50% 45%, #1b2b2a, #171c20 65%);
}

#graph {
    width: 100%;
    height: 100%;
    display: block;
    cursor: grab;
    touch-action: none;
}

#graph:active {
    cursor: grabbing;
}

.graph-legend {
    position: absolute;
    left: 14px;
    top: 14px;
    padding: 12px;
    border-radius: 8px;
    background: #121719e8;
    border: 1px solid var(--border);
    color: var(--muted);
    font-size: 9px;
    line-height: 2.1;
    pointer-events: none;
}

.dot {
    display: inline-block;
    width: 8px;
    height: 8px;
    border-radius: 50%;
    margin-right: 6px;
}

/* VARIABLE EXPLORER */

.detail-content {
    padding: 20px;
}

.detail-label {
    color: var(--muted);
    font-size: 10px;
    margin-bottom: 9px;
}

.detail-value {
    font: 600 18px 'Space Grotesk', sans-serif;
    margin-bottom: 22px;
}

.variable-item {
    background: var(--panel-hover);
    border: 1px solid var(--border);
    border-radius: 9px;
    padding: 13px;
    margin-bottom: 10px;
    transition: .2s;
    cursor: pointer;
}

.variable-item:hover {
    border-color: var(--teal);
    background: #252e32;
}

.variable-item.selected {
    border-color: var(--teal);
}

.variable-row {
    display: flex;
    justify-content: space-between;
    gap: 10px;
    font-size: 11px;
}

.variable-row span:last-child {
    color: var(--teal);
}

.progress {
    height: 5px;
    background: #384147;
    border-radius: 20px;
    overflow: hidden;
    margin-top: 10px;
}

.progress div {
    height: 100%;
    background: var(--teal);
    border-radius: 20px;
}

/* CHARTS */

.bottom-grid {
    display: grid;
    grid-template-columns: minmax(0, 1.4fr) minmax(260px, 1fr);
    gap: 18px;
    margin-top: 18px;
}

.chart-box {
    width: 100%;
    height: 280px;
    padding: 15px;
}

#chart {
    width: 100%;
    height: 100%;
}

.history-list {
    padding: 10px 17px;
    max-height: 280px;
    overflow-y: auto;
}

.history-item {
    display: flex;
    justify-content: space-between;
    gap: 12px;
    padding: 14px 0;
    border-bottom: 1px solid var(--border);
    font-size: 10px;
}

.history-item:last-child {
    border: none;
}

.history-item small {
    display: block;
    color: var(--muted);
    margin-top: 6px;
}

.positive {
    color: var(--green);
}

.negative {
    color: var(--red);
}

/* SIMULATOR */

.form-panel {
    padding: 24px;
}

.field {
    margin-bottom: 19px;
}

.field label {
    display: block;
    color: var(--muted);
    font-size: 10px;
    margin-bottom: 9px;
}

.field input:not([type=range]),
.field select {
    width: 100%;
    background: #111719;
    border: 1px solid var(--border);
    border-radius: 8px;
    color: var(--text);
    padding: 12px;
    outline: none;
}

.field input:focus,
.field select:focus {
    border-color: var(--teal);
}

.range-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 11px;
    margin-bottom: 10px;
}

input[type=range] {
    width: 100%;
    accent-color: var(--teal);
}

.result-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 10px;
    margin-top: 15px;
}

.result-card {
    background: var(--panel-hover);
    border: 1px solid var(--border);
    padding: 15px;
    border-radius: 9px;
    min-width: 0;
}

.result-card small {
    color: var(--muted);
    font-size: 9px;
}

.result-card strong {
    display: block;
    font: 600 23px 'Space Grotesk', sans-serif;
    margin-top: 9px;
}

.result-box {
    display: none;
    padding: 17px;
    background: #142522;
    border: 1px solid #28584f;
    border-radius: 10px;
    margin-top: 17px;
}

.result-box.show {
    display: block;
}

.result-box h3 {
    font: 600 16px 'Space Grotesk', sans-serif;
}

.result-box p {
    color: #a9bcb7;
    font-size: 11px;
    line-height: 1.8;
    margin-top: 9px;
}

.notice {
    padding: 13px;
    margin-top: 16px;
    border: 1px solid #51432a;
    border-radius: 8px;
    color: #d1b77d;
    background: #29251c;
    font-size: 10px;
    line-height: 1.7;
}

/* TABLE */

.table-wrap {
    overflow-x: auto;
}

table {
    width: 100%;
    min-width: 600px;
    border-collapse: collapse;
    font-size: 11px;
}

th, td {
    text-align: left;
    padding: 15px;
    border-bottom: 1px solid var(--border);
}

th {
    color: var(--muted);
    font-weight: 500;
    background: #171c20;
}

tbody tr:hover {
    background: #20272b;
}

.empty {
    padding: 35px;
    text-align: center;
    color: var(--muted);
    font-size: 11px;
}

/* FOOTER & TOAST */

footer {
    text-align: center;
    color: var(--muted);
    font-size: 9px;
    padding: 24px;
    line-height: 1.8;
}

.toast {
    position: fixed;
    right: 24px;
    bottom: 24px;
    z-index: 20;
    padding: 13px 19px;
    border-radius: 9px;
    background: var(--teal);
    color: #071816;
    font-weight: 700;
    font-size: 11px;
    opacity: 0;
    transform: translateY(12px);
    pointer-events: none;
    transition: .25s;
}

.toast.show {
    opacity: 1;
    transform: translateY(0);
}

/* TABLET */

@media(max-width: 1050px) {
    .content {
        padding: 20px;
    }

    .workspace-grid,
    .bottom-grid {
        grid-template-columns: minmax(0, 1fr);
    }

    .stats {
        grid-template-columns: repeat(2, minmax(0, 1fr));
    }

    .graph-wrap {
        height: 400px;
    }
}

/* MOBILE */

@media(max-width: 650px) {
    .sidebar {
        width: 58px;
        padding: 12px 5px;
    }

    .side-btn {
        width: 46px;
        min-height: 53px;
    }

    .main {
        margin-left: 58px;
        width: calc(100% - 58px);
    }

    .topbar {
        height: 58px;
        padding: 0 12px;
    }

    .top-title {
        font-size: 11px;
    }

    .workspace {
        display: none;
    }

    .content {
        padding: 14px;
    }

    .page-heading h1 {
        font-size: 21px;
    }

    .page-heading p {
        font-size: 11px;
    }

    .stats {
        gap: 10px;
    }

    .stat-card {
        padding: 14px;
    }

    .stat-top {
        font-size: 9px;
    }

    .stat-number {
        font-size: 23px;
    }

    .graph-wrap {
        height: 340px;
    }

    .graph-legend {
        padding: 8px;
        font-size: 8px;
    }

    .panel-head {
        padding: 13px;
    }

    .detail-content,
    .form-panel {
        padding: 15px;
    }

    .chart-box {
        height: 240px;
        padding: 10px;
    }

    .result-grid {
        grid-template-columns: repeat(2, minmax(0, 1fr));
    }
}

@media(max-width: 380px) {
    .stats {
        grid-template-columns: 1fr;
    }

    .graph-wrap {
        height: 290px;
    }

    .top-title {
        font-size: 10px;
    }
}
</style>
</head>

<body>

<div class="app">

<!-- SIDEBAR -->

<aside class="sidebar">
    <div class="logo">∿</div>

    <button class="side-btn active" data-page="dashboard">
        ⌂<span>Home</span>
    </button>

    <button class="side-btn" data-page="variables">
        ◈<span>Data</span>
    </button>

    <button class="side-btn" data-page="simulator">
        ⌘<span>Simulate</span>
    </button>

    <button class="side-btn" data-page="relationships">
        ◎<span>Relations</span>
    </button>

    <button class="side-btn" data-page="history">
        ▤<span>History</span>
    </button>
</aside>


<div class="main">

<!-- HEADER -->

<header class="topbar">
    <div class="top-title">
        COUNTERFACTUAL <span>WORLD</span>
    </div>

    <div class="top-right">
        <div class="workspace">
            WORLD MODEL · GLOBAL SYSTEM
        </div>

        <div class="live">● SYSTEM ONLINE</div>
    </div>
</header>


<div class="content">

<!-- DASHBOARD -->

<section class="page active" id="dashboard">

    <div class="page-heading">
        <div>
            <h1>Digital World Twin</h1>
            <p>
                Explore alternative realities through interactive
                what-if simulations.
            </p>
        </div>

        <button class="btn primary" onclick="navigate('simulator')">
            + New Simulation
        </button>
    </div>


    <div class="stats">

        <div class="stat-card">
            <div class="stat-top">
                MODEL VARIABLES <span class="stat-icon">◈</span>
            </div>
            <div class="stat-number" id="statVariables">05</div>
            <div class="stat-foot">Connected world parameters</div>
        </div>

        <div class="stat-card">
            <div class="stat-top">
                RELATIONSHIPS <span class="stat-icon">⌘</span>
            </div>
            <div class="stat-number" id="statRelations">08</div>
            <div class="stat-foot">Model connections</div>
        </div>

        <div class="stat-card">
            <div class="stat-top">
                SIMULATIONS <span class="stat-icon">◉</span>
            </div>
            <div class="stat-number" id="statSimulations">00</div>
            <div class="stat-foot">Saved experiments</div>
        </div>

        <div class="stat-card">
            <div class="stat-top">
                BASELINE SCORE <span class="stat-icon">↗</span>
            </div>
            <div class="stat-number" id="statScore">0.0</div>
            <div class="stat-foot">Current world model score</div>
        </div>

    </div>


    <div class="workspace-grid">

        <!-- GRAPH -->

        <div class="panel">

            <div class="panel-head">
                <div>
                    <h3>World Relationship Graph</h3>
                    <small>Drag nodes to explore connections</small>
                </div>

                <button class="btn" onclick="resetGraph()">↻ Reset</button>
            </div>

            <div class="graph-wrap">

                <canvas id="graph"></canvas>

                <div class="graph-legend">
                    <div><span class="dot" style="background:#32C6B5"></span>Education</div>
                    <div><span class="dot" style="background:#5799F5"></span>Technology</div>
                    <div><span class="dot" style="background:#E9A34A"></span>Economy</div>
                    <div><span class="dot" style="background:#9B7CE8"></span>Healthcare</div>
                    <div><span class="dot" style="background:#8AC66D"></span>Environment</div>
                    <div>━ Positive influence</div>
                    <div style="color:var(--red)">━ Negative influence</div>
                </div>

            </div>
        </div>


        <!-- VARIABLE EXPLORER -->

        <div class="panel">

            <div class="panel-head">
                <h3>Variable Explorer</h3>
                <small>SELECT A NODE</small>
            </div>

            <div class="detail-content">

                <div class="detail-label">SELECTED VARIABLE</div>
                <div class="detail-value" id="selectedName">Education</div>

                <div class="detail-label">CURRENT VALUE</div>
                <div class="detail-value" id="selectedValue">70 / 100</div>

                <div class="detail-label">MODEL WEIGHT</div>
                <div class="detail-value" id="selectedWeight">24%</div>

                <div class="detail-label">CONNECTED VARIABLES</div>
                <div id="connectedList"></div>

            </div>
        </div>

    </div>


    <!-- CHARTS -->

    <div class="bottom-grid">

        <div class="panel">
            <div class="panel-head">
                <h3>World Variable Distribution</h3>
                <small>BASELINE MODEL</small>
            </div>

            <div class="chart-box">
                <canvas id="chart"></canvas>
            </div>
        </div>

        <div class="panel">

            <div class="panel-head">
                <h3>Recent Experiments</h3>
                <button class="btn" onclick="navigate('history')">
                    View All →
                </button>
            </div>

            <div class="history-list" id="recentHistory">
                <div class="empty">Loading experiments...</div>
            </div>

        </div>

    </div>

</section>


<!-- VARIABLES -->

<section class="page" id="variables">

    <div class="page-heading">
        <div>
            <h1>World Variables</h1>
            <p>Explore the parameters that define this simulated world.</p>
        </div>
    </div>

    <div class="panel">

        <div class="panel-head">
            <h3>Variable Configuration</h3>
            <small>ACTIVE PARAMETERS</small>
        </div>

        <div class="detail-content" id="variableList"></div>

    </div>

</section>


<!-- SIMULATOR -->

<section class="page" id="simulator">

    <div class="page-heading">
        <div>
            <h1>Counterfactual Simulator</h1>
            <p>
                Change one variable and compare an alternative world
                with the baseline.
            </p>
        </div>
    </div>


    <div class="workspace-grid">

        <div class="panel">

            <div class="panel-head">
                <h3>Scenario Configuration</h3>
                <small>WHAT-IF ENGINE</small>
            </div>

            <div class="form-panel">

                <div class="field">
                    <label>Scenario Name</label>
                    <input
                        id="scenarioName"
                        maxlength="80"
                        placeholder="e.g. What if education improved?"
                    >
                </div>

                <div class="field">
                    <label>Select Variable</label>
                    <select id="scenarioVariable" onchange="updateSlider()"></select>
                </div>

                <div class="field">
                    <div class="range-row">
                        <label>Current Baseline</label>
                        <strong id="baselineValue">70</strong>
                    </div>

                    <input
                        type="range"
                        id="scenarioRange"
                        min="0"
                        max="100"
                        value="70"
                        disabled
                    >
                </div>

                <div class="field">

                    <div class="range-row">
                        <label>Alternative Value</label>
                        <strong id="alternativeValue" style="color:var(--teal)">
                            85
                        </strong>
                    </div>

                    <input
                        type="range"
                        id="alternativeRange"
                        min="0"
                        max="100"
                        value="85"
                        oninput="updateAlternativeValue(this.value)"
                    >

                </div>

                <button
                    class="btn primary"
                    style="width:100%"
                    onclick="runSimulation()"
                >
                    ▶ Run Counterfactual Simulation
                </button>

                <div class="notice">
                    This experiment changes one variable at a time.
                    The remaining variables stay at their baseline values.
                </div>

            </div>

        </div>


        <!-- RESULTS -->

        <div class="panel">

            <div class="panel-head">
                <h3>Simulation Results</h3>
                <small>LIVE COMPARISON</small>
            </div>

            <div class="detail-content">

                <div class="result-grid">

                    <div class="result-card">
                        <small>BASELINE</small>
                        <strong id="resultBaseline">—</strong>
                    </div>

                    <div class="result-card">
                        <small>ALTERNATIVE</small>
                        <strong id="resultAlternative">—</strong>
                    </div>

                </div>


                <div class="result-box" id="resultBox">

                    <h3 id="resultStatus">Simulation completed</h3>

                    <p id="resultDescription"></p>

                    <div class="result-grid">

                        <div class="result-card">
                            <small>NET IMPACT</small>
                            <strong id="resultImpact">0</strong>
                        </div>

                        <div class="result-card">
                            <small>DIRECT EFFECT</small>
                            <strong id="resultDirect">0</strong>
                        </div>

                        <div class="result-card">
                            <small>CHANGED VARIABLE</small>
                            <strong id="resultVariable">—</strong>
                        </div>

                    </div>

                </div>

                <div class="empty" id="resultPlaceholder">
                    Configure a scenario and run your first simulation.
                </div>

            </div>

        </div>

    </div>

</section>


<!-- RELATIONSHIPS -->

<section class="page" id="relationships">

    <div class="page-heading">
        <div>
            <h1>Relationship Analysis</h1>
            <p>Understand how variables influence one another.</p>
        </div>
    </div>

    <div class="panel">

        <div class="panel-head">
            <h3>Causal Relationship Map</h3>
            <small>MODEL CONNECTIONS</small>
        </div>

        <div class="table-wrap">
            <table>
                <thead>
                    <tr>
                        <th>SOURCE</th>
                        <th>TARGET</th>
                        <th>STRENGTH</th>
                        <th>RELATIONSHIP</th>
                    </tr>
                </thead>

                <tbody id="relationshipTable"></tbody>
            </table>
        </div>

    </div>

</section>


<!-- HISTORY -->

<section class="page" id="history">

    <div class="page-heading">
        <div>
            <h1>Simulation History</h1>
            <p>Review your previous alternative-world experiments.</p>
        </div>

        <button class="btn" onclick="loadHistory()">↻ Refresh</button>
    </div>

    <div class="panel">

        <div class="panel-head">
            <h3>Saved Experiments</h3>
            <small>LAST 30 SIMULATIONS</small>
        </div>

        <div class="table-wrap">

            <table>
                <thead>
                    <tr>
                        <th>SCENARIO</th>
                        <th>VARIABLE</th>
                        <th>BASELINE</th>
                        <th>ALTERNATIVE</th>
                        <th>IMPACT</th>
                        <th>DATE</th>
                    </tr>
                </thead>

                <tbody id="historyTable"></tbody>
            </table>

        </div>

    </div>

</section>

</div>


<footer>
    COUNTERFACTUAL WORLD SIMULATOR · EXPLORE THE POSSIBILITIES
    <br>
    An illustrative mathematical model — not a real-world forecasting system.
</footer>

</div>
</div>


<div class="toast" id="toast"></div>


<script>

// =========================================================
// GLOBAL STATE
// =========================================================

let world = null;
let history = [];
let selectedNode = "education";
let dragging = null;

const positions = {
    education: [0.50, 0.18],
    technology: [0.79, 0.39],
    economy: [0.72, 0.77],
    healthcare: [0.29, 0.73],
    environment: [0.19, 0.38]
};

const nodePositions = {};


// =========================================================
// API
// =========================================================

async function api(url, method = "GET", body = null) {
    const options = {
        method,
        headers: {}
    };

    if (body) {
        options.headers["Content-Type"] = "application/json";
        options.body = JSON.stringify(body);
    }

    const response = await fetch(url, options);
    const result = await response.json();

    if (!response.ok) {
        throw new Error(result.error || "Request failed.");
    }

    return result;
}


// =========================================================
// UTILITIES
// =========================================================

function notify(message) {
    const toast = document.getElementById("toast");

    toast.textContent = message;
    toast.classList.add("show");

    setTimeout(() => {
        toast.classList.remove("show");
    }, 2500);
}


function escapeHTML(value) {
    return String(value ?? "").replace(/[&<>"']/g, char => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;"
    })[char]);
}


function variableById(id) {
    return world.variables.find(v => v.id === id);
}


// =========================================================
// NAVIGATION
// =========================================================

function navigate(page) {

    document.querySelectorAll(".page").forEach(element => {
        element.classList.remove("active");
    });

    document.querySelectorAll(".side-btn").forEach(element => {
        element.classList.remove("active");
    });

    document.getElementById(page).classList.add("active");

    const button = document.querySelector(
        `[data-page="${page}"]`
    );

    if (button) {
        button.classList.add("active");
    }

    if (page === "history") {
        loadHistory();
    }

    if (page === "dashboard") {
        requestAnimationFrame(() => {
            drawGraph();
            drawChart();
        });
    }
}


document.querySelectorAll(".side-btn").forEach(button => {
    button.addEventListener("click", () => {
        navigate(button.dataset.page);
    });
});


// =========================================================
// DASHBOARD
// =========================================================

function renderDashboard() {

    document.getElementById("statVariables").textContent =
        String(world.variables.length).padStart(2, "0");

    document.getElementById("statRelations").textContent =
        String(world.relationships.length).padStart(2, "0");

    document.getElementById("statSimulations").textContent =
        String(world.simulation_count).padStart(2, "0");

    document.getElementById("statScore").textContent =
        world.baseline.toFixed(1);

    renderVariableList();
    renderRelationships();
    selectVariable(selectedNode);

    drawGraph();
    drawChart();
}


// =========================================================
// VARIABLE LIST
// =========================================================

function renderVariableList() {

    const container = document.getElementById("variableList");

    container.innerHTML = world.variables.map(variable => `

        <div
            class="variable-item ${selectedNode === variable.id ? "selected" : ""}"
            onclick="selectVariable('${variable.id}')"
        >

            <div class="variable-row">
                <strong>${escapeHTML(variable.name)}</strong>
                <span>${variable.value}%</span>
            </div>

            <div class="progress">
                <div style="width:${variable.value}%"></div>
            </div>

            <div class="detail-label" style="margin-top:9px">
                Model weight: ${(variable.weight * 100).toFixed(0)}%
            </div>

        </div>

    `).join("");


    const select = document.getElementById("scenarioVariable");

    select.innerHTML = world.variables.map(variable => `
        <option value="${variable.id}">
            ${escapeHTML(variable.name)}
        </option>
    `).join("");

    updateSlider();
}


// =========================================================
// SELECT VARIABLE
// =========================================================

function selectVariable(id) {

    const variable = variableById(id);

    if (!variable) return;

    selectedNode = id;

    document.getElementById("selectedName").textContent =
        variable.name;

    document.getElementById("selectedValue").textContent =
        `${variable.value} / 100`;

    document.getElementById("selectedWeight").textContent =
        `${(variable.weight * 100).toFixed(0)}%`;

    const related = world.relationships.filter(
        relation =>
            relation.source === id ||
            relation.target === id
    );

    document.getElementById("connectedList").innerHTML =
        related.map(relation => {

            const otherId =
                relation.source === id
                    ? relation.target
                    : relation.source;

            const other = variableById(otherId);

            return `

                <div class="variable-item">

                    <div class="variable-row">
                        <span>${escapeHTML(other.name)}</span>

                        <span style="color:${
                            relation.strength < 0
                                ? "var(--red)"
                                : "var(--green)"
                        }">
                            ${relation.strength > 0 ? "+" : ""}
                            ${relation.strength.toFixed(2)}
                        </span>
                    </div>

                    <div class="detail-label" style="margin-top:6px">
                        ${relation.strength > 0 ? "Positive" : "Negative"} influence
                    </div>

                </div>

            `;
        }).join("");

    drawGraph();
}


// =========================================================
// CANVAS HELPER
// =========================================================

function resizeCanvas(canvas) {

    const rect = canvas.getBoundingClientRect();
    const ratio = window.devicePixelRatio || 1;

    canvas.width = Math.max(1, rect.width * ratio);
    canvas.height = Math.max(1, rect.height * ratio);

    const ctx = canvas.getContext("2d");

    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);

    return {
        ctx,
        width: rect.width,
        height: rect.height
    };
}


// =========================================================
// GRAPH POSITIONS
// =========================================================

function getNodePositions(width, height) {

    world.variables.forEach(variable => {

        if (!nodePositions[variable.id]) {

            const [x, y] = positions[variable.id];

            nodePositions[variable.id] = {
                x: x * width,
                y: y * height
            };
        }

    });

    return nodePositions;
}


// =========================================================
// DRAW GRAPH
// =========================================================

function drawGraph() {

    const canvas = document.getElementById("graph");

    if (!canvas || !world || !canvas.clientWidth) return;

    const { ctx, width, height } = resizeCanvas(canvas);

    const points = getNodePositions(width, height);

    ctx.clearRect(0, 0, width, height);


    // Relationships

    world.relationships.forEach(relation => {

        const a = points[relation.source];
        const b = points[relation.target];

        ctx.beginPath();
        ctx.moveTo(a.x, a.y);
        ctx.lineTo(b.x, b.y);

        ctx.strokeStyle =
            relation.strength < 0
                ? "rgba(229,108,118,.65)"
                : "rgba(115,139,151,.45)";

        ctx.lineWidth = 1.5;
        ctx.stroke();

    });


    // Nodes

    world.variables.forEach(variable => {

        const point = points[variable.id];

        const selected = selectedNode === variable.id;

        ctx.beginPath();

        ctx.arc(
            point.x,
            point.y,
            selected ? 23 : 18,
            0,
            Math.PI * 2
        );

        ctx.fillStyle = variable.color;

        ctx.shadowBlur = selected ? 22 : 10;
        ctx.shadowColor = variable.color;

        ctx.fill();

        ctx.shadowBlur = 0;


        if (selected) {

            ctx.beginPath();

            ctx.arc(
                point.x,
                point.y,
                28,
                0,
                Math.PI * 2
            );

            ctx.strokeStyle = variable.color;
            ctx.lineWidth = 1;
            ctx.stroke();
        }


        ctx.fillStyle = "#101719";
        ctx.font = "bold 9px DM Sans";
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";

        ctx.fillText(
            variable.name.slice(0, 2).toUpperCase(),
            point.x,
            point.y
        );


        ctx.fillStyle = "#e8eeee";
        ctx.font = "11px DM Sans";

        ctx.fillText(
            variable.name,
            point.x,
            point.y + 36
        );

    });

}


// =========================================================
// GRAPH INTERACTION
// =========================================================

const graph = document.getElementById("graph");


function graphPoint(event) {

    const rect = graph.getBoundingClientRect();

    return {
        x: event.clientX - rect.left,
        y: event.clientY - rect.top
    };
}


graph.addEventListener("pointerdown", event => {

    if (!world) return;

    const point = graphPoint(event);

    for (const variable of world.variables) {

        const node = nodePositions[variable.id];

        if (!node) continue;

        const distance = Math.hypot(
            point.x - node.x,
            point.y - node.y
        );

        if (distance < 28) {

            dragging = variable.id;

            graph.setPointerCapture(event.pointerId);

            selectVariable(variable.id);

            break;
        }
    }

});


graph.addEventListener("pointermove", event => {

    if (!dragging) return;

    const point = graphPoint(event);
    const rect = graph.getBoundingClientRect();

    nodePositions[dragging] = {

        x: Math.max(
            30,
            Math.min(rect.width - 30, point.x)
        ),

        y: Math.max(
            35,
            Math.min(rect.height - 45, point.y)
        )

    };

    drawGraph();

});


graph.addEventListener("pointerup", () => {
    dragging = null;
});

graph.addEventListener("pointercancel", () => {
    dragging = null;
});


function resetGraph() {

    Object.keys(nodePositions).forEach(id => {
        delete nodePositions[id];
    });

    drawGraph();

    notify("Graph layout reset.");
}


// =========================================================
// CHART
// =========================================================

function drawChart(result = null) {

    const canvas = document.getElementById("chart");

    if (!canvas || !world || !canvas.clientWidth) return;

    const { ctx, width, height } = resizeCanvas(canvas);

    ctx.clearRect(0, 0, width, height);


    const values = result

        ? [
            {
                name: "Baseline",
                value: result.baseline,
                color: "#5799F5"
            },
            {
                name: "Alternative",
                value: result.counterfactual,
                color: "#32C6B5"
            }
        ]

        : world.variables.map(variable => ({
            name: variable.name,
            value: variable.value,
            color: variable.color
        }));


    const left = 35;
    const bottom = height - 30;
    const chartHeight = height - 60;
    const chartWidth = width - 55;


    // Grid

    ctx.font = "9px DM Sans";
    ctx.textAlign = "right";

    for (let i = 0; i <= 100; i += 20) {

        const y = bottom - chartHeight * i / 100;

        ctx.strokeStyle = "#343b40";

        ctx.beginPath();
        ctx.moveTo(left, y);
        ctx.lineTo(width - 10, y);
        ctx.stroke();

        ctx.fillStyle = "#89949b";
        ctx.fillText(i, left - 8, y + 3);

    }


    // Bars

    const gap = chartWidth / values.length;
    const barWidth = Math.min(45, gap * 0.55);

    values.forEach((item, index) => {

        const x = left + gap * index + gap / 2 - barWidth / 2;

        const barHeight = chartHeight * item.value / 100;

        ctx.fillStyle = item.color;
        ctx.globalAlpha = 0.88;

        ctx.fillRect(
            x,
            bottom - barHeight,
            barWidth,
            barHeight
        );

        ctx.globalAlpha = 1;

        ctx.fillStyle = "#e8eeee";
        ctx.textAlign = "center";

        ctx.fillText(
            item.value.toFixed(1),
            x + barWidth / 2,
            bottom - barHeight - 8
        );

        ctx.fillStyle = "#89949b";

        ctx.fillText(
            item.name,
            x + barWidth / 2,
            bottom + 16
        );

    });

}


// =========================================================
// SIMULATOR CONTROLS
// =========================================================

function updateSlider() {

    const id = document.getElementById("scenarioVariable").value;

    const variable = variableById(id);

    if (!variable) return;

    document.getElementById("baselineValue").textContent =
        variable.value;

    document.getElementById("scenarioRange").value =
        variable.value;

    const alternative = Math.min(100, variable.value + 15);

    document.getElementById("alternativeRange").value =
        alternative;

    updateAlternativeValue(alternative);
}


function updateAlternativeValue(value) {

    document.getElementById("alternativeValue").textContent = value;
}


// =========================================================
// RUN SIMULATION
// =========================================================

async function runSimulation() {

    const scenario =
        document.getElementById("scenarioName").value.trim()
        || "Untitled Scenario";

    const variable =
        document.getElementById("scenarioVariable").value;

    const value =
        document.getElementById("alternativeRange").value;

    const button = document.querySelector(
        "#simulator .btn.primary"
    );

    button.disabled = true;
    button.textContent = "Running model...";

    try {

        const result = await api(
            "/api/simulate",
            "POST",
            {
                scenario,
                variable,
                value
            }
        );


        document.getElementById("resultPlaceholder").style.display =
            "none";

        document.getElementById("resultBox").classList.add("show");


        document.getElementById("resultBaseline").textContent =
            result.baseline.toFixed(2);

        document.getElementById("resultAlternative").textContent =
            result.counterfactual.toFixed(2);

        document.getElementById("resultStatus").textContent =
            result.status;

        document.getElementById("resultDescription").textContent =
            `${result.variable} changed from ${result.old_value} to ${result.new_value}. ` +
            `The model outcome changed by ${result.impact > 0 ? "+" : ""}${result.impact} points. ` +
            `This is a mathematical model result, not a real-world prediction.`;

        document.getElementById("resultImpact").textContent =
            `${result.impact > 0 ? "+" : ""}${result.impact}`;

        document.getElementById("resultDirect").textContent =
            `${result.direct_effect > 0 ? "+" : ""}${result.direct_effect}`;

        document.getElementById("resultVariable").textContent =
            result.variable;


        drawChart(result);

        await loadHistory();
        await loadWorld();

        notify("Counterfactual simulation completed.");

    } catch (error) {

        notify(error.message);

    } finally {

        button.disabled = false;
        button.textContent = "▶ Run Counterfactual Simulation";

    }

}


// =========================================================
// RELATIONSHIPS
// =========================================================

function renderRelationships() {

    document.getElementById("relationshipTable").innerHTML =
        world.relationships.map(relation => {

            const source = variableById(relation.source);
            const target = variableById(relation.target);

            const positive = relation.strength > 0;

            return `

                <tr>
                    <td>${escapeHTML(source.name)}</td>
                    <td>${escapeHTML(target.name)}</td>

                    <td>
                        ${positive ? "+" : ""}
                        ${relation.strength.toFixed(2)}
                    </td>

                    <td class="${positive ? "positive" : "negative"}">
                        ${positive ? "Positive" : "Negative"}
                    </td>
                </tr>

            `;

        }).join("");

}


// =========================================================
// HISTORY
// =========================================================

async function loadHistory() {

    try {

        history = await api("/api/history");

        document.getElementById("historyTable").innerHTML =
            history.length

            ? history.map(item => `

                <tr>

                    <td>${escapeHTML(item.scenario)}</td>

                    <td>${escapeHTML(item.variable)}</td>

                    <td>${Number(item.baseline).toFixed(2)}</td>

                    <td>${Number(item.counterfactual).toFixed(2)}</td>

                    <td class="${item.impact >= 0 ? "positive" : "negative"}">
                        ${item.impact > 0 ? "+" : ""}
                        ${Number(item.impact).toFixed(2)}
                    </td>

                    <td>${escapeHTML(item.created_at)}</td>

                </tr>

            `).join("")

            : `
                <tr>
                    <td colspan="6" class="empty">
                        No experiments saved yet.
                    </td>
                </tr>
            `;


        document.getElementById("recentHistory").innerHTML =
            history.length

            ? history.slice(0, 4).map(item => `

                <div class="history-item">

                    <div>
                        <strong>${escapeHTML(item.scenario)}</strong>

                        <small>
                            ${escapeHTML(item.variable)}
                            · ${escapeHTML(item.created_at)}
                        </small>
                    </div>

                    <strong class="${item.impact >= 0 ? "positive" : "negative"}">
                        ${item.impact > 0 ? "+" : ""}
                        ${Number(item.impact).toFixed(2)}
                    </strong>

                </div>

            `).join("")

            : `<div class="empty">No experiments yet.</div>`;


    } catch (error) {

        notify("Unable to load simulation history.");

    }

}


// =========================================================
// LOAD WORLD
// =========================================================

async function loadWorld() {

    world = await api("/api/world");

    renderDashboard();

}


// =========================================================
// INITIALIZATION
// =========================================================

async function initializeApp() {

    try {

        await loadWorld();

        await loadHistory();

        requestAnimationFrame(() => {
            drawGraph();
            drawChart();
        });

    } catch (error) {

        notify("Could not connect to the simulation engine.");

    }

}


// =========================================================
// RESIZE
// =========================================================

let resizeTimer;

window.addEventListener("resize", () => {

    clearTimeout(resizeTimer);

    resizeTimer = setTimeout(() => {

        drawGraph();
        drawChart();

    }, 120);

});


// START APPLICATION

initializeApp();

</script>

</body>
</html>
"""


# =========================================================
# HTTP HELPERS
# =========================================================

def send_json(handler, data, status=200):

    body = json.dumps(data).encode("utf-8")

    handler.send_response(status)

    handler.send_header(
        "Content-Type",
        "application/json; charset=utf-8"
    )

    handler.send_header(
        "Content-Length",
        str(len(body))
    )

    handler.send_header("Cache-Control", "no-store")

    handler.end_headers()

    handler.wfile.write(body)


def read_json(handler):

    length = int(handler.headers.get("Content-Length", 0))

    if length > 20000:
        raise ValueError("Request too large.")

    return json.loads(
        handler.rfile.read(length) or b"{}"
    )


def get_history():

    with get_db() as connection:

        rows = connection.execute("""
            SELECT *
            FROM simulations
            ORDER BY id DESC
            LIMIT 30
        """).fetchall()

    return [dict(row) for row in rows]


# =========================================================
# HTTP SERVER
# =========================================================

class AppHandler(BaseHTTPRequestHandler):

    def send_html(self):

        body = HTML.encode("utf-8")

        self.send_response(200)

        self.send_header(
            "Content-Type",
            "text/html; charset=utf-8"
        )

        self.send_header(
            "Content-Length",
            str(len(body))
        )

        self.end_headers()

        self.wfile.write(body)


    def do_GET(self):

        path = urlparse(self.path).path

        if path == "/":
            return self.send_html()


        if path == "/api/world":

            values = {
                variable["id"]: variable["value"]
                for variable in VARIABLES
            }

            with get_db() as connection:

                count = connection.execute(
                    "SELECT COUNT(*) FROM simulations"
                ).fetchone()[0]

            return send_json(self, {
                "variables": VARIABLES,
                "relationships": [
                    {
                        **relation,
                        "type": (
                            "Positive"
                            if relation["strength"] > 0
                            else "Negative"
                        )
                    }
                    for relation in RELATIONSHIPS
                ],
                "baseline": calculate_world(values),
                "simulation_count": count
            })


        if path == "/api/history":
            return send_json(self, get_history())


        return send_json(
            self,
            {"error": "Endpoint not found."},
            404
        )


    def do_POST(self):

        path = urlparse(self.path).path

        try:

            data = read_json(self)

            if path != "/api/simulate":

                return send_json(
                    self,
                    {"error": "Endpoint not found."},
                    404
                )


            scenario = str(
                data.get("scenario", "Untitled Scenario")
            ).strip()[:80] or "Untitled Scenario"

            variable = str(
                data.get("variable", "")
            ).strip()[:40]

            try:
                value = float(data.get("value"))
            except (TypeError, ValueError):
                return send_json(
                    self,
                    {"error": "Invalid numeric value."},
                    400
                )


            result = simulate(
                variable,
                value,
                scenario
            )


            with get_db() as connection:

                connection.execute("""
                    INSERT INTO simulations (
                        scenario,
                        variable,
                        old_value,
                        new_value,
                        baseline,
                        counterfactual,
                        impact,
                        created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    scenario,
                    result["variable"],
                    result["old_value"],
                    result["new_value"],
                    result["baseline"],
                    result["counterfactual"],
                    result["impact"],
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                ))


            return send_json(self, result, 201)


        except ValueError as error:

            return send_json(
                self,
                {"error": str(error)},
                400
            )


        except Exception as error:

            print("Server error:", error)

            return send_json(
                self,
                {"error": "Internal server error."},
                500
            )


    def log_message(self, format, *args):
        pass


# =========================================================
# START APPLICATION
# =========================================================

if __name__ == "__main__":

    initialize_database()

    server = ThreadingHTTPServer(
        (HOST, PORT),
        AppHandler
    )

    print("\n" + "=" * 55)
    print("       COUNTERFACTUAL WORLD SIMULATOR")
    print("=" * 55)

    print(f"\n  Dashboard : http://{HOST}:{PORT}")
    print(f"  Database  : {DB_NAME}")

    print("\n  Press CTRL + C to stop.")

    print("=" * 55 + "\n")

    try:

        server.serve_forever()

    except KeyboardInterrupt:

        print("\nSimulator stopped.")

        server.server_close()
