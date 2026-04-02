from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, render_template

from clean_and_merge import DATABASE_FILE, main as build_database

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path(DATABASE_FILE)
POLL_INTERVAL_MS = 5000

app = Flask(__name__)


def ensure_database() -> None:
    if not DB_PATH.exists():
        build_database()
        return

    required_tables = {"merged_orders", "region_summary"}
    with sqlite3.connect(DB_PATH) as connection:
        rows = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name IN (?, ?)",
            tuple(required_tables),
        ).fetchall()

    existing_tables = {row[0] for row in rows}
    if required_tables - existing_tables:
        build_database()


def get_connection() -> sqlite3.Connection:
    ensure_database()
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def fetch_dashboard_data() -> dict[str, object]:
    with get_connection() as connection:
        merged_orders = [dict(row) for row in connection.execute(
            """
            SELECT order_id, customer_id, customer_name, region, amount, currency, amount_cny
            FROM merged_orders
            ORDER BY order_id
            """
        ).fetchall()]

        summary_rows = [dict(row) for row in connection.execute(
            """
            SELECT region, avg_amount_cny
            FROM region_summary
            ORDER BY region
            """
        ).fetchall()]

    last_updated = datetime.fromtimestamp(DB_PATH.stat().st_mtime).isoformat() if DB_PATH.exists() else None

    return {
        "merged_orders": merged_orders,
        "summary": summary_rows,
        "last_updated": last_updated,
        "poll_interval_ms": POLL_INTERVAL_MS,
        "order_count": len(merged_orders),
        "summary_count": len(summary_rows),
    }


@app.after_request
def add_no_cache_headers(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


@app.route("/")
def index():
    return render_template("index.html", poll_interval_ms=POLL_INTERVAL_MS)


@app.route("/api/dashboard-data")
def dashboard_data():
    return jsonify(fetch_dashboard_data())


if __name__ == "__main__":
    ensure_database()
    app.run(host="0.0.0.0", port=5001, debug=True)
