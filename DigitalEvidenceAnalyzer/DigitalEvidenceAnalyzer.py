# DigitalEvidenceAnalyzer.py
# Digital Evidence Analyzer
# Read-only file metadata and integrity analysis
# Python standard library only

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse, parse_qs
import csv
import hashlib
import io
import json
import os
import sqlite3
import threading
import webbrowser


# ============================================================
# CONFIGURATION
# ============================================================

HOST = "127.0.0.1"
PORT = 8002

APP_DIR = Path.home() / ".digital_evidence_analyzer"
DATABASE = APP_DIR / "evidence.db"

MAX_FILES = 5000
MAX_FILE_SIZE = 500 * 1024 * 1024
MAX_SCAN_SECONDS = 60

EXCLUDED_DIRS = {
    ".git", ".venv", "venv", "node_modules",
    "__pycache__", ".idea", ".vscode"
}

FILE_CATEGORIES = {
    "Images": {
        ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp",
        ".tiff", ".tif", ".heic", ".svg"
    },
    "Documents": {
        ".pdf", ".doc", ".docx", ".txt", ".rtf", ".odt",
        ".xls", ".xlsx", ".csv", ".ppt", ".pptx"
    },
    "Audio": {
        ".mp3", ".wav", ".aac", ".flac", ".ogg", ".m4a"
    },
    "Video": {
        ".mp4", ".mov", ".avi", ".mkv", ".webm", ".wmv"
    },
    "Archives": {
        ".zip", ".rar", ".7z", ".tar", ".gz", ".bz2"
    },
    "Executables": {
        ".exe", ".dll", ".sys", ".bat", ".cmd", ".ps1",
        ".sh", ".com", ".msi"
    },
}


# ============================================================
# GENERAL HELPERS
# ============================================================

def now_iso():
    """Return a local timestamp in ISO format."""
    return datetime.now().isoformat(timespec="seconds")


def classify_file(path):
    """Return a human-readable file category."""
    extension = path.suffix.lower()

    for category, extensions in FILE_CATEGORIES.items():
        if extension in extensions:
            return category

    return "Other"


def format_size(size):
    """Convert bytes into a readable size."""
    units = ["B", "KB", "MB", "GB", "TB"]
    value = float(size)

    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024

    return f"{size} B"


def sha256_file(path):
    """Calculate a file's SHA-256 hash without loading it all into memory."""
    digest = hashlib.sha256()

    with path.open("rb") as file:
        while True:
            chunk = file.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)

    return digest.hexdigest()


# ============================================================
# DATABASE AND CASE HISTORY
# ============================================================

class EvidenceStore:
    """Persist case reports and provide previous evidence snapshots."""

    def __init__(self, database=DATABASE):
        APP_DIR.mkdir(parents=True, exist_ok=True)
        self.database = database
        self.initialize()

    def connect(self):
        connection = sqlite3.connect(self.database, timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    def initialize(self):
        with self.connect() as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS scans (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    case_name TEXT NOT NULL,
                    case_notes TEXT NOT NULL,
                    folder_path TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    file_count INTEGER NOT NULL,
                    total_bytes INTEGER NOT NULL,
                    report_json TEXT NOT NULL
                )
            """)

    def save(self, case_name, case_notes, folder_path, report):
        with self.connect() as connection:
            cursor = connection.execute("""
                INSERT INTO scans (
                    case_name, case_notes, folder_path, created_at,
                    file_count, total_bytes, report_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                case_name,
                case_notes,
                folder_path,
                report["createdAt"],
                report["stats"]["files"],
                report["stats"]["totalBytes"],
                json.dumps(report, ensure_ascii=False)
            ))

            scan_id = cursor.lastrowid

            # Retain recent reports to keep local history manageable.
            connection.execute("""
                DELETE FROM scans
                WHERE id NOT IN (
                    SELECT id FROM scans ORDER BY id DESC LIMIT 100
                )
            """)

        return scan_id

    def list_scans(self):
        with self.connect() as connection:
            rows = connection.execute("""
                SELECT id, case_name, case_notes, folder_path,
                       created_at, file_count, total_bytes
                FROM scans
                ORDER BY id DESC
                LIMIT 100
            """).fetchall()

        return [dict(row) for row in rows]

    def get_scan(self, scan_id):
        with self.connect() as connection:
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

    def previous_hashes(self, case_name, folder_path):
        """Find the most recent saved hash for each file in this case."""
        with self.connect() as connection:
            row = connection.execute("""
                SELECT report_json FROM scans
                WHERE case_name = ? AND folder_path = ?
                ORDER BY id DESC LIMIT 1
            """, (case_name, folder_path)).fetchone()

        if not row:
            return {}

        try:
            report = json.loads(row["report_json"])
            return {
                item["relativePath"]: item["sha256"]
                for item in report.get("files", [])
                if item.get("sha256")
            }
        except (json.JSONDecodeError, KeyError, TypeError):
            return {}


# ============================================================
# EVIDENCE SCANNER
# ============================================================

