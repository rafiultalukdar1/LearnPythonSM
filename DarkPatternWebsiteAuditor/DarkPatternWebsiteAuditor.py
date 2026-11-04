
import json
import csv
import io
import re
import uuid
import sqlite3
import threading
import urllib.request
import urllib.error
from datetime import datetime
from html.parser import HTMLParser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

HOST = "127.0.0.1"
PORT = 8005
DB = "dark_pattern_auditor.db"

# =====================================================
# DATABASE
# =====================================================

def database():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with database() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS audits (
                id TEXT PRIMARY KEY,
                url TEXT,
                score INTEGER,
                risk TEXT,
                findings TEXT,
                stats TEXT,
                created_at TEXT
            )
        """)


# =====================================================
# HTML PARSER
# =====================================================

class PageParser(HTMLParser):

    def __init__(self):
        super().__init__()
        self.text = []
        self.elements = []
        self.buttons = []
        self.links = 0
        self.forms = 0
        self.inputs = 0
        self.current_button = None
        self.current_text = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)

        self.elements.append((tag, attrs))

        if tag == "a":
            self.links += 1

        if tag == "form":
            self.forms += 1

        if tag == "input":
            self.inputs += 1

        if tag == "button":
            self.current_button = []

    def handle_endtag(self, tag):
        if tag == "button" and self.current_button is not None:
            self.buttons.append(" ".join(self.current_button))
            self.current_button = None

    def handle_data(self, data):
        value = data.strip()

        if value:
            self.text.append(value)

            if self.current_button is not None:
                self.current_button.append(value)


# =====================================================
# WEBSITE FETCHER
# =====================================================

def fetch_page(url):

    parsed = urlparse(url)

    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValueError("Enter a valid HTTP or HTTPS website URL.")

    if parsed.username or parsed.password:
        raise ValueError("URLs containing credentials are not supported.")

    # Basic protection against local/private network targets.
    import ipaddress
    import socket

    try:
        addresses = socket.getaddrinfo(
            parsed.hostname, None, type=socket.SOCK_STREAM
        )
    except socket.gaierror:
        raise ValueError("Could not resolve the website hostname.")

    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if not ip.is_global:
            raise ValueError("Private and local network targets are not allowed.")

    class SafeRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            target = urlparse(newurl)
            if target.scheme not in ("http", "https"):
                raise ValueError("Unsupported redirect destination.")
            return super().redirect_request(req, fp, code, msg, headers, newurl)

    opener = urllib.request.build_opener(SafeRedirect)

    request = urllib.request.Request(
        url,
        headers={"User-Agent": "PatternLensAuditor/1.0"}
    )

    with opener.open(request, timeout=15) as response:

        final_url = response.geturl()
        content_type = response.headers.get("Content-Type", "")

        if "text/html" not in content_type.lower():
            raise ValueError("The target did not return HTML content.")

        if not urlparse(final_url).hostname:
            raise ValueError("Invalid final website URL.")

        raw = response.read(2_000_000)
        encoding = response.headers.get_content_charset() or "utf-8"

        return raw.decode(encoding, errors="replace"), final_url


# =====================================================
# DARK PATTERN DETECTION ENGINE
# =====================================================

PATTERNS = [

    {
        "name": "Fake Urgency",
        "category": "Manipulation",
        "severity": "High",
        "icon": "⏱",
        "patterns": [
            r"only\s+\d+\s+(minutes?|hours?|days?)\s+left",
            r"limited\s+time\s+offer",
            r"act\s+now",
            r"offer\s+ends\s+soon",
            r"expires\s+in",
            r"last\s+chance"
        ],
        "recommendation": "Verify that deadlines and countdowns represent genuine offers."
    },

    {
        "name": "False Scarcity",
        "category": "Manipulation",
        "severity": "High",
        "icon": "⚠",
        "patterns": [
            r"only\s+\d+\s+left",
            r"almost\s+sold\s+out",
            r"selling\s+fast",
            r"few\s+items\s+remaining",
            r"limited\s+stock"
        ],
        "recommendation": "Display accurate inventory and availability information."
    },

    {
        "name": "Confirm Shaming",
        "category": "User Control",
        "severity": "Medium",
        "icon": "◈",
        "patterns": [
            r"no\s+thanks,?\s+i\s+don't\s+want",
            r"i\s+don't\s+care\s+about",
            r"i\s+prefer\s+to\s+miss\s+out",
            r"no,?\s+i\s+like\s+paying\s+more"
        ],
        "recommendation": "Use neutral language for accepting and declining choices."
    },

    {
        "name": "Hidden Fee Indicators",
        "category": "Pricing",
        "severity": "High",
        "icon": "$",
        "patterns": [
            r"service\s+fee",
            r"processing\s+fee",
            r"handling\s+fee",
            r"convenience\s+fee",
            r"additional\s+charges",
            r"extra\s+charges"
        ],
        "recommendation": "Disclose mandatory charges before checkout."
    },

    {
        "name": "Subscription Trap Indicators",
        "category": "Subscription",
        "severity": "High",
        "icon": "↻",
        "patterns": [
            r"automatically\s+renew",
            r"auto[\s-]?renewal",
            r"recurring\s+payment",
            r"charged\s+automatically",
            r"subscription\s+continues"
        ],
        "recommendation": "Clearly explain billing, renewal and cancellation terms."
    },

    {
        "name": "Misleading Discount",
        "category": "Pricing",
        "severity": "Medium",
        "icon": "%",
        "patterns": [
            r"up\s+to\s+\d+%\s+off",
            r"save\s+\d+%",
            r"original\s+price",
            r"was\s+\$[\d,.]+"
        ],
        "recommendation": "Make reference prices and discount calculations verifiable."
    },

    {
        "name": "Forced Action Indicators",
        "category": "User Control",
        "severity": "Medium",
        "icon": "→",
        "patterns": [
            r"sign\s+up\s+to\s+continue",
            r"subscribe\s+to\s+continue",
            r"create\s+an\s+account\s+to\s+view",
            r"register\s+to\s+continue"
        ],
        "recommendation": "Avoid unnecessary registration requirements."
    }
]


def add_finding(results, name, category, severity, icon, evidence, description, recommendation):

    results.append({
        "id": str(uuid.uuid4())[:8],
        "name": name,
        "category": category,
        "severity": severity,
        "icon": icon,
        "evidence": evidence[:250],
        "description": description,
        "recommendation": recommendation
    })


def analyze_website(url, html):

    parser = PageParser()
    parser.feed(html)

    text = " ".join(parser.text)
    searchable = text.lower()

    findings = []

    # Text-based detection
    for pattern in PATTERNS:

        matches = []

        for expression in pattern["patterns"]:
            found = re.search(expression, searchable, re.I)

            if found:
                matches.append(found.group(0))

        if matches:

            evidence = ", ".join(dict.fromkeys(matches))

            add_finding(
                findings,
                pattern["name"],
                pattern["category"],
                pattern["severity"],
                pattern["icon"],
                evidence,
                "Potentially suspicious language was detected in the accessible page text.",
                pattern["recommendation"]
            )

    # Cookie consent analysis
    cookie_text = " ".join([
        item for item in parser.text
        if any(word in item.lower() for word in ["cookie", "consent", "tracking"])
    ]).lower()

    if cookie_text:

        accepts = any(x in cookie_text for x in ["accept", "agree", "allow"])
        rejects = any(x in cookie_text for x in ["reject", "decline", "deny"])

        if accepts and not rejects:

            add_finding(
                findings,
                "Cookie Choice Imbalance",
                "Privacy",
                "Medium",
                "◉",
                "Acceptance language found; rejection language not detected.",
                "The accessible cookie-related text may not present balanced choices.",
                "Offer clear and accessible accept and reject options."
            )

    # Button choice analysis
    button_text = " ".join(parser.buttons).lower()

    positive = ["accept", "allow", "agree", "continue", "subscribe"]
    negative = ["reject", "decline", "cancel", "no thanks"]

    positive_count = sum(button_text.count(x) for x in positive)
    negative_count = sum(button_text.count(x) for x in negative)

    if positive_count and not negative_count:

        add_finding(
            findings,
            "One-Sided Button Choices",
            "User Control",
            "Low",
            "◈",
            "Positive action wording found without obvious alternative wording.",
            "Button labels may provide an imbalanced choice experience.",
            "Provide clearly labelled alternatives for both actions."
        )

    # Hidden element indicators
    hidden = sum(
        1 for tag, attrs in parser.elements
        if attrs.get("type", "").lower() == "hidden"
        or attrs.get("aria-hidden", "").lower() == "true"
        or "display:none" in attrs.get("style", "").replace(" ", "").lower()
    )

    if hidden:

        add_finding(
            findings,
            "Hidden Element Indicators",
            "Transparency",
            "Low",
            "◉",
            f"{hidden} potentially hidden elements detected.",
            "Some elements are hidden from normal presentation.",
            "Inspect hidden elements to ensure important choices are not concealed."
        )

    # Risk score
    weights = {"High": 20, "Medium": 10, "Low": 5}

    score = min(
        100,
        sum(weights[x["severity"]] for x in findings)
    )

    risk = (
        "Critical" if score >= 80 else
        "High" if score >= 60 else
        "Moderate" if score >= 30 else
        "Low" if score > 0 else
        "Minimal"
    )

    severity = {
        "High": 0,
        "Medium": 0,
        "Low": 0
    }

    categories = {}

    for item in findings:
        severity[item["severity"]] += 1
        categories[item["category"]] = categories.get(item["category"], 0) + 1

    stats = {
        "characters": len(text),
        "buttons": len(parser.buttons),
        "links": parser.links,
        "forms": parser.forms,
        "inputs": parser.inputs,
        "hidden": hidden
    }

    return {
        "id": str(uuid.uuid4())[:8],
        "url": url,
        "score": score,
        "risk": risk,
        "findings": findings,
        "total": len(findings),
        "severity": severity,
        "categories": categories,
        "stats": stats,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }


# =====================================================
# AUDIT SERVICE
# =====================================================

def save_audit(result):

    with database() as conn:
        conn.execute("""
            INSERT INTO audits
            (id, url, score, risk, findings, stats, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            result["id"],
            result["url"],
            result["score"],
            result["risk"],
            json.dumps(result["findings"]),
            json.dumps(result["stats"]),
            result["created_at"]
        ))


