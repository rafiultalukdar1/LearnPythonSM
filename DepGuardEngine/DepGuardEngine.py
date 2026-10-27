from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
from datetime import datetime
import json
import re
import sqlite3
import threading
import webbrowser


# ============================================================
# CONFIGURATION
# ============================================================

HOST = "127.0.0.1"
PORT = 8001

APP_DIR = Path.home() / ".depguard"
DATABASE = APP_DIR / "depguard.db"

EXCLUDED_DIRS = {
    ".git", ".venv", "venv", "env", "__pycache__",
    "node_modules", "site-packages", "dist", "build"
}

SOURCE_PATTERNS = [
    (r"\beval\s*\(", "Use of eval()", "High", 75),
    (r"\bexec\s*\(", "Use of exec()", "High", 75),
    (r"\bpickle\.loads?\s*\(", "Unsafe pickle deserialization", "High", 75),
    (r"\bshell\s*=\s*True", "Subprocess shell=True", "Medium", 45),
    (r"\bverify\s*=\s*False", "TLS verification disabled", "Medium", 45),
]

SEVERITY_ORDER = {"High": 3, "Medium": 2, "Low": 1, "Info": 0}


# ============================================================
# DATABASE
# ============================================================

class HistoryStore:
    """Persist recent scan summaries using SQLite."""

    def __init__(self, database=DATABASE):
        self.database = database
        APP_DIR.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def connect(self):
        return sqlite3.connect(self.database, timeout=10)

    def initialize(self):
        with self.connect() as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS scans (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    dependencies INTEGER NOT NULL,
                    high_risk INTEGER NOT NULL,
                    unpinned INTEGER NOT NULL,
                    source_findings INTEGER NOT NULL,
                    report_json TEXT NOT NULL
                )
            """)

    def save(self, project, report):
        stats = report["stats"]
        created_at = datetime.now().isoformat(timespec="seconds")

        with self.connect() as connection:
            cursor = connection.execute("""
                INSERT INTO scans (
                    project, created_at, dependencies, high_risk,
                    unpinned, source_findings, report_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                project or "Pasted requirements",
                created_at,
                stats["dependencies"],
                stats["high"],
                stats["unpinned"],
                stats["sourceFindings"],
                json.dumps(report)
            ))
            scan_id = cursor.lastrowid

            # Keep the latest 50 scans.
            connection.execute("""
                DELETE FROM scans
                WHERE id NOT IN (
                    SELECT id FROM scans ORDER BY id DESC LIMIT 50
                )
            """)

        return scan_id

    def list_scans(self):
        with self.connect() as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute("""
                SELECT id, project, created_at, dependencies,
                       high_risk, unpinned, source_findings
                FROM scans ORDER BY id DESC LIMIT 50
            """).fetchall()
        return [dict(row) for row in rows]

    def get_scan(self, scan_id):
        with self.connect() as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                "SELECT * FROM scans WHERE id = ?", (scan_id,)
            ).fetchone()

        if not row:
            return None

        result = dict(row)
        result["report"] = json.loads(result.pop("report_json"))
        return result

    def delete_scan(self, scan_id):
        with self.connect() as connection:
            cursor = connection.execute(
                "DELETE FROM scans WHERE id = ?", (scan_id,)
            )
        return cursor.rowcount > 0


# ============================================================
# DEPENDENCY ANALYZER
# ============================================================

class DependencyAnalyzer:
    """Analyze dependency declarations with transparent heuristics."""

    @staticmethod
    def risk_level(score):
        if score >= 60:
            return "High"
        if score >= 30:
            return "Medium"
        return "Low"

    @staticmethod
    def parse_line(line):
        line = line.strip()

        if not line or line.startswith("#"):
            return None

        if line.startswith(("-r ", "--requirement ")):
            return {
                "name": line,
                "version": "include directive",
                "score": 15,
                "risk": "Low",
                "issue": "Nested requirements file; review separately",
                "unpinned": False,
                "type": "dependency"
            }

        if line.startswith(("-e ", "--editable ")):
            return {
                "name": line,
                "version": "editable",
                "score": 55,
                "risk": "Medium",
                "issue": "Editable installation needs review",
                "unpinned": True,
                "type": "dependency"
            }

        if line.startswith((
            "--index-url", "--extra-index-url", "--trusted-host"
        )):
            return {
                "name": line.split()[0],
                "version": "configuration",
                "score": 35,
                "risk": "Medium",
                "issue": "Package index configuration needs review",
                "unpinned": False,
                "type": "configuration"
            }

        if line.startswith(("git+", "http://", "https://")):
            return {
                "name": line[:120],
                "version": "direct URL",
                "score": 70,
                "risk": "High",
                "issue": "Direct URL dependency; verify source integrity",
                "unpinned": True,
                "type": "dependency"
            }

        # Ignore environment markers for basic package parsing.
        line = line.split(";", 1)[0].strip()

        match = re.match(r"^([A-Za-z0-9_.-]+)\s*(.*)$", line)
        if not match:
            return None

        name, spec = match.groups()
        name = name.replace("_", "-").lower()
        spec = spec.strip()

        exact = re.fullmatch(r"==\s*([A-Za-z0-9_.+-]+)", spec)

        if not spec:
            version = "not pinned"
            score = 40
            issue = "No version constraint"
            unpinned = True
        elif exact:
            version = exact.group(1)
            score = 0
            issue = "Exact version specified"
            unpinned = False
        else:
            version = spec
            score = 20
            issue = "Flexible version constraint"
            unpinned = True

        # Direct references can bypass normal package resolution.
        if "://" in spec:
            score = max(score, 70)
            issue = "External source reference; verify integrity"
            unpinned = True

        return {
            "name": name,
            "version": version,
            "score": score,
            "risk": DependencyAnalyzer.risk_level(score),
            "issue": issue,
            "unpinned": unpinned,
            "type": "dependency"
        }

    @classmethod
    def analyze(cls, text):
        items = []
        seen = {}
        duplicates = set()

        for line in text.splitlines():
            item = cls.parse_line(line)
            if not item:
                continue

            key = item["name"].lower()

            if key in seen:
                duplicates.add(key)
            else:
                seen[key] = item
                items.append(item)

        for name in sorted(duplicates):
            items.append({
                "name": name,
                "version": "duplicate",
                "score": 35,
                "risk": "Medium",
                "issue": "Package appears more than once",
                "unpinned": False,
                "type": "duplicate"
            })

        return items, duplicates