class EvidenceScanner:
    """Collect file metadata and hashes without modifying evidence files."""

    def __init__(self, root, previous_hashes=None):
        self.root = Path(root).expanduser().resolve()
        self.previous_hashes = previous_hashes or {}
        self.files = []
        self.errors = []
        self.skipped = 0
        self.started_at = now_iso()

    def scan(self):
        if not self.root.exists():
            raise ValueError("The selected path does not exist.")

        if not self.root.is_dir():
            raise ValueError("Please select a folder, not a single file.")

        started = datetime.now().timestamp()

        for current_root, directories, filenames in os.walk(
            self.root, followlinks=False
        ):
            current_path = Path(current_root)

            # Avoid traversing common development/cache directories.
            directories[:] = [
                name for name in directories
                if name not in EXCLUDED_DIRS
                and not (current_path / name).is_symlink()
            ]

            for filename in filenames:
                path = current_path / filename

                if path.is_symlink():
                    self.skipped += 1
                    continue

                if len(self.files) >= MAX_FILES:
                    self.errors.append(
                        f"File limit reached: {MAX_FILES} files."
                    )
                    return self.files

                if datetime.now().timestamp() - started > MAX_SCAN_SECONDS:
                    self.errors.append(
                        f"Time limit reached: {MAX_SCAN_SECONDS} seconds."
                    )
                    return self.files

                try:
                    item = self.inspect_file(path)
                    if item:
                        self.files.append(item)
                except (OSError, PermissionError) as error:
                    self.skipped += 1
                    self.errors.append(
                        f"{path.name}: {type(error).__name__}"
                    )

        return self.files

    def inspect_file(self, path):
        """Read metadata, calculate a hash, and compare saved snapshots."""
        try:
            before = path.stat()
        except OSError:
            self.skipped += 1
            return None

        if not path.is_file():
            return None

        if before.st_size > MAX_FILE_SIZE:
            self.skipped += 1
            return {
                "name": path.name,
                "relativePath": path.relative_to(self.root).as_posix(),
                "extension": path.suffix.lower() or "(none)",
                "category": classify_file(path),
                "size": before.st_size,
                "sizeFormatted": format_size(before.st_size),
                "createdAt": datetime.fromtimestamp(
                    before.st_ctime
                ).isoformat(timespec="seconds"),
                "modifiedAt": datetime.fromtimestamp(
                    before.st_mtime
                ).isoformat(timespec="seconds"),
                "sha256": None,
                "integrity": "Not hashed",
                "status": "Skipped: file too large",
                "error": "File exceeds configured hash size limit",
            }

        digest = sha256_file(path)

        # Check whether the file changed while it was being hashed.
        
        after = path.stat()

        if (
            before.st_size != after.st_size
            or before.st_mtime_ns != after.st_mtime_ns
        ):
            integrity = "Unstable during scan"
            status = "Review required"
        else:
            relative_path = path.relative_to(self.root).as_posix()
            previous = self.previous_hashes.get(relative_path)

            if previous is None:
                integrity = "Baseline"
                status = "First recorded snapshot"
            elif previous == digest:
                integrity = "Unchanged"
                status = "Hash matches previous snapshot"
            else:
                integrity = "Changed"
                status = "Hash differs from previous snapshot"

        return {
            "name": path.name,
            "relativePath": path.relative_to(self.root).as_posix(),
            "extension": path.suffix.lower() or "(none)",
            "category": classify_file(path),
            "size": after.st_size,
            "sizeFormatted": format_size(after.st_size),
            "createdAt": datetime.fromtimestamp(
                after.st_ctime
            ).isoformat(timespec="seconds"),
            "modifiedAt": datetime.fromtimestamp(
                after.st_mtime
            ).isoformat(timespec="seconds"),
            "sha256": digest,
            "integrity": integrity,
            "status": status,
            "error": None,
        }


# ============================================================
# REPORT BUILDER
# ============================================================

