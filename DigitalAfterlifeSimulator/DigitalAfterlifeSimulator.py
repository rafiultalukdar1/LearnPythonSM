
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse
import sqlite3
import json
import os
import re
from datetime import datetime

HOST = "127.0.0.1"
PORT = 8006
DB = "digital_afterlife.db"


# ========================= DATABASE =========================

def connect_db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con


def initialize_db():
    with connect_db() as con:
        con.executescript("""
            CREATE TABLE IF NOT EXISTS members (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                relation TEXT,
                birth_year TEXT,
                initials TEXT,
                color TEXT DEFAULT '#B18B45',
                created_at TEXT
            );

            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                person TEXT,
                category TEXT,
                year TEXT,
                content TEXT,
                created_at TEXT
            );

            CREATE TABLE IF NOT EXISTS legacy_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                person TEXT,
                message TEXT,
                created_at TEXT
            );
        """)

        count = con.execute(
            "SELECT COUNT(*) FROM members"
        ).fetchone()[0]

        if count == 0:
            now = datetime.now().isoformat(timespec="seconds")

            members = [
                ("John Doe Sr.", "Grandfather", "1932", "JD", "#A88443"),
                ("Jane Doe", "Grandmother", "1958", "JN", "#7D9A82"),
                ("James Doe", "Father", "1962", "JM", "#C18C48"),
                ("Mary Doe", "Aunt", "1965", "MD", "#8E729B"),
                ("Sarah Doe", "Daughter", "1988", "SD", "#6598A9"),
                ("Michael Doe", "Son", "1991", "MI", "#BC7777")
            ]

            con.executemany("""
                INSERT INTO members
                (name, relation, birth_year, initials, color, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, [(*m, now) for m in members])

            memories = [
                (
                    "The Sunday Family Dinner",
                    "John Doe Sr.",
                    "Family",
                    "1985",
                    "Every Sunday, the whole family gathered around one table. "
                    "Grandfather always told stories after dinner."
                ),
                (
                    "A Letter to My Children",
                    "Jane Doe",
                    "Letters",
                    "1992",
                    "I hope you always remember that kindness matters more "
                    "than anything you own."
                ),
                (
                    "Our First Family Vacation",
                    "James Doe",
                    "Travel",
                    "2001",
                    "We travelled together and made memories that we still "
                    "talk about today."
                ),
                (
                    "A Special Birthday",
                    "Sarah Doe",
                    "Celebrations",
                    "2020",
                    "The best gift was having everyone together."
                )
            ]

            con.executemany("""
                INSERT INTO memories
                (title, person, category, year, content, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, [(*m, now) for m in memories])


# ========================= API HELPERS =========================

def get_dashboard_data():
    with connect_db() as con:
        members = [
            dict(row) for row in con.execute(
                "SELECT * FROM members ORDER BY id"
            ).fetchall()
        ]

        memories = [
            dict(row) for row in con.execute(
                "SELECT * FROM memories ORDER BY year DESC, id DESC"
            ).fetchall()
        ]

        messages = [
            dict(row) for row in con.execute(
                "SELECT * FROM legacy_messages ORDER BY id DESC"
            ).fetchall()
        ]

    return {
        "members": members,
        "memories": memories,
        "messages": messages,
        "stats": {
            "members": len(members),
            "memories": len(memories),
            "generations": 4,
            "recordings": len(messages)
        }
    }


def clean(value, limit=1000):
    return str(value or "").strip()[:limit]


def json_response(handler, data, status=200):
    body = json.dumps(data).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Access-Control-Allow-Origin", "same-origin")
    handler.end_headers()
    handler.wfile.write(body)


# ========================= FRONTEND =========================

HTML = r"""
<!DOCTYPE html>
<html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Kindred — Digital Legacy</title>
        <style>
            @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Playfair+Display:wght@500;600;700&display=swap');

            :root {
                --bg: #f8f6f0;
                --surface: #ffffff;
                --ink: #302d23;
                --muted: #969084;
                --gold: #b18b45;
                --gold-light: #f2ead9;
                --green: #7f9c85;
                --green-light: #edf3ed;
                --border: #e7e1d6;
                --dark: #2d291e;
                --red: #b97770;
            }

            * {
                box-sizing: border-box;
            }

            body {
                margin: 0;
                background: var(--bg);
                color: var(--ink);
                font-family: 'DM Sans', sans-serif;
            }

            button,
            input,
            select,
            textarea {
                font: inherit;
            }

            button {
                cursor: pointer;
            }

            .topbar {
                height: 66px;
                padding: 0 4%;
                display: flex;
                align-items: center;
                justify-content: space-between;
                background: rgba(255, 255, 255, .85);
                border-bottom: 1px solid var(--border);
                position: sticky;
                top: 0;
                z-index: 10;
            }

            .brand {
                display: flex;
                align-items: center;
                gap: 12px;
                font-family: 'Playfair Display', serif;
                font-size: 22px;
                font-weight: 700;
            }

            .brand-icon {
                width: 39px;
                height: 39px;
                display: grid;
                place-items: center;
                border-radius: 50%;
                background: var(--gold);
                color: white;
                font-size: 19px;
            }

            .brand small {
                font-family: 'DM Sans', sans-serif;
                font-size: 10px;
                color: var(--muted);
                font-weight: 400;
            }

            .nav {
                display: flex;
                align-items: center;
                gap: 7px;
            }

            .nav button {
                border: 0;
                background: transparent;
                color: #777064;
                padding: 10px 15px;
                border-radius: 9px;
                font-size: 13px;
            }

            .nav button.active,
            .nav button:hover {
                background: var(--gold-light);
                color: #96753d;
            }

            .profile {
                border: 1px solid var(--border);
                background: white;
                padding: 9px 14px;
                border-radius: 30px;
                font-size: 12px;
            }

            main {
                max-width: 1240px;
                width: 92%;
                margin: 30px auto 70px;
            }

            .page {
                display: none;
            }

            .page.active {
                display: block;
            }

            .hero-grid {
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 22px;
            }

            .hero {
                min-height: 335px;
                padding: 37px;
                border-radius: 21px;
                background: var(--dark);
                color: white;
                position: relative;
                overflow: hidden;
            }

            .hero:after {
                content: "";
                position: absolute;
                width: 230px;
                height: 230px;
                border: 1px solid rgba(198, 166, 101, .17);
                border-radius: 50%;
                right: -70px;
                bottom: -75px;
            }

            .eyebrow {
                color: #c6a96d;
                font-size: 10px;
                letter-spacing: 3px;
                font-weight: 700;
            }

            h1,
            h2,
            h3,
            p {
                margin-top: 0;
            }

            .hero h1 {
                font: 700 31px/1.35 'Playfair Display', serif;
                margin: 19px 0 13px;
                max-width: 410px;
            }

            .hero h1 em {
                color: #c6a96d;
            }

            .hero p {
                color: #c9c4b8;
                font-size: 13px;
                line-height: 1.9;
                max-width: 380px;
            }

            .stats {
                display: flex;
                gap: 30px;
                margin-top: 31px;
                flex-wrap: wrap;
            }

            .stat strong {
                display: block;
                font: 700 24px 'Playfair Display', serif;
            }

            .stat span {
                display: block;
                color: #a49d8e;
                font-size: 9px;
                letter-spacing: 1px;
                margin-top: 5px;
            }

            .panel {
                background: var(--surface);
                border: 1px solid var(--border);
                border-radius: 19px;
                padding: 25px;
                box-shadow: 0 5px 20px rgba(53, 45, 30, .035);
            }

            .panel-head {
                display: flex;
                justify-content: space-between;
                align-items: center;
                gap: 10px;
                margin-bottom: 20px;
            }

            .panel-head h3 {
                font: 600 17px 'Playfair Display', serif;
                margin: 0;
            }

            .subtle {
                color: var(--muted);
                font-size: 11px;
            }

            .outline-btn,
            .primary-btn {
                border-radius: 30px;
                padding: 9px 16px;
                font-size: 11px;
                border: 1px solid var(--border);
                background: white;
                color: #716b60;
            }

            .primary-btn {
                background: var(--gold);
                border-color: var(--gold);
                color: white;
                font-weight: 600;
            }

            .primary-btn:hover {
                background: #98763c;
            }

            .tree {
                min-height: 235px;
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                gap: 25px;
            }

            .tree-row {
                display: flex;
                justify-content: center;
                gap: 35px;
                flex-wrap: wrap;
            }

            .person {
                text-align: center;
                min-width: 65px;
                cursor: pointer;
            }

            .avatar {
                width: 43px;
                height: 43px;
                margin: auto;
                border-radius: 50%;
                color: white;
                display: grid;
                place-items: center;
                font-weight: 700;
                font-size: 12px;
                box-shadow: 0 0 0 5px #f8f6f0;
            }

            .person b {
                display: block;
                font-size: 10px;
                margin-top: 9px;
            }

            .person small {
                color: var(--muted);
                font-size: 9px;
            }

            .section-label {
                display: flex;
                align-items: center;
                gap: 15px;
                margin: 30px 0 17px;
                color: #aaa18f;
                font-size: 10px;
                letter-spacing: 2px;
            }

            .section-label:before,
            .section-label:after {
                content: "";
                height: 1px;
                background: var(--border);
                flex: 1;
            }

            .decades {
                display: grid;
                grid-template-columns: repeat(5, 1fr);
                gap: 12px;
            }

            .decade {
                border: 1px solid var(--border);
                border-radius: 15px;
                background: white;
                text-align: center;
                padding: 19px 10px;
                transition: .2s;
                cursor: pointer;
            }

            .decade:hover,
            .decade.selected {
                border-color: var(--gold);
                background: #fcfaf5;
                transform: translateY(-2px);
            }

            .decade strong {
                font: 700 20px 'Playfair Display', serif;
            }

            .decade small {
                display: block;
                margin-top: 6px;
                color: var(--muted);
                font-size: 10px;
            }

            .lower-grid {
                display: grid;
                grid-template-columns: 2fr 1fr;
                gap: 20px;
                margin-top: 28px;
            }

            .voice-grid {
                display: grid;
                grid-template-columns: repeat(2, 1fr);
                gap: 12px;
            }

            .voice-card {
                border: 1px solid var(--border);
                border-top: 4px solid var(--green);
                border-radius: 15px;
                padding: 18px;
                background: white;
            }

            .voice-person {
                display: flex;
                align-items: center;
                gap: 12px;
            }

            .voice-person .avatar {
                margin: 0;
                width: 42px;
                height: 42px;
            }

            .voice-person strong {
                font-size: 12px;
            }

            .voice-person small {
                display: block;
                color: var(--muted);
                font-size: 10px;
                margin-top: 5px;
            }

            .status {
                margin-left: auto;
                color: var(--green);
                background: var(--green-light);
                border-radius: 20px;
                padding: 5px 9px;
                font-size: 9px;
            }

            .voice-note {
                margin-top: 16px;
                font-size: 11px;
                color: var(--muted);
                line-height: 1.7;
            }

            .voice-actions {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-top: 13px;
            }

            .voice-actions button {
                width: 34px;
                height: 34px;
                border: none;
                border-radius: 50%;
                background: var(--green);
                color: white;
            }

            .upload-box {
                border: 2px dashed #d8cfbd;
                background: #fcfbf7;
                border-radius: 16px;
                min-height: 205px;
                padding: 30px;
                text-align: center;
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
            }

            .upload-icon {
                width: 45px;
                height: 45px;
                display: grid;
                place-items: center;
                border-radius: 50%;
                background: var(--gold-light);
                color: var(--gold);
                font-size: 21px;
                margin-bottom: 12px;
            }

            .upload-box h3 {
                font: 600 15px 'Playfair Display', serif;
                margin-bottom: 7px;
            }

            .upload-box p {
                color: var(--muted);
                font-size: 11px;
                line-height: 1.7;
            }

            .chips {
                display: flex;
                gap: 6px;
                flex-wrap: wrap;
                justify-content: center;
            }

            .chip {
                background: #f1ede5;
                color: #8f8778;
                border-radius: 20px;
                padding: 5px 9px;
                font-size: 9px;
            }

            .page-title {
                font: 700 30px 'Playfair Display', serif;
                margin-bottom: 8px;
            }

            .page-description {
                color: var(--muted);
                font-size: 13px;
                margin-bottom: 25px;
            }

            .memory-grid {
                display: grid;
                grid-template-columns: repeat(3, 1fr);
                gap: 15px;
            }

            .memory-card {
                background: white;
                border: 1px solid var(--border);
                border-radius: 15px;
                padding: 20px;
                transition: .2s;
            }

            .memory-card:hover {
                transform: translateY(-3px);
                box-shadow: 0 10px 25px #302d2310;
            }

            .memory-icon {
                width: 38px;
                height: 38px;
                display: grid;
                place-items: center;
                border-radius: 11px;
                background: var(--gold-light);
                margin-bottom: 14px;
            }

            .memory-card h3 {
                font: 600 16px 'Playfair Display', serif;
                margin-bottom: 7px;
            }

            .memory-card p {
                color: #827c70;
                font-size: 11px;
                line-height: 1.7;
            }

            .memory-meta {
                font-size: 10px;
                color: var(--muted);
            }

            .toolbar {
                display: flex;
                justify-content: space-between;
                align-items: center;
                gap: 12px;
                margin-bottom: 18px;
                flex-wrap: wrap;
            }

            .toolbar input,
            .toolbar select {
                background: white;
                border: 1px solid var(--border);
                border-radius: 10px;
                padding: 11px 13px;
                outline: none;
                color: var(--ink);
            }

            .toolbar input {
                min-width: 220px;
            }

            .form-card {
                max-width: 650px;
                margin: auto;
            }

            .field {
                margin-bottom: 15px;
            }

            .field label {
                display: block;
                font-size: 11px;
                font-weight: 600;
                margin-bottom: 7px;
            }

            .field input,
            .field textarea,
            .field select {
                width: 100%;
                padding: 12px;
                border: 1px solid var(--border);
                border-radius: 10px;
                outline: none;
                background: #fff;
                color: var(--ink);
            }

            .field textarea {
                min-height: 110px;
                resize: vertical;
            }

            .field input:focus,
            .field textarea:focus {
                border-color: var(--gold);
            }

            .simulator {
                max-width: 800px;
                margin: auto;
            }

            .simulator-intro {
                background: var(--dark);
                color: white;
                border-radius: 18px;
                padding: 30px;
                margin-bottom: 18px;
            }

            .simulator-intro h2 {
                font: 600 25px 'Playfair Display', serif;
            }

            .simulator-intro p {
                color: #c9c4b8;
                font-size: 12px;
                line-height: 1.8;
            }

            .simulation-result {
                display: none;
                background: white;
                border: 1px solid var(--border);
                border-radius: 15px;
                padding: 25px;
                margin-top: 18px;
            }

            .simulation-result.show {
                display: block;
            }

            .result-label {
                color: var(--gold);
                font-size: 9px;
                letter-spacing: 2px;
                font-weight: 700;
            }

            .result-text {
                font: 500 19px/1.8 'Playfair Display', serif;
                margin-top: 12px;
                white-space: pre-wrap;
            }

            .notice {
                background: #f8f2e5;
                color: #8a7345;
                border-radius: 10px;
                padding: 12px;
                font-size: 10px;
                line-height: 1.7;
                margin-top: 14px;
            }

            .empty {
                text-align: center;
                color: var(--muted);
                padding: 45px 15px;
                background: white;
                border: 1px dashed var(--border);
                border-radius: 14px;
            }

            .toast {
                position: fixed;
                right: 25px;
                bottom: 25px;
                background: var(--dark);
                color: white;
                padding: 13px 19px;
                border-radius: 10px;
                font-size: 12px;
                opacity: 0;
                transform: translateY(15px);
                transition: .3s;
                pointer-events: none;
                z-index: 99;
            }

            .toast.show {
                opacity: 1;
                transform: translateY(0);
            }

            footer {
                text-align: center;
                color: var(--muted);
                font-size: 10px;
                padding: 25px;
                border-top: 1px solid var(--border);
            }

            @media(max-width:900px) {
                .nav {
                    overflow-x: auto;
                }

                .nav button {
                    padding: 9px;
                }

                .hero-grid,
                .lower-grid {
                    grid-template-columns: 1fr;
                }
            }

            @media(max-width:650px) {
                .topbar {
                    padding: 0 4%;
                }

                .profile {
                    display: none;
                }

                .nav {
                    max-width: 55%;
                }

                main {
                    width: 94%;
                    margin-top: 18px;
                }

                .hero {
                    padding: 25px;
                }

                .hero h1 {
                    font-size: 25px;
                }

                .decades {
                    grid-template-columns: repeat(2, 1fr);
                }

                .voice-grid,
                .memory-grid {
                    grid-template-columns: 1fr;
                }

                .stats {
                    gap: 20px;
                }

                .panel {
                    padding: 18px;
                }
            }
        </style>
    </head>
    <body>
        <header class="topbar">
            <div class="brand">
                <div class="brand-icon">✺</div> Kindred <small>· digital legacy</small>
            </div>
            <nav class="nav">
                <button class="active" data-page="home">Home</button>
                <button data-page="family">Family Tree</button>
                <button data-page="memories">Memories</button>
                <button data-page="voices">Legacy Voices</button>
                <button data-page="simulator">Simulator</button>
            </nav>
            <div class="profile">◉ &nbsp; The Doe Family</div>
        </header>
        <main>
            <!-- HOME -->
            <section class="page active" id="home">
                <div class="hero-grid">
                    <div class="hero">
                        <div class="eyebrow">THE DOE LEGACY</div>
                        <h1>Every voice matters. <br>Every story <em>endures.</em>
                        </h1>
                        <p> Your family's digital legacy — preserving meaningful stories, memories and messages for generations to come. </p>
                        <div class="stats">
                            <div class="stat">
                                <strong id="statMemories">0</strong>
                                <span>MEMORIES</span>
                            </div>
                            <div class="stat">
                                <strong id="statMembers">0</strong>
                                <span>MEMBERS</span>
                            </div>
                            <div class="stat">
                                <strong id="statMessages">0</strong>
                                <span>LEGACY NOTES</span>
                            </div>
                            <div class="stat">
                                <strong>4</strong>
                                <span>GENERATIONS</span>
                            </div>
                        </div>
                    </div>
                    <div class="panel">
                        <div class="panel-head">
                            <h3>Family Tree <span class="subtle">· Doe</span>
                            </h3>
                            <button class="outline-btn" onclick="navigate('family')">Full View ↗</button>
                        </div>
                        <div id="miniTree" class="tree"></div>
                    </div>
                </div>
                <div class="section-label">FAMILY TIMELINE</div>
                <div class="decades" id="decades"></div>
                <div class="lower-grid">
                    <div>
                        <div class="panel-head">
                            <h3>♙ &nbsp; Legacy Voices</h3>
                            <button class="outline-btn" onclick="navigate('voices')">View All →</button>
                        </div>
                        <div class="voice-grid" id="homeVoices"></div>
                    </div>
                    <div class="upload-box">
                        <div class="upload-icon">☁</div>
                        <h3>Add to the Archive</h3>
                        <p>Preserve your family's memories, stories and letters in one place.</p>
                        <div class="chips">
                            <span class="chip">Stories</span>
                            <span class="chip">Photos</span>
                            <span class="chip">Letters</span>
                            <span class="chip">Documents</span>
                        </div>
                        <br>
                        <button class="primary-btn" onclick="navigate('add-memory')">+ Add a Memory</button>
                    </div>
                </div>
            </section>
            <!-- FAMILY TREE -->
            <section class="page" id="family">
                <h1 class="page-title">Our Family Tree</h1>
                <p class="page-description">The people and relationships behind every family story.</p>
                <div class="panel">
                    <div class="panel-head">
                        <h3>Family Members</h3>
                        <button class="primary-btn" onclick="navigate('add-member')">+ Add Member</button>
                    </div>
                    <div id="familyGrid" class="memory-grid"></div>
                </div>
            </section>
            <!-- MEMORIES -->
            <section class="page" id="memories">
                <h1 class="page-title">Memory Archive</h1>
                <p class="page-description">A collection of stories, moments and memories worth keeping.</p>
                <div class="toolbar">
                    <input id="memorySearch" placeholder="Search memories..." oninput="renderMemories()">
                    <select id="memoryCategory" onchange="renderMemories()">
                        <option value="">All categories</option>
                        <option>Family</option>
                        <option>Letters</option>
                        <option>Travel</option>
                        <option>Celebrations</option>
                        <option>Life Lessons</option>
                        <option>Other</option>
                    </select>
                    <button class="primary-btn" onclick="navigate('add-memory')">+ New Memory</button>
                </div>
                <div class="memory-grid" id="memoryGrid"></div>
            </section>
            <!-- LEGACY VOICES -->
            <section class="page" id="voices">
                <h1 class="page-title">Legacy Voices</h1>
                <p class="page-description">Keep meaningful written messages and the stories behind them.</p>
                <div class="panel">
                    <div class="panel-head">
                        <h3>Saved Legacy Messages</h3>
                        <button class="primary-btn" onclick="navigate('add-message')">+ Save Message</button>
                    </div>
                    <div id="messageList"></div>
                    <div class="notice"> This demo stores written legacy messages only. It does not clone, recreate or imitate anyone's voice. </div>
                </div>
            </section>
            <!-- SIMULATOR -->
            <section class="page" id="simulator">
                <div class="simulator">
                    <div class="simulator-intro">
                        <div class="eyebrow">A MOMENT OF REFLECTION</div>
                        <h2>Digital Afterlife Simulator</h2>
                        <p> Explore a gentle, AI-style reflection based on memories your family has chosen to preserve. Create a meaningful legacy message inspired by those stories. </p>
                    </div>
                    <div class="panel">
                        <div class="field">
                            <label>Choose a family member</label>
                            <select id="simPerson"></select>
                        </div>
                        <div class="field">
                            <label>What would you like to reflect on?</label>
                            <select id="simTopic">
                                <option value="advice">Life advice</option>
                                <option value="family">Family and togetherness</option>
                                <option value="memories">Favorite memories</option>
                                <option value="future">A message for future generations</option>
                                <option value="kindness">Kindness and gratitude</option>
                            </select>
                        </div>
                        <button class="primary-btn" onclick="runSimulation()"> Generate Legacy Reflection ✦ </button>
                    </div>
                    <div class="simulation-result" id="simulationResult">
                        <div class="result-label">GENERATED LEGACY REFLECTION</div>
                        <div class="result-text" id="simulationText"></div>
                        <div class="notice"> This is an AI-style fictional reflection generated from saved family memories. It is not an authentic statement from the selected person. </div>
                    </div>
                </div>
            </section>
            <!-- ADD MEMORY -->
            <section class="page" id="add-memory">
                <div class="panel form-card">
                    <div class="panel-head">
                        <h3>Add a Family Memory</h3>
                        <button class="outline-btn" onclick="navigate('memories')">Cancel</button>
                    </div>
                    <form onsubmit="addMemory(event)">
                        <div class="field">
                            <label>Memory Title</label>
                            <input id="memoryTitle" placeholder="e.g. Our childhood home" required maxlength="100">
                        </div>
                        <div class="field">
                            <label>Related Family Member</label>
                            <select id="memoryPerson"></select>
                        </div>
                        <div class="field">
                            <label>Category</label>
                            <select id="memoryType">
                                <option>Family</option>
                                <option>Letters</option>
                                <option>Travel</option>
                                <option>Celebrations</option>
                                <option>Life Lessons</option>
                                <option>Other</option>
                            </select>
                        </div>
                        <div class="field">
                            <label>Year</label>
                            <input id="memoryYear" type="number" min="1900" max="2100" placeholder="e.g. 2005">
                        </div>
                        <div class="field">
                            <label>Tell the Story</label>
                            <textarea id="memoryContent" placeholder="Write down the memory..." required maxlength="3000"></textarea>
                        </div>
                        <button class="primary-btn" type="submit">Save Memory</button>
                    </form>
                </div>
            </section>
            <!-- ADD MEMBER -->
            <section class="page" id="add-member">
                <div class="panel form-card">
                    <div class="panel-head">
                        <h3>Add Family Member</h3>
                        <button class="outline-btn" onclick="navigate('family')">Cancel</button>
                    </div>
                    <form onsubmit="addMember(event)">
                        <div class="field">
                            <label>Full Name</label>
                            <input id="memberName" required maxlength="70">
                        </div>
                        <div class="field">
                            <label>Relationship</label>
                            <input id="memberRelation" placeholder="e.g. Grandmother">
                        </div>
                        <div class="field">
                            <label>Birth Year</label>
                            <input id="memberYear" type="number" min="1800" max="2100">
                        </div>
                        <button class="primary-btn" type="submit">Add to Family Tree</button>
                    </form>
                </div>
            </section>
            <!-- ADD MESSAGE -->
            <section class="page" id="add-message">
                <div class="panel form-card">
                    <div class="panel-head">
                        <h3>Save a Legacy Message</h3>
                        <button class="outline-btn" onclick="navigate('voices')">Cancel</button>
                    </div>
                    <form onsubmit="addMessage(event)">
                        <div class="field">
                            <label>Family Member</label>
                            <select id="messagePerson"></select>
                        </div>
                        <div class="field">
                            <label>Written Message</label>
                            <textarea id="messageContent" placeholder="Write a message or preserve a meaningful quote..." required maxlength="3000"></textarea>
                        </div>
                        <button class="primary-btn" type="submit">Save Legacy Message</button>
                    </form>
                </div>
            </section>
        </main>
        <footer> KINDRED · PRESERVING STORIES, CONNECTING GENERATIONS <br>
            <br> Your family's memories deserve a place to live on.
        </footer>
        <div class="toast" id="toast"></div>
        <script>
            let data = {
                members: [],
                memories: [],
                messages: []
            };
            const colors = ['#A88443', '#7D9A82', '#C18C48', '#8E729B', '#6598A9', '#BC7777'];
            const icons = {
                Family: '♡',
                Letters: '✉',
                Travel: '⌁',
                Celebrations: '✦',
                'Life Lessons': '✧',
                Other: '◇'
            };

            function escapeHTML(value) {
                return String(value ?? '').replace(/[&<>"']/g, char => ({
                    '&': '&amp;',
                    '<': '&lt;',
                    '>': '&gt;',
                    '"': '&quot;',
                    "'": '&#39;'
                })[char]);
            }
            async function api(url, method = 'GET', body = null) {
                const options = {
                    method,
                    headers: {}
                };
                if (body) {
                    options.headers['Content-Type'] = 'application/json';
                    options.body = JSON.stringify(body);
                }
                const response = await fetch(url, options);
                const result = await response.json();
                if (!response.ok) throw new Error(result.error || 'Something went wrong');
                return result;
            }

            function notify(message) {
                const toast = document.getElementById('toast');
                toast.textContent = message;
                toast.classList.add('show');
                setTimeout(() => toast.classList.remove('show'), 2500);
            }

            function navigate(page) {
                document.querySelectorAll('.page').forEach(el => el.classList.remove('active'));
                document.querySelectorAll('.nav button').forEach(el => el.classList.remove('active'));
                const target = document.getElementById(page);
                if (target) target.classList.add('active');
                const nav = document.querySelector(`[data-page="${page}"]`);
                if (nav) nav.classList.add('active');
                if (page === 'add-memory') fillPersonOptions('memoryPerson');
                if (page === 'add-message') fillPersonOptions('messagePerson');
                if (page === 'simulator') fillPersonOptions('simPerson');
                window.scrollTo({
                    top: 0,
                    behavior: 'smooth'
                });
            }
            document.querySelectorAll('.nav button').forEach(button => {
                button.addEventListener('click', () => navigate(button.dataset.page));
            });

            function fillPersonOptions(id) {
                const select = document.getElementById(id);
                if (!select) return;
                select.innerHTML = data.members.map(member => `
				<option value="${escapeHTML(member.name)}">${escapeHTML(member.name)}</option>`).join('');
                if (!data.members.length) {
                    select.innerHTML = ' < option value = "" > No family members available < /option>';
                }
            }

            function renderStats() {
                document.getElementById('statMemories').textContent = data.memories.length.toLocaleString();
                document.getElementById('statMembers').textContent = data.members.length.toLocaleString();
                document.getElementById('statMessages').textContent = data.messages.length.toLocaleString();
            }

            function personCard(member) {
                return `
        
                    <div class="memory-card">
                        <div class="voice-person">
                            <div class="avatar" style="background:${escapeHTML(member.color)}">
                    ${escapeHTML(member.initials)}
                </div>
                    <div>
                        <strong>${escapeHTML(member.name)}</strong>
                        <small>${escapeHTML(member.relation || 'Family member')}</small>
                    </div>
                </div>
                <p style="margin-top:18px">
                Born ${escapeHTML(member.birth_year || 'Unknown')}
            </p>
		</div>
    `;
            }

            function renderTree() {
                const container = document.getElementById('miniTree');
                const members = data.members;
                if (!members.length) {
                    container.innerHTML = ' < div class = "empty" > Add your first family member. < /div>';
                    return;
                }
                const first = members.slice(0, 1);
                const others = members.slice(1);
                const card = member => `
        
                <div class="person">
                    <div class="avatar" style="background:${escapeHTML(member.color)}">
                ${escapeHTML(member.initials)}
            </div>
                    <b>${escapeHTML(member.name)}</b>
                    <small>${escapeHTML(member.birth_year || '')}</small>
                </div>
    `;
                container.innerHTML = `
        
                    <div class="tree-row">${first.map(card).join('')}</div>
                    <div class="tree-row">${others.slice(0, 3).map(card).join('')}</div>
                    <div class="tree-row">${others.slice(3).map(card).join('')}</div>
    `;
            }

            function renderDecades() {
                const decades = {};
                data.memories.forEach(memory => {
                    const year = Number(memory.year);
                    if (!year) return;
                    const decade = Math.floor(year / 10) * 10;
                    const label = `${decade}s`;
                    decades[label] = (decades[label] || 0) + 1;
                });
                const container = document.getElementById('decades');
                const entries = Object.entries(decades).sort((a, b) => a[0].localeCompare(b[0]));
                if (!entries.length) {
                    container.innerHTML = ' < div class = "empty" > Add memories with a year to build your timeline. < /div>';
                    return;
                }
                container.innerHTML = entries.map(([label, count]) => `
        
                <div class="decade" onclick="filterDecade('${label}', this)">
                    <strong>${label}</strong>
                    <small>${count} memories</small>
                    <div style="color:#b18b45;font-size:10px;margin-top:8px">● ● ● ● ●</div>
                </div>
    `).join('');
            }

            function filterDecade(label, element) {
                document.querySelectorAll('.decade').forEach(el => el.classList.remove('selected'));
                element.classList.add('selected');
                const decade = parseInt(label);
                const filtered = data.memories.filter(memory => Math.floor(Number(memory.year) / 10) * 10 === decade);
                showFilteredMemories(filtered);
                navigate('memories');
            }

            function memoryCard(memory) {
                return `
        
                <article class="memory-card">
                    <div class="memory-icon">${icons[memory.category] || '◇'}</div>
                    <h3>${escapeHTML(memory.title)}</h3>
                    <div class="memory-meta">
                ${escapeHTML(memory.person || 'Family')} · ${escapeHTML(memory.year || 'Year unknown')}
            </div>
                <p style="margin-top:12px">${escapeHTML(memory.content)}</p>
                <span class="chip">${escapeHTML(memory.category || 'Other')}</span>
            </article>
    `;
            }

            function showFilteredMemories(memories) {
                const container = document.getElementById('memoryGrid');
                container.innerHTML = memories.length ? memories.map(memoryCard).join('') : ' < div class = "empty" > No memories found. < /div>';
            }

            function renderMemories() {
                const search = document.getElementById('memorySearch').value.toLowerCase();
                const category = document.getElementById('memoryCategory').value;
                const filtered = data.memories.filter(memory => {
                    const text = `${memory.title} ${memory.person} ${memory.content}`.toLowerCase();
                    return text.includes(search) && (!category || memory.category === category);
                });
                showFilteredMemories(filtered);
            }

            function renderVoices() {
                const container = document.getElementById('homeVoices');
                const people = data.members.slice(0, 2);
                container.innerHTML = people.map(member => `
        
                <div class="voice-card">
                    <div class="voice-person">
                        <div class="avatar" style="background:${escapeHTML(member.color)}">
                    ${escapeHTML(member.initials)}
                </div>
                    <div>
                        <strong>${escapeHTML(member.name)}</strong>
                        <small>${escapeHTML(member.relation || 'Family member')}</small>
                    </div>
                    <span class="status">SAVED</span>
                </div>
                <div class="voice-note">
                ${data.messages.filter(m => m.person === member.name).length}
                saved written messages
            </div>
            <div class="voice-actions">
                <small class="subtle">Legacy collection</small>
                <button onclick="navigate('voices')">→</button>
            </div>
        </div>
    `).join('') || ' < div class = "empty" > No members added yet. < /div>';
                const messageList = document.getElementById('messageList');
                messageList.innerHTML = data.messages.length ? data.messages.map(message => `
            
                    <div class="memory-card" style="margin-bottom:12px">
                        <div class="memory-meta">${escapeHTML(message.person)} · ${escapeHTML(message.created_at)}</div>
                        <p style="margin:12px 0 0;font:500 16px/1.7 'Playfair Display',serif">
                    “${escapeHTML(message.message)}”
                </p>
			</div>
        `).join('') : ' < div class = "empty" > No legacy messages saved yet. < /div>';
            }

            function renderFamily() {
                document.getElementById('familyGrid').innerHTML = data.members.length ? data.members.map(personCard).join('') : ' < div class = "empty" > Your family tree is waiting
                for its first member. < /div>';
            }
            async function addMember(event) {
                event.preventDefault();
                try {
                    await api('/api/member', 'POST', {
                        name: document.getElementById('memberName').value,
                        relation: document.getElementById('memberRelation').value,
                        birth_year: document.getElementById('memberYear').value
                    });
                    event.target.reset();
                    await refresh();
                    navigate('family');
                    notify('Family member added successfully.');
                } catch (error) {
                    notify(error.message);
                }
            }
            async function addMemory(event) {
                event.preventDefault();
                try {
                    await api('/api/memory', 'POST', {
                        title: document.getElementById('memoryTitle').value,
                        person: document.getElementById('memoryPerson').value,
                        category: document.getElementById('memoryType').value,
                        year: document.getElementById('memoryYear').value,
                        content: document.getElementById('memoryContent').value
                    });
                    event.target.reset();
                    await refresh();
                    navigate('memories');
                    notify('Memory saved to your archive.');
                } catch (error) {
                    notify(error.message);
                }
            }
            async function addMessage(event) {
                event.preventDefault();
                try {
                    await api('/api/message', 'POST', {
                        person: document.getElementById('messagePerson').value,
                        message: document.getElementById('messageContent').value
                    });
                    event.target.reset();
                    await refresh();
                    navigate('voices');
                    notify('Legacy message saved.');
                } catch (error) {
                    notify(error.message);
                }
            }
            async function runSimulation() {
                const person = document.getElementById('simPerson').value;
                const topic = document.getElementById('simTopic').value;
                if (!person) {
                    notify('Add a family member first.');
                    return;
                }
                const button = document.querySelector('#simulator .primary-btn');
                button.textContent = 'Creating reflection...';
                button.disabled = true;
                try {
                    const result = await api('/api/simulate', 'POST', {
                        person,
                        topic
                    });
                    document.getElementById('simulationText').textContent = result.reflection;
                    document.getElementById('simulationResult').classList.add('show');
                } catch (error) {
                    notify(error.message);
                } finally {
                    button.textContent = 'Generate Legacy Reflection ✦';
                    button.disabled = false;
                }
            }
            async function refresh() {
                try {
                    data = await api('/api/data');
                    renderStats();
                    renderTree();
                    renderDecades();
                    renderVoices();
                    renderMemories();
                    renderFamily();
                    fillPersonOptions('simPerson');
                } catch (error) {
                    notify('Unable to load your archive.');
                }
            }
            refresh();
        </script>
    </body>
</html>
"""

# ========================= HTTP SERVER =========================

class AppHandler(BaseHTTPRequestHandler):

    def send_html(self):
        body = HTML.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def read_json(self):
        length = int(self.headers.get("Content-Length", 0))

        if length > 20000:
            raise ValueError("Request is too large.")

        raw = self.rfile.read(length)
        return json.loads(raw or b"{}")

    def do_GET(self):
        path = urlparse(self.path).path

        if path == "/":
            return self.send_html()

        if path == "/api/data":
            return json_response(self, get_dashboard_data())

        json_response(self, {"error": "Endpoint not found."}, 404)

    def do_POST(self):
        path = urlparse(self.path).path

        try:
            data = self.read_json()

            if path == "/api/member":
                name = clean(data.get("name"), 70)

                if not name:
                    return json_response(self, {"error": "Name is required."}, 400)

                relation = clean(data.get("relation"), 50)
                year = clean(data.get("birth_year"), 4)

                if year and (not year.isdigit() or not 1800 <= int(year) <= 2100):
                    return json_response(self, {"error": "Invalid birth year."}, 400)

                initials = "".join(
                    word[0] for word in name.split()[:2]
                ).upper()

                with connect_db() as con:
                    index = con.execute(
                        "SELECT COUNT(*) FROM members"
                    ).fetchone()[0]

                    con.execute("""
                        INSERT INTO members
                        (name, relation, birth_year, initials, color, created_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        name, relation, year, initials,
                        colors[index % len(colors)],
                        datetime.now().isoformat(timespec="seconds")
                    ))

                return json_response(self, {"success": True}, 201)

            if path == "/api/memory":
                title = clean(data.get("title"), 100)
                content = clean(data.get("content"), 3000)

                if not title or not content:
                    return json_response(
                        self, {"error": "Title and story are required."}, 400
                    )

                year = clean(data.get("year"), 4)

                if year and (not year.isdigit() or not 1900 <= int(year) <= 2100):
                    return json_response(self, {"error": "Invalid year."}, 400)

                with connect_db() as con:
                    con.execute("""
                        INSERT INTO memories
                        (title, person, category, year, content, created_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        title,
                        clean(data.get("person"), 70),
                        clean(data.get("category"), 30),
                        year,
                        content,
                        datetime.now().isoformat(timespec="seconds")
                    ))

                return json_response(self, {"success": True}, 201)

            if path == "/api/message":
                person = clean(data.get("person"), 70)
                message = clean(data.get("message"), 3000)

                if not message:
                    return json_response(
                        self, {"error": "Message cannot be empty."}, 400
                    )

                with connect_db() as con:
                    con.execute("""
                        INSERT INTO legacy_messages
                        (person, message, created_at)
                        VALUES (?, ?, ?)
                    """, (
                        person,
                        message,
                        datetime.now().strftime("%Y-%m-%d %H:%M")
                    ))

                return json_response(self, {"success": True}, 201)

            if path == "/api/simulate":
                return self.simulate(data)

            return json_response(self, {"error": "Endpoint not found."}, 404)

        except (ValueError, json.JSONDecodeError):
            return json_response(self, {"error": "Invalid request data."}, 400)

        except Exception as error:
            print("Server error:", error)
            return json_response(self, {"error": "Internal server error."}, 500)

    def simulate(self, data):
        person = clean(data.get("person"), 70)
        topic = clean(data.get("topic"), 30)

        with connect_db() as con:
            member = con.execute(
                "SELECT * FROM members WHERE name = ?", (person,)
            ).fetchone()

            memories = con.execute("""
                SELECT title, content FROM memories
                WHERE person = ? ORDER BY id DESC LIMIT 3
            """, (person,)).fetchall()

            messages = con.execute("""
                SELECT message FROM legacy_messages
                WHERE person = ? ORDER BY id DESC LIMIT 2
            """, (person,)).fetchall()

        if not member:
            return json_response(self, {"error": "Member not found."}, 404)

        stories = [row["title"] for row in memories]
        notes = [row["message"] for row in messages]

        story_text = (
            "Your family's archive remembers " + ", ".join(stories) + "."
            if stories else
            "Your family's archive is still waiting for more stories."
        )

        if topic == "family":
            reflection = (
                f"Looking through {person}'s family memories, one idea stands out: "
                "the moments we share with one another often become our most "
                "meaningful inheritance.\n\n"
                + story_text +
                "\n\nKeep making time for the people who make life feel like home."
            )

        elif topic == "memories":
            reflection = (
                f"A life is made of many little moments. "
                f"The archive connected with {person} includes these stories: "
                + ", ".join(stories or ["More memories are yet to be added"]) +
                ".\n\nPreserving these moments gives future generations "
                "a way to understand where their family stories began."
            )

        elif topic == "future":
            reflection = (
                "To the generations still to come:\n\n"
                "Your family's story did not begin with you, and it does not "
                "end with you. Learn from the past, make your own memories, "
                "and leave something kind behind for those who follow."
                "\n\nThis reflection is inspired by the family's saved archive."
            )

        elif topic == "kindness":
            reflection = (
                "Among the many things a family can pass down, kindness "
                "is one of the most valuable.\n\n"
                "Remember the people who helped you, be generous with your "
                "time, and never underestimate a small act of care.\n\n"
                + story_text
            )

        else:
            reflection = (
                "Life advice inspired by the family's preserved memories:\n\n"
                "Make time for the people you love. Keep learning, stay curious, "
                "and do not measure a meaningful life only by achievements. "
                "The stories we share and the kindness we leave behind "
                "can matter for generations.\n\n"
                + story_text
            )

        if notes:
            reflection += "\n\nA saved family message also says: “" + notes[0] + "”"

        return json_response(self, {
            "reflection": reflection,
            "person": person,
            "type": "fictional_legacy_reflection"
        })


# ========================= START =========================

if __name__ == "__main__":
    initialize_db()

    server = HTTPServer((HOST, PORT), AppHandler)

    print("\n" + "=" * 55)
    print("       DIGITAL AFTERLIFE SIMULATOR")
    print("=" * 55)
    print(f"\n  Dashboard: http://{HOST}:{PORT}")
    print(f"  Database : {DB}")
    print("\n  Press CTRL + C to stop the server.")
    print("=" * 55 + "\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
        server.server_close()