# ============================================================
# SOURCE CODE SCANNER
# ============================================================

class SourceScanner:
    """Find selected code patterns for manual security review."""

    @staticmethod
    def scan(project_path):
        root = Path(project_path).expanduser().resolve()
        findings = []

        if not root.is_dir():
            raise ValueError("Project folder does not exist.")

        for file_path in root.rglob("*.py"):
            if any(part in EXCLUDED_DIRS for part in file_path.parts):
                continue

            try:
                if file_path.stat().st_size > 1_000_000:
                    continue

                source = file_path.read_text(
                    encoding="utf-8", errors="replace"
                )
            except OSError:
                continue

            relative_name = file_path.relative_to(root).as_posix()

            for line_number, line in enumerate(source.splitlines(), 1):
                for pattern, issue, risk, score in SOURCE_PATTERNS:
                    if not re.search(pattern, line):
                        continue

                    findings.append({
                        "name": relative_name,
                        "version": f"line {line_number}",
                        "score": score,
                        "risk": DependencyAnalyzer.risk_level(score),
                        "issue": issue,
                        "unpinned": False,
                        "type": "source",
                    })

                    if len(findings) >= 500:
                        return findings

        return findings


# ============================================================
# REPORT BUILDER
# ============================================================

class ReportBuilder:
    @staticmethod
    def build(requirements, project_path=""):
        items, duplicates = DependencyAnalyzer.analyze(requirements)

        source_findings = []
        if project_path:
            source_findings = SourceScanner.scan(project_path)
            items.extend(source_findings)

        stats = {
            "dependencies": sum(
                item["type"] == "dependency" for item in items
            ),
            "high": sum(item["risk"] == "High" for item in items),
            "medium": sum(item["risk"] == "Medium" for item in items),
            "low": sum(item["risk"] == "Low" for item in items),
            "unpinned": sum(
                item["unpinned"]
                for item in items
                if item["type"] == "dependency"
            ),
            "sourceFindings": len(source_findings),
            "duplicates": len(duplicates),
            "totalItems": len(items),
        }

        recommendations = []

        if stats["high"]:
            recommendations.append({
                "title": "Review high-risk flags",
                "detail": "Verify direct URLs and inspect flagged source lines.",
                "priority": "High"
            })

        if stats["unpinned"]:
            recommendations.append({
                "title": "Review version constraints",
                "detail": "Use reviewed versions and reproducible dependency files.",
                "priority": "Medium"
            })

        if stats["duplicates"]:
            recommendations.append({
                "title": "Clean duplicate declarations",
                "detail": "Keep dependency declarations consistent.",
                "priority": "Medium"
            })

        if stats["sourceFindings"]:
            recommendations.append({
                "title": "Inspect source findings",
                "detail": "Review flagged lines in context before changing code.",
                "priority": "High"
            })

        if not recommendations:
            recommendations.append({
                "title": "Keep dependencies maintained",
                "detail": "Review updates and run a CVE-aware security scanner.",
                "priority": "Low"
            })

        return {
            "engine": "DepGuard",
            "createdAt": datetime.now().isoformat(timespec="seconds"),
            "analysisType": "Heuristic analysis",
            "summary": (
                f"Analyzed {stats['dependencies']} dependencies and found "
                f"{stats['high']} high-risk flags."
            ),
            "stats": stats,
            "items": items,
            "recommendations": recommendations,
        }


# ============================================================
# WEB DASHBOARD
# ============================================================