class ReportBuilder:
    """Generate dashboard metrics and export-friendly report data."""

    @staticmethod
    def build(case_name, case_notes, folder_path, files, scanner):
        total_bytes = sum(item["size"] for item in files)
        categories = {}

        for item in files:
            category = item["category"]
            categories[category] = categories.get(category, 0) + 1

        integrity_counts = {
            "Baseline": 0,
            "Unchanged": 0,
            "Changed": 0,
            "Unstable during scan": 0,
            "Not hashed": 0,
        }

        for item in files:
            integrity = item["integrity"]
            integrity_counts[integrity] = (
                integrity_counts.get(integrity, 0) + 1
            )

        return {
            "application": "Digital Evidence Analyzer",
            "version": "1.0",
            "createdAt": now_iso(),
            "case": {
                "name": case_name,
                "notes": case_notes,
                "folderPath": folder_path,
            },
            "analysis": {
                "mode": "Read-only metadata and SHA-256 analysis",
                "hashAlgorithm": "SHA-256",
                "sourceFilesModified": False,
            },
            "stats": {
                "files": len(files),
                "totalBytes": total_bytes,
                "totalSize": format_size(total_bytes),
                "categories": categories,
                "integrity": integrity_counts,
                "skipped": scanner.skipped,
                "errors": len(scanner.errors),
            },
            "files": files,
            "warnings": scanner.errors[:100],
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
        <title>EvidenceVault | Digital Evidence Analyzer</title>
        <style>
            :root {
                --bg: #0a0d12;
                --panel: #12161e;
                --panel2: #191e28;
                --line: #2a303d;
                --text: #edf1f8;
                --muted: #929caf;
                --orange: #ff8b38;
                --green: #4bd6a0;
                --red: #ff6b7e;
                --yellow: #f2c15d;
                --blue: #8baaff
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
                opacity: .4;
                cursor: wait
            }

            .sidebar {
                position: fixed;
                inset: 0 auto 0 0;
                width: 235px;
                background: #0d1016;
                border-right: 1px solid var(--line);
                padding: 23px 14px;
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
                width: 42px;
                height: 42px;
                background: var(--orange);
                color: #251509;
                border-radius: 13px;
                display: grid;
                place-items: center;
                font-weight: 950;
                font-size: 22px
            }

            .brand-name {
                font-size: 18px;
                font-weight: 850;
                letter-spacing: -.6px
            }

            .brand-sub {
                font-size: 9px;
                letter-spacing: 1.5px;
                color: var(--muted)
            }

            .nav-label {
                padding: 13px 10px 8px;
                font-size: 10px;
                color: #727b8e;
                font-weight: 850;
                letter-spacing: 1.5px;
                text-transform: uppercase
            }

            .nav {
                display: flex;
                align-items: center;
                gap: 11px;
                width: 100%;
                text-align: left;
                border: 0;
                background: transparent;
                color: #a7afbf;
                border-radius: 9px;
                padding: 11px 12px;
                margin: 2px 0;
                transition: .18s
            }

            .nav:hover {
                background: #1b202b;
                color: white
            }

            .nav.active {
                background: #30231b;
                color: #ffb67c
            }

            .nav-icon {
                width: 19px;
                text-align: center;
                font-size: 16px
            }

            .sidebar-foot {
                margin-top: auto;
                background: #141923;
                border: 1px solid var(--line);
                border-radius: 12px;
                padding: 13px
            }

            .sidebar-foot b {
                font-size: 12px
            }

            .sidebar-foot p {
                font-size: 10px;
                color: var(--muted);
                margin: 5px 0 0
            }

            .main {
                margin-left: 235px;
                min-width: 0
            }

            .topbar {
                height: 69px;
                border-bottom: 1px solid var(--line);
                padding: 0 29px;
                display: flex;
                align-items: center;
                justify-content: space-between;
                gap: 12px
            }

            .breadcrumb {
                font-size: 12px;
                color: var(--muted)
            }

            .breadcrumb b {
                color: var(--text)
            }

            .top-right {
                display: flex;
                align-items: center;
                gap: 9px
            }

            .local-tag {
                border: 1px solid var(--line);
                border-radius: 20px;
                padding: 7px 10px;
                font-size: 10px;
                color: var(--muted)
            }

            .content {
                max-width: 1500px;
                padding: 27px 29px 15px;
                margin: auto
            }

            .page {
                display: none
            }

            .page.active {
                display: block;
                animation: fade .2s ease
            }

            @keyframes fade {
                from {
                    opacity: .4;
                    transform: translateY(3px)
                }

                to {
                    opacity: 1;
                    transform: none
                }
            }

            .heading {
                display: flex;
                align-items: flex-start;
                justify-content: space-between;
                gap: 15px;
                flex-wrap: wrap;
                margin-bottom: 22px
            }

            .eyebrow {
                font-size: 10px;
                font-weight: 850;
                letter-spacing: 1.7px;
                text-transform: uppercase;
                color: var(--orange)
            }

            h1 {
                font-size: 28px;
                line-height: 1.2;
                letter-spacing: -1px;
                margin: 6px 0
            }

            .subtitle {
                color: var(--muted);
                font-size: 12px;
                max-width: 700px
            }

            .btn {
                border: 1px solid var(--line);
                border-radius: 9px;
                padding: 10px 13px;
                background: #202532;
                color: var(--text);
                font-weight: 750;
                transition: .16s
            }

            .btn:hover {
                transform: translateY(-1px);
                border-color: #596274
            }

            .btn-primary {
                background: var(--orange);
                border-color: var(--orange);
                color: #241509
            }

            .btn-primary:hover {
                background: #ffa25f
            }

            .btn-quiet {
                background: transparent
            }

            .metrics {
                display: grid;
                grid-template-columns: repeat(4, minmax(0, 1fr));
                gap: 12px
            }

            .metric {
                border: 1px solid var(--line);
                background: var(--panel);
                border-radius: 14px;
                padding: 17px;
                min-width: 0
            }

            .metric-head {
                display: flex;
                justify-content: space-between;
                gap: 8px;
                font-size: 11px;
                color: var(--muted)
            }

            .metric-icon {
                width: 29px;
                height: 29px;
                display: grid;
                place-items: center;
                background: #29221d;
                color: var(--orange);
                border-radius: 9px;
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

            .panel {
                border: 1px solid var(--line);
                background: var(--panel);
                border-radius: 14px;
                padding: 19px;
                min-width: 0
            }

            .panel h2 {
                font-size: 15px;
                margin: 0;
                font-weight: 850
            }

            .panel-desc {
                font-size: 11px;
                color: var(--muted);
                margin: 5px 0 17px
            }

            .workspace {
                display: grid;
                grid-template-columns: 330px minmax(0, 1fr);
                gap: 15px;
                margin-top: 16px;
                align-items: start
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
                background: #0c1016;
                border: 1px solid #303746;
                border-radius: 9px;
                padding: 10px 11px;
                color: var(--text);
                outline: none
            }

            input:focus,
            textarea:focus,
            select:focus {
                border-color: var(--orange);
                box-shadow: 0 0 0 3px #ff8b3818
            }

            textarea {
                min-height: 76px;
                resize: vertical
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
                margin-top: 12px;
                padding: 10px;
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
                background: #14291f;
                color: #9be8c6;
                border: 1px solid #28513e
            }

            .progress {
                height: 3px;
                background: #2a303b;
                border-radius: 5px;
                overflow: hidden;
                display: none;
                margin-top: 13px
            }

            .progress.show {
                display: block
            }

            .progress span {
                display: block;
                height: 100%;
                width: 40%;
                background: var(--orange);
                animation: loading 1s ease-in-out infinite alternate
            }

            @keyframes loading {
                from {
                    transform: translateX(-80%)
                }

                to {
                    transform: translateX(180%)
                }
            }

            .results {
                padding: 0;
                overflow: hidden
            }

            .results-head {
                display: flex;
                justify-content: space-between;
                align-items: center;
                gap: 10px;
                flex-wrap: wrap;
                padding: 18px;
                border-bottom: 1px solid var(--line)
            }

            .result-count {
                font-size: 10px;
                color: var(--muted);
                margin-top: 4px
            }

            .filters {
                display: grid;
                grid-template-columns: minmax(100px, 1fr) 130px 130px;
                gap: 8px;
                padding: 13px 18px
            }

            .filters input,
            .filters select {
                padding: 9px;
                font-size: 11px
            }

            .table-wrap {
                overflow: auto
            }

            table {
                border-collapse: collapse;
                width: 100%;
                min-width: 650px;
                text-align: left
            }

            th {
                background: #171b24;
                color: var(--muted);
                font-size: 9px;
                letter-spacing: .8px;
                text-transform: uppercase;
                font-weight: 850
            }

            th,
            td {
                padding: 12px 13px;
                border-bottom: 1px solid var(--line)
            }

            td {
                font-size: 11px
            }

            tbody tr:hover {
                background: #ffffff05
            }

            .file-name {
                font-weight: 800;
                font-size: 12px;
                overflow-wrap: anywhere
            }

            .file-path {
                font-size: 10px;
                color: var(--muted);
                margin-top: 3px;
                overflow-wrap: anywhere
            }

            .mono {
                font-family: ui-monospace, monospace;
                color: #b5bfd1;
                font-size: 10px
            }

            .badge {
                display: inline-block;
                padding: 4px 7px;
                border-radius: 20px;
                font-size: 9px;
                font-weight: 850;
                white-space: nowrap
            }

            .good {
                background: #17372d;
                color: #8ce6bd
            }

            .warn {
                background: #3c301b;
                color: #f5d17e
            }

            .danger {
                background: #421d27;
                color: #ff9eac
            }

            .neutral {
                background: #262c38;
                color: #c5cedd
            }

            .empty {
                padding: 35px 13px;
                text-align: center;
                color: var(--muted);
                font-size: 11px
            }

            .empty b {
                display: block;
                color: var(--text);
                margin-bottom: 5px;
                font-size: 12px
            }

            .lower-grid {
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 14px;
                margin-top: 14px
            }

            .bar-row {
                display: grid;
                grid-template-columns: 80px minmax(40px, 1fr) 27px;
                gap: 9px;
                align-items: center;
                margin: 16px 0;
                font-size: 11px
            }

            .bar-track {
                height: 7px;
                background: #2a303b;
                border-radius: 6px;
                overflow: hidden
            }

            .bar-fill {
                height: 100%;
                background: var(--orange);
                border-radius: 6px;
                transition: width .4s
            }

            .bar-fill.green {
                background: var(--green)
            }

            .bar-fill.yellow {
                background: var(--yellow)
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

            .action-index {
                width: 24px;
                height: 24px;
                border-radius: 8px;
                background: #2a221c;
                color: var(--orange);
                display: grid;
                place-items: center;
                flex-shrink: 0;
                font-size: 10px;
                font-weight: 850
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
                background: #10141b
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
                background: #202532;
                color: #e2e7f1;
                border-radius: 7px;
                padding: 6px 8px;
                font-size: 10px
            }

            .small-btn:hover {
                border-color: var(--orange)
            }

            .hash-box {
                overflow-wrap: anywhere;
                word-break: break-all;
                background: #0c1016;
                border: 1px solid var(--line);
                border-radius: 8px;
                padding: 10px;
                font: 10px/1.7 ui-monospace, monospace
            }

            .info-grid {
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 12px
            }

            .info-card {
                background: #171b24;
                border: 1px solid var(--line);
                border-radius: 11px;
                padding: 15px
            }

            .info-card b {
                font-size: 12px
            }

            .info-card p {
                font-size: 11px;
                color: var(--muted);
                margin-bottom: 0
            }

            .footer {
                text-align: center;
                color: #6f788b;
                font-size: 10px;
                padding: 24px 0
            }

            .modal-bg {
                display: none;
                position: fixed;
                inset: 0;
                z-index: 20;
                background: #000b;
                padding: 20px;
                place-items: center
            }

            .modal-bg.show {
                display: grid
            }

            .modal {
                width: min(620px, 100%);
                max-height: 85vh;
                overflow: auto;
                background: #151923;
                border: 1px solid var(--line);
                border-radius: 15px;
                padding: 20px
            }

            .modal-head {
                display: flex;
                align-items: center;
                justify-content: space-between;
                gap: 10px
            }

            .modal h2 {
                font-size: 16px;
                margin: 0
            }

            .modal-body {
                margin-top: 17px
            }

            .modal-body .field {
                margin-top: 12px
            }

            @media(max-width:1120px) {
                .sidebar {
                    width: 75px;
                    padding: 20px 9px
                }

                .brand {
                    padding: 0 7px 25px
                }

                .brand-copy,
                .nav-label,
                .nav-text,
                .sidebar-foot {
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
                    padding: 0 14px;
                    height: 60px
                }

                .content {
                    padding: 19px 13px
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

                .lower-grid,
                .info-grid {
                    grid-template-columns: 1fr
                }

                .filters {
                    grid-template-columns: 1fr 1fr;
                    padding: 11px
                }

                .filters input {
                    grid-column: 1/-1
                }

                .results-head {
                    padding: 14px
                }

                .local-tag {
                    display: none
                }

                h1 {
                    font-size: 24px
                }
            }
        </style>
    </head>
    <body>
        <aside class="sidebar">
            <div class="brand">
                <div class="logo">E</div>
                <div class="brand-copy">
                    <div class="brand-name">EvidenceVault <span style="color:var(--orange)">.</span>
                    </div>
                    <div class="brand-sub">DIGITAL FORENSICS</div>
                </div>
            </div>
            <div class="nav-label">Workspace</div>
            <button class="nav active" data-page="dashboard">
                <span class="nav-icon">▦</span>
                <span class="nav-text">Dashboard</span>
            </button>
            <button class="nav" data-page="scan">
                <span class="nav-icon">⌕</span>
                <span class="nav-text">Evidence scan</span>
            </button>
            <button class="nav" data-page="history">
                <span class="nav-icon">◷</span>
                <span class="nav-text">Case history</span>
            </button>
            <div class="nav-label">Reference</div>
            <button class="nav" data-page="about">
                <span class="nav-icon">ⓘ</span>
                <span class="nav-text">Methodology</span>
            </button>
            <div class="sidebar-foot">
                <b>● Local analysis</b>
                <p>Metadata and hash reports remain on this computer.</p>
            </div>
        </aside>
        <div class="main">
            <header class="topbar">
                <div class="breadcrumb">EvidenceVault / <b id="crumb">Dashboard</b>
                </div>
                <div class="top-right">
                    <span class="local-tag">READ-ONLY WORKFLOW</span>
                    <button class="btn btn-primary" onclick="navigate('scan')">+ New scan</button>
                </div>
            </header>
            <div class="content">
                <section class="page active" id="page-dashboard">
                    <div class="heading">
                        <div>
                            <div class="eyebrow">Forensic workspace</div>
                            <h1>Digital evidence overview</h1>
                            <div class="subtitle">Inventory files, calculate SHA-256 hashes, and compare saved snapshots.</div>
                        </div>
                        <button class="btn" onclick="navigate('history')">Case history ↗</button>
                    </div>
                    <div class="metrics">
                        <div class="metric">
                            <div class="metric-head">Evidence files <span class="metric-icon">▤</span>
                            </div>
                            <div class="metric-value" id="m-files">—</div>
                            <div class="metric-foot">Files in latest scan</div>
                        </div>
                        <div class="metric">
                            <div class="metric-head">Total size <span class="metric-icon">◫</span>
                            </div>
                            <div class="metric-value" id="m-size">—</div>
                            <div class="metric-foot">Combined file size</div>
                        </div>
                        <div class="metric">
                            <div class="metric-head">Changed hashes <span class="metric-icon">↻</span>
                            </div>
                            <div class="metric-value" id="m-changed" style="color:var(--red)">—</div>
                            <div class="metric-foot">Compared with prior snapshot</div>
                        </div>
                        <div class="metric">
                            <div class="metric-head">Skipped files <span class="metric-icon">!</span>
                            </div>
                            <div class="metric-value" id="m-skipped">—</div>
                            <div class="metric-foot">Unavailable or over size limit</div>
                        </div>
                    </div>
                    <div class="workspace">
                        <section class="panel">
                            <h2>New evidence scan</h2>
                            <div class="panel-desc">Create a case snapshot from a local folder.</div>
                            <label class="field" for="caseName">Case name</label>
                            <input id="caseName" placeholder="e.g. Case-2026-001">
                            <label class="field" for="caseNotes">Case notes (optional)</label>
                            <textarea id="caseNotes" placeholder="Brief case context or collection notes..."></textarea>
                            <label class="field" for="folderPath">Evidence folder path</label>
                            <input id="folderPath" placeholder="D:\Evidence\Case-001">
                            <div class="hint">Enter the full folder path on the computer running this app.</div>
                            <div class="actions">
                                <button class="btn btn-primary" id="scanBtn" onclick="runScan()">Analyze folder ↗</button>
                                <button class="btn" onclick="loadDemo()">Demo report</button>
                            </div>
                            <div class="progress" id="progress">
                                <span></span>
                            </div>
                            <div class="notice" id="notice" role="status"></div>
                        </section>
                        <section class="panel results">
                            <div class="results-head">
                                <div>
                                    <h2>Evidence inventory</h2>
                                    <div class="result-count" id="resultCount">No report loaded</div>
                                </div>
                                <div class="actions" style="margin:0">
                                    <button class="btn" id="jsonBtn" onclick="exportReport('json')" disabled>JSON ↓</button>
                                    <button class="btn" id="csvBtn" onclick="exportReport('csv')" disabled>CSV ↓</button>
                                </div>
                            </div>
                            <div class="filters">
                                <input id="search" placeholder="Search name, path or hash..." oninput="renderFiles()">
                                <select id="categoryFilter" onchange="renderFiles()">
                                    <option value="all">All file types</option>
                                </select>
                                <select id="integrityFilter" onchange="renderFiles()">
                                    <option value="all">All statuses</option>
                                    <option>Baseline</option>
                                    <option>Unchanged</option>
                                    <option>Changed</option>
                                    <option>Unstable during scan</option>
                                    <option>Not hashed</option>
                                </select>
                            </div>
                            <div class="table-wrap">
                                <table>
                                    <thead>
                                        <tr>
                                            <th>Evidence file</th>
                                            <th>Type</th>
                                            <th>Size</th>
                                            <th>Integrity</th>
                                            <th></th>
                                        </tr>
                                    </thead>
                                    <tbody id="fileRows">
                                        <tr>
                                            <td colspan="5">
                                                <div class="empty">
                                                    <b>No evidence loaded</b>Scan a folder to populate the inventory.
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
                            <h2>File type distribution</h2>
                            <div class="panel-desc">Number of files grouped by category</div>
                            <div id="categories">
                                <div class="empty">Scan a folder to view statistics.</div>
                            </div>
                        </section>
                        <section class="panel">
                            <h2>Integrity summary</h2>
                            <div class="panel-desc">Hash comparisons with the last saved snapshot</div>
                            <div id="integritySummary">
                                <div class="empty">No report available.</div>
                            </div>
                        </section>
                    </div>
                </section>
                <section class="page" id="page-scan">
                    <div class="heading">
                        <div>
                            <div class="eyebrow">Collection workspace</div>
                            <h1>Analyze evidence folder</h1>
                            <div class="subtitle">Record metadata and file hashes for a folder you are authorized to examine.</div>
                        </div>
                    </div>
                    <section class="panel" style="max-width:760px">
                        <h2>Scan configuration</h2>
                        <div class="panel-desc">Files are read for metadata and hashing only.</div>
                        <label class="field" for="caseName2">Case name</label>
                        <input id="caseName2" placeholder="Case-2026-001">
                        <label class="field" for="caseNotes2">Case notes</label>
                        <textarea id="caseNotes2" placeholder="Optional collection notes"></textarea>
                        <label class="field" for="folderPath2">Folder path</label>
                        <input id="folderPath2" placeholder="D:\Evidence\Case-001">
                        <div class="actions">
                            <button class="btn btn-primary" onclick="copyScanFields();runScan()">Start analysis ↗</button>
                            <button class="btn" onclick="copyScanFields();loadDemo()">Preview demo</button>
                        </div>
                    </section>
                </section>
                <section class="page" id="page-history">
                    <div class="heading">
                        <div>
                            <div class="eyebrow">Saved snapshots</div>
                            <h1>Case history</h1>
                            <div class="subtitle">Open or remove reports stored in the local database.</div>
                        </div>
                        <button class="btn" onclick="loadHistory()">↻ Refresh</button>
                    </div>
                    <section class="panel">
                        <div id="historyList" class="history-list">
                            <div class="empty">Loading history...</div>
                        </div>
                    </section>
                </section>
                <section class="page" id="page-about">
                    <div class="heading">
                        <div>
                            <div class="eyebrow">Methodology</div>
                            <h1>Analysis and limitations</h1>
                            <div class="subtitle">Understand what the current tool records—and what it does not establish.</div>
                        </div>
                    </div>
                    <div class="info-grid">
                        <div class="info-card">
                            <b>01 · File inventory</b>
                            <p>Records file paths relative to the selected root, extension, size, timestamps and category.</p>
                        </div>
                        <div class="info-card">
                            <b>02 · SHA-256 hashing</b>
                            <p>Computes a cryptographic hash for each supported-size file without loading the whole file into memory.</p>
                        </div>
                        <div class="info-card">
                            <b>03 · Snapshot comparison</b>
                            <p>Compares the current hash with the most recent saved scan for the same case and folder.</p>
                        </div>
                        <div class="info-card">
                            <b>04 · Report export</b>
                            <p>Exports inventory and metadata to JSON or CSV for further review.</p>
                        </div>
                    </div>
                    <section class="panel" style="margin-top:14px">
                        <h2>Important forensic limitations</h2>
                        <p class="subtitle" style="line-height:1.9;margin-top:12px"> A matching SHA-256 hash indicates that the file content matches the saved hash value. It does not prove who created the file, when it was originally created, or whether the first snapshot was trustworthy. <br>
                            <br> File timestamps may be changed by the operating system or copied files. This tool does not acquire disk images, recover deleted data, parse application artifacts, verify digital signatures, or provide a legally validated chain of custody. <br>
                            <br> For evidentiary work, use validated forensic procedures, preserve originals, document acquisition steps, and store reports securely.
                        </p>
                    </section>
                </section>
                <footer class="footer">EvidenceVault · Local file analysis · Preserve originals and document every collection step</footer>
            </div>
        </div>
        <div class="modal-bg" id="modal" onclick="if(event.target===this)closeModal()">
            <div class="modal">
                <div class="modal-head">
                    <h2 id="modalTitle">Evidence details</h2>
                    <button class="btn" onclick="closeModal()">✕</button>
                </div>
                <div class="modal-body" id="modalBody"></div>
            </div>
        </div>
        <script>
            let report = null;
            let busy = false;
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
                document.querySelectorAll(".page").forEach(el => el.classList.remove("active"));
                $("page-" + page).classList.add("active");
                document.querySelectorAll(".nav").forEach(el => el.classList.toggle("active", el.dataset.page === page));
                const names = {
                    dashboard: "Dashboard",
                    scan: "Evidence scan",
                    history: "Case history",
                    about: "Methodology"
                };
                $("crumb").textContent = names[page] || "Dashboard";
                if (page === "history") loadHistory();
            }
            document.querySelectorAll(".nav").forEach(button => button.addEventListener("click", () => navigate(button.dataset.page)));

            function copyScanFields() {
                $("caseName").value = $("caseName2").value;
                $("caseNotes").value = $("caseNotes2").value;
                $("folderPath").value = $("folderPath2").value;
            }
            async function api(url, options = {}) {
                const response = await fetch(url, options);
                const data = await response.json();
                if (!response.ok) throw new Error(data.error || "Request failed");
                return data;
            }
            async function runScan() {
                if (busy) return;
                const caseName = $("caseName").value.trim();
                const caseNotes = $("caseNotes").value.trim();
                const folderPath = $("folderPath").value.trim();
                if (!caseName || !folderPath) {
                    notify("Enter a case name and a valid evidence folder path.", "error");
                    return;
                }
                busy = true;
                $("scanBtn").disabled = true;
                $("scanBtn").textContent = "Analyzing...";
                $("progress").classList.add("show");
                notify("Reading metadata and calculating SHA-256 hashes. Large folders may take time.");
                try {
                    report = await api("/api/scan", {
                        method: "POST",
                        headers: {
                            "Content-Type": "application/json"
                        },
                        body: JSON.stringify({
                            caseName,
                            caseNotes,
                            folderPath
                        })
                    });
                    updateDashboard();
                    $("jsonBtn").disabled = false;
                    $("csvBtn").disabled = false;
                    notify(report.summary);
                    navigate("dashboard");
                } catch (error) {
                    notify(error.message, "error");
                } finally {
                    busy = false;
                    $("scanBtn").disabled = false;
                    $("scanBtn").textContent = "Analyze folder ↗";
                    $("progress").classList.remove("show");
                }
            }

            function integrityClass(status) {
                if (status === "Unchanged") return "good";
                if (status === "Changed" || status === "Unstable during scan") return "danger";
                if (status === "Baseline") return "warn";
                return "neutral";
            }

            function renderFiles() {
                if (!report) return;
                const query = $("search").value.toLowerCase().trim();
                const category = $("categoryFilter").value;
                const integrity = $("integrityFilter").value;
                const filtered = report.files.filter(item => (category === "all" || item.category === category) && (integrity === "all" || item.integrity === integrity) && (item.name + " " + item.relativePath + " " + (item.sha256 || "") + " " + item.category).toLowerCase().includes(query));
                $("resultCount").textContent = `${filtered.length} shown · ${report.files.length} total evidence files`;
                $("fileRows").innerHTML = filtered.length ? filtered.map(item => {
                    const index = report.files.indexOf(item);
                    return `
                        <tr>
                            <td>
                                <div class="file-name">${esc(item.name)}</div>
                                <div class="file-path">${esc(item.relativePath)}</div>
                            </td>
                            <td>${esc(item.category)}</td>
                            <td>${esc(item.sizeFormatted)}</td>
                            <td>
                                <span class="badge ${integrityClass(item.integrity)}">${esc(item.integrity)}</span>
                            </td>
                            <td>
                                <button class="small-btn" onclick="showEvidence(${index})">Details</button>
                            </td>
                        </tr>`;
                }).join("") : `
                    <tr>
                        <td colspan="5">
                            <div class="empty">
                                <b>No matching evidence</b>Change the search or filters.
                            </div>
                        </td>
                    </tr>`;
            }

            function showEvidence(index) {
                const item = report?.files[index];
                if (!item) return;
                $("modalTitle").textContent = item.name;
                $("modalBody").innerHTML = `
  
                    <p>
                        <span class="badge ${integrityClass(item.integrity)}">${esc(item.integrity)}</span>
                        <span class="badge neutral">${esc(item.category)}</span>
                    </p>
                    <div class="field">Relative path</div>
                    <div class="hash-box">${esc(item.relativePath)}</div>
                    <div class="field">SHA-256</div>
                    <div class="hash-box">${esc(item.sha256||"Not calculated")}</div>
                    <div class="field">Metadata</div>
                    <div class="hash-box">${esc(JSON.stringify({
   extension:item.extension,size:item.size,sizeFormatted:item.sizeFormatted,
   createdAt:item.createdAt,modifiedAt:item.modifiedAt,status:item.status,error:item.error
  },null,2))}</div>`;
                $("modal").classList.add("show");
            }

            function closeModal() {
                $("modal").classList.remove("show");
            }

            function updateDashboard() {
                const s = report.stats;
                $("m-files").textContent = s.files;
                $("m-size").textContent = s.totalSize;
                $("m-changed").textContent = s.integrity.Changed || 0;
                $("m-skipped").textContent = s.skipped;
                renderFiles();
                const categoryEntries = Object.entries(s.categories).sort((a, b) => b[1] - a[1]);
                const maxCategory = Math.max(1, ...categoryEntries.map(item => item[1]));
                $("categories").innerHTML = categoryEntries.length ? categoryEntries.map(([name, count]) => `
  
                    <div class="bar-row">
                        <span>${esc(name)}</span>
                        <div class="bar-track">
                            <div class="bar-fill" style="width:${count/maxCategory*100}%"></div>
                        </div>
                        <span class="bar-number">${count}</span>
                    </div>`).join("") : ' < div class = "empty" > No files found. < /div>';
                const integrity = s.integrity;
                const entries = [
                    ["Baseline", integrity.Baseline || 0, ""],
                    ["Unchanged", integrity.Unchanged || 0, "green"],
                    ["Changed", integrity.Changed || 0, ""],
                    ["Unstable", integrity["Unstable during scan"] || 0, "yellow"],
                    ["Not hashed", integrity["Not hashed"] || 0, "yellow"]
                ];
                const max = Math.max(1, ...entries.map(item => item[1]));
                $("integritySummary").innerHTML = entries.map(([name, count, color]) => `
  
                    <div class="bar-row">
                        <span>${esc(name)}</span>
                        <div class="bar-track">
                            <div class="bar-fill ${color}" style="width:${count/max*100}%"></div>
                        </div>
                        <span class="bar-number">${count}</span>
                    </div>`).join("");
                const select = $("categoryFilter");
                const selected = select.value;
                select.innerHTML = ' < option value = "all" > All file types < /option>'+
                Object.keys(s.categories).sort().map(name => `
					<option value="${esc(name)}">${esc(name)}</option>`).join("");
                if ([...select.options].some(option => option.value === selected)) select.value = selected;
            }

            function exportReport(format) {
                if (!report) return;
                let content, mime, filename;
                if (format === "json") {
                    content = JSON.stringify(report, null, 2);
                    mime = "application/json";
                    filename = "digital-evidence-report.json";
                } else {
                    const rows = report.files;
                    const headers = ["name", "relativePath", "category", "extension", "size", "sizeFormatted", "createdAt", "modifiedAt", "sha256", "integrity", "status"];
                    const quote = value => '"' + String(value ?? "").replace(/"/g, '""') + '"';
                    content = [headers.join(","), ...rows.map(row => headers.map(key => quote(row[key])).join(","))].join("\r\n");
                    mime = "text/csv;charset=utf-8";
                    filename = "digital-evidence-inventory.csv";
                }
                const blob = new Blob([content], {
                    type: mime
                });
                const url = URL.createObjectURL(blob);
                const link = document.createElement("a");
                link.href = url;
                link.download = filename;
                link.click();
                setTimeout(() => URL.revokeObjectURL(url), 1000);
            }

            function loadDemo() {
                const files = [
                    ["meeting-notes.txt", "Documents", 2300, "Baseline"],
                    ["photo-01.jpg", "Images", 180000, "Baseline"],
                    ["recording.wav", "Audio", 450000, "Unchanged"],
                    ["archive.zip", "Archives", 2000000, "Changed"],
                    ["report.pdf", "Documents", 42000, "Baseline"]
                ];
                report = {
                    application: "Digital Evidence Analyzer",
                    createdAt: new Date().toISOString(),
                    case: {
                        name: "DEMO-CASE-001",
                        notes: "Illustrative sample only",
                        folderPath: "Demo folder"
                    },
                    stats: {
                        files: 5,
                        totalBytes: 2672300,
                        totalSize: "2.5 MB",
                        categories: {
                            Documents: 2,
                            Images: 1,
                            Audio: 1,
                            Archives: 1
                        },
                        integrity: {
                            Baseline: 3,
                            Unchanged: 1,
                            Changed: 1,
                            "Unstable during scan": 0,
                            "Not hashed": 0
                        },
                        skipped: 0,
                        errors: 0
                    },
                    files: files.map(([name, category, size, integrity], i) => ({
                        name,
                        relativePath: name,
                        category,
                        extension: name.slice(name.lastIndexOf(".")),
                        size,
                        sizeFormatted: size + " B",
                        createdAt: "Demo timestamp",
                        modifiedAt: "Demo timestamp",
                        sha256: "DEMO-ONLY-NOT-A-REAL-HASH-" + String(i + 1).padStart(3, "0"),
                        integrity,
                        status: "Illustrative sample data",
                        error: null
                    })),
                    warnings: ["This is demonstration data and does not represent real evidence."]
                };
                updateDashboard();
                $("jsonBtn").disabled = false;
                $("csvBtn").disabled = false;
                notify("Demo report loaded. The hashes and timestamps are illustrative only.");
                navigate("dashboard");
            }
            async function loadHistory() {
                const container = $("historyList");
                container.innerHTML = ' < div class = "empty" > Loading
                case history... < /div>';
                try {
                    const scans = await api("/api/history");
                    if (!scans.length) {
                        container.innerHTML = ' < div class = "empty" > < b > No saved scans < /b>Your reports will appear here. < /div>';
                        return;
                    }
                    container.innerHTML = scans.map(item => `
   
                        <div class="history-item">
                            <div>
                                <b>${esc(item.case_name)}</b>
                                <div class="history-meta">${esc(item.created_at)} · ${item.file_count} files · ${esc(item.folder_path)}</div>
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
                    const result = await api("/api/history?id=" + id);
                    report = result.report;
                    updateDashboard();
                    $("jsonBtn").disabled = false;
                    $("csvBtn").disabled = false;
                    navigate("dashboard");
                    notify("Saved report loaded. It represents a previous snapshot, not a new scan.");
                } catch (error) {
                    alert(error.message);
                }
            }
            async function deleteHistory(id) {
                if (!confirm("Delete this saved report?")) return;
                try {
                    await api("/api/history?id=" + id, {
                        method: "DELETE"
                    });
                    loadHistory();
                } catch (error) {
                    alert(error.message);
                }
            }
            $("folderPath").addEventListener("keydown", event => {
                if (event.key === "Enter") runScan();
            });
        </script>
    </body>
</html>
"""


# ============================================================
# HTTP SERVER AND API
# ============================================================

class EvidenceHandler(BaseHTTPRequestHandler):
    store = EvidenceStore()

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

        if length <= 0 or length > 1_000_000:
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
            params = parse_qs(parsed.query)

            if "id" in params:
                try:
                    scan_id = int(params["id"][0])
                except ValueError:
                    self.send_json({"error": "Invalid report ID."}, 400)
                    return

                result = self.store.get_scan(scan_id)
                if not result:
                    self.send_json({"error": "Report not found."}, 404)
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
            case_name = payload.get("caseName", "")
            case_notes = payload.get("caseNotes", "")
            folder_path = payload.get("folderPath", "")

            if not all(isinstance(value, str) for value in (
                case_name, case_notes, folder_path
            )):
                self.send_json({"error": "All fields must be text."}, 400)
                return

            case_name = case_name.strip()
            case_notes = case_notes.strip()
            folder_path = folder_path.strip()

            if not case_name or not folder_path:
                self.send_json(
                    {"error": "Case name and folder path are required."}, 400
                )
                return

            root = Path(folder_path).expanduser().resolve()

            if not root.exists() or not root.is_dir():
                self.send_json(
                    {"error": "The selected folder does not exist."}, 400
                )
                return

            previous = self.store.previous_hashes(
                case_name, str(root)
            )

            scanner = EvidenceScanner(root, previous)
            files = scanner.scan()

            report = ReportBuilder.build(
                case_name, case_notes, str(root), files, scanner
            )

            scan_id = self.store.save(
                case_name, case_notes, str(root), report
            )
            report["scanId"] = scan_id
            report["summary"] = (
                f"Scan complete: {len(files)} files inventoried, "
                f"{report['stats']['integrity']['Changed']} changed hashes."
            )

            self.send_json(report)

        except ValueError as error:
            self.send_json({"error": str(error)}, 400)
        except (OSError, sqlite3.Error):
            self.send_json(
                {"error": "File access or local database error."}, 500
            )
        except Exception:
            self.send_json(
                {"error": "Unexpected analysis error. Check the folder and permissions."},
                500
            )

    def do_DELETE(self):
        parsed = urlparse(self.path)

        if parsed.path != "/api/history":
            self.send_json({"error": "Endpoint not found."}, 404)
            return

        params = parse_qs(parsed.query)

        try:
            scan_id = int(params.get("id", [""])[0])
        except ValueError:
            self.send_json({"error": "Invalid report ID."}, 400)
            return

        if self.store.delete_scan(scan_id):
            self.send_json({"deleted": True})
        else:
            self.send_json({"error": "Report not found."}, 404)

    def log_message(self, format, *args):
        # Keep the terminal output clean.
        return


# ============================================================
# APPLICATION ENTRY POINT
# ============================================================

def main():
    server = ThreadingHTTPServer((HOST, PORT), EvidenceHandler)

    print("=" * 58)
    print("  DIGITAL EVIDENCE ANALYZER")
    print("=" * 58)
    print(f"  Dashboard : http://{HOST}:{PORT}")
    print(f"  Database  : {DATABASE}")
    print("  Mode      : Read-only metadata and hashing")
    print("  Stop      : Ctrl + C")
    print("=" * 58)

    threading.Timer(
        0.8,
        lambda: webbrowser.open(f"http://{HOST}:{PORT}")
    ).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nDigital Evidence Analyzer stopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
