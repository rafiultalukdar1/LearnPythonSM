
"""
SUPPLY CHAIN DISRUPTION SIMULATOR
--------------------------------
A single-file Python application using only the standard library.

Features:
- Interactive supply chain simulation
- Supplier, transport, demand and material disruptions
- Inventory and stockout projections
- Estimated revenue loss and recovery costs
- Supplier risk comparison
- Scenario comparison
- Simulation history with SQLite
- CSV and JSON report exports
- Responsive dark dashboard

Run:
    python SupplyChainDisruptionSimulator.py

Open:
    http://127.0.0.1:8004
"""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
from datetime import datetime
from pathlib import Path
from collections import defaultdict
import json
import sqlite3
import threading
import random
import math
import uuid
import webbrowser


HOST = "127.0.0.1"
PORT = 8004
DB_FILE = Path(__file__).with_name("supply_chain_simulator.db")
MAX_BODY = 1024 * 1024

DB_LOCK = threading.Lock()


# ============================================================
# DATABASE
# ============================================================

def connect_db():
    conn = sqlite3.connect(DB_FILE, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with DB_LOCK:
        with connect_db() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS simulations (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    duration INTEGER NOT NULL,
                    report_json TEXT NOT NULL
                )
            """)
            conn.commit()


def save_simulation(report):
    with DB_LOCK:
        with connect_db() as conn:
            conn.execute("""
                INSERT INTO simulations
                (id, name, created_at, duration, report_json)
                VALUES (?, ?, ?, ?, ?)
            """, (
                report["id"],
                report["name"],
                report["createdAt"],
                report["duration"],
                json.dumps(report, ensure_ascii=False)
            ))
            conn.commit()


def get_history():
    with DB_LOCK:
        with connect_db() as conn:
            rows = conn.execute("""
                SELECT id, name, created_at, duration, report_json
                FROM simulations
                ORDER BY created_at DESC
                LIMIT 50
            """).fetchall()

    items = []
    for row in rows:
        try:
            report = json.loads(row["report_json"])
            items.append({
                "id": row["id"],
                "name": row["name"],
                "createdAt": row["created_at"],
                "duration": row["duration"],
                "summary": report.get("summary", {})
            })
        except (TypeError, json.JSONDecodeError):
            continue

    return items


def get_simulation(simulation_id):
    with DB_LOCK:
        with connect_db() as conn:
            row = conn.execute(
                "SELECT report_json FROM simulations WHERE id = ?",
                (simulation_id,)
            ).fetchone()

    if not row:
        return None

    return json.loads(row["report_json"])


# ============================================================
# DEFAULT SUPPLY CHAIN MODEL
# ============================================================

DEFAULT_PRODUCTS = [
    {
        "id": "P001",
        "name": "Electronic Components",
        "supplier": "Alpha Electronics",
        "supplierRegion": "East Asia",
        "inventory": 900,
        "dailyDemand": 90,
        "unitCost": 18,
        "unitPrice": 35,
        "leadTime": 5,
        "safetyStock": 300,
        "criticality": 1.4
    },
    {
        "id": "P002",
        "name": "Industrial Motors",
        "supplier": "Global Motor Works",
        "supplierRegion": "Europe",
        "inventory": 650,
        "dailyDemand": 55,
        "unitCost": 75,
        "unitPrice": 125,
        "leadTime": 7,
        "safetyStock": 200,
        "criticality": 1.3
    },
    {
        "id": "P003",
        "name": "Packaging Materials",
        "supplier": "PackRight Industries",
        "supplierRegion": "South Asia",
        "inventory": 1400,
        "dailyDemand": 120,
        "unitCost": 4,
        "unitPrice": 9,
        "leadTime": 3,
        "safetyStock": 400,
        "criticality": 0.8
    },
    {
        "id": "P004",
        "name": "Battery Cells",
        "supplier": "VoltSource Ltd",
        "supplierRegion": "East Asia",
        "inventory": 500,
        "dailyDemand": 65,
        "unitCost": 42,
        "unitPrice": 78,
        "leadTime": 9,
        "safetyStock": 250,
        "criticality": 1.5
    },
    {
        "id": "P005",
        "name": "Steel Frames",
        "supplier": "Metro Steel",
        "supplierRegion": "North America",
        "inventory": 1100,
        "dailyDemand": 70,
        "unitCost": 28,
        "unitPrice": 52,
        "leadTime": 6,
        "safetyStock": 250,
        "criticality": 1.0
    }
]


DISRUPTION_TYPES = {
    "supplier_shutdown": {
        "label": "Supplier Shutdown",
        "description": "A supplier temporarily stops production.",
        "supply_impact": 0.95,
        "delay": 8,
        "cost": 0.08
    },
    "shipping_delay": {
        "label": "Shipping Delay",
        "description": "Transportation takes longer than expected.",
        "supply_impact": 0.45,
        "delay": 5,
        "cost": 0.12
    },
    "material_shortage": {
        "label": "Raw Material Shortage",
        "description": "A shortage reduces supplier production capacity.",
        "supply_impact": 0.65,
        "delay": 6,
        "cost": 0.18
    },
    "demand_spike": {
        "label": "Demand Spike",
        "description": "Customer demand increases unexpectedly.",
        "supply_impact": 0.0,
        "delay": 0,
        "cost": 0.0
    },
    "transport_strike": {
        "label": "Transport Strike",
        "description": "A transport network experiences a labor disruption.",
        "supply_impact": 0.75,
        "delay": 9,
        "cost": 0.2
    },
    "natural_disaster": {
        "label": "Natural Disaster",
        "description": "A regional event disrupts supplier and transport operations.",
        "supply_impact": 0.8,
        "delay": 12,
        "cost": 0.25
    }
}


# ============================================================
# SIMULATION ENGINE
# ============================================================

def clamp(value, minimum, maximum):
    return max(minimum, min(maximum, value))


def money(value):
    return round(float(value), 2)


def simulate(payload):
    name = str(payload.get("name", "Supply Chain Scenario")).strip()
    name = name[:100] or "Supply Chain Scenario"

    duration = int(payload.get("duration", 30))
    severity = int(payload.get("severity", 60))
    demand_change = int(payload.get("demandChange", 0))
    seed = int(payload.get("seed", 42))

    if not 7 <= duration <= 180:
        raise ValueError("Simulation duration must be between 7 and 180 days.")

    if not 10 <= severity <= 100:
        raise ValueError("Disruption severity must be between 10 and 100.")

    if not -50 <= demand_change <= 150:
        raise ValueError("Demand change must be between -50% and 150%.")

    selected_types = payload.get("disruptions", [])
    if not isinstance(selected_types, list):
        raise ValueError("Disruptions must be a list.")

    selected_types = list(dict.fromkeys(selected_types))

    if not selected_types:
        raise ValueError("Select at least one disruption type.")

    for kind in selected_types:
        if kind not in DISRUPTION_TYPES:
            raise ValueError(f"Unknown disruption type: {kind}")

    rng = random.Random(seed)
    products = [dict(p) for p in DEFAULT_PRODUCTS]

    disruption_factor = severity / 100
    demand_factor = 1 + demand_change / 100

    # Apply selected disruption impacts to each product.
    product_states = []

    for product in products:
        inventory = float(product["inventory"])
        daily_demand = product["dailyDemand"] * demand_factor
        lead_time = product["leadTime"]
        supply_reduction = 0.0
        added_delay = 0
        extra_cost_rate = 0.0
        events = []

        for kind in selected_types:
            config = DISRUPTION_TYPES[kind]

            # Demand spike is handled through demand_factor.
            if kind == "demand_spike":
                continue

            # Different products have different exposure.
            exposure = (
                0.75 + rng.random() * 0.5
            ) * product["criticality"]

            impact = (
                config["supply_impact"]
                * disruption_factor
                * exposure
            )
            supply_reduction += impact

            added_delay += int(
                config["delay"] * disruption_factor * exposure
            )

            extra_cost_rate += config["cost"] * disruption_factor

            events.append({
                "type": kind,
                "label": config["label"],
                "impact": round(impact * 100, 1)
            })

        supply_reduction = clamp(supply_reduction, 0, 0.98)
        added_delay = min(added_delay, 45)

        effective_lead_time = lead_time + added_delay

        product_states.append({
            **product,
            "inventoryStart": inventory,
            "inventory": inventory,
            "dailyDemand": daily_demand,
            "baseLeadTime": lead_time,
            "effectiveLeadTime": effective_lead_time,
            "supplyReduction": supply_reduction,
            "extraCostRate": extra_cost_rate,
            "events": events,
            "stockoutDay": None,
            "stockoutDays": 0,
            "unitsLost": 0,
            "unitsServed": 0,
            "unitsDemanded": 0,
            "recoveryCost": 0.0,
            "revenueLost": 0.0,
            "history": []
        })

    total_revenue_lost = 0.0
    total_recovery_cost = 0.0
    total_demand = 0.0
    total_served = 0.0
    daily_summary = []

    # Simplified replenishment model:
    # replenishment arrives after effective lead time, with reduced quantity.
    # A recurring replenishment order is placed each lead-time cycle.
    for day in range(1, duration + 1):
        day_demand = 0.0
        day_served = 0.0
        day_lost = 0.0
        day_recovery = 0.0
        day_stockout_products = 0

        for state in product_states:
            demand = state["dailyDemand"] * (
                1 + rng.uniform(-0.04, 0.04)
            )
            demand = max(0, demand)

            state["unitsDemanded"] += demand
            day_demand += demand

            # Replenishment is delivered at the start of each cycle.
            if (
                day > 1
                and (day - 1) % max(1, state["effectiveLeadTime"]) == 0
            ):
                order_quantity = (
                    state["dailyDemand"]
                    * state["effectiveLeadTime"]
                )
                delivered = order_quantity * (
                    1 - state["supplyReduction"]
                )

                state["inventory"] += delivered

                expedited_cost = (
                    delivered
                    * state["unitCost"]
                    * state["extraCostRate"]
                )
                state["recoveryCost"] += expedited_cost
                day_recovery += expedited_cost

            available = max(0, state["inventory"])
            served = min(available, demand)
            lost = max(0, demand - served)

            state["inventory"] -= served
            state["unitsServed"] += served
            state["unitsLost"] += lost

            revenue_lost = lost * state["unitPrice"]
            state["revenueLost"] += revenue_lost

            day_served += served
            day_lost += lost

            if lost > 0:
                if state["stockoutDay"] is None:
                    state["stockoutDay"] = day
                state["stockoutDays"] += 1

            if state["inventory"] <= state["safetyStock"]:
                day_stockout_products += 1

            state["history"].append({
                "day": day,
                "inventory": round(state["inventory"], 1),
                "demand": round(demand, 1),
                "served": round(served, 1),
                "lost": round(lost, 1)
            })

        total_demand += day_demand
        total_served += day_served
        total_revenue_lost += day_lost * 1  # Per-product revenue added below.
        total_recovery_cost += day_recovery

        # Correct daily lost revenue using product-specific prices.
        daily_revenue_lost = sum(
            state["history"][-1]["lost"] * state["unitPrice"]
            for state in product_states
        )

        daily_summary.append({
            "day": day,
            "demand": round(day_demand, 1),
            "served": round(day_served, 1),
            "lost": round(day_lost, 1),
            "revenueLost": money(daily_revenue_lost),
            "recoveryCost": money(day_recovery),
            "atRiskProducts": day_stockout_products
        })

    total_revenue_lost = sum(p["revenueLost"] for p in product_states)
    total_recovery_cost = sum(p["recoveryCost"] for p in product_states)

    initial_inventory = sum(p["inventoryStart"] for p in product_states)
    final_inventory = sum(p["inventory"] for p in product_states)
    total_units_lost = sum(p["unitsLost"] for p in product_states)

    service_level = (
        total_served / total_demand * 100
        if total_demand else 100
    )

    stockout_products = [
        p for p in product_states if p["stockoutDay"] is not None
    ]

    total_financial_impact = total_revenue_lost + total_recovery_cost

    if service_level >= 95:
        risk_level = "Low"
    elif service_level >= 80:
        risk_level = "Moderate"
    elif service_level >= 60:
        risk_level = "High"
    else:
        risk_level = "Critical"

    # Supplier exposure summary.
    supplier_map = defaultdict(list)
    for product in product_states:
        supplier_map[product["supplier"]].append(product)

    suppliers = []
    for supplier_name, supplier_products in supplier_map.items():
        average_reduction = (
            sum(p["supplyReduction"] for p in supplier_products)
            / len(supplier_products)
        )

        suppliers.append({
            "name": supplier_name,
            "region": supplier_products[0]["supplierRegion"],
            "products": len(supplier_products),
            "averageSupplyReduction": round(average_reduction * 100, 1),
            "risk": (
                "High" if average_reduction >= 0.55
                else "Moderate" if average_reduction >= 0.25
                else "Low"
            )
        })

    suppliers.sort(
        key=lambda s: s["averageSupplyReduction"],
        reverse=True
    )

    recommendations = []

    if stockout_products:
        recommendations.append(
            "Prioritize replenishment for products that experienced stockouts."
        )

    if service_level < 95:
        recommendations.append(
            "Review safety-stock levels and consider increasing buffer inventory."
        )

    if len(selected_types) > 1:
        recommendations.append(
            "Evaluate combined-disruption scenarios instead of planning for "
            "each disruption independently."
        )

    if any(p["supplyReduction"] >= 0.5 for p in product_states):
        recommendations.append(
            "Identify alternative suppliers for products with high supply exposure."
        )

    if demand_change > 0:
        recommendations.append(
            "Use demand forecasting and capacity planning to prepare for increased demand."
        )

    if not recommendations:
        recommendations.append(
            "Continue monitoring inventory, supplier lead times, and demand changes."
        )

    report = {
        "id": uuid.uuid4().hex[:12],
        "name": name,
        "createdAt": datetime.now().astimezone().isoformat(timespec="seconds"),
        "duration": duration,
        "severity": severity,
        "demandChange": demand_change,
        "seed": seed,
        "disruptions": [
            {
                "id": kind,
                "label": DISRUPTION_TYPES[kind]["label"],
                "description": DISRUPTION_TYPES[kind]["description"]
            }
            for kind in selected_types
        ],
        "summary": {
            "serviceLevel": round(service_level, 2),
            "riskLevel": risk_level,
            "totalDemand": round(total_demand, 1),
            "unitsServed": round(total_served, 1),
            "unitsLost": round(total_units_lost, 1),
            "stockoutProducts": len(stockout_products),
            "initialInventory": round(initial_inventory, 1),
            "finalInventory": round(final_inventory, 1),
            "revenueLost": money(total_revenue_lost),
            "recoveryCost": money(total_recovery_cost),
            "financialImpact": money(total_financial_impact)
        },
        "products": [
            {
                **{
                    k: v for k, v in p.items()
                    if k not in ("history",)
                },
                "inventory": round(p["inventory"], 1),
                "supplyReductionPercent": round(
                    p["supplyReduction"] * 100, 1
                ),
                "unitsDemanded": round(p["unitsDemanded"], 1),
                "unitsServed": round(p["unitsServed"], 1),
                "unitsLost": round(p["unitsLost"], 1),
                "revenueLost": money(p["revenueLost"]),
                "recoveryCost": money(p["recoveryCost"])
            }
            for p in product_states
        ],
        "daily": daily_summary,
        "suppliers": suppliers,
        "recommendations": recommendations,
        "methodology": {
            "type": "Deterministic scenario with seeded random daily demand variation",
            "replenishment": (
                "Simplified periodic replenishment based on effective lead time "
                "and supply reduction."
            ),
            "limitations": [
                "This is an educational model, not a live supply-chain forecast.",
                "The default supplier and inventory data are illustrative.",
                "The model does not represent actual shipping networks or contracts.",
                "Financial impact is estimated from configured unit prices and costs.",
                "Actual recovery time and supplier behavior may differ."
            ]
        }
    }

    return report


# ============================================================
# WEB DASHBOARD
# ============================================================

HTML = r"""

<!DOCTYPE html>
<html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Supply Chain Disruption Simulator</title>
        <style>
            :root {
                --bg: #0b0e13;
                --panel: #141a23;
                --panel2: #1b2330;
                --line: #293443;
                --text: #f3f5f8;
                --muted: #8e9aab;
                --orange: #ff8a32;
                --orange2: #ffb46f;
                --green: #48d6a0;
                --red: #ff6878;
                --yellow: #f4c15d;
                --blue: #79b7ff;
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
            select {
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
                background: #0e1219;
                border-right: 1px solid var(--line);
                padding: 24px 17px
            }

            .brand {
                display: flex;
                align-items: center;
                gap: 11px;
                padding: 0 8px 30px
            }

            .logo {
                width: 41px;
                height: 41px;
                display: grid;
                place-items: center;
                background: var(--orange);
                color: #211208;
                border-radius: 12px;
                font-weight: 900;
                font-size: 20px
            }

            .brand strong {
                display: block;
                font-size: 14px
            }

            .brand small {
                color: var(--muted);
                font-size: 11px
            }

            .nav-label {
                font-size: 10px;
                letter-spacing: 1.7px;
                color: #697587;
                padding: 12px 10px
            }

            .nav {
                width: 100%;
                padding: 11px 12px;
                margin: 3px 0;
                border: 0;
                border-radius: 9px;
                background: transparent;
                color: var(--muted);
                text-align: left
            }

            .nav:hover,
            .nav.active {
                background: #302216;
                color: var(--orange2)
            }

            .side-card {
                margin-top: 30px;
                border: 1px solid var(--line);
                border-radius: 12px;
                padding: 14px;
                color: var(--muted);
                font-size: 12px
            }

            main {
                padding: 30px clamp(16px, 3vw, 42px);
                max-width: 1600px;
                width: 100%;
                min-width: 0
            }

            .top {
                display: flex;
                align-items: center;
                justify-content: space-between;
                gap: 15px;
                margin-bottom: 25px
            }

            .eyebrow {
                font-size: 11px;
                color: var(--orange);
                letter-spacing: 1.8px;
                font-weight: 800
            }

            h1 {
                font-size: clamp(24px, 3vw, 34px);
                line-height: 1.2;
                margin: 7px 0
            }

            .subtitle {
                color: var(--muted);
                margin: 8px 0 0
            }

            .local {
                color: var(--green);
                border: 1px solid #285b48;
                border-radius: 30px;
                padding: 7px 11px;
                font-size: 11px;
                white-space: nowrap
            }

            .page {
                display: none
            }

            .page.active {
                display: block
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

            .metric,
            .panel {
                background: var(--panel);
                border: 1px solid var(--line);
                border-radius: 14px
            }

            .metric {
                padding: 18px
            }

            .metric-label {
                color: var(--muted);
                font-size: 12px
            }

            .metric-value {
                font-size: 27px;
                font-weight: 800;
                letter-spacing: -.7px;
                margin: 7px 0 2px
            }

            .metric-hint {
                font-size: 11px;
                color: var(--muted)
            }

            .panel {
                padding: 20px;
                margin-bottom: 17px;
                min-width: 0
            }

            .panel-head {
                display: flex;
                align-items: center;
                justify-content: space-between;
                gap: 12px;
                margin-bottom: 15px
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

            .fields {
                display: grid;
                grid-template-columns: repeat(2, minmax(0, 1fr));
                gap: 15px
            }

            label {
                display: block;
                color: #ccd3df;
                font-size: 12px;
                margin-bottom: 7px
            }

            input,
            select {
                width: 100%;
                background: #0d121a;
                color: var(--text);
                border: 1px solid #303c4d;
                border-radius: 9px;
                padding: 11px;
                outline: none
            }

            input:focus,
            select:focus {
                border-color: var(--orange)
            }

            input[type=range] {
                padding: 0;
                accent-color: var(--orange)
            }

            .field {
                min-width: 0
            }

            .range-row {
                display: flex;
                justify-content: space-between;
                color: var(--muted);
                font-size: 12px
            }

            .checks {
                display: grid;
                grid-template-columns: repeat(2, minmax(0, 1fr));
                gap: 10px
            }

            .check {
                display: flex;
                align-items: flex-start;
                gap: 10px;
                padding: 12px;
                background: #101620;
                border: 1px solid var(--line);
                border-radius: 10px
            }

            .check input {
                width: auto;
                margin-top: 4px;
                accent-color: var(--orange)
            }

            .check strong {
                display: block;
                font-size: 12px
            }

            .check small {
                display: block;
                color: var(--muted);
                font-size: 11px
            }

            .btn {
                border: 1px solid var(--line);
                border-radius: 9px;
                background: #202a38;
                color: var(--text);
                padding: 10px 14px
            }

            .btn.primary {
                background: var(--orange);
                border-color: var(--orange);
                color: #1c1008;
                font-weight: 800
            }

            .btn:hover {
                filter: brightness(1.1)
            }

            .btn:disabled {
                opacity: .5;
                cursor: wait
            }

            .actions {
                display: flex;
                flex-wrap: wrap;
                gap: 9px;
                margin-top: 16px
            }

            .pill {
                display: inline-block;
                border-radius: 30px;
                padding: 4px 8px;
                font-size: 10px;
                background: #273140;
                color: #d0d7e3
            }

            .pill.low {
                background: #15372b;
                color: #83e4b7
            }

            .pill.moderate {
                background: #3c331b;
                color: #f2d17a
            }

            .pill.high,
            .pill.critical {
                background: #412326;
                color: #ff9aa4
            }

            .chart {
                display: flex;
                flex-direction: column;
                gap: 14px
            }

            .chart-row {
                display: grid;
                grid-template-columns: minmax(100px, 145px) minmax(40px, 1fr) 65px;
                gap: 10px;
                align-items: center
            }

            .chart-label {
                overflow: hidden;
                text-overflow: ellipsis;
                white-space: nowrap;
                font-size: 12px;
                color: #d8deea
            }

            .track {
                height: 12px;
                border-radius: 20px;
                background: #293240;
                overflow: hidden
            }

            .fill {
                height: 100%;
                border-radius: 20px;
                background: linear-gradient(90deg, #ff7624, #ffb46f)
            }

            .chart-value {
                text-align: right;
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
                background: #19212d;
                color: var(--muted);
                font-weight: 600
            }

            td {
                color: #dce2ec
            }

            .notice {
                border: 1px solid #5d4024;
                background: #241c15;
                color: #f0c49b;
                padding: 12px 14px;
                border-radius: 10px;
                margin: 15px 0;
                font-size: 12px
            }

            .alert {
                border: 1px solid #5d4024;
                background: #241c15;
                color: #f0c49b;
                padding: 12px 14px;
                border-radius: 10px;
                margin: 8px 0;
                font-size: 12px
            }

            .empty {
                padding: 25px;
                text-align: center;
                color: var(--muted)
            }

            .kv {
                display: grid;
                grid-template-columns: 145px 1fr;
                gap: 10px;
                padding: 9px 0;
                border-bottom: 1px solid var(--line)
            }

            .kv strong {
                font-size: 12px
            }

            .kv span {
                font-size: 12px;
                color: var(--muted)
            }

            .product-list {
                display: grid;
                gap: 12px
            }

            .product-card {
                border: 1px solid var(--line);
                border-radius: 11px;
                padding: 13px;
                background: #101620
            }

            .product-top {
                display: flex;
                justify-content: space-between;
                gap: 12px
            }

            .product-name {
                font-weight: 700
            }

            .product-meta {
                color: var(--muted);
                font-size: 11px
            }

            .product-stats {
                display: grid;
                grid-template-columns: repeat(3, 1fr);
                gap: 8px;
                margin-top: 12px
            }

            .product-stat {
                background: #1a2230;
                border-radius: 8px;
                padding: 8px
            }

            .product-stat small {
                display: block;
                color: var(--muted);
                font-size: 10px
            }

            .product-stat strong {
                font-size: 13px
            }

            footer {
                margin-top: 25px;
                padding: 17px 0;
                border-top: 1px solid var(--line);
                color: #697587;
                font-size: 11px
            }

            .toast {
                position: fixed;
                right: 20px;
                bottom: 20px;
                z-index: 9;
                background: #202a38;
                border: 1px solid var(--line);
                border-radius: 10px;
                padding: 13px 17px;
                display: none;
                max-width: 90vw
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
                    padding: 12px;
                    border: 0;
                    border-bottom: 1px solid var(--line)
                }

                .brand {
                    padding: 5px 6px 12px
                }

                .nav-label,
                .side-card {
                    display: none
                }

                .navs {
                    display: flex;
                    overflow: auto;
                    gap: 4px
                }

                .nav {
                    width: auto;
                    white-space: nowrap;
                    padding: 9px 11px
                }

                main {
                    padding: 22px 14px
                }

                .top {
                    align-items: flex-start;
                    flex-direction: column
                }

                .two,
                .fields {
                    grid-template-columns: 1fr
                }

                .checks {
                    grid-template-columns: 1fr
                }

                .chart-row {
                    grid-template-columns: 90px minmax(30px, 1fr) 55px
                }
            }
        </style>
    </head>
    <body>
        <div class="app">
            <aside>
                <div class="brand">
                    <div class="logo">S</div>
                    <div>
                        <strong>SupplyChain Lab</strong>
                        <small>Disruption Simulator</small>
                    </div>
                </div>
                <div class="nav-label">WORKSPACE</div>
                <div class="navs">
                    <button class="nav active" data-page="overview">◈ &nbsp; Overview</button>
                    <button class="nav" data-page="configure">＋ &nbsp; Configure</button>
                    <button class="nav" data-page="history">◷ &nbsp; History</button>
                    <button class="nav" data-page="methodology">◎ &nbsp; Methodology</button>
                </div>
                <div class="side-card">
                    <strong style="color:#e2e7ef">Scenario engine</strong>
                    <p>Test how disruptions can affect inventory, service levels, and estimated financial impact.</p>
                    <span class="pill low">LOCAL SIMULATION</span>
                </div>
            </aside>
            <main>
                <div class="top">
                    <div>
                        <div class="eyebrow">OPERATIONS INTELLIGENCE / RISK LAB</div>
                        <h1 id="pageTitle">Supply Chain Overview</h1>
                        <p class="subtitle" id="pageSubtitle">Understand how unexpected events can affect your supply chain.</p>
                    </div>
                    <span class="local">● Running locally</span>
                </div>
                <section id="overview" class="page active">
                    <div class="grid metrics">
                        <div class="metric">
                            <div class="metric-label">Service level</div>
                            <div class="metric-value" id="mService">—</div>
                            <div class="metric-hint">Demand successfully served</div>
                        </div>
                        <div class="metric">
                            <div class="metric-label">Financial impact</div>
                            <div class="metric-value" id="mImpact">—</div>
                            <div class="metric-hint">Revenue loss + recovery cost</div>
                        </div>
                        <div class="metric">
                            <div class="metric-label">Stockout products</div>
                            <div class="metric-value" id="mStockouts">—</div>
                            <div class="metric-hint">Products with unmet demand</div>
                        </div>
                        <div class="metric">
                            <div class="metric-label">Risk level</div>
                            <div class="metric-value" id="mRisk">—</div>
                            <div class="metric-hint">Based on service level</div>
                        </div>
                    </div>
                    <div class="grid two" style="margin-top:18px">
                        <div class="panel">
                            <div class="panel-head">
                                <h2>Daily demand vs fulfilled</h2>
                                <span class="pill">LATEST RUN</span>
                            </div>
                            <div id="overviewChart" class="chart">
                                <div class="empty">Run a simulation to view projections.</div>
                            </div>
                        </div>
                        <div class="panel">
                            <div class="panel-head">
                                <h2>Scenario summary</h2>
                            </div>
                            <div id="overviewSummary" class="empty">No simulation has been run yet.</div>
                        </div>
                    </div>
                    <div class="panel">
                        <div class="panel-head">
                            <h2>Product inventory status</h2>
                        </div>
                        <div id="overviewProducts" class="empty">Inventory projections will appear here.</div>
                    </div>
                    <div class="panel">
                        <div class="panel-head">
                            <h2>Recent simulations</h2>
                            <button class="btn" onclick="showPage('history')">View history →</button>
                        </div>
                        <div id="recentHistory" class="table-wrap">
                            <div class="empty">No saved simulations.</div>
                        </div>
                    </div>
                </section>
                <section id="configure" class="page">
                    <div class="panel">
                        <div class="panel-head">
                            <h2>Configure disruption scenario</h2>
                            <span class="pill">SIMULATION SETTINGS</span>
                        </div>
                        <div class="fields">
                            <div class="field">
                                <label for="scenarioName">Scenario name</label>
                                <input id="scenarioName" value="Port Disruption Scenario" maxlength="100">
                            </div>
                            <div class="field">
                                <label for="duration">Simulation duration (days)</label>
                                <input id="duration" type="number" min="7" max="180" value="30">
                            </div>
                            <div class="field">
                                <label for="severity">Disruption severity</label>
                                <div class="range-row">
                                    <span>Low</span>
                                    <strong id="severityValue">60%</strong>
                                    <span>Extreme</span>
                                </div>
                                <input id="severity" type="range" min="10" max="100" value="60">
                            </div>
                            <div class="field">
                                <label for="demandChange">Demand change (%)</label>
                                <div class="range-row">
                                    <span>Lower demand</span>
                                    <strong id="demandValue">0%</strong>
                                    <span>Higher demand</span>
                                </div>
                                <input id="demandChange" type="range" min="-50" max="150" value="0">
                            </div>
                            <div class="field">
                                <label for="seed">Random seed</label>
                                <input id="seed" type="number" value="42" min="1" max="999999999">
                            </div>
                        </div>
                        <div class="notice">Severity affects disruption impact. Demand change is applied to all products. Use the same seed and settings to reproduce a scenario.</div>
                    </div>
                    <div class="panel">
                        <div class="panel-head">
                            <h2>Select disruption events</h2>
                            <span class="pill">MULTI-SELECT</span>
                        </div>
                        <div class="checks" id="disruptionChecks">
                            <label class="check">
                                <input type="checkbox" value="supplier_shutdown" checked>
                                <span>
                                    <strong>Supplier Shutdown</strong>
                                    <small>A supplier temporarily stops production.</small>
                                </span>
                            </label>
                            <label class="check">
                                <input type="checkbox" value="shipping_delay" checked>
                                <span>
                                    <strong>Shipping Delay</strong>
                                    <small>Transportation takes longer than expected.</small>
                                </span>
                            </label>
                            <label class="check">
                                <input type="checkbox" value="material_shortage">
                                <span>
                                    <strong>Raw Material Shortage</strong>
                                    <small>Supplier production capacity decreases.</small>
                                </span>
                            </label>
                            <label class="check">
                                <input type="checkbox" value="demand_spike">
                                <span>
                                    <strong>Demand Spike</strong>
                                    <small>Customer demand increases unexpectedly.</small>
                                </span>
                            </label>
                            <label class="check">
                                <input type="checkbox" value="transport_strike">
                                <span>
                                    <strong>Transport Strike</strong>
                                    <small>A transport network experiences disruption.</small>
                                </span>
                            </label>
                            <label class="check">
                                <input type="checkbox" value="natural_disaster">
                                <span>
                                    <strong>Natural Disaster</strong>
                                    <small>A regional event affects suppliers and routes.</small>
                                </span>
                            </label>
                        </div>
                        <div class="actions">
                            <button class="btn" onclick="selectAll(true)">Select all</button>
                            <button class="btn" onclick="selectAll(false)">Clear selection</button>
                            <button class="btn primary" id="runBtn" onclick="runSimulation()">Run simulation ↗</button>
                        </div>
                    </div>
                    <div class="panel">
                        <h2>Default supply chain products</h2>
                        <p class="muted small">The simulator uses five illustrative products, suppliers, inventory levels, and lead times. These values are not live business data.</p>
                        <div id="defaultProducts" class="product-list"></div>
                    </div>
                </section>
                <section id="results" class="page">
                    <div class="panel">
                        <div class="panel-head">
                            <h2 id="resultTitle">Simulation results</h2>
                            <div class="actions" style="margin:0">
                                <button class="btn" onclick="downloadReport('json')">Export JSON</button>
                                <button class="btn" onclick="downloadReport('csv')">Export CSV</button>
                            </div>
                        </div>
                        <p id="resultMeta" class="muted small"></p>
                    </div>
                    <div class="grid metrics">
                        <div class="metric">
                            <div class="metric-label">Service level</div>
                            <div class="metric-value" id="rService">—</div>
                        </div>
                        <div class="metric">
                            <div class="metric-label">Financial impact</div>
                            <div class="metric-value" id="rImpact">—</div>
                        </div>
                        <div class="metric">
                            <div class="metric-label">Stockout products</div>
                            <div class="metric-value" id="rStockouts">—</div>
                        </div>
                        <div class="metric">
                            <div class="metric-label">Risk level</div>
                            <div class="metric-value" id="rRisk">—</div>
                        </div>
                    </div>
                    <div class="grid two" style="margin-top:18px">
                        <div class="panel">
                            <div class="panel-head">
                                <h2>Daily demand vs fulfilled</h2>
                            </div>
                            <div id="resultChart" class="chart"></div>
                        </div>
                        <div class="panel">
                            <div class="panel-head">
                                <h2>Financial breakdown</h2>
                            </div>
                            <div id="financialBreakdown"></div>
                        </div>
                    </div>
                    <div class="panel">
                        <div class="panel-head">
                            <h2>Product-level impact</h2>
                        </div>
                        <div id="productResults" class="product-list"></div>
                    </div>
                    <div class="panel">
                        <div class="panel-head">
                            <h2>Supplier exposure</h2>
                        </div>
                        <div id="supplierResults" class="table-wrap"></div>
                    </div>
                    <div class="panel">
                        <div class="panel-head">
                            <h2>Recommended actions</h2>
                        </div>
                        <div id="recommendations"></div>
                    </div>
                    <div class="panel">
                        <div class="panel-head">
                            <h2>Daily simulation data</h2>
                        </div>
                        <div id="dailyTable" class="table-wrap"></div>
                    </div>
                </section>
                <section id="history" class="page">
                    <div class="panel">
                        <div class="panel-head">
                            <h2>Saved simulation history</h2>
                            <button class="btn" onclick="refreshHistory()">Refresh</button>
                        </div>
                        <p class="muted small">The latest 50 simulation reports are saved in a local SQLite database.</p>
                        <div id="historyTable" class="table-wrap">
                            <div class="empty">Loading…</div>
                        </div>
                    </div>
                </section>
                <section id="methodology" class="page">
                    <div class="panel">
                        <h2>How the simulation works</h2>
                        <div class="kv">
                            <strong>Inventory</strong>
                            <span>Each product starts with a configured stock quantity and daily demand.</span>
                        </div>
                        <div class="kv">
                            <strong>Disruptions</strong>
                            <span>Selected events reduce supply availability, increase lead times, or increase demand.</span>
                        </div>
                        <div class="kv">
                            <strong>Replenishment</strong>
                            <span>Orders are modeled periodically using effective lead time and adjusted supply quantities.</span>
                        </div>
                        <div class="kv">
                            <strong>Service level</strong>
                            <span>Units served divided by total units demanded, expressed as a percentage.</span>
                        </div>
                        <div class="kv">
                            <strong>Revenue loss</strong>
                            <span>Unfulfilled units multiplied by each product's illustrative unit selling price.</span>
                        </div>
                        <div class="kv">
                            <strong>Recovery cost</strong>
                            <span>Estimated additional replenishment cost based on the selected disruption cost factors.</span>
                        </div>
                        <div class="kv">
                            <strong>Risk level</strong>
                            <span>Low: 95%+ service; Moderate: 80–94.99%; High: 60–79.99%; Critical: below 60%.</span>
                        </div>
                    </div>
                    <div class="panel">
                        <h2>Model limitations</h2>
                        <ul class="muted">
                            <li>All default products and supplier details are fictional examples.</li>
                            <li>Demand variation is simulated, not learned from historical sales.</li>
                            <li>Supplier capacity, shipping routes, and lead times are simplified.</li>
                            <li>Recovery cost is an illustrative estimate, not an accounting forecast.</li>
                            <li>The simulator does not connect to live logistics, ERP, or inventory systems.</li>
                            <li>Use real operational data and expert review before making business decisions.</li>
                        </ul>
                    </div>
                </section>
                <footer>SupplyChain Lab · Local scenario simulator · Educational planning prototype, not a live operational forecast.</footer>
            </main>
        </div>
        <div id="toast" class="toast"></div>
        <script>
            const $ = id => document.getElementById(id);
            let currentReport = null;
            const pageInfo = {
                overview: ["Supply Chain Overview", "Understand how unexpected events can affect your supply chain."],
                configure: ["Configure Scenario", "Choose disruption events, severity, and simulation duration."],
                results: ["Simulation Results", "Review operational impact, product exposure, and recovery priorities."],
                history: ["Simulation History", "Reopen previously saved supply chain scenarios."],
                methodology: ["Methodology", "Understand the model assumptions and simulation calculations."]
            };
            document.querySelectorAll(".nav").forEach(b => b.addEventListener("click", () => showPage(b.dataset.page)));

            function showPage(name) {
                document.querySelectorAll(".page").forEach(p => p.classList.toggle("active", p.id === name));
                document.querySelectorAll(".nav").forEach(b => b.classList.toggle("active", b.dataset.page === name));
                $("pageTitle").textContent = pageInfo[name]?.[0] || "Simulation Results";
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

            function money(value) {
                return new Intl.NumberFormat("en-US", {
                    style: "currency",
                    currency: "USD",
                    maximumFractionDigits: 0
                }).format(value || 0);
            }

            function number(value) {
                return Number(value || 0).toLocaleString(undefined, {
                    maximumFractionDigits: 1
                });
            }
            $("severity").addEventListener("input", () => {
                $("severityValue").textContent = $("severity").value + "%"
            });
            $("demandChange").addEventListener("input", () => {
                $("demandValue").textContent = $("demandChange").value + "%"
            });

            function selectAll(value) {
                document.querySelectorAll('#disruptionChecks input').forEach(el => el.checked = value);
            }

            function renderDefaultProducts() {
                const products = [
                    ["Electronic Components", "Alpha Electronics", "900 units", "90/day", "5 days"],
                    ["Industrial Motors", "Global Motor Works", "650 units", "55/day", "7 days"],
                    ["Packaging Materials", "PackRight Industries", "1,400 units", "120/day", "3 days"],
                    ["Battery Cells", "VoltSource Ltd", "500 units", "65/day", "9 days"],
                    ["Steel Frames", "Metro Steel", "1,100 units", "70/day", "6 days"]
                ];
                $("defaultProducts").innerHTML = products.map(p => `
 
																<div class="product-card">
																	<div class="product-top">
																		<div>
																			<div class="product-name">${p[0]}</div>
																			<div class="product-meta">${p[1]}</div>
																		</div>
																		<span class="pill">DEFAULT</span>
																	</div>
																	<div class="product-stats">
																		<div class="product-stat">
																			<small>Inventory</small>
																			<strong>${p[2]}</strong>
																		</div>
																		<div class="product-stat">
																			<small>Daily demand</small>
																			<strong>${p[3]}</strong>
																		</div>
																		<div class="product-stat">
																			<small>Lead time</small>
																			<strong>${p[4]}</strong>
																		</div>
																	</div>
																</div>`).join("");
            }

            function renderChart(id, daily) {
                const el = $(id);
                if (!daily?.length) {
                    el.innerHTML = ' < div class = "empty" > No daily data available. < /div>';return;}
                    const step = Math.max(1, Math.ceil(daily.length / 15));
                    const selected = daily.filter((d, i) => i % step === 0 || i === daily.length - 1);
                    const max = Math.max(1, ...selected.map(d => d.demand));
                    el.innerHTML = selected.map(d => {
                        const width = Math.max(0, Math.min(100, d.served / max * 100));
                        return `
																<div class="chart-row">
																	<div class="chart-label">Day ${d.day}</div>
																	<div class="track">
																		<div class="fill" style="width:${width}%"></div>
																	</div>
																	<div class="chart-value">${Math.round(d.served)} / ${Math.round(d.demand)}</div>
																</div>`;
                    }).join("");
                }

                function metricCards(prefix, report) {
                    const s = report.summary;
                    $(prefix + "Service").textContent = s.serviceLevel.toFixed(1) + "%";
                    $(prefix + "Impact").textContent = money(s.financialImpact);
                    $(prefix + "Stockouts").textContent = s.stockoutProducts;
                    $(prefix + "Risk").textContent = s.riskLevel;
                    $(prefix + "Risk").className = "metric-value " + (s.riskLevel === "Low" ? "green" : s.riskLevel === "Moderate" ? "" : "red");
                }

                function renderSummary(report) {
                    const s = report.summary;
                    $("overviewSummary").innerHTML = `
 
																<div class="kv">
																	<strong>Scenario</strong>
																	<span>${escapeHtml(report.name)}</span>
																</div>
																<div class="kv">
																	<strong>Duration</strong>
																	<span>${report.duration} days</span>
																</div>
																<div class="kv">
																	<strong>Disruptions</strong>
																	<span>${report.disruptions.map(x=>escapeHtml(x.label)).join(", ")}</span>
																</div>
																<div class="kv">
																	<strong>Demand change</strong>
																	<span>${report.demandChange>0?"+":""}${report.demandChange}%</span>
																</div>
																<div class="kv">
																	<strong>Units lost</strong>
																	<span>${number(s.unitsLost)}</span>
																</div>
																<div class="kv">
																	<strong>Final inventory</strong>
																	<span>${number(s.finalInventory)}</span>
																</div>`;
                }

                function productCards(products) {
                    return products.map(p => {
                        const stockout = p.stockoutDay !== null;
                        return `
																<div class="product-card">
																	<div class="product-top">
																		<div>
																			<div class="product-name">${escapeHtml(p.name)}</div>
																			<div class="product-meta">${escapeHtml(p.supplier)} · ${escapeHtml(p.supplierRegion)}</div>
																		</div>
																		<span class="pill ${stockout?"high":"low"}">${stockout?"Stockout":"No stockout"}</span>
																	</div>
																	<div class="product-stats">
																		<div class="product-stat">
																			<small>Ending inventory</small>
																			<strong>${number(p.inventory)}</strong>
																		</div>
																		<div class="product-stat">
																			<small>Supply reduction</small>
																			<strong>${p.supplyReductionPercent}%</strong>
																		</div>
																		<div class="product-stat">
																			<small>Units lost</small>
																			<strong>${number(p.unitsLost)}</strong>
																		</div>
																		<div class="product-stat">
																			<small>Revenue lost</small>
																			<strong>${money(p.revenueLost)}</strong>
																		</div>
																		<div class="product-stat">
																			<small>Recovery cost</small>
																			<strong>${money(p.recoveryCost)}</strong>
																		</div>
																		<div class="product-stat">
																			<small>Effective lead time</small>
																			<strong>${p.effectiveLeadTime} days</strong>
																		</div>
																	</div>
   ${stockout?`
																	<p class="muted small">First stockout: day ${p.stockoutDay} · Stockout days: ${p.stockoutDays}</p>`:""}
  
																</div>`;
                    }).join("");
                }

                function renderSuppliers(report) {
                    $("supplierResults").innerHTML = `
																<table>
																	<thead>
																		<tr>
																			<th>Supplier</th>
																			<th>Region</th>
																			<th>Products</th>
																			<th>Supply reduction</th>
																			<th>Risk</th>
																		</tr>
																	</thead>
																	<tbody>
 ${report.suppliers.map(s=>`
																		<tr>
																			<td>${escapeHtml(s.name)}</td>
																			<td>${escapeHtml(s.region)}</td>
																			<td>${s.products}</td>
																			<td>${s.averageSupplyReduction}%</td>
																			<td>
																				<span class="pill ${s.risk.toLowerCase()}">${s.risk}</span>
																			</td>
																		</tr>`).join("")}
 
																	</tbody>
																</table>`;
                }

                function renderDaily(report) {
                    $("dailyTable").innerHTML = `
																<table>
																	<thead>
																		<tr>
																			<th>Day</th>
																			<th>Demand</th>
																			<th>Served</th>
																			<th>Lost units</th>
																			<th>Revenue lost</th>
																			<th>Recovery cost</th>
																			<th>Products at risk</th>
																		</tr>
																	</thead>
																	<tbody>
 ${report.daily.map(d=>`
																		<tr>
																			<td>${d.day}</td>
																			<td>${number(d.demand)}</td>
																			<td>${number(d.served)}</td>
																			<td>${number(d.lost)}</td>
																			<td>${money(d.revenueLost)}</td>
																			<td>${money(d.recoveryCost)}</td>
																			<td>${d.atRiskProducts}</td>
																		</tr>`).join("")}
 
																	</tbody>
																</table>`;
                }

                function renderReport(report) {
                    currentReport = report;
                    metricCards("r", report);
                    metricCards("m", report);
                    $("resultTitle").textContent = report.name;
                    $("resultMeta").textContent = `${report.duration} days · ${report.disruptions.length} disruption types · ${new Date(report.createdAt).toLocaleString()}`;
                    renderChart("resultChart", report.daily);
                    renderChart("overviewChart", report.daily);
                    renderSummary(report);
                    $("overviewProducts").innerHTML = productCards(report.products);
                    $("productResults").innerHTML = productCards(report.products);
                    renderSuppliers(report);
                    renderDaily(report);
                    $("financialBreakdown").innerHTML = `
 
																<div class="kv">
																	<strong>Revenue loss</strong>
																	<span>${money(report.summary.revenueLost)}</span>
																</div>
																<div class="kv">
																	<strong>Recovery cost</strong>
																	<span>${money(report.summary.recoveryCost)}</span>
																</div>
																<div class="kv">
																	<strong>Total impact</strong>
																	<span style="color:var(--orange2);font-weight:800">${money(report.summary.financialImpact)}</span>
																</div>
																<div class="kv">
																	<strong>Units demanded</strong>
																	<span>${number(report.summary.totalDemand)}</span>
																</div>
																<div class="kv">
																	<strong>Units served</strong>
																	<span>${number(report.summary.unitsServed)}</span>
																</div>
																<div class="kv">
																	<strong>Units lost</strong>
																	<span>${number(report.summary.unitsLost)}</span>
																</div>`;
                    $("recommendations").innerHTML = report.recommendations.map((r, i) => `
																<div class="alert">${i+1}. ${escapeHtml(r)}</div>`).join("");
                    showPage("results");
                    refreshHistory();
                }
                async function runSimulation() {
                    const btn = $("runBtn");
                    const disruptions = [...document.querySelectorAll('#disruptionChecks input:checked')].map(x => x.value);
                    const payload = {
                        name: $("scenarioName").value,
                        duration: Number($("duration").value),
                        severity: Number($("severity").value),
                        demandChange: Number($("demandChange").value),
                        seed: Number($("seed").value),
                        disruptions
                    };
                    btn.disabled = true;
                    btn.textContent = "Simulating…";
                    try {
                        const response = await fetch("/api/simulate", {
                            method: "POST",
                            headers: {
                                "Content-Type": "application/json"
                            },
                            body: JSON.stringify(payload)
                        });
                        const data = await response.json();
                        if (!response.ok) throw new Error(data.error || "Simulation failed.");
                        renderReport(data);
                        toast("Simulation completed and saved locally.");
                    } catch (err) {
                        toast(err.message || "Simulation failed.");
                    } finally {
                        btn.disabled = false;
                        btn.textContent = "Run simulation ↗";
                    }
                }
                async function refreshHistory() {
                    try {
                        const response = await fetch("/api/history");
                        const data = await response.json();
                        if (!response.ok) throw new Error(data.error || "Could not load history.");
                        const rows = data.items.map(item => `
																<tr>
																	<td>${escapeHtml(item.name)}</td>
																	<td>${new Date(item.createdAt).toLocaleString()}</td>
																	<td>${item.duration} days</td>
																	<td>${Number(item.summary?.serviceLevel??0).toFixed(1)}%</td>
																	<td>${money(item.summary?.financialImpact)}</td>
																	<td>
																		<button class="btn" onclick="openReport('${encodeURIComponent(item.id)}')">Open</button>
																	</td>
																</tr>`).join("");
                        const html = rows ? `
																<table>
																	<thead>
																		<tr>
																			<th>Scenario</th>
																			<th>Date</th>
																			<th>Duration</th>
																			<th>Service level</th>
																			<th>Financial impact</th>
																			<th></th>
																		</tr>
																	</thead>
																	<tbody>${rows}</tbody>
																</table>` : ' < div class = "empty" > No saved simulations yet. < /div>';
                        $("historyTable").innerHTML = html;
                        $("recentHistory").innerHTML = html;
                    } catch (err) {
                        $("historyTable").innerHTML = `
																<div class="alert">${escapeHtml(err.message)}</div>`;
                    }
                }
                async function openReport(id) {
                    try {
                        const response = await fetch("/api/report?id=" + id);
                        const report = await response.json();
                        if (!response.ok) throw new Error(report.error || "Could not open report.");
                        renderReport(report);
                    } catch (err) {
                        toast(err.message);
                    }
                }

                function downloadReport(format) {
                    if (!currentReport) {
                        toast("Run or open a simulation first.");
                        return;
                    }
                    let content, type;
                    if (format === "json") {
                        content = JSON.stringify(currentReport, null, 2);
                        type = "application/json";
                    } else {
                        const columns = ["id", "name", "supplier", "supplierRegion", "inventoryStart", "inventory", "dailyDemand", "baseLeadTime", "effectiveLeadTime", "supplyReductionPercent", "unitsDemanded", "unitsServed", "unitsLost", "revenueLost", "recoveryCost"];
                        const lines = [columns.join(",")];
                        currentReport.products.forEach(p => {
                            lines.push(columns.map(k => {
                                const v = p[k] ?? "";
                                return typeof v === "string" ? '"' + v.replace(/"/g, '""') + '"' : v;
                            }).join(","));
                        });
                        content = lines.join("\r\n");
                        type = "text/csv;charset=utf-8";
                    }
                    const blob = new Blob([content], {
                        type
                    });
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement("a");
                    a.href = url;
                    a.download = `supply-chain-report-${currentReport.id}.${format}`;
                    document.body.appendChild(a);
                    a.click();
                    a.remove();
                    URL.revokeObjectURL(url);
                }
                renderDefaultProducts();
                refreshHistory();
        </script>
    </body>
</html>

"""


# ============================================================
# HTTP SERVER
# ============================================================

class SupplyChainHandler(BaseHTTPRequestHandler):
    server_version = "SupplyChainSimulator/1.0"

    def log_message(self, fmt, *args):
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
            raise ValueError("Request is too large.")

        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
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
            simulation_id = parse_qs(parsed.query).get("id", [""])[0]
            report = get_simulation(simulation_id)

            if report is None:
                self.send_json({"error": "Simulation not found."}, 404)
            else:
                self.send_json(report)
            return

        self.send_json({"error": "Endpoint not found."}, 404)

    def do_POST(self):
        if urlparse(self.path).path != "/api/simulate":
            self.send_json({"error": "Endpoint not found."}, 404)
            return

        try:
            payload = self.read_json()

            if not isinstance(payload, dict):
                raise ValueError("Expected a JSON object.")

            report = simulate(payload)
            save_simulation(report)
            self.send_json(report, 201)

        except (ValueError, TypeError) as exc:
            self.send_json({"error": str(exc)}, 400)
        except sqlite3.Error:
            self.send_json(
                {"error": "Database error. Restart the application and try again."},
                500
            )
        except Exception as exc:
            print(f"Unexpected simulation error: {type(exc).__name__}: {exc}")
            self.send_json(
                {"error": "Unexpected error. Check the terminal for details."},
                500
            )


# ============================================================
# APPLICATION ENTRY POINT
# ============================================================

def main():
    init_db()

    server = ThreadingHTTPServer((HOST, PORT), SupplyChainHandler)
    server.daemon_threads = True

    print("=" * 60)
    print("  SUPPLY CHAIN DISRUPTION SIMULATOR")
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