HTML = r"""
<!DOCTYPE html>
<html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>DepGuard | Security Workspace</title>
        <style>
            :root {
                --bg: #0b0d12;
                --panel: #12151d;
                --panel2: #181c26;
                --line: #292e3b;
                --text: #edf0f7;
                --muted: #9099ad;
                --orange: #ff8b35;
                --green: #47d7a0;
                --red: #ff697d;
                --yellow: #f4c15e;
                --blue: #8caaff;
            }

            * {
                box-sizing: border-box
            }

            body {
                margin: 0;
                background: var(--bg);
                color: var(--text);
                font: 14px/1.55 Inter, system-ui, -apple-system, sans-serif
            }

            button,
            input,
            textarea,
            select {
                font: inherit
            }

            button {
                cursor: pointer
            }

            button:disabled {
                opacity: .45;
                cursor: wait
            }

            .app {
                min-height: 100vh
            }

            .sidebar {
                position: fixed;
                inset: 0 auto 0 0;
                width: 235px;
                padding: 24px 15px;
                background: #0e1016;
                border-right: 1px solid var(--line);
                display: flex;
                flex-direction: column;
                z-index: 5
            }

            .brand {
                display: flex;
                align-items: center;
                gap: 11px;
                padding: 0 8px 29px
            }

            .logo {
                width: 40px;
                height: 40px;
                border-radius: 12px;
                background: var(--orange);
                color: #251509;
                display: grid;
                place-items: center;
                font-size: 21px;
                font-weight: 950
            }

            .brand-name {
                font-weight: 850;
                font-size: 19px;
                letter-spacing: -.6px
            }

            .brand-sub {
                font-size: 9px;
                letter-spacing: 1.5px;
                color: var(--muted)
            }

            .nav-label {
                padding: 12px 10px 8px;
                color: #727b8e;
                font-size: 10px;
                font-weight: 800;
                letter-spacing: 1.5px;
                text-transform: uppercase
            }

            .nav {
                width: 100%;
                border: 0;
                background: transparent;
                color: #a7afbf;
                text-align: left;
                padding: 11px 12px;
                border-radius: 9px;
                display: flex;
                align-items: center;
                gap: 11px;
                margin: 2px 0;
                transition: .18s
            }

            .nav:hover {
                background: #1a1e28;
                color: white
            }

            .nav.active {
                background: #302319;
                color: #ffb578
            }

            .nav-icon {
                width: 20px;
                text-align: center;
                font-size: 16px
            }

            .sidebar-bottom {
                margin-top: auto;
                border: 1px solid var(--line);
                background: #141720;
                border-radius: 12px;
                padding: 14px
            }

            .local-label {
                font-size: 12px;
                font-weight: 750
            }

            .local-note {
                font-size: 11px;
                color: var(--muted);
                margin-top: 5px
            }

            .green-dot {
                display: inline-block;
                width: 7px;
                height: 7px;
                border-radius: 50%;
                background: var(--green);
                margin-right: 7px
            }

            .main {
                margin-left: 235px;
                min-width: 0
            }

            .topbar {
                height: 72px;
                border-bottom: 1px solid var(--line);
                padding: 0 30px;
                display: flex;
                align-items: center;
                justify-content: space-between;
                gap: 15px
            }

            .breadcrumb {
                color: var(--muted);
                font-size: 12px
            }

            .breadcrumb b {
                color: var(--text)
            }

            .top-actions {
                display: flex;
                align-items: center;
                gap: 9px
            }

            .tag {
                border: 1px solid var(--line);
                border-radius: 20px;
                padding: 7px 11px;
                color: var(--muted);
                font-size: 11px
            }

            .content {
                max-width: 1500px;
                margin: auto;
                padding: 28px 30px 18px
            }

            .page-heading {
                display: flex;
                align-items: flex-start;
                justify-content: space-between;
                gap: 18px;
                flex-wrap: wrap;
                margin-bottom: 23px
            }

            .eyebrow {
                color: var(--orange);
                font-size: 10px;
                font-weight: 850;
                letter-spacing: 1.7px;
                text-transform: uppercase
            }

            h1 {
                font-size: 29px;
                letter-spacing: -1px;
                line-height: 1.2;
                margin: 6px 0
            }

            .subheading {
                color: var(--muted);
                max-width: 650px
            }

            .btn {
                border: 1px solid var(--line);
                background: #202430;
                color: var(--text);
                border-radius: 9px;
                padding: 10px 13px;
                font-weight: 700;
                transition: .18s
            }

            .btn:hover {
                transform: translateY(-1px);
                border-color: #515a6d
            }

            .btn-primary {
                background: var(--orange);
                color: #241409;
                border-color: var(--orange)
            }

            .btn-primary:hover {
                background: #ffa45e
            }

            .btn-quiet {
                background: transparent
            }

            .metrics {
                display: grid;
                grid-template-columns: repeat(4, minmax(0, 1fr));
                gap: 13px
            }

            .metric {
                border: 1px solid var(--line);
                background: var(--panel);
                border-radius: 14px;
                padding: 17px;
                min-width: 0
            }

            .metric-top {
                display: flex;
                align-items: center;
                justify-content: space-between;
                gap: 7px;
                color: var(--muted);
                font-size: 11px
            }

            .metric-icon {
                width: 29px;
                height: 29px;
                display: grid;
                place-items: center;
                border-radius: 9px;
                background: #28221e;
                color: var(--orange);
                font-weight: 850
            }

            .metric-value {
                font-size: 29px;
                font-weight: 850;
                letter-spacing: -1px;
                margin-top: 12px
            }

            .metric-foot {
                font-size: 10px;
                color: var(--muted);
                margin-top: 3px
            }

            .workspace {
                display: grid;
                grid-template-columns: 330px minmax(0, 1fr);
                gap: 16px;
                margin-top: 17px;
                align-items: start
            }

            .panel {
                border: 1px solid var(--line);
                background: var(--panel);
                border-radius: 14px;
                padding: 19px;
                min-width: 0
            }

            .panel-heading {
                display: flex;
                align-items: flex-start;
                justify-content: space-between;
                gap: 10px;
                margin-bottom: 4px
            }

            h2 {
                font-size: 15px;
                margin: 0;
                font-weight: 800
            }

            .panel-desc {
                font-size: 11px;
                color: var(--muted);
                margin: 5px 0 17px
            }

            .field {
                display: block;
                font-size: 11px;
                font-weight: 750;
                margin: 15px 0 7px
            }

            input,
            textarea,
            select {
                width: 100%;
                border: 1px solid #303644;
                background: #0d1016;
                color: var(--text);
                border-radius: 9px;
                padding: 10px 11px;
                outline: none
            }

            input:focus,
            textarea:focus,
            select:focus {
                border-color: var(--orange);
                box-shadow: 0 0 0 3px #ff8b3517
            }

            textarea {
                min-height: 142px;
                resize: vertical;
                line-height: 1.65;
                font-family: ui-monospace, monospace;
                font-size: 12px
            }

            .hint {
                font-size: 10px;
                color: var(--muted);
                margin-top: 6px
            }

            .actions {
                display: flex;
                gap: 8px;
                flex-wrap: wrap;
                margin-top: 17px
            }

            .actions .btn {
                flex: 1
            }

            .notice {
                display: none;
                margin-top: 13px;
                padding: 10px 11px;
                border-radius: 9px;
                font-size: 11px;
                overflow-wrap: anywhere
            }

            .notice.show {
                display: block
            }

            .notice.error {
                background: #351b23;
                color: #ffacb7;
                border: 1px solid #63313c
            }

            .notice.success {
                background: #13291f;
                color: #9ce7c7;
                border: 1px solid #28513e
            }

            .progress {
                height: 3px;
                background: #292f3a;
                border-radius: 5px;
                overflow: hidden;
                margin-top: 13px;
                display: none
            }

            .progress.show {
                display: block
            }

            .progress span {
                display: block;
                height: 100%;
                width: 45%;
                background: var(--orange);
                animation: progress 1s ease-in-out infinite alternate
            }

            @keyframes progress {
                from {
                    transform: translateX(-80%)
                }

                to {
                    transform: translateX(180%)
                }
            }

            .results-panel {
                padding: 0;
                overflow: hidden
            }

            .results-header {
                padding: 19px;
                border-bottom: 1px solid var(--line);
                display: flex;
                justify-content: space-between;
                align-items: center;
                gap: 12px;
                flex-wrap: wrap
            }

            .result-count {
                font-size: 10px;
                color: var(--muted);
                margin-top: 4px
            }

            .filters {
                display: grid;
                grid-template-columns: minmax(120px, 1fr) 130px 125px;
                gap: 8px;
                padding: 14px 19px
            }

            .filters input,
            .filters select {
                font-size: 11px;
                padding: 9px
            }

            .table-wrap {
                overflow-x: auto
            }

            table {
                width: 100%;
                border-collapse: collapse;
                min-width: 570px;
                text-align: left
            }

            th {
                font-size: 9px;
                color: var(--muted);
                letter-spacing: .8px;
                text-transform: uppercase;
                background: #171b24;
                font-weight: 850
            }

            th,
            td {
                padding: 12px 15px;
                border-bottom: 1px solid var(--line)
            }

            td {
                font-size: 11px
            }

            tbody tr:hover {
                background: #ffffff05
            }

            .package {
                font-size: 12px;
                font-weight: 800;
                overflow-wrap: anywhere
            }

            .subtext {
                font-size: 10px;
                color: var(--muted);
                margin-top: 3px;
                max-width: 290px;
                overflow-wrap: anywhere
            }

            .version {
                color: #aab3c5;
                font-family: ui-monospace, monospace;
                overflow-wrap: anywhere
            }

            .badge {
                display: inline-block;
                border-radius: 20px;
                padding: 4px 7px;
                font-size: 9px;
                font-weight: 850;
                white-space: nowrap
            }

            .high {
                background: #421d27;
                color: #ff9eac
            }

            .medium {
                background: #3b301b;
                color: #f5d17e
            }

            .low {
                background: #17372d;
                color: #8ce5bd
            }

            .info {
                background: #262c38;
                color: #c3ccdc
            }

            .score {
                font-weight: 850;
                font-variant-numeric: tabular-nums
            }

            .empty {
                text-align: center;
                color: var(--muted);
                padding: 37px 14px;
                font-size: 11px
            }

            .empty b {
                display: block;
                color: var(--text);
                font-size: 12px;
                margin-bottom: 5px
            }

            .lower-grid {
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 15px;
                margin-top: 15px
            }

            .bar-row {
                display: grid;
                grid-template-columns: 72px minmax(40px, 1fr) 26px;
                gap: 10px;
                align-items: center;
                margin: 17px 0;
                font-size: 11px
            }

            .bar-track {
                height: 7px;
                background: #292e39;
                border-radius: 6px;
                overflow: hidden
            }

            .bar-fill {
                height: 100%;
                border-radius: 6px;
                background: var(--orange);
                transition: width .4s
            }

            .bar-fill.medium-fill {
                background: var(--yellow)
            }

            .bar-fill.low-fill {
                background: var(--green)
            }

            .bar-number {
                text-align: right;
                color: var(--muted)
            }

            .action-row {
                display: flex;
                gap: 10px;
                padding: 12px 0;
                border-bottom: 1px solid var(--line)
            }

            .action-row:last-child {
                border-bottom: 0
            }

            .action-number {
                width: 24px;
                height: 24px;
                border-radius: 8px;
                display: grid;
                place-items: center;
                background: #2b241e;
                color: var(--orange);
                font-size: 10px;
                font-weight: 850;
                flex-shrink: 0
            }

            .action-title {
                font-size: 11px;
                font-weight: 800
            }

            .action-detail {
                font-size: 10px;
                color: var(--muted);
                margin-top: 3px
            }

            .history-list {
                display: grid;
                gap: 9px
            }

            .history-item {
                display: flex;
                align-items: center;
                justify-content: space-between;
                gap: 10px;
                padding: 12px;
                border: 1px solid var(--line);
                border-radius: 10px;
                background: #10131a
            }

            .history-item b {
                font-size: 12px;
                overflow-wrap: anywhere
            }

            .history-meta {
                font-size: 10px;
                color: var(--muted);
                margin-top: 3px
            }

            .history-actions {
                display: flex;
                gap: 6px;
                flex-shrink: 0
            }

            .small-btn {
                border: 1px solid var(--line);
                background: #202430;
                color: #dfe3ed;
                padding: 6px 8px;
                border-radius: 7px;
                font-size: 10px
            }

            .small-btn:hover {
                border-color: var(--orange)
            }

            .page {
                display: none
            }

            .page.active {
                display: block;
                animation: appear .2s ease
            }

            @keyframes appear {
                from {
                    opacity: .4;
                    transform: translateY(3px)
                }

                to {
                    opacity: 1;
                    transform: none
                }
            }

            .footer {
                text-align: center;
                color: #6f788b;
                font-size: 10px;
                padding: 25px 0
            }

            .modal-backdrop {
                position: fixed;
                inset: 0;
                background: #000b;
                z-index: 20;
                display: none;
                place-items: center;
                padding: 20px
            }

            .modal-backdrop.show {
                display: grid
            }

            .modal {
                width: min(520px, 100%);
                background: #151923;
                border: 1px solid var(--line);
                border-radius: 15px;
                padding: 22px;
                max-height: 80vh;
                overflow: auto
            }

            .modal-top {
                display: flex;
                justify-content: space-between;
                align-items: center;
                gap: 12px
            }

            .modal pre {
                white-space: pre-wrap;
                overflow-wrap: anywhere;
                background: #0b0e14;
                border: 1px solid var(--line);
                padding: 13px;
                border-radius: 9px;
                color: #cbd3e2;
                font-size: 11px
            }

            @media(max-width:1120px) {
                .sidebar {
                    width: 75px;
                    padding: 20px 10px
                }

                .brand {
                    padding: 0 7px 25px
                }

                .brand-copy,
                .nav-label,
                .nav-text,
                .sidebar-bottom {
                    display: none
                }

                .nav {
                    justify-content: center;
                    padding: 13px 5px
                }

                .nav-icon {
                    font-size: 18px
                }

                .main {
                    margin-left: 75px
                }

                .workspace {
                    grid-template-columns: 1fr
                }
            }

            @media(max-width:760px) {
                .topbar {
                    padding: 0 16px;
                    height: 60px
                }

                .content {
                    padding: 20px 14px
                }

                .metrics {
                    grid-template-columns: repeat(2, minmax(0, 1fr));
                    gap: 9px
                }

                .metric {
                    padding: 13px
                }

                .metric-value {
                    font-size: 25px
                }

                .lower-grid {
                    grid-template-columns: 1fr
                }

                .filters {
                    grid-template-columns: 1fr 1fr;
                    padding: 12px
                }

                .filters input {
                    grid-column: 1/-1
                }

                .results-header {
                    padding: 15px
                }

                .page-heading h1 {
                    font-size: 25px
                }

                .tag {
                    display: none
                }
            }
        </style>
    </head>
    <body>
        <aside class="sidebar">
            <div class="brand">
                <div class="logo">D</div>
                <div class="brand-copy">
                    <div class="brand-name">DepGuard <span style="color:var(--orange)">.</span>
                    </div>
                    <div class="brand-sub">SECURITY WORKSPACE</div>
                </div>
            </div>
            <div class="nav-label">Workspace</div>
            <button class="nav active" data-page="dashboard">
                <span class="nav-icon">▦</span>
                <span class="nav-text">Dashboard</span>
            </button>
            <button class="nav" data-page="scanner">
                <span class="nav-icon">⌕</span>
                <span class="nav-text">New scan</span>
            </button>
            <button class="nav" data-page="history">
                <span class="nav-icon">◷</span>
                <span class="nav-text">Scan history</span>
            </button>
            <div class="nav-label">Information</div>
            <button class="nav" data-page="about">
                <span class="nav-icon">ⓘ</span>
                <span class="nav-text">About DepGuard</span>
            </button>
            <div class="sidebar-bottom">
                <div class="local-label">
                    <span class="green-dot"></span>Local analysis
                </div>
                <div class="local-note">Your source files are analyzed locally. Reports are stored on this computer.</div>
            </div>
        </aside>
        <div class="main">
            <header class="topbar">
                <div class="breadcrumb">DepGuard / <b id="crumb">Dashboard</b>
                </div>
                <div class="top-actions">
                    <span class="tag">PYTHON TOOLKIT</span>
                    <button class="btn btn-primary" onclick="navigate('scanner')">+ New scan</button>
                </div>
            </header>
            <div class="content">
                <section class="page active" id="page-dashboard">
                    <div class="page-heading">
                        <div>
                            <div class="eyebrow">Security overview</div>
                            <h1>Project health dashboard</h1>
                            <div class="subheading">Understand dependency configuration and review potential risk indicators.</div>
                        </div>
                        <button class="btn" onclick="navigate('history')">View scan history ↗</button>
                    </div>
                    <div class="metrics">
                        <div class="metric">
                            <div class="metric-top">Dependencies <span class="metric-icon">D</span>
                            </div>
                            <div class="metric-value" id="m-deps">—</div>
                            <div class="metric-foot">Unique dependency declarations</div>
                        </div>
                        <div class="metric">
                            <div class="metric-top">High-risk flags <span class="metric-icon">!</span>
                            </div>
                            <div class="metric-value" id="m-high" style="color:var(--red)">—</div>
                            <div class="metric-foot">Prioritize manual review</div>
                        </div>
                        <div class="metric">
                            <div class="metric-top">Unpinned packages <span class="metric-icon">↗</span>
                            </div>
                            <div class="metric-value" id="m-unpinned">—</div>
                            <div class="metric-foot">Flexible or unspecified versions</div>
                        </div>
                        <div class="metric">
                            <div class="metric-top">Source findings <span class="metric-icon">⌘</span>
                            </div>
                            <div class="metric-value" id="m-source">—</div>
                            <div class="metric-foot">Patterns flagged in Python files</div>
                        </div>
                    </div>
                    <div class="workspace">
                        <section class="panel">
                            <div class="panel-heading">
                                <h2>Quick scan</h2>
                                <span class="badge info">LOCAL</span>
                            </div>
                            <div class="panel-desc">Paste requirements or scan a project folder.</div>
                            <label class="field" for="projectPath">Project folder path (optional)</label>
                            <input id="projectPath" placeholder="D:\Projects\my-app">
                            <div class="hint">Scans requirements.txt and Python source files.</div>
                            <label class="field" for="requirements">Requirements content</label>
                            <textarea id="requirements" spellcheck="false" placeholder="flask==3.0.0&#10;requests>=2.31&#10;django"></textarea>
                            <div class="hint">When a folder has requirements.txt, that file is used automatically.</div>
                            <div class="actions">
                                <button class="btn btn-primary" id="scanBtn" onclick="runScan()">Run analysis ↗</button>
                                <button class="btn" onclick="loadDemo()">Demo data</button>
                            </div>
                            <div class="progress" id="progress">
                                <span></span>
                            </div>
                            <div class="notice" id="notice" role="status"></div>
                        </section>
                        <section class="panel results-panel">
                            <div class="results-header">
                                <div>
                                    <h2>Latest findings</h2>
                                    <div class="result-count" id="resultCount">Run a scan to populate results</div>
                                </div>
                                <button class="btn" id="exportBtn" onclick="exportReport()" disabled>Export JSON ↓</button>
                            </div>
                            <div class="filters">
                                <input id="search" placeholder="Search findings..." oninput="renderTable()">
                                <select id="riskFilter" onchange="renderTable()">
                                    <option value="all">All risks</option>
                                    <option>High</option>
                                    <option>Medium</option>
                                    <option>Low</option>
                                </select>
                                <select id="sortBy" onchange="renderTable()">
                                    <option value="risk">Sort: Risk</option>
                                    <option value="name">Sort: Name</option>
                                    <option value="score">Sort: Score</option>
                                </select>
                            </div>
                            <div class="table-wrap">
                                <table>
                                    <thead>
                                        <tr>
                                            <th>Finding</th>
                                            <th>Version</th>
                                            <th>Risk</th>
                                            <th>Score</th>
                                            <th></th>
                                        </tr>
                                    </thead>
                                    <tbody id="tableBody">
                                        <tr>
                                            <td colspan="5">
                                                <div class="empty">
                                                    <b>No scan results yet</b>Run a scan to inspect your project.
                                                </div>
                                            </td>
                                        </tr>
                                    </tbody>
                                </table>
                            </div>
                        </section>
                    </div>
                    <div class="lower-grid">
                        <section class="panel">
                            <h2>Risk distribution</h2>
                            <div class="panel-desc">Current report severity breakdown</div>
                            <div id="riskBreakdown" class="empty">
                                <b>No data available</b>Run a scan to see analytics.
                            </div>
                        </section>
                        <section class="panel">
                            <h2>Recommended actions</h2>
                            <div class="panel-desc">Suggested next steps from the report</div>
                            <div id="recommendations" class="empty">
                                <b>Action plan pending</b>Your recommendations appear after a scan.
                            </div>
                        </section>
                    </div>
                </section>
                <section class="page" id="page-scanner">
                    <div class="page-heading">
                        <div>
                            <div class="eyebrow">Analysis workspace</div>
                            <h1>Start a new scan</h1>
                            <div class="subheading">Provide a project path or paste dependency declarations.</div>
                        </div>
                    </div>
                    <div class="panel" style="max-width:760px">
                        <h2>Scan configuration</h2>
                        <div class="panel-desc">All processing runs on your local machine.</div>
                        <label class="field" for="projectPath2">Project folder path</label>
                        <input id="projectPath2" placeholder="D:\Projects\my-app">
                        <label class="field" for="requirements2">requirements.txt content</label>
                        <textarea id="requirements2" placeholder="flask==3.0.0&#10;requests>=2.31"></textarea>
                        <div class="actions">
                            <button class="btn btn-primary" onclick="copyScannerInputs();runScan()">Start scan ↗</button>
                            <button class="btn" onclick="loadDemo()">Load sample</button>
                        </div>
                        <div class="hint">Tip: Ctrl + Enter inside the requirements box on the dashboard also starts a scan.</div>
                    </div>
                </section>
                <section class="page" id="page-history">
                    <div class="page-heading">
                        <div>
                            <div class="eyebrow">Saved reports</div>
                            <h1>Scan history</h1>
                            <div class="subheading">Review recent scans stored in your local SQLite database.</div>
                        </div>
                        <button class="btn" onclick="loadHistory()">↻ Refresh</button>
                    </div>
                    <section class="panel">
                        <div id="historyList" class="history-list">
                            <div class="empty">Loading scan history...</div>
                        </div>
                    </section>
                </section>
                <section class="page" id="page-about">
                    <div class="page-heading">
                        <div>
                            <div class="eyebrow">Product information</div>
                            <h1>About DepGuard</h1>
                            <div class="subheading">A local-first helper for dependency hygiene and code review.</div>
                        </div>
                    </div>
                    <div class="lower-grid">
                        <section class="panel">
                            <h2>What it checks</h2>
                            <div class="panel-desc">The current analyzer supports these heuristics.</div>
                            <div class="action-row">
                                <div class="action-number">01</div>
                                <div>
                                    <div class="action-title">Dependency pinning</div>
                                    <div class="action-detail">Detects unspecified and flexible version constraints.</div>
                                </div>
                            </div>
                            <div class="action-row">
                                <div class="action-number">02</div>
                                <div>
                                    <div class="action-title">Duplicate declarations</div>
                                    <div class="action-detail">Highlights repeated dependency names.</div>
                                </div>
                            </div>
                            <div class="action-row">
                                <div class="action-number">03</div>
                                <div>
                                    <div class="action-title">Source patterns</div>
                                    <div class="action-detail">Flags selected patterns such as eval, exec and disabled TLS verification.</div>
                                </div>
                            </div>
                            <div class="action-row">
                                <div class="action-number">04</div>
                                <div>
                                    <div class="action-title">Exportable reports</div>
                                    <div class="action-detail">Download the structured scan report as JSON.</div>
                                </div>
                            </div>
                        </section>
                        <section class="panel">
                            <h2>Important limitations</h2>
                            <div class="panel-desc">Read before interpreting risk scores.</div>
                            <p class="subtext" style="font-size:12px;line-height:1.8">Risk scores are heuristic indicators, not confirmed vulnerabilities. This version does not query a CVE database, check package advisories, resolve transitive dependencies, or compare installed package versions against known vulnerable releases.</p>
                            <p class="subtext" style="font-size:12px;line-height:1.8">Source scanning uses simple text patterns and may produce false positives or miss issues. Review each finding in context.</p>
                        </section>
                    </div>
                </section>
                <footer class="footer">DepGuard · Local-first analysis · Heuristic results require manual review</footer>
            </div>
        </div>
        <div class="modal-backdrop" id="modal" onclick="if(event.target===this)closeModal()">
            <div class="modal">
                <div class="modal-top">
                    <h2 id="modalTitle">Finding details</h2>
                    <button class="btn" onclick="closeModal()">✕</button>
                </div>
                <div id="modalBody"></div>
            </div>
        </div>
        <script>
            let report = null;
            let currentPage = "dashboard";
            let scanInProgress = false;
            const $ = id => document.getElementById(id);

            function esc(value) {
                return String(value ?? "").replace(/[&<>"']/g, c => ({
                    "&": "&amp;",
                    "<": "&lt;",
                    ">": "&gt;",
                    '"': "&quot;",
                    "'": "&#39;"
                })[c]);
            }

            function notify(message, type = "success") {
                const el = $("notice");
                el.textContent = message;
                el.className = "notice show " + type;
            }

            function navigate(page) {
                currentPage = page;
                document.querySelectorAll(".page").forEach(el => el.classList.remove("active"));
                $("page-" + page).classList.add("active");
                document.querySelectorAll(".nav").forEach(el => el.classList.toggle("active", el.dataset.page === page));
                const names = {
                    dashboard: "Dashboard",
                    scanner: "New scan",
                    history: "Scan history",
                    about: "About DepGuard"
                };
                $("crumb").textContent = names[page] || "Dashboard";
                if (page === "history") loadHistory();
            }
            document.querySelectorAll(".nav").forEach(button => {
                button.addEventListener("click", () => navigate(button.dataset.page));
            });

            function copyScannerInputs() {
                $("projectPath").value = $("projectPath2").value.trim();
                $("requirements").value = $("requirements2").value;
            }

            function loadDemo() {
                const sample = ["flask==3.0.0", "requests>=2.31", "django", "numpy==1.26.4", "flask==3.0.0", "git+https://example.com/sample-package.git"].join("\\n");
                $("requirements").value = sample;
                $("requirements2").value = sample;
                $("projectPath").value = "";
                $("projectPath2").value = "";
                notify("Sample dependencies loaded. Run analysis to inspect the report.");
            }
            async function api(url, options = {}) {
                const response = await fetch(url, options);
                const data = await response.json();
                if (!response.ok) throw new Error(data.error || "Request failed");
                return data;
            }
            async function runScan() {
                if (scanInProgress) return;
                const path = $("projectPath").value.trim();
                const requirements = $("requirements").value;
                if (!path && !requirements.trim()) {
                    notify("Enter a project folder path or paste requirements first.", "error");
                    return;
                }
                scanInProgress = true;
                $("scanBtn").disabled = true;
                $("scanBtn").textContent = "Analyzing...";
                $("progress").classList.add("show");
                notify("Analyzing dependency configuration and source patterns...");
                try {
                    report = await api("/api/scan", {
                        method: "POST",
                        headers: {
                            "Content-Type": "application/json"
                        },
                        body: JSON.stringify({
                            path,
                            requirements
                        })
                    });
                    updateDashboard();
                    $("exportBtn").disabled = false;
                    notify(report.summary);
                    navigate("dashboard");
                } catch (error) {
                    notify(error.message, "error");
                } finally {
                    scanInProgress = false;
                    $("scanBtn").disabled = false;
                    $("scanBtn").textContent = "Run analysis ↗";
                    $("progress").classList.remove("show");
                }
            }

            function badgeClass(risk) {
                return risk === "High" ? "high" : risk === "Medium" ? "medium" : risk === "Low" ? "low" : "info";
            }

            function renderTable() {
                if (!report) return;
                const query = $("search").value.toLowerCase().trim();
                const risk = $("riskFilter").value;
                const sort = $("sortBy").value;
                const filtered = report.items.filter(item => (risk === "all" || item.risk === risk) && (item.name + " " + item.version + " " + item.issue).toLowerCase().includes(query));
                filtered.sort((a, b) => {
                    if (sort === "name") return a.name.localeCompare(b.name);
                    if (sort === "score") return b.score - a.score;
                    return ({
                        "High": 3,
                        "Medium": 2,
                        "Low": 1
                    } [b.risk] || 0) - ({
                        "High": 3,
                        "Medium": 2,
                        "Low": 1
                    } [a.risk] || 0) || b.score - a.score;
                });
                $("resultCount").textContent = `${filtered.length} shown · ${report.items.length} total findings`;
                $("tableBody").innerHTML = filtered.length ? filtered.map((item, index) => `
  
								<tr>
									<td>
										<div class="package">${esc(item.name)}</div>
										<div class="subtext">${esc(item.issue)}</div>
									</td>
									<td class="version">${esc(item.version)}</td>
									<td>
										<span class="badge ${badgeClass(item.risk)}">${esc(item.risk)}</span>
									</td>
									<td class="score">${item.score}/100</td>
									<td>
										<button class="small-btn" onclick="showFinding(${index},${JSON.stringify(item.name).replace(/
										</g,"\\u003c")})">Details
									</button>
								</td>
							</tr>`).join("") : `
							<tr>
								<td colspan="5">
									<div class="empty">
										<b>No matching findings</b>Change the search or filters and try again.
									</div>
								</td>
							</tr>`;
            }

            function showFinding(index, name) {
                const item = report.items.find(entry => entry.name === name);
                if (!item) return;
                $("modalTitle").textContent = item.name;
                $("modalBody").innerHTML = `
  
							<p>
								<span class="badge ${badgeClass(item.risk)}">${esc(item.risk)} risk</span>
								<span class="badge info">${item.score}/100 heuristic score</span>
							</p>
							<p class="subtext" style="font-size:12px">${esc(item.issue)}</p>
							<pre>${esc(JSON.stringify(item,null,2))}</pre>`;
                $("modal").classList.add("show");
            }

            function closeModal() {
                $("modal").classList.remove("show");
            }

            function updateDashboard() {
                const stats = report.stats;
                $("m-deps").textContent = stats.dependencies;
                $("m-high").textContent = stats.high;
                $("m-unpinned").textContent = stats.unpinned;
                $("m-source").textContent = stats.sourceFindings;
                renderTable();
                const groups = [
                    ["High", stats.high, ""],
                    ["Medium", stats.medium, "medium-fill"],
                    ["Low", stats.low, "low-fill"]
                ];
                const max = Math.max(1, ...groups.map(item => item[1]));
                $("riskBreakdown").innerHTML = groups.map(([name, count, extra]) => `
  
							<div class="bar-row">
								<span>${name} risk</span>
								<div class="bar-track">
									<div class="bar-fill ${extra}" style="width:${count/max*100}%"></div>
								</div>
								<span class="bar-number">${count}</span>
							</div>`).join("");
                $("recommendations").innerHTML = report.recommendations.map((item, index) => `
  
							<div class="action-row">
								<div class="action-number">${index+1}</div>
								<div>
									<div class="action-title">${esc(item.title)}</div>
									<div class="action-detail">${esc(item.detail)}</div>
								</div>
							</div>`).join("");
            }

            function exportReport() {
                if (!report) return;
                const blob = new Blob([JSON.stringify(report, null, 2)], {
                    type: "application/json"
                });
                const url = URL.createObjectURL(blob);
                const link = document.createElement("a");
                link.href = url;
                link.download = "depguard-report.json";
                link.click();
                setTimeout(() => URL.revokeObjectURL(url), 1000);
            }
            async function loadHistory() {
                const container = $("historyList");
                container.innerHTML = ' < div class = "empty" > Loading scan history... < /div>';
                try {
                    const history = await api("/api/history");
                    if (!history.length) {
                        container.innerHTML = ' < div class = "empty" > < b > No saved scans < /b>Your scan history will appear here. < /div>';
                        return;
                    }
                    container.innerHTML = history.map(item => `
   
							<div class="history-item">
								<div>
									<b>${esc(item.project)}</b>
									<div class="history-meta">${esc(item.created_at)} · ${item.dependencies} dependencies · ${item.high_risk} high-risk flags</div>
								</div>
								<div class="history-actions">
									<button class="small-btn" onclick="openHistory(${item.id})">Open</button>
									<button class="small-btn" onclick="deleteHistory(${item.id})">Delete</button>
								</div>
							</div>`).join("");
                } catch (error) {
                    container.innerHTML = `
							<div class="empty">
								<b>Could not load history</b>${esc(error.message)}
							</div>`;
                }
            }
            async function openHistory(id) {
                try {
                    const data = await api("/api/history?id=" + id);
                    report = data.report;
                    updateDashboard();
                    $("exportBtn").disabled = false;
                    notify("Loaded saved scan report.");
                    navigate("dashboard");
                } catch (error) {
                    alert(error.message);
                }
            }
            async function deleteHistory(id) {
                if (!confirm("Delete this saved scan?")) return;
                try {
                    await api("/api/history?id=" + id, {
                        method: "DELETE"
                    });
                    await loadHistory();
                } catch (error) {
                    alert(error.message);
                }
            }
            $("requirements").addEventListener("keydown", event => {
                if ((event.ctrlKey || event.metaKey) && event.key === "Enter") runScan();
            });
        </script>
    </body>
</html>
"""


