
"""
Algorithmic Bias Detector
-------------------------
Single-file local web application using Python standard library.

Features:
- CSV dataset analysis
- Group selection-rate comparison
- Statistical parity difference and disparate impact ratio
- Optional false-positive / false-negative rate comparison
- Group-level sample counts and outcome summaries
- SQLite analysis history
- CSV and JSON report exports
- Dark, responsive dashboard with interactive charts

Educational screening tool only. Results are not proof of discrimination.
"""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
from pathlib import Path
from datetime import datetime
from collections import defaultdict
import csv
import io
import json
import math
import sqlite3
import threading
import webbrowser
import uuid


HOST = "127.0.0.1"
PORT = 8003
DB_FILE = Path(__file__).with_name("bias_detector.db")
MAX_ROWS = 50000
MAX_BODY = 8 * 1024 * 1024

DB_LOCK = threading.Lock()


# ----------------------------- DATABASE -----------------------------

def connect_db():
    conn = sqlite3.connect(DB_FILE, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with DB_LOCK:
        with connect_db() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS analyses (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    group_column TEXT NOT NULL,
                    decision_column TEXT NOT NULL,
                    positive_value TEXT NOT NULL,
                    outcome_column TEXT,
                    report_json TEXT NOT NULL
                )
            """)
            conn.commit()


def save_analysis(report):
    with DB_LOCK:
        with connect_db() as conn:
            conn.execute("""
                INSERT INTO analyses
                (id, name, created_at, group_column, decision_column,
                 positive_value, outcome_column, report_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                report["id"],
                report["name"],
                report["createdAt"],
                report["groupColumn"],
                report["decisionColumn"],
                report["positiveValue"],
                report.get("outcomeColumn") or None,
                json.dumps(report, ensure_ascii=False)
            ))
            conn.commit()


def get_history():
    with DB_LOCK:
        with connect_db() as conn:
            rows = conn.execute("""
                SELECT id, name, created_at, group_column,
                       decision_column, report_json
                FROM analyses
                ORDER BY created_at DESC
                LIMIT 50
            """).fetchall()

    result = []
    for row in rows:
        try:
            report = json.loads(row["report_json"])
            result.append({
                "id": row["id"],
                "name": row["name"],
                "createdAt": row["created_at"],
                "groupColumn": row["group_column"],
                "decisionColumn": row["decision_column"],
                "summary": report.get("summary", {})
            })
        except (TypeError, json.JSONDecodeError):
            continue
    return result


def get_analysis(analysis_id):
    with DB_LOCK:
        with connect_db() as conn:
            row = conn.execute(
                "SELECT report_json FROM analyses WHERE id = ?",
                (analysis_id,)
            ).fetchone()

    if not row:
        return None

    return json.loads(row["report_json"])


# ----------------------------- CSV PARSING -----------------------------

def parse_csv(text):
    if not text or not text.strip():
        raise ValueError("Paste a CSV dataset before analyzing.")

    try:
        reader = csv.DictReader(io.StringIO(text.lstrip("\ufeff")))
        headers = reader.fieldnames

        if not headers or len(headers) < 2:
            raise ValueError("CSV needs a header row and at least two columns.")

        headers = [str(h).strip() if h else "" for h in headers]

        if any(not h for h in headers):
            raise ValueError("Every CSV column must have a name.")

        if len(set(headers)) != len(headers):
            raise ValueError("CSV column names must be unique.")

        rows = []
        for row in reader:
            if not row or all(
                value is None or not str(value).strip()
                for value in row.values()
            ):
                continue

            clean = {}
            for key in headers:
                value = row.get(key, "")
                clean[key] = str(value).strip() if value is not None else ""

            rows.append(clean)

            if len(rows) > MAX_ROWS:
                raise ValueError(
                    f"Dataset exceeds the {MAX_ROWS:,}-row limit."
                )

        if not rows:
            raise ValueError("No data rows found in the CSV.")

        return headers, rows

    except csv.Error as exc:
        raise ValueError(f"Could not read CSV: {exc}") from exc


# ----------------------------- FAIRNESS METRICS -----------------------------

def safe_rate(numerator, denominator):
    if denominator == 0:
        return None
    return numerator / denominator


def percentage(value):
    if value is None:
        return None
    return round(value * 100, 2)


def round_value(value, digits=4):
    if value is None or not math.isfinite(value):
        return None
    return round(value, digits)