def run_audit(url):

    page, final_url = fetch_page(url)

    result = analyze_website(final_url, page)

    save_audit(result)

    return result


# =====================================================
# DASHBOARD HTML
# =====================================================

HTML = r"""

<!DOCTYPE html>
<html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>PatternLens | Dark Pattern Auditor</title>
        <style>
            @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700;800&family=Space+Grotesk:wght@500;600;700&display=swap');

            :root {
                --bg: #0b1220;
                --sidebar: #101b2d;
                --card: #142137;
                --card2: #1b2b42;
                --border: #293d56;
                --text: #f0f6ff;
                --muted: #91a4ba;
                --teal: #27ddc2;
                --blue: #61aaff;
                --orange: #ff9d68;
                --red: #ff637c;
                --yellow: #ffd16a;
                --green: #5de0a7;
            }

            * {
                box-sizing: border-box;
                margin: 0;
                padding: 0
            }

            body {
                background: var(--bg);
                color: var(--text);
                font-family: 'DM Sans', sans-serif
            }

            button,
            input {
                font: inherit
            }

            .app {
                display: grid;
                grid-template-columns: 250px minmax(0, 1fr);
                min-height: 100vh
            }

            .sidebar {
                background: var(--sidebar);
                border-right: 1px solid var(--border);
                padding: 25px 16px;
                display: flex;
                flex-direction: column;
                position: sticky;
                top: 0;
                height: 100vh;
            }

            .brand {
                display: flex;
                align-items: center;
                gap: 11px;
                font: 700 21px 'Space Grotesk';
                padding: 4px 8px 38px;
            }

            .logo {
                width: 40px;
                height: 40px;
                border-radius: 12px;
                background: linear-gradient(135deg, var(--teal), #4388aa);
                color: #081a24;
                display: grid;
                place-items: center;
                font-size: 23px;
            }

            .nav-label {
                font-size: 10px;
                letter-spacing: 1.8px;
                color: #71859e;
                margin: 17px 10px 10px;
                font-weight: 800
            }

            .nav {
                padding: 12px;
                border-radius: 9px;
                color: var(--muted);
                font-size: 12px;
                margin-bottom: 5px;
                cursor: pointer
            }

            .nav.active,
            .nav:hover {
                background: #1c3945;
                color: var(--teal)
            }

            .nav span {
                display: inline-block;
                width: 27px
            }

            .sidebar-bottom {
                margin-top: auto
            }

            .system {
                border: 1px solid #28564e;
                background: #15322f;
                padding: 15px;
                border-radius: 12px;
            }

            .system strong {
                font-size: 11px;
                color: var(--teal)
            }

            .system p {
                font-size: 10px;
                color: #9ab4ae;
                line-height: 1.7;
                margin-top: 7px
            }

            .online {
                font-size: 10px;
                color: var(--green);
                margin-top: 12px
            }

            main {
                width: 100%;
                max-width: 1600px;
                margin: auto;
                padding: 30px 34px 45px;
                min-width: 0
            }

            .topbar {
                display: flex;
                justify-content: space-between;
                align-items: center;
                gap: 15px;
                margin-bottom: 28px
            }

            h1 {
                font: 700 25px 'Space Grotesk'
            }

            .subtitle {
                color: var(--muted);
                font-size: 11px;
                margin-top: 6px
            }

            .status {
                padding: 9px 12px;
                border-radius: 30px;
                background: #14312f;
                color: var(--teal);
                font-size: 10px;
                border: 1px solid #28584e
            }

            .hero {
                background: radial-gradient(circle at 85% 20%, #1b6b5d44, transparent 35%), linear-gradient(110deg, #172c40, #15333b);
                border: 1px solid #2d6157;
                border-radius: 16px;
                padding: 25px;
                margin-bottom: 18px;
            }

            .eyebrow {
                color: var(--teal);
                font-size: 10px;
                letter-spacing: 1.8px;
                font-weight: 800
            }

            .hero h2 {
                font: 700 23px 'Space Grotesk';
                margin: 10px 0
            }

            .hero p {
                color: #a6c0c4;
                font-size: 12px
            }

            .search {
                display: flex;
                gap: 10px;
                margin-top: 22px
            }

            input {
                background: #0e1a2b;
                color: white;
                border: 1px solid #314b61;
                padding: 14px;
                border-radius: 9px;
                outline: none;
                min-width: 0;
            }

            input:focus {
                border-color: var(--teal)
            }

            .search input {
                flex: 1
            }

            .btn {
                background: var(--teal);
                color: #081c21;
                border: 0;
                border-radius: 9px;
                padding: 0 20px;
                font-weight: 800;
                cursor: pointer;
            }

            .btn:disabled {
                opacity: .5;
                cursor: wait
            }

            .message {
                font-size: 11px;
                color: var(--muted);
                margin-top: 11px
            }

            .message.error {
                color: var(--red)
            }

            .message.success {
                color: var(--green)
            }

            .progress {
                display: none;
                margin-top: 15px
            }

            .track {
                height: 5px;
                background: #2a3c4e;
                border-radius: 20px;
                overflow: hidden
            }

            .fill {
                height: 100%;
                width: 0;
                background: linear-gradient(90deg, var(--teal), var(--blue));
                transition: width .3s
            }

            .progress-info {
                display: flex;
                justify-content: space-between;
                font-size: 10px;
                color: var(--muted);
                margin-top: 7px
            }

            .heading {
                display: flex;
                justify-content: space-between;
                align-items: center;
                gap: 12px;
                margin: 27px 0 14px
            }

            .heading h2 {
                font: 600 15px 'Space Grotesk'
            }

            .heading span {
                font-size: 10px;
                color: var(--muted)
            }

            .metrics {
                display: grid;
                grid-template-columns: repeat(4, 1fr);
                gap: 12px
            }

            .metric,
            .panel {
                background: var(--card);
                border: 1px solid var(--border);
                border-radius: 13px;
                padding: 18px
            }

            .metric {
                position: relative;
                overflow: hidden
            }

            .metric:after {
                content: "";
                position: absolute;
                width: 60px;
                height: 60px;
                border-radius: 50%;
                right: -25px;
                top: -25px;
                background: var(--glow)
            }

            .metric small {
                color: var(--muted);
                font-size: 10px
            }

            .metric h2 {
                font: 700 26px 'Space Grotesk';
                margin: 12px 0 5px
            }

            .metric p {
                font-size: 10px;
                color: #758ba3
            }

            .grid {
                display: grid;
                grid-template-columns: 1fr 1fr 1fr;
                gap: 13px
            }

            .panel-title {
                font: 600 13px 'Space Grotesk'
            }

            .panel-sub {
                font-size: 10px;
                color: var(--muted);
                margin-top: 5px
            }

            .gauge {
                width: 150px;
                height: 150px;
                border-radius: 50%;
                display: grid;
                place-items: center;
                background: conic-gradient(var(--teal) 0deg, #2a3b4e 0deg);
                position: relative;
                margin: 22px auto 12px;
            }

            .gauge:before {
                content: "";
                position: absolute;
                inset: 12px;
                border-radius: 50%;
                background: var(--card)
            }

            .gauge-inner {
                position: relative;
                text-align: center
            }

            .gauge-number {
                font: 700 38px 'Space Grotesk'
            }

            .gauge-inner small {
                color: var(--muted);
                font-size: 10px
            }

            .risk {
                text-align: center;
                font-size: 11px;
                color: var(--teal);
                background: #193b39;
                padding: 7px 15px;
                border-radius: 20px;
                display: table;
                margin: auto
            }

            .severity-row {
                display: flex;
                justify-content: space-between;
                font-size: 10px;
                color: var(--muted);
                padding: 8px 0
            }

            .severity-row b {
                color: var(--text)
            }

            .dot {
                width: 8px;
                height: 8px;
                border-radius: 3px;
                display: inline-block;
                margin-right: 7px
            }

            .bar-row {
                margin-top: 18px
            }

            .bar-info {
                display: flex;
                justify-content: space-between;
                font-size: 10px;
                margin-bottom: 7px
            }

            .bar-info span:last-child {
                color: var(--muted)
            }

            .bar-track {
                height: 7px;
                background: #2b3d52;
                border-radius: 20px;
                overflow: hidden
            }

            .bar-fill {
                height: 100%;
                width: 0;
                transition: width .5s;
                border-radius: 20px
            }

            .insight {
                margin-top: 19px;
                padding: 12px;
                background: #173a39;
                border: 1px solid #2b5b53;
                border-radius: 10px
            }

            .insight b {
                color: var(--teal);
                font-size: 10px
            }

            .insight p {
                font-size: 10px;
                color: #a0bcb7;
                line-height: 1.7;
                margin-top: 5px
            }

            .toolbar {
                display: flex;
                justify-content: space-between;
                gap: 10px;
                flex-wrap: wrap;
                margin-bottom: 13px
            }

            .filters {
                display: flex;
                gap: 6px;
                flex-wrap: wrap
            }

            .filter {
                padding: 8px 12px;
                background: var(--card);
                border: 1px solid var(--border);
                color: var(--muted);
                border-radius: 8px;
                font-size: 10px;
                cursor: pointer
            }

            .filter.active {
                color: var(--teal);
                background: #183a3c;
                border-color: #30685e
            }

            .toolbar input {
                padding: 8px 11px;
                font-size: 10px;
                width: 190px
            }

            .finding {
                border: 1px solid var(--border);
                background: var(--card);
                border-radius: 11px;
                margin-bottom: 9px;
                overflow: hidden
            }

            .finding-head {
                display: flex;
                align-items: center;
                gap: 12px;
                padding: 14px;
                cursor: pointer
            }

            .finding-icon {
                width: 37px;
                height: 37px;
                border-radius: 10px;
                background: #20384a;
                display: grid;
                place-items: center;
                color: var(--teal)
            }

            .finding-content {
                flex: 1;
                min-width: 0
            }

            .finding-content b {
                font-size: 12px
            }

            .finding-content p {
                font-size: 10px;
                color: var(--muted);
                margin-top: 5px
            }

            .badge {
                padding: 6px 9px;
                border-radius: 20px;
                font-size: 9px
            }

            .badge.High {
                background: #472633;
                color: var(--red)
            }

            .badge.Medium {
                background: #443a24;
                color: var(--yellow)
            }

            .badge.Low {
                background: #1d3d35;
                color: var(--green)
            }

            .details {
                display: none;
                padding: 0 15px 15px 64px
            }

            .finding.open .details {
                display: block
            }

            .details p {
                font-size: 10px;
                color: var(--muted);
                line-height: 1.7;
                margin-bottom: 9px
            }

            .evidence {
                padding: 11px;
                background: #0e1b2b;
                border: 1px solid var(--border);
                border-radius: 8px;
                color: var(--teal);
                font-size: 10px;
                word-break: break-word
            }

            .recommendation {
                color: var(--green) !important;
                margin-top: 10px
            }

            .history-row {
                display: grid;
                grid-template-columns: 2fr .7fr .8fr 1.2fr;
                gap: 10px;
                align-items: center;
                padding: 13px 0;
                border-bottom: 1px solid var(--border);
                font-size: 10px
            }

            .history-row:last-child {
                border: 0
            }

            .history-url {
                overflow: hidden;
                text-overflow: ellipsis;
                white-space: nowrap
            }

            .muted {
                color: var(--muted)
            }

            .history-risk {
                color: var(--teal)
            }

            .export {
                color: var(--teal);
                text-decoration: none;
                font-size: 10px;
                border: 1px solid #326c61;
                padding: 8px 12px;
                border-radius: 8px
            }

            .empty {
                text-align: center;
                padding: 32px 12px;
                color: var(--muted);
                font-size: 11px;
                line-height: 1.8
            }

            footer {
                text-align: center;
                color: #687d94;
                font-size: 10px;
                line-height: 1.8;
                margin-top: 30px
            }

            @media(max-width:1100px) {
                .grid {
                    grid-template-columns: 1fr 1fr
                }

                .grid .panel:first-child {
                    grid-column: span 2
                }
            }

            @media(max-width:850px) {
                .app {
                    grid-template-columns: 1fr
                }

                .sidebar {
                    display: none
                }

                main {
                    padding: 22px 17px
                }
            }

            @media(max-width:600px) {
                .metrics {
                    grid-template-columns: 1fr 1fr
                }

                .grid {
                    grid-template-columns: 1fr
                }

                .grid .panel:first-child {
                    grid-column: auto
                }

                .search {
                    flex-direction: column
                }

                .btn {
                    padding: 14px
                }

                .status {
                    display: none
                }

                .history-row {
                    grid-template-columns: 1fr auto
                }

                .history-date {
                    display: none
                }

                .details {
                    padding-left: 15px
                }
            }
        </style>
    </head>
    <body>
        <div class="app">
            <aside class="sidebar">
                <div class="brand">
                    <div class="logo">⌕</div> PatternLens
                </div>
                <div class="nav-label">WORKSPACE</div>
                <div class="nav active">
                    <span>◈</span> Dashboard
                </div>
                <div class="nav">
                    <span>⌕</span> Website Scanner
                </div>
                <div class="nav">
                    <span>▤</span> Audit Reports
                </div>
                <div class="nav">
                    <span>◷</span> Scan History
                </div>
                <div class="nav-label">INTELLIGENCE</div>
                <div class="nav">
                    <span>◎</span> Pattern Detection
                </div>
                <div class="nav">
                    <span>◉</span> Risk Analytics
                </div>
                <div class="sidebar-bottom">
                    <div class="system">
                        <b>SCANNER ENGINE</b>
                        <p>Python-powered website inspection and UX risk analysis.</p>
                        <div class="online">● &nbsp; Engine online</div>
                    </div>
                </div>
            </aside>
            <main>
                <header class="topbar">
                    <div>
                        <h1>Intelligence Dashboard</h1>
                        <p class="subtitle">Website transparency and user experience risk monitoring.</p>
                    </div>
                    <div class="status">● SYSTEM OPERATIONAL</div>
                </header>
                <section class="hero">
                    <div class="eyebrow">WEBSITE TRANSPARENCY INTELLIGENCE</div>
                    <h2>Discover what websites don't tell you.</h2>
                    <p>Analyze public website HTML and identify potentially manipulative UX patterns.</p>
                    <div class="search">
                        <input id="url" type="url" placeholder="https://example.com">
                        <button class="btn" id="scanBtn" onclick="startAudit()">⌕ Analyze Website</button>
                    </div>
                    <div class="message" id="message">Enter a website URL to start your audit.</div>
                    <div class="progress" id="progress">
                        <div class="track">
                            <div class="fill" id="fill"></div>
                        </div>
                        <div class="progress-info">
                            <span id="progressText">Preparing scan...</span>
                            <span id="progressValue">0%</span>
                        </div>
                    </div>
                </section>
                <div class="heading">
                    <h2>Audit Overview</h2>
                    <span id="lastScan">No scan yet</span>
                </div>
                <section class="metrics">
                    <div class="metric" style="--glow:#27ddc222">
                        <small>Total Findings</small>
                        <h2 id="total">0</h2>
                        <p>Detected indicators</p>
                    </div>
                    <div class="metric" style="--glow:#ff9d6822">
                        <small>Risk Score</small>
                        <h2 id="score">0 / 100</h2>
                        <p>Heuristic score</p>
                    </div>
                    <div class="metric" style="--glow:#ff637c22">
                        <small>High Severity</small>
                        <h2 id="high">0</h2>
                        <p>Priority review</p>
                    </div>
                    <div class="metric" style="--glow:#61aaff22">
                        <small>Total Audits</small>
                        <h2 id="auditCount">0</h2>
                        <p>Saved scan history</p>
                    </div>
                </section>
                <div class="heading">
                    <h2>Risk Intelligence</h2>
                    <span>Based on latest scan</span>
                </div>
                <section class="grid">
                    <div class="panel">
                        <div class="panel-title">Overall Risk Score</div>
                        <div class="panel-sub">Potential manipulation indicators</div>
                        <div class="gauge" id="gauge">
                            <div class="gauge-inner">
                                <div class="gauge-number" id="bigScore">0</div>
                                <small>OUT OF 100</small>
                            </div>
                        </div>
                        <div class="risk" id="risk">Awaiting scan</div>
                        <div style="margin-top:18px">
                            <div class="severity-row">
                                <span>
                                    <i class="dot" style="background:var(--red)"></i>High </span>
                                <b id="highLegend">0</b>
                            </div>
                            <div class="severity-row">
                                <span>
                                    <i class="dot" style="background:var(--yellow)"></i>Medium </span>
                                <b id="mediumLegend">0</b>
                            </div>
                            <div class="severity-row">
                                <span>
                                    <i class="dot" style="background:var(--green)"></i>Low </span>
                                <b id="lowLegend">0</b>
                            </div>
                        </div>
                    </div>
                    <div class="panel">
                        <div class="panel-title">Severity Distribution</div>
                        <div class="panel-sub">Findings by severity level</div>
                        <div class="bar-row">
                            <div class="bar-info">
                                <span>High</span>
                                <span id="highPct">0%</span>
                            </div>
                            <div class="bar-track">
                                <div class="bar-fill" id="highBar" style="background:var(--red)"></div>
                            </div>
                        </div>
                        <div class="bar-row">
                            <div class="bar-info">
                                <span>Medium</span>
                                <span id="mediumPct">0%</span>
                            </div>
                            <div class="bar-track">
                                <div class="bar-fill" id="mediumBar" style="background:var(--yellow)"></div>
                            </div>
                        </div>
                        <div class="bar-row">
                            <div class="bar-info">
                                <span>Low</span>
                                <span id="lowPct">0%</span>
                            </div>
                            <div class="bar-track">
                                <div class="bar-fill" id="lowBar" style="background:var(--green)"></div>
                            </div>
                        </div>
                        <div class="insight">
                            <b>ANALYSIS INSIGHT</b>
                            <p id="insight">Run your first scan to generate risk insights.</p>
                        </div>
                    </div>
                    <div class="panel">
                        <div class="panel-title">Category Breakdown</div>
                        <div class="panel-sub">Detected patterns grouped by category</div>
                        <div id="categories">
                            <div class="empty">No category data yet.</div>
                        </div>
                    </div>
                </section>
                <div class="heading">
                    <h2>Detailed Findings</h2>
                    <span id="findingCount">0 results</span>
                </div>
                <div class="toolbar">
                    <div class="filters">
                        <button class="filter active" data-filter="All">All</button>
                        <button class="filter" data-filter="High">High</button>
                        <button class="filter" data-filter="Medium">Medium</button>
                        <button class="filter" data-filter="Low">Low</button>
                    </div>
                    <input id="search" placeholder="Search findings...">
                </div>
                <div id="findings">
                    <div class="panel empty">Your scan findings will appear here.</div>
                </div>
                <div class="heading">
                    <h2>Audit History</h2>
                    <a class="export" href="/api/export">↓ Export CSV</a>
                </div>
                <div class="panel" id="history">
                    <div class="empty">No audit history yet.</div>
                </div>
                <footer> PATTERNLENS · PYTHON WEBSITE AUDITOR <br> Automated heuristic analysis · Manual verification required </footer>
            </main>
        </div>
        <script>
            const $ = id => document.getElementById(id);
            let findings = [];
            let filter = "All";

            function message(text, type = "") {
                $("message").textContent = text;
                $("message").className = "message " + type;
            }

            function progressAnimation() {
                $("progress").style.display = "block";
                let value = 0;
                const labels = ["Connecting to website...", "Reading accessible HTML...", "Inspecting UX indicators...", "Calculating risk score...", "Generating report..."];
                const timer = setInterval(() => {
                    value = Math.min(value + Math.floor(Math.random() * 8) + 4, 90);
                    $("fill").style.width = value + "%";
                    $("progressValue").textContent = value + "%";
                    $("progressText").textContent = labels[Math.min(4, Math.floor(value / 20))];
                    if (value >= 90) clearInterval(timer);
                }, 200);
                return () => {
                    clearInterval(timer);
                    $("fill").style.width = "100%";
                    $("progressValue").textContent = "100%";
                    $("progressText").textContent = "Analysis completed";
                };
            }
            async function startAudit() {
                const url = $("url").value.trim();
                if (!url) return message("Enter a website URL first.", "error");
                $("scanBtn").disabled = true;
                $("scanBtn").textContent = "Scanning...";
                message("Please wait while the Python scanner analyzes the website.");
                const finish = progressAnimation();
                try {
                    const response = await fetch("/api/audit", {
                        method: "POST",
                        headers: {
                            "Content-Type": "application/json"
                        },
                        body: JSON.stringify({
                            url
                        })
                    });
                    const data = await response.json();
                    if (!response.ok) throw new Error(data.error);
                    finish();
                    display(data);
                    await loadHistory();
                    message("Audit completed successfully.", "success");
                } catch (error) {
                    finish();
                    message(error.message || "Unable to analyze website.", "error");
                } finally {
                    $("scanBtn").disabled = false;
                    $("scanBtn").textContent = "⌕ Analyze Website";
                }
            }

            function display(data) {
                findings = data.findings;
                const counts = data.severity;
                const total = Math.max(1, data.total);
                $("total").textContent = data.total;
                $("score").textContent = data.score + " / 100";
                $("high").textContent = counts.High;
                $("bigScore").textContent = data.score;
                $("lastScan").textContent = data.created_at;
                $("highLegend").textContent = counts.High;
                $("mediumLegend").textContent = counts.Medium;
                $("lowLegend").textContent = counts.Low;
                const color = data.score >= 60 ? "var(--red)" : data.score >= 30 ? "var(--orange)" : data.score > 0 ? "var(--yellow)" : "var(--teal)";
                $("gauge").style.background = `conic-gradient(${color} ${data.score*3.6}deg,#2a3b4e 0deg)`;
                $("risk").textContent = data.risk + " Risk";
                $("risk").style.color = color;
                const levels = ["High", "Medium", "Low"];
                levels.forEach(level => {
                    const key = level.toLowerCase();
                    const pct = Math.round(counts[level] / total * 100);
                    $(key + "Pct").textContent = pct + "%";
                    $(key + "Bar").style.width = pct + "%";
                });
                $("insight").textContent = counts.High ? `${counts.High} high-severity indicator(s) need priority manual review.` : "No high-severity indicators were detected. This is not proof of a safe website.";
                renderCategories(data.categories);
                renderFindings();
                window.scrollTo({
                    top: 0,
                    behavior: "smooth"
                });
            }

            function renderCategories(categories) {
                const box = $("categories");
                box.innerHTML = "";
                const entries = Object.entries(categories);
                if (!entries.length) {
                    box.innerHTML = ' < div class = "empty" > No categories detected. < /div>';
                    return;
                }
                const max = Math.max(...entries.map(x => x[1]));
                entries.sort((a, b) => b[1] - a[1]).forEach(([name, count], i) => {
                    const row = document.createElement("div");
                    row.className = "bar-row";
                    const info = document.createElement("div");
                    info.className = "bar-info";
                    const label = document.createElement("span");
                    label.textContent = name;
                    const number = document.createElement("span");
                    number.textContent = count + " findings";
                    info.append(label, number);
                    const track = document.createElement("div");
                    track.className = "bar-track";
                    const bar = document.createElement("div");
                    bar.className = "bar-fill";
                    bar.style.background = ["#27ddc2", "#61aaff", "#ff9d68", "#a68bff", "#ff729f"][i % 5];
                    bar.style.width = (count / max * 100) + "%";
                    track.appendChild(bar);
                    row.append(info, track);
                    box.appendChild(row);
                });
            }

            function renderFindings() {
                const query = $("search").value.toLowerCase();
                const result = findings.filter(item => (filter === "All" || item.severity === filter) && (item.name + item.category + item.description + item.evidence).toLowerCase().includes(query));
                $("findingCount").textContent = result.length + " results";
                const box = $("findings");
                box.innerHTML = "";
                if (!result.length) {
                    box.innerHTML = ' < div class = "panel empty" > No matching findings found. < /div>';
                    return;
                }
                result.forEach(item => {
                    const card = document.createElement("div");
                    card.className = "finding";
                    const head = document.createElement("div");
                    head.className = "finding-head";
                    const icon = document.createElement("div");
                    icon.className = "finding-icon";
                    icon.textContent = item.icon;
                    const content = document.createElement("div");
                    content.className = "finding-content";
                    const title = document.createElement("b");
                    title.textContent = item.name;
                    const description = document.createElement("p");
                    description.textContent = item.category + " · " + item.description;
                    content.append(title, description);
                    const badge = document.createElement("span");
                    badge.className = "badge " + item.severity;
                    badge.textContent = item.severity;
                    head.append(icon, content, badge);
                    const details = document.createElement("div");
                    details.className = "details";
                    const evidenceTitle = document.createElement("p");
                    evidenceTitle.textContent = "Detected evidence";
                    const evidence = document.createElement("div");
                    evidence.className = "evidence";
                    evidence.textContent = item.evidence;
                    const explanation = document.createElement("p");
                    explanation.style.marginTop = "10px";
                    explanation.textContent = item.description;
                    const recommendation = document.createElement("p");
                    recommendation.className = "recommendation";
                    recommendation.textContent = "Recommendation: " + item.recommendation;
                    details.append(evidenceTitle, evidence, explanation, recommendation);
                    card.append(head, details);
                    head.addEventListener("click", () => {
                        card.classList.toggle("open");
                    });
                    box.appendChild(card);
                });
            }
            document.querySelectorAll(".filter").forEach(button => {
                button.addEventListener("click", () => {
                    document.querySelectorAll(".filter").forEach(x => x.classList.remove("active"));
                    button.classList.add("active");
                    filter = button.dataset.filter;
                    renderFindings();
                });
            });
            $("search").addEventListener("input", renderFindings);
            async function loadHistory() {
                try {
                    const response = await fetch("/api/history");
                    const data = await response.json();
                    $("auditCount").textContent = data.length;
                    const box = $("history");
                    box.innerHTML = "";
                    if (!data.length) {
                        box.innerHTML = ' < div class = "empty" > No audit history available. < /div>';
                        return;
                    }
                    data.forEach(item => {
                        const row = document.createElement("div");
                        row.className = "history-row";
                        const url = document.createElement("strong");
                        url.className = "history-url";
                        url.textContent = item.url;
                        const score = document.createElement("span");
                        score.textContent = item.score + "/100";
                        const risk = document.createElement("span");
                        risk.className = "history-risk";
                        risk.textContent = item.risk;
                        const date = document.createElement("span");
                        date.className = "muted history-date";
                        date.textContent = item.created_at;
                        row.append(url, score, risk, date);
                        box.appendChild(row);
                    });
                } catch (error) {
                    $("history").textContent = "Unable to load history.";
                }
            }
            $("url").addEventListener("keydown", event => {
                if (event.key === "Enter") startAudit();
            });
            loadHistory();
        </script>
    </body>
</html>

"""