# ============================================================
# HTTP API
# ============================================================

class DepGuardHandler(BaseHTTPRequestHandler):
    store = HistoryStore()

    def send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def read_json(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            raise ValueError("Invalid request length.")

        if length <= 0 or length > 2_000_000:
            raise ValueError("Request body is empty or too large.")

        try:
            data = json.loads(self.rfile.read(length))
        except json.JSONDecodeError:
            raise ValueError("Invalid JSON request.")

        if not isinstance(data, dict):
            raise ValueError("Expected a JSON object.")

        return data

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == "/":
            body = HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if parsed.path == "/api/history":
            from urllib.parse import parse_qs
            params = parse_qs(parsed.query)

            if "id" in params:
                try:
                    scan_id = int(params["id"][0])
                except ValueError:
                    self.send_json({"error": "Invalid scan ID."}, 400)
                    return

                result = self.store.get_scan(scan_id)
                if not result:
                    self.send_json({"error": "Scan not found."}, 404)
                    return

                self.send_json(result)
                return

            self.send_json(self.store.list_scans())
            return

        self.send_json({"error": "Endpoint not found."}, 404)

    def do_POST(self):
        if urlparse(self.path).path != "/api/scan":
            self.send_json({"error": "Endpoint not found."}, 404)
            return

        try:
            payload = self.read_json()
            requirements = payload.get("requirements", "")
            project_path = payload.get("path", "")

            if not isinstance(requirements, str) or not isinstance(project_path, str):
                self.send_json({"error": "Input values must be text."}, 400)
                return

            project_path = project_path.strip()

            if project_path:
                root = Path(project_path).expanduser().resolve()

                if not root.is_dir():
                    self.send_json({"error": "Project folder does not exist."}, 400)
                    return

                requirements_file = root / "requirements.txt"

                if requirements_file.is_file():
                    try:
                        requirements = requirements_file.read_text(
                            encoding="utf-8", errors="replace"
                        )
                    except OSError:
                        self.send_json(
                            {"error": "Could not read requirements.txt."}, 400
                        )
                        return

            report = ReportBuilder.build(requirements, project_path)
            scan_id = self.store.save(project_path, report)
            report["scanId"] = scan_id
            self.send_json(report)

        except ValueError as error:
            self.send_json({"error": str(error)}, 400)
        except Exception:
            self.send_json(
                {"error": "Analysis failed. Check the project path and permissions."},
                500
            )

    def do_DELETE(self):
        parsed = urlparse(self.path)

        if parsed.path != "/api/history":
            self.send_json({"error": "Endpoint not found."}, 404)
            return

        from urllib.parse import parse_qs
        params = parse_qs(parsed.query)

        try:
            scan_id = int(params.get("id", [""])[0])
        except ValueError:
            self.send_json({"error": "Invalid scan ID."}, 400)
            return

        if self.store.delete_scan(scan_id):
            self.send_json({"deleted": True})
        else:
            self.send_json({"error": "Scan not found."}, 404)

    def log_message(self, format, *args):
        # Keep console output readable.
        return

# ============================================================
# APPLICATION ENTRY POINT
# ============================================================

def main():
    server = ThreadingHTTPServer((HOST, PORT), DepGuardHandler)

    print("=" * 54)
    print("  DepGuard - Smart Dependency Risk Analyzer")
    print("=" * 54)
    print(f"  Dashboard : http://{HOST}:{PORT}")
    print(f"  Database  : {DATABASE}")
    print("  Stop      : Ctrl + C")
    print("=" * 54)

    threading.Timer(
        0.8, lambda: webbrowser.open(f"http://{HOST}:{PORT}")
    ).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nDepGuard stopped.")
    finally:
        server.server_close()
        

if __name__ == "__main__":
    main()