def analyze_dataset(payload):
    dataset_name = str(payload.get("name", "Untitled Analysis")).strip()
    dataset_name = dataset_name[:100] or "Untitled Analysis"

    headers, rows = parse_csv(str(payload.get("csv", "")))

    group_col = str(payload.get("groupColumn", "")).strip()
    decision_col = str(payload.get("decisionColumn", "")).strip()
    positive_value = str(payload.get("positiveValue", "")).strip()
    outcome_col = str(payload.get("outcomeColumn", "")).strip()

    if group_col not in headers:
        raise ValueError("Select a valid demographic/group column.")

    if decision_col not in headers:
        raise ValueError("Select a valid decision/prediction column.")

    if outcome_col and outcome_col not in headers:
        raise ValueError("Select a valid ground-truth outcome column.")

    if not positive_value:
        raise ValueError("Enter the positive decision value, such as 1 or hired.")

    if outcome_col == decision_col:
        raise ValueError(
            "The prediction column and ground-truth column must be different."
        )

    valid_rows = []
    excluded = 0

    for row in rows:
        group = row.get(group_col, "").strip()
        decision = row.get(decision_col, "").strip()

        if not group or not decision:
            excluded += 1
            continue

        if outcome_col and not row.get(outcome_col, "").strip():
            excluded += 1
            continue

        valid_rows.append(row)

    if len(valid_rows) < 2:
        raise ValueError("At least two valid records are required.")

    groups = defaultdict(list)
    for row in valid_rows:
        groups[row[group_col]].append(row)

    if len(groups) < 2:
        raise ValueError(
            "The selected group column must contain at least two distinct groups."
        )


    # Keep all groups visible, but avoid comparing extremely small groups
    # as though their estimates were reliable.
    group_results = []

    for group_name, group_rows in sorted(groups.items()):
        total = len(group_rows)
        positives = sum(
            row[decision_col] == positive_value for row in group_rows
        )
        selection_rate = safe_rate(positives, total)

        item = {
            "group": group_name,
            "count": total,
            "positiveCount": positives,
            "negativeCount": total - positives,
            "selectionRate": round_value(selection_rate),
            "selectionRatePercent": percentage(selection_rate),
            "positiveSharePercent": percentage(
                safe_rate(positives, total)
            ),
            "falsePositiveRate": None,
            "falseNegativeRate": None,
            "truePositiveRate": None,
            "trueNegativeRate": None,
            "accuracy": None,
            "confusion": None,
            "warnings": []
        }

        if total < 30:
            item["warnings"].append(
                "Small sample: fewer than 30 records."
            )

        if outcome_col:
            actual_positive = [
                row for row in group_rows
                if row[outcome_col] == positive_value
            ]
            actual_negative = [
                row for row in group_rows
                if row[outcome_col] != positive_value
            ]

            tp = sum(
                row[decision_col] == positive_value
                for row in actual_positive
            )
            fn = len(actual_positive) - tp

            fp = sum(
                row[decision_col] == positive_value
                for row in actual_negative
            )
            tn = len(actual_negative) - fp

            fpr = safe_rate(fp, len(actual_negative))
            fnr = safe_rate(fn, len(actual_positive))
            tpr = safe_rate(tp, len(actual_positive))
            tnr = safe_rate(tn, len(actual_negative))
            accuracy = safe_rate(tp + tn, total)

            item.update({
                "falsePositiveRate": round_value(fpr),
                "falseNegativeRate": round_value(fnr),
                "truePositiveRate": round_value(tpr),
                "trueNegativeRate": round_value(tnr),
                "accuracy": round_value(accuracy),
                "confusion": {
                    "tp": tp, "fp": fp, "tn": tn, "fn": fn
                }
            })

            if not actual_positive:
                item["warnings"].append(
                    "No actual positive examples; FNR/TPR unavailable."
                )
            if not actual_negative:
                item["warnings"].append(
                    "No actual negative examples; FPR/TNR unavailable."
                )

        group_results.append(item)

    # Reference group = highest selection rate.

    # Ties are resolved by group name for reproducible reports.
    ranked = sorted(
        group_results,
        key=lambda g: (
            g["selectionRate"] is not None,
            g["selectionRate"] if g["selectionRate"] is not None else -1,
            g["group"]
        ),
        reverse=True
    )
    reference = ranked[0]

    rates = [
        g["selectionRate"] for g in group_results
        if g["selectionRate"] is not None
    ]

    min_rate = min(rates) if rates else None
    max_rate = max(rates) if rates else None

    statistical_parity_difference = (
        min_rate - max_rate
        if min_rate is not None and max_rate is not None
        else None
    )

    disparate_impact_ratio = (
        min_rate / max_rate
        if min_rate is not None and max_rate is not None and max_rate > 0
        else None
    )

    # Pairwise differences against the group with the highest selection rate.
    comparisons = []
    for item in group_results:
        rate = item["selectionRate"]
        ref_rate = reference["selectionRate"]

        difference = (
            rate - ref_rate
            if rate is not None and ref_rate is not None
            else None
        )
        ratio = (
            rate / ref_rate
            if rate is not None and ref_rate is not None and ref_rate > 0
            else None
        )

        comparisons.append({
            "group": item["group"],
            "referenceGroup": reference["group"],
            "selectionRate": rate,
            "referenceSelectionRate": ref_rate,
            "difference": round_value(difference),
            "differencePercentagePoints": round_value(
                difference * 100 if difference is not None else None, 2
            ),
            "ratio": round_value(ratio)
        })

    # These thresholds are screening flags, not legal conclusions.
    warnings = []
    if excluded:
        warnings.append(
            f"{excluded} rows were excluded due to missing required values."
        )
    if len(valid_rows) < 100:
        warnings.append(
            "Small overall dataset: interpret all metrics cautiously."
        )
    if disparate_impact_ratio is not None and disparate_impact_ratio < 0.8:
        warnings.append(
            "The minimum-to-maximum selection-rate ratio is below 0.80. "
            "Review the groups, context, and data quality."
        )
    if statistical_parity_difference is not None and abs(
        statistical_parity_difference
    ) >= 0.1:
        warnings.append(
            "The selection-rate gap is at least 10 percentage points. "
            "Investigate potential causes before drawing conclusions."
        )

    if not outcome_col:
        warnings.append(
            "No ground-truth outcome column was selected; error-rate metrics "
            "cannot be calculated."
        )

    report = {
        "id": uuid.uuid4().hex[:12],
        "name": dataset_name,
        "createdAt": datetime.now().astimezone().isoformat(timespec="seconds"),
        "groupColumn": group_col,
        "decisionColumn": decision_col,
        "positiveValue": positive_value,
        "outcomeColumn": outcome_col or None,
        "rowsAnalyzed": len(valid_rows),
        "rowsExcluded": excluded,
        "groupCount": len(group_results),
        "referenceGroup": reference["group"],
        "summary": {
            "minimumSelectionRate": round_value(min_rate),
            "maximumSelectionRate": round_value(max_rate),
            "statisticalParityDifference": round_value(
                statistical_parity_difference
            ),
            "disparateImpactRatio": round_value(disparate_impact_ratio),
            "selectionRateGapPercentagePoints": round_value(
                (max_rate - min_rate) * 100
                if max_rate is not None and min_rate is not None
                else None, 2
            )
        },
        "groups": group_results,
        "comparisons": comparisons,
        "warnings": warnings,
        "methodology": {
            "selectionRate": "Positive decisions / group record count",
            "statisticalParityDifference":
                "Minimum group selection rate minus maximum group selection rate",
            "disparateImpactRatio":
                "Minimum group selection rate divided by maximum group selection rate",
            "referenceGroup":
                "Group with the highest observed selection rate",
            "errorRates":
                "Calculated only when a ground-truth outcome column is provided",
            "limitations": [
                "Metrics describe observed data, not intent or causation.",
                "Group labels and positive values are matched exactly.",
                "The 0.80 ratio is a screening heuristic, not a universal legal test.",
                "Small samples can produce unstable estimates.",
                "Fairness depends on context, data quality, and the metric chosen."
            ]
        }
    }

    return report