# =====================================================
# HTTP API
# =====================================================

class AuditorHandler(BaseHTTPRequestHandler):

    def send_json(self, data, status=200):

        raw = json.dumps(data).encode()

        self.send_response(status)
        self.send_header("Content-Type","application/json; charset=utf-8")
        self.send_header("Content-Length",str(len(raw)))
        self.send_header("Cache-Control","no-store")
        self.send_header("X-Content-Type-Options","nosniff")
        self.end_headers()

        self.wfile.write(raw)

    def do_GET(self):

        if self.path == "/":

            raw = HTML.encode()

            self.send_response(200)
            self.send_header("Content-Type","text/html; charset=utf-8")
            self.send_header("Content-Length",str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
            return

        if self.path == "/api/history":

            with database() as conn:
                rows = conn.execute("""
                    SELECT id,url,score,risk,created_at
                    FROM audits ORDER BY created_at DESC LIMIT 50
                """).fetchall()

            self.send_json([dict(row) for row in rows])
            return

        if self.path == "/api/export":

            with database() as conn:
                rows = conn.execute("""
                    SELECT id,url,score,risk,findings,created_at
                    FROM audits ORDER BY created_at DESC
                """).fetchall()

            output = io.StringIO()
            writer = csv.writer(output)

            writer.writerow([
                "ID","Website","Score","Risk","Findings","Date"
            ])

            for row in rows:
                writer.writerow(list(row))

            raw = output.getvalue().encode()

            self.send_response(200)
            self.send_header("Content-Type","text/csv")
            self.send_header(
                "Content-Disposition",
                'attachment; filename="patternlens-report.csv"'
            )
            self.send_header("Content-Length",str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
            return

        self.send_error(404)

    def do_POST(self):

        if self.path != "/api/audit":
            self.send_error(404)
            return

        try:

            length = int(self.headers.get("Content-Length",0))

            if length > 5000:
                raise ValueError("Request too large.")

            payload = json.loads(self.rfile.read(length))
            url = payload.get("url","").strip()

            if not url:
                raise ValueError("Website URL is required.")

            result = run_audit(url)
            self.send_json(result)

        except urllib.error.HTTPError as error:
            self.send_json({"error":f"Website returned HTTP {error.code}."},400)

        except (urllib.error.URLError,TimeoutError):
            self.send_json({"error":"Could not connect to website."},400)

        except Exception as error:
            self.send_json({"error":str(error)},400)

    def log_message(self,format,*args):
        pass


# =====================================================
# APPLICATION START
# =====================================================

if __name__ == "__main__":

    init_db()

    server = HTTPServer((HOST,PORT),AuditorHandler)

    print("="*55)
    print("       PATTERNLENS - DARK PATTERN WEBSITE AUDITOR")
    print("="*55)
    print(f"Dashboard: http://{HOST}:{PORT}")
    print("Database:",DB)
    print("Press CTRL+C to stop.")

    try:
        server.serve_forever()

    except KeyboardInterrupt:
        print("\nApplication stopped.")
        server.server_close()