# ----------------------------- WEB UI -----------------------------

HTML = r"""

<!doctype html>
<html lang="en">
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Algorithmic Bias Detector</title>
        <style>
            :root {
                --bg: #0b0d12;
                --panel: #141821;
                --panel2: #191f2b;
                --line: #293142;
                --text: #f4f6fa;
                --muted: #929bad;
                --orange: #ff8a32;
                --orange2: #ffb36b;
                --green: #48d6a0;
                --red: #ff6b78;
                --blue: #7eb8ff;
            }

            * {
                box-sizing: border-box
            }

            body {
                margin: 0;
                background: var(--bg);
                color: var(--text);
                font: 14px/1.6 Inter, Segoe UI, Arial, sans-serif
            }

            button,
            input,
            select,
            textarea {
                font: inherit
            }

            button {
                cursor: pointer
            }

            .app {
                display: grid;
                grid-template-columns: 245px minmax(0, 1fr);
                min-height: 100vh
            }

            aside {
                border-right: 1px solid var(--line);
                padding: 26px 17px;
                background: #0e1118
            }

            .brand {
                display: flex;
                gap: 11px;
                align-items: center;
                padding: 0 9px 30px
            }

            .logo {
                height: 40px;
                width: 40px;
                display: grid;
                place-items: center;
                border-radius: 12px;
                background: var(--orange);
                color: #17100a;
                font-weight: 900;
                font-size: 20px
            }

            .brand strong {
                font-size: 14px;
                display: block
            }

            .brand small {
                color: var(--muted);
                font-size: 11px
            }

            .navlabel {
                font-size: 10px;
                letter-spacing: 1.6px;
                color: #697386;
                padding: 14px 10px 8px
            }

            .nav {
                width: 100%;
                border: 0;
                background: transparent;
                color: var(--muted);
                text-align: left;
                padding: 11px 12px;
                border-radius: 9px;
                margin: 3px 0
            }

            .nav.active,
            .nav:hover {
                background: #282017;
                color: var(--orange2)
            }

            .side-note {
                margin-top: 30px;
                padding: 14px;
                border: 1px solid var(--line);
                border-radius: 12px;
                color: var(--muted);
                font-size: 12px
            }

            main {
                padding: 30px clamp(16px, 3vw, 42px);
                min-width: 0;
                max-width: 1600px;
                width: 100%
            }

            .topbar {
                display: flex;
                align-items: center;
                justify-content: space-between;
                gap: 15px;
                margin-bottom: 26px
            }

            .eyebrow {
                color: var(--orange);
                font-size: 11px;
                font-weight: 800;
                letter-spacing: 1.7px
            }

            h1 {
                font-size: clamp(24px, 3vw, 34px);
                line-height: 1.2;
                margin: 7px 0
            }

            .subtitle {
                color: var(--muted);
                margin: 8px 0 0;
                max-width: 760px
            }

            .local-badge {
                border: 1px solid #315846;
                color: var(--green);
                padding: 7px 10px;
                border-radius: 30px;
                font-size: 11px;
                white-space: nowrap
            }

            .page {
                display: none
            }

            .page.active {
                display: block
            }

            .panel {
                background: var(--panel);
                border: 1px solid var(--line);
                border-radius: 15px;
                padding: 21px;
                margin-bottom: 18px;
                min-width: 0
            }

            .panel-head {
                display: flex;
                justify-content: space-between;
                align-items: center;
                gap: 12px;
                margin-bottom: 16px
            }

            h2 {
                font-size: 16px;
                margin: 0
            }

            h3 {
                font-size: 13px;
                margin: 0 0 12px
            }

            .muted {
                color: var(--muted)
            }

            .small {
                font-size: 12px
            }

            .grid {
                display: grid;
                gap: 16px
            }

            .metrics {
                grid-template-columns: repeat(4, minmax(0, 1fr))
            }

            .two {
                grid-template-columns: repeat(2, minmax(0, 1fr))
            }

            .metric {
                background: var(--panel);
                border: 1px solid var(--line);
                padding: 19px;
                border-radius: 14px
            }

            .metric .label {
                font-size: 12px;
                color: var(--muted)
            }

            .metric .value {
                font-size: 27px;
                font-weight: 750;
                margin: 8px 0 2px;
                letter-spacing: -.7px
            }

            .metric .hint {
                font-size: 11px;
                color: var(--muted)
            }

            .orange {
                color: var(--orange2)
            }

            .green {
                color: var(--green)
            }

            .red {
                color: var(--red)
            }

            label {
                display: block;
                color: #cbd2df;
                font-size: 12px;
                margin: 0 0 7px
            }

            input,
            select,
            textarea {
                width: 100%;
                background: #0d1119;
                border: 1px solid #30394b;
                color: var(--text);
                padding: 11px 12px;
                border-radius: 9px;
                outline: none
            }

            input:focus,
            select:focus,
            textarea:focus {
                border-color: var(--orange)
            }

            textarea {
                min-height: 190px;
                resize: vertical;
                font: 12px/1.6 Consolas, monospace
            }

            select option {
                background: #141821;
                color: #fff
            }

            .fields {
                display: grid;
                grid-template-columns: repeat(2, minmax(0, 1fr));
                gap: 15px
            }

            .field {
                min-width: 0
            }

            .actions {
                display: flex;
                flex-wrap: wrap;
                gap: 9px;
                margin-top: 16px
            }

            .btn {
                border: 1px solid var(--line);
                border-radius: 9px;
                background: #202635;
                color: var(--text);
                padding: 10px 14px
            }

            .btn.primary {
                background: var(--orange);
                border-color: var(--orange);
                color: #1a1008;
                font-weight: 800
            }

            .btn:hover {
                filter: brightness(1.1)
            }

            .notice {
                padding: 13px 15px;
                border-radius: 10px;
                background: #201b15;
                border: 1px solid #5c3d22;
                color: #f2c49d;
                margin: 14px 0
            }

            .alert {
                padding: 12px 14px;
                border-radius: 10px;
                margin: 9px 0;
                background: #201b15;
                border: 1px solid #5c3d22;
                color: #f4c59d;
                font-size: 12px
            }

            .alert.good {
                background: #10251f;
                border-color: #245b48;
                color: #8fe4bf
            }

            .chart {
                display: flex;
                flex-direction: column;
                gap: 15px
            }

            .bar-row {
                display: grid;
                grid-template-columns: minmax(85px, 130px) minmax(60px, 1fr) 55px;
                align-items: center;
                gap: 10px
            }

            .bar-label {
                overflow: hidden;
                text-overflow: ellipsis;
                white-space: nowrap;
                color: #d8deea;
                font-size: 12px
            }

            .bar-track {
                height: 12px;
                background: #252c3a;
                border-radius: 20px;
                overflow: hidden
            }

            .bar-fill {
                height: 100%;
                border-radius: 20px;
                background: linear-gradient(90deg, #ff7a24, #ffb66f)
            }

            .bar-value {
                text-align: right;
                font-variant-numeric: tabular-nums;
                color: var(--orange2);
                font-size: 12px
            }

            .table-wrap {
                overflow: auto
            }

            table {
                width: 100%;
                border-collapse: collapse;
                white-space: nowrap;
                font-size: 12px
            }

            th,
            td {
                text-align: left;
                padding: 12px 10px;
                border-bottom: 1px solid var(--line)
            }

            th {
                color: var(--muted);
                font-weight: 600;
                background: #171c26
            }

            td {
                color: #dce1eb
            }

            .pill {
                display: inline-block;
                padding: 4px 8px;
                border-radius: 30px;
                background: #262c38;
                color: #c8d0df;
                font-size: 10px
            }

            .pill.warn {
                background: #3a2819;
                color: #ffbd7b
            }

            .pill.ok {
                background: #14352b;
                color: #7fe2b6
            }

            .empty {
                padding: 30px 12px;
                text-align: center;
                color: var(--muted)
            }

            .kv {
                display: grid;
                grid-template-columns: 150px 1fr;
                gap: 8px;
                padding: 8px 0;
                border-bottom: 1px solid var(--line)
            }

            pre {
                white-space: pre-wrap;
                overflow-wrap: anywhere
            }

            footer {
                margin-top: 28px;
                padding: 18px 0;
                color: #687386;
                font-size: 11px;
                border-top: 1px solid var(--line)
            }

            .toast {
                position: fixed;
                right: 20px;
                bottom: 20px;
                background: #202635;
                border: 1px solid var(--line);
                border-radius: 10px;
                padding: 13px 17px;
                display: none;
                max-width: min(400px, 90vw);
                z-index: 9
            }

            .toast.show {
                display: block
            }

            @media(max-width:1050px) {
                .metrics {
                    grid-template-columns: repeat(2, minmax(0, 1fr))
                }
            }

            @media(max-width:760px) {
                .app {
                    grid-template-columns: 1fr
                }

                aside {
                    border-right: 0;
                    border-bottom: 1px solid var(--line);
                    padding: 12px
                }

                .brand {
                    padding: 5px 6px 12px
                }

                .navlabel,
                .side-note {
                    display: none
                }

                .navs {
                    display: flex;
                    gap: 5px;
                    overflow: auto
                }

                .nav {
                    white-space: nowrap;
                    width: auto;
                    padding: 9px 11px
                }

                main {
                    padding: 22px 14px
                }

                .fields,
                .two {
                    grid-template-columns: 1fr
                }

                .topbar {
                    align-items: flex-start;
                    flex-direction: column
                }

                .bar-row {
                    grid-template-columns: 85px minmax(40px, 1fr) 48px
                }
            }
        </style>
    </head>
    <body>
        <div class="app">
            <aside>
                <div class="brand">
                    <div class="logo">B</div>
                    <div><strong>Bias Detector</strong><small>Responsible AI Toolkit</small></div>
                </div>
                <div class="navlabel">WORKSPACE</div>
                <div class="navs"><button class="nav active" data-page="overview">◈ &nbsp; Overview</button><button class="nav" data-page="analyze">＋ &nbsp; New Analysis</button><button class="nav" data-page="history">◷ &nbsp; History</button><button class="nav" data-page="methodology">◎ &nbsp; Methodology</button></div>
                <div class="side-note"><strong style="color:#dce1eb">Local-first analysis</strong>
                    <p>Data is processed by this Python app on your computer. Avoid using sensitive personal data in shared environments.</p><span class="pill ok">LOCAL SERVER</span>
                </div>
            </aside>
            <main>
                <div class="topbar">
                    <div>
                        <div class="eyebrow">RESPONSIBLE AI / DATA AUDIT</div>
                        <h1 id="pageTitle">Algorithmic Bias Detector</h1>
                        <p class="subtitle" id="pageSubtitle">Explore group-level differences in algorithmic decisions.</p>
                    </div><span class="local-badge">● Running locally</span>
                </div>
                <section id="overview" class="page active">
                    <div class="grid metrics">
                        <div class="metric">
                            <div class="label">Records analyzed</div>
                            <div class="value" id="mRows">—</div>
                            <div class="hint">Latest analysis</div>
                        </div>
                        <div class="metric">
                            <div class="label">Groups compared</div>
                            <div class="value" id="mGroups">—</div>
                            <div class="hint">Distinct group labels</div>
                        </div>
                        <div class="metric">
                            <div class="label">Selection rate gap</div>
                            <div class="value orange" id="mGap">—</div>
                            <div class="hint">Percentage-point difference</div>
                        </div>
                        <div class="metric">
                            <div class="label">Impact ratio</div>
                            <div class="value" id="mRatio">—</div>
                            <div class="hint">Minimum / maximum rate</div>
                        </div>
                    </div>
                    <div class="grid two" style="margin-top:18px">
                        <div class="panel">
                            <div class="panel-head">
                                <h2>Selection rates by group</h2><span class="pill">LATEST</span>
                            </div>
                            <div id="overviewChart" class="chart">
                                <div class="empty">Run an analysis to see results.</div>
                            </div>
                        </div>
                        <div class="panel">
                            <div class="panel-head">
                                <h2>Analysis summary</h2>
                            </div>
                            <div id="overviewSummary" class="empty">No analysis yet. Start with a sample dataset or paste your own CSV.</div>
                        </div>
                    </div>
                    <div class="panel">
                        <div class="panel-head">
                            <h2>Potential review flags</h2><span class="pill warn">SCREENING ONLY</span>
                        </div>
                        <div id="overviewWarnings">
                            <div class="empty">Warnings will appear after analysis.</div>
                        </div>
                    </div>
                    <div class="panel">
                        <div class="panel-head">
                            <h2>Recent analyses</h2><button class="btn" onclick="showPage('history')">View history →</button>
                        </div>
                        <div id="recentHistory" class="table-wrap">
                            <div class="empty">No saved analyses.</div>
                        </div>
                    </div>
                </section>
                <section id="analyze" class="page">
                    <div class="panel">
                        <div class="panel-head">
                            <h2>Dataset configuration</h2><span class="pill">CSV INPUT</span>
                        </div>
                        <p class="muted small">Paste CSV text below. The first row must contain column names. Use exact values for group labels and positive decisions.</p>
                        <div class="fields" style="margin:18px 0">
                            <div class="field"><label for="datasetName">Analysis name</label><input id="datasetName" value="Hiring Decisions Audit" maxlength="100"></div>
                            <div class="field"><label for="fileInput">Or load a CSV file</label><input id="fileInput" type="file" accept=".csv,text/csv"></div>
                        </div><label for="csvInput">CSV dataset</label><textarea id="csvInput" spellcheck="false" placeholder="group,decision,actual_outcome&#10;Group A,1,1&#10;Group B,0,1"></textarea>
                        <div class="actions"><button class="btn" onclick="loadSample()">Load sample dataset</button><button class="btn" onclick="clearDataset()">Clear</button><button class="btn" onclick="detectColumns()">Detect columns</button></div>
                        <div class="notice small">Use synthetic or appropriately authorized data. Avoid uploading names, email addresses, IDs, or other unnecessary personal information.</div>
                        <div class="fields">
                            <div class="field"><label for="groupColumn">Group / demographic column</label><select id="groupColumn">
                                    <option value="">Paste CSV first</option>
                                </select></div>
                            <div class="field"><label for="decisionColumn">Decision / prediction column</label><select id="decisionColumn">
                                    <option value="">Paste CSV first</option>
                                </select></div>
                            <div class="field"><label for="positiveValue">Positive decision value</label><input id="positiveValue" value="1" placeholder="e.g. 1, yes, hired"></div>
                            <div class="field"><label for="outcomeColumn">Ground-truth outcome column (optional)</label><select id="outcomeColumn">
                                    <option value="">Not available</option>
                                </select></div>
                        </div>
                        <p class="muted small">When ground truth is provided, its positive value must match the positive decision value for error-rate calculations.</p>
                        <div class="actions"><button class="btn primary" id="analyzeBtn" onclick="runAnalysis()">Analyze dataset ↗</button></div>
                    </div>
                </section>
                <section id="results" class="page">
                    <div class="panel">
                        <div class="panel-head">
                            <h2 id="resultTitle">Analysis results</h2>
                            <div class="actions" style="margin:0"><button class="btn" onclick="downloadReport('json')">Export JSON</button><button class="btn" onclick="downloadReport('csv')">Export CSV</button></div>
                        </div>
                        <p id="resultMeta" class="muted small"></p>
                    </div>
                    <div class="grid metrics">
                        <div class="metric">
                            <div class="label">Records analyzed</div>
                            <div class="value" id="rRows">—</div>
                        </div>
                        <div class="metric">
                            <div class="label">Groups compared</div>
                            <div class="value" id="rGroups">—</div>
                        </div>
                        <div class="metric">
                            <div class="label">Selection rate gap</div>
                            <div class="value orange" id="rGap">—</div>
                        </div>
                        <div class="metric">
                            <div class="label">Impact ratio</div>
                            <div class="value" id="rRatio">—</div>
                        </div>
                    </div>
                    <div class="grid two" style="margin-top:18px">
                        <div class="panel">
                            <div class="panel-head">
                                <h2>Selection rate comparison</h2>
                            </div>
                            <div id="resultChart" class="chart"></div>
                        </div>
                        <div class="panel">
                            <div class="panel-head">
                                <h2>Metric interpretation</h2>
                            </div>
                            <div id="metricInterpretation"></div>
                        </div>
                    </div>
                    <div class="panel">
                        <div class="panel-head">
                            <h2>Group-level metrics</h2>
                        </div>
                        <div id="groupTable" class="table-wrap"></div>
                    </div>
                    <div class="panel">
                        <div class="panel-head">
                            <h2>Review flags and limitations</h2>
                        </div>
                        <div id="resultWarnings"></div>
                    </div>
                    <div class="panel">
                        <div class="panel-head">
                            <h2>Pairwise comparison against reference group</h2>
                        </div>
                        <div id="comparisonTable" class="table-wrap"></div>
                    </div>
                </section>
                <section id="history" class="page">
                    <div class="panel">
                        <div class="panel-head">
                            <h2>Saved analysis history</h2><button class="btn" onclick="refreshHistory()">Refresh</button>
                        </div>
                        <p class="muted small">Up to 50 recent reports are stored in a local SQLite database.</p>
                        <div id="historyTable" class="table-wrap">
                            <div class="empty">Loading history…</div>
                        </div>
                    </div>
                </section>
                <section id="methodology" class="page">
                    <div class="panel">
                        <h2>Metrics and methodology</h2>
                        <p class="muted">This tool measures observed differences. No single metric can establish that an algorithm is fair or unfair.</p>
                        <div class="kv"><strong>Selection rate</strong><span>Number of positive decisions divided by all valid records in a group.</span></div>
                        <div class="kv"><strong>Statistical parity difference</strong><span>Minimum group selection rate minus maximum group selection rate. A negative result indicates a gap between the extremes.</span></div>
                        <div class="kv"><strong>Disparate impact ratio</strong><span>Minimum group selection rate divided by maximum group selection rate. A value near 1 means the observed rates are closer together. It is undefined when the maximum rate is zero.</span></div>
                        <div class="kv"><strong>False-positive rate</strong><span>Predicted positive among actually negative examples.</span></div>
                        <div class="kv"><strong>False-negative rate</strong><span>Predicted negative among actually positive examples.</span></div>
                        <div class="kv"><strong>Reference group</strong><span>The group with the highest observed selection rate. This is a comparison reference, not a privileged or correct group.</span></div>
                    </div>
                    <div class="panel">
                        <h2>Interpretation safeguards</h2>
                        <ul class="muted">
                            <li>The 0.80 ratio is a commonly discussed screening heuristic, not a universal legal standard or proof of discrimination.</li>
                            <li>Small groups and missing data can make estimates unstable or misleading.</li>
                            <li>Differences may reflect data quality, historical inequities, model design, decision thresholds, or contextual factors.</li>
                            <li>Fairness metrics can conflict. Choose metrics based on the decision context and consult relevant domain and legal experts.</li>
                            <li>Use only data you are authorized to process. Minimize sensitive information and follow applicable privacy rules.</li>
                        </ul>
                    </div>
                </section>
                <footer>Algorithmic Bias Detector · Local educational prototype · Results require human review and contextual validation.</footer>
            </main>
        </div>
        <div id="toast" class="toast"></div>
        <script>
            const $ = id => document.getElementById(id);
            let currentReport = null;
            let currentPage = "overview";
            const pageInfo = {
                overview: ["Algorithmic Bias Detector", "Explore group-level differences in algorithmic decisions."],
                analyze: ["New dataset analysis", "Configure your dataset and select the fields to compare."],
                results: ["Analysis results", "Review selection-rate differences and potential risk indicators."],
                history: ["Analysis history", "Return to saved reports from previous local analyses."],
                methodology: ["Methodology", "Understand what the metrics measure and what they cannot tell you."]
            };
            document.querySelectorAll(".nav").forEach(btn => {
                btn.addEventListener("click", () => showPage(btn.dataset.page));
            });

            function showPage(name) {
                currentPage = name;
                document.querySelectorAll(".page").forEach(p => p.classList.toggle("active", p.id === name));
                document.querySelectorAll(".nav").forEach(b => b.classList.toggle("active", b.dataset.page === name));
                $("pageTitle").textContent = pageInfo[name]?.[0] || "Analysis results";
                $("pageSubtitle").textContent = pageInfo[name]?.[1] || "";
                if (name === "history") refreshHistory();
            }

            function toast(message) {
                const el = $("toast");
                el.textContent = message;
                el.classList.add("show");
                setTimeout(() => el.classList.remove("show"), 3200);
            }

            function escapeHtml(value) {
                return String(value ?? "").replace(/[&<>"']/g, c => ({
                    "&": "&amp;",
                    "<": "&lt;",
                    ">": "&gt;",
                    '"': "&quot;",
                    "'": "&#39;"
                } [c]));
            }

            function parseHeaders(text) {
                const first = (text.trimStart().split(/\r?\n/, 1)[0] || "");
                // Lightweight header preview; the server performs the authoritative CSV parse.
                return first.split(",").map(s => s.trim().replace(/^"|"$/g, ""));
            }

            function detectColumns() {
                const text = $("csvInput").value;
                const headers = parseHeaders(text);
                if (headers.length < 2 || !headers[0]) {
                    toast("Paste a CSV dataset with a header row first.");
                    return;
                }
                const oldGroup = $("groupColumn").value;
                const oldDecision = $("decisionColumn").value;
                const oldOutcome = $("outcomeColumn").value;
                setOptions("groupColumn", headers, oldGroup, headers[0]);
                setOptions("decisionColumn", headers, oldDecision, headers.find(h => /decision|prediction|approved|hired|selected/i.test(h)) || headers[1]);
                setOptions("outcomeColumn", headers, oldOutcome, "", true);
                toast("Column options updated. Verify them before analysis.");
            }

            function setOptions(id, headers, selected, defaultValue, optional = false) {
                const el = $(id);
                el.innerHTML = "";
                if (optional) {
                    const opt = document.createElement("option");
                    opt.value = "";
                    opt.textContent = "Not available";
                    el.appendChild(opt);
                }
                headers.forEach(h => {
                    const opt = document.createElement("option");
                    opt.value = h;
                    opt.textContent = h;
                    el.appendChild(opt);
                });
                if (selected && headers.includes(selected)) el.value = selected;
                else if (defaultValue && headers.includes(defaultValue)) el.value = defaultValue;
                else if (optional) el.value = "";
            }

            function loadSample() {
                $("datasetName").value = "Hiring Decisions Audit — Sample";
                $("csvInput").value = `group,decision,actual_outcome
                    Group A,1,1
                    Group A,1,1
                    Group A,1,0
                    Group A,1,1
                    Group A,1,0
                    Group A,0,1
                    Group A,1,1
                    Group A,1,0
                    Group A,0,0
                    Group A,1,1
                    Group A,1,1
                    Group A,0,0
                    Group B,1,1
                    Group B,0,1
                    Group B,0,1
                    Group B,0,0
                    Group B,1,0
                    Group B,0,1
                    Group B,0,0
                    Group B,0,0
                    Group B,1,1
                    Group B,0,0
                    Group B,0,1
                    Group B,0,0
                    Group C,1,1
                    Group C,0,1
                    Group C,0,0
                    Group C,0,0
                    Group C,0,1
                    Group C,1,1
                    Group C,0,0
                    Group C,0,0
                    Group C,0,1
                    Group C,0,0
                    Group C,0,0`;
                detectColumns();
                $("groupColumn").value = "group";
                $("decisionColumn").value = "decision";
                $("outcomeColumn").value = "actual_outcome";
                $("positiveValue").value = "1";
                toast("Sample data loaded. Click Analyze dataset.");
            }

            function clearDataset() {
                $("csvInput").value = "";
                $("fileInput").value = "";
                $("groupColumn").innerHTML = '<option value="">Paste CSV first</option>';
                $("decisionColumn").innerHTML = '<option value="">Paste CSV first</option>';
                $("outcomeColumn").innerHTML = '<option value="">Not available</option>';
            }
            $("fileInput").addEventListener("change", async e => {
                const file = e.target.files?.[0];
                if (!file) return;
                try {
                    $("csvInput").value = await file.text();
                    detectColumns();
                    toast("CSV loaded: " + file.name);
                } catch (err) {
                    toast("Could not read that file.");
                }
            });

            function fmtPercent(value) {
                return value === null || value === undefined ? "N/A" : Number(value * 100).toFixed(1) + "%";
            }

            function fmtRatio(value) {
                return value === null || value === undefined ? "N/A" : Number(value).toFixed(3);
            }

            function fmtNum(value, digits = 3) {
                return value === null || value === undefined ? "N/A" : Number(value).toFixed(digits);
            }

            function renderChart(containerId, groups) {
                const el = $(containerId);
                if (!groups?.length) {
                    el.innerHTML = '<div class="empty">No group data available.</div>';
                    return;
                }
                el.innerHTML = groups.map(g => {
                    const rate = g.selectionRatePercent ?? 0;
                    const width = Math.max(0, Math.min(100, rate));
                    return `<div class="bar-row"><div class="bar-label" title="${escapeHtml(g.group)}">${escapeHtml(g.group)}</div><div class="bar-track"><div class="bar-fill" style="width:${width}%"></div></div><div class="bar-value">${rate.toFixed(1)}%</div></div>`;
                }).join("");
            }

            function renderWarnings(containerId, warnings) {
                const el = $(containerId);
                if (!warnings?.length) {
                    el.innerHTML = '<div class="alert good">No automated screening flags were raised. This does not prove that the system is fair.</div>';
                    return;
                }
                el.innerHTML = warnings.map(w => `<div class="alert">${escapeHtml(w)}</div>`).join("");
            }

            function metricCards(prefix, report) {
                const s = report.summary;
                $(prefix + "Rows").textContent = Number(report.rowsAnalyzed).toLocaleString();
                $(prefix + "Groups").textContent = report.groupCount;
                $(prefix + "Gap").textContent = s.selectionRateGapPercentagePoints === null ? "N/A" : s.selectionRateGapPercentagePoints.toFixed(1) + " pp";
                $(prefix + "Ratio").textContent = fmtRatio(s.disparateImpactRatio);
                const ratioEl = $(prefix + "Ratio");
                ratioEl.className = "value " + (s.disparateImpactRatio !== null && s.disparateImpactRatio < 0.8 ? "red" : "");
            }

            function renderSummary(report) {
                const s = report.summary;
                $("overviewSummary").innerHTML = `
 <div class="kv"><strong>Analysis</strong><span>${escapeHtml(report.name)}</span></div><div class="kv"><strong>Reference group</strong><span>${escapeHtml(report.referenceGroup)}</span></div><div class="kv"><strong>Selection-rate gap</strong><span>${s.selectionRateGapPercentagePoints===null?"N/A":s.selectionRateGapPercentagePoints+" percentage points"}</span></div><div class="kv"><strong>Impact ratio</strong><span>${fmtRatio(s.disparateImpactRatio)}</span></div><div class="kv"><strong>Excluded rows</strong><span>${report.rowsExcluded}</span></div><div class="kv"><strong>Created</strong><span>${escapeHtml(new Date(report.createdAt).toLocaleString())}</span></div>`;
            }

            function renderGroupTable(report) {
                $("groupTable").innerHTML = `<table><thead><tr><th>Group</th><th>Count</th><th>Positive</th><th>Selection rate</th><th>FPR</th><th>FNR</th><th>Accuracy</th><th>Notes</th></tr></thead><tbody>${report.groups.map(g=>`<tr><td>${escapeHtml(g.group)}</td><td>${g.count}</td><td>${g.positiveCount}</td><td>${fmtPercent(g.selectionRate)}</td><td>${fmtPercent(g.falsePositiveRate)}</td><td>${fmtPercent(g.falseNegativeRate)}</td><td>${fmtPercent(g.accuracy)}</td><td>${g.warnings.length?'<span class="pill warn">Review</span>':'<span class="pill">—</span>'}</td></tr>`).join("")}</tbody></table>`;
            }

            function renderComparisons(report) {
                $("comparisonTable").innerHTML = `<table><thead><tr><th>Group</th><th>Reference group</th><th>Selection rate</th><th>Difference (pp)</th><th>Rate ratio</th></tr></thead><tbody>${report.comparisons.map(c=>`<tr><td>${escapeHtml(c.group)}</td><td>${escapeHtml(c.referenceGroup)}</td><td>${fmtPercent(c.selectionRate)}</td><td>${c.differencePercentagePoints===null?"N/A":c.differencePercentagePoints.toFixed(2)+" pp"}</td><td>${fmtRatio(c.ratio)}</td></tr>`).join("")}</tbody></table>`;
            }

            function renderInterpretation(report) {
                const s = report.summary;
                const ratio = s.disparateImpactRatio;
                const ratioText = ratio === null ? "Undefined because all groups have zero selection rate." : ratio < 0.8 ? "The ratio is below 0.80; review potential disparities and context." : "The ratio is at least 0.80; this alone does not establish fairness.";
                $("metricInterpretation").innerHTML = `
 <div class="kv"><strong>Statistical parity difference</strong><span>${s.statisticalParityDifference===null?"N/A":s.statisticalParityDifference.toFixed(3)}</span></div><p class="muted small">Minimum selection rate minus maximum selection rate. Values closer to zero indicate a smaller gap between the observed extremes.</p><div class="kv"><strong>Disparate impact ratio</strong><span>${fmtRatio(ratio)}</span></div><p class="muted small">${escapeHtml(ratioText)}</p><div class="kv"><strong>Reference group</strong><span>${escapeHtml(report.referenceGroup)}</span></div><p class="muted small">This is the group with the highest observed selection rate, not a normative benchmark.</p>`;
            }

            function renderReport(report) {
                currentReport = report;
                metricCards("r", report);
                $("resultTitle").textContent = report.name;
                $("resultMeta").textContent = `${report.rowsAnalyzed.toLocaleString()} rows analyzed · ${report.rowsExcluded} excluded · ${new Date(report.createdAt).toLocaleString()}`;
                renderChart("resultChart", report.groups);
                renderGroupTable(report);
                renderComparisons(report);
                renderWarnings("resultWarnings", report.warnings);
                renderInterpretation(report);
                metricCards("m", report);
                renderChart("overviewChart", report.groups);
                renderSummary(report);
                renderWarnings("overviewWarnings", report.warnings);
                showPage("results");
                refreshHistory();
            }
            async function runAnalysis() {
                const btn = $("analyzeBtn");
                const payload = {
                    name: $("datasetName").value,
                    csv: $("csvInput").value,
                    groupColumn: $("groupColumn").value,
                    decisionColumn: $("decisionColumn").value,
                    positiveValue: $("positiveValue").value,
                    outcomeColumn: $("outcomeColumn").value
                };
                btn.disabled = true;
                btn.textContent = "Analyzing…";
                try {
                    const response = await fetch("/api/analyze", {
                        method: "POST",
                        headers: {
                            "Content-Type": "application/json"
                        },
                        body: JSON.stringify(payload)
                    });
                    const data = await response.json();
                    if (!response.ok) throw new Error(data.error || "Analysis failed.");
                    renderReport(data);
                    toast("Analysis completed and saved locally.");
                } catch (err) {
                    toast(err.message || "Could not analyze the dataset.");
                } finally {
                    btn.disabled = false;
                    btn.textContent = "Analyze dataset ↗";
                }
            }
            async function refreshHistory() {
                try {
                    const response = await fetch("/api/history");
                    const data = await response.json();
                    if (!response.ok) throw new Error(data.error || "Could not load history.");
                    const html = data.items.map(item => `<tr><td>${escapeHtml(item.name)}</td><td>${escapeHtml(new Date(item.createdAt).toLocaleString())}</td><td>${Number(item.summary?.selectionRateGapPercentagePoints??0).toFixed(1)} pp</td><td>${fmtRatio(item.summary?.disparateImpactRatio)}</td><td><button class="btn" onclick="openReport('${encodeURIComponent(item.id)}')">Open</button></td></tr>`).join("");
                    const table = html ? `<table><thead><tr><th>Name</th><th>Date</th><th>Gap</th><th>Ratio</th><th></th></tr></thead><tbody>${html}</tbody></table>` : '<div class="empty">No saved analyses yet.</div>';
                    $("historyTable").innerHTML = table;
                    $("recentHistory").innerHTML = table;
                } catch (err) {
                    $("historyTable").innerHTML = `<div class="alert">${escapeHtml(err.message)}</div>`;
                }
            }
            async function openReport(encodedId) {
                try {
                    const response = await fetch("/api/report?id=" + encodedId);
                    const report = await response.json();
                    if (!response.ok) throw new Error(report.error || "Could not open report.");
                    renderReport(report);
                } catch (err) {
                    toast(err.message);
                }
            }

            function downloadReport(format) {
                if (!currentReport) {
                    toast("Run or open an analysis first.");
                    return;
                }
                const content = format === "json" ? JSON.stringify(currentReport, null, 2) : reportToCsv(currentReport);
                const blob = new Blob([content], {
                    type: format === "json" ? "application/json" : "text/csv;charset=utf-8"
                });
                const url = URL.createObjectURL(blob);
                const a = document.createElement("a");
                a.href = url;
                a.download = `bias-report-${currentReport.id}.${format}`;
                document.body.appendChild(a);
                a.click();
                a.remove();
                URL.revokeObjectURL(url);
            }

            function reportToCsv(report) {
                const columns = ["group", "count", "positiveCount", "negativeCount", "selectionRatePercent", "falsePositiveRate", "falseNegativeRate", "truePositiveRate", "trueNegativeRate", "accuracy"];
                const lines = [columns.join(",")];
                for (const g of report.groups) {
                    lines.push(columns.map(k => {
                        let v = g[k] ?? "";
                        if (typeof v === "string") v = '"' + v.replace(/"/g, '""') + '"';
                        return v;
                    }).join(","));
                }
                return lines.join("\r\n");
            }
            loadSample();
            refreshHistory();
        </script>
    </body>
</html>

"""


# ----------------------------- HTTP SERVER -----------------------------

class BiasDetectorHandler(BaseHTTPRequestHandler):
    server_version = "AlgorithmicBiasDetector/1.0"

    def log_message(self, fmt, *args):
        # Keep terminal output short and avoid logging submitted dataset contents.
        print(f"[{self.log_date_time_string()}] {fmt % args}")

    def send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def read_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            raise ValueError("Request body is empty.")
        if length > MAX_BODY:
            raise ValueError("Request is too large. Maximum request size is 8 MB.")
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("Invalid JSON request.") from exc

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == "/":
            body = HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
            return

        if parsed.path == "/api/history":
            self.send_json({"items": get_history()})
            return

        if parsed.path == "/api/report":
            analysis_id = parse_qs(parsed.query).get("id", [""])[0]
            report = get_analysis(analysis_id)
            if report is None:
                self.send_json({"error": "Analysis not found."}, 404)
            else:
                self.send_json(report)
            return

        self.send_json({"error": "Endpoint not found."}, 404)

    def do_POST(self):
        if urlparse(self.path).path != "/api/analyze":
            self.send_json({"error": "Endpoint not found."}, 404)
            return

        try:
            payload = self.read_json()
            if not isinstance(payload, dict):
                raise ValueError("Expected a JSON object.")
            report = analyze_dataset(payload)
            save_analysis(report)
            self.send_json(report, 201)

        except ValueError as exc:
            self.send_json({"error": str(exc)}, 400)
        except sqlite3.Error:
            self.send_json(
                {"error": "Database error. Close the app and try again."}, 500
            )
        except Exception as exc:
            print(f"Unexpected analysis error: {type(exc).__name__}: {exc}")
            self.send_json(
                {"error": "Unexpected error. Check the terminal for details."},
                500
            )


# ----------------------------- START APPLICATION -----------------------------

def main():
    init_db()
    server = ThreadingHTTPServer((HOST, PORT), BiasDetectorHandler)
    server.daemon_threads = True

    print("=" * 60)
    print("  ALGORITHMIC BIAS DETECTOR")
    print("=" * 60)
    print(f"  Dashboard: http://{HOST}:{PORT}")
    print(f"  Database:  {DB_FILE}")
    print("  Press Ctrl+C to stop.")
    print("=" * 60)

    try:
        webbrowser.open(f"http://{HOST}:{PORT}")
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
