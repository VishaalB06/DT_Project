"""
Delhi Air Quality Dashboard — Flask App
Team 8: Nelson, Rutvi, AlaguVishaal Balaji

Serves the SQLite warehouse as a web dashboard + JSON API.
Run with: python app.py
Then visit: http://localhost:5000
"""
from flask import Flask, jsonify, render_template
import sqlite3
import json
import os

app = Flask(__name__)

DB_PATH = os.path.join(os.path.dirname("delhi_air_quality.db"), "delhi_air_quality.db")
KV_PATH = os.path.join(os.path.dirname("kv_store.json"), "kv_store.json")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ── PAGE ROUTES ──────────────────────────────────────────────────────────────

@app.route("/")
def dashboard():
    """Main dashboard page."""
    return render_template("dashboard.html")


# ── API ROUTES (JSON) ────────────────────────────────────────────────────────

@app.route("/api/summary")
def api_summary():
    """Overall dataset summary stats."""
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS n FROM stations")
    stations = cur.fetchone()["n"]
    cur.execute("SELECT COUNT(*) AS n FROM pollutants")
    pollutants = cur.fetchone()["n"]
    cur.execute("SELECT COUNT(*) AS n FROM measurements")
    measurements = cur.fetchone()["n"]
    conn.close()
    return jsonify({
        "stations": stations,
        "pollutants": pollutants,
        "measurements": measurements
    })


@app.route("/api/trend/<pollutant>")
def api_trend(pollutant):
    """Monthly trend for a given pollutant."""
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT m.year, m.month, ROUND(AVG(m.avg_value), 2) AS avg_value
        FROM measurements m
        JOIN pollutants p ON m.pollutant_id = p.pollutant_id
        WHERE p.pollutant_name = ?
        GROUP BY m.year, m.month
        ORDER BY m.year, m.month
    """, (pollutant,))
    rows = cur.fetchall()
    conn.close()
    return jsonify([
        {"year": r["year"], "month": r["month"], "avg_value": r["avg_value"]}
        for r in rows
    ])


@app.route("/api/top-stations/<pollutant>")
def api_top_stations(pollutant):
    """Top 5 worst stations for a given pollutant."""
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT s.station_name, ROUND(AVG(m.avg_value), 2) AS avg_value
        FROM measurements m
        JOIN stations s ON m.station_id = s.station_id
        JOIN pollutants p ON m.pollutant_id = p.pollutant_id
        WHERE p.pollutant_name = ?
        GROUP BY s.station_name
        ORDER BY avg_value DESC
        LIMIT 5
    """, (pollutant,))
    rows = cur.fetchall()
    conn.close()
    return jsonify([
        {"station_name": r["station_name"], "avg_value": r["avg_value"]}
        for r in rows
    ])


@app.route("/api/hourly/<pollutant>")
def api_hourly(pollutant):
    """Average pollutant value by hour of day."""
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT m.hour, ROUND(AVG(m.avg_value), 2) AS avg_value
        FROM measurements m
        JOIN pollutants p ON m.pollutant_id = p.pollutant_id
        WHERE p.pollutant_name = ?
        GROUP BY m.hour
        ORDER BY m.hour
    """, (pollutant,))
    rows = cur.fetchall()
    conn.close()
    return jsonify([
        {"hour": r["hour"], "avg_value": r["avg_value"]}
        for r in rows
    ])


@app.route("/api/seasonal/<pollutant>")
def api_seasonal(pollutant):
    """Seasonal comparison for a given pollutant."""
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT season, ROUND(AVG(avg_value), 2) AS avg_value
        FROM (
            SELECT
                CASE
                    WHEN m.month IN (12,1,2) THEN 'Winter'
                    WHEN m.month IN (3,4,5)  THEN 'Summer'
                    WHEN m.month IN (6,7,8,9) THEN 'Monsoon'
                    ELSE 'Post-monsoon'
                END AS season,
                m.avg_value
            FROM measurements m
            JOIN pollutants p ON m.pollutant_id = p.pollutant_id
            WHERE p.pollutant_name = ?
        )
        GROUP BY season
        ORDER BY avg_value DESC
    """, (pollutant,))
    rows = cur.fetchall()
    conn.close()
    return jsonify([
        {"season": r["season"], "avg_value": r["avg_value"]}
        for r in rows
    ])


@app.route("/api/station/<station_id>")
def api_station(station_id):
    """Single station lookup — served from the key-value store (fast, no SQL)."""
    if not os.path.exists(KV_PATH):
        return jsonify({"error": "key-value store not found"}), 404
    with open(KV_PATH) as f:
        kv = json.load(f)
    if station_id not in kv:
        return jsonify({"error": "station not found"}), 404
    return jsonify(kv[station_id])


@app.route("/api/forecast")
def api_forecast():
    """PM2.5 forecast for next month — served from the key-value store."""
    if not os.path.exists(KV_PATH):
        return jsonify({"error": "key-value store not found"}), 404
    with open(KV_PATH) as f:
        kv = json.load(f)
    return jsonify(kv.get("__forecast__", {"error": "forecast not found"}))


@app.route("/api/stations")
def api_stations():
    """List all stations (for populating dropdown menus)."""
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT station_id, station_name FROM stations ORDER BY station_name")
    rows = cur.fetchall()
    conn.close()
    return jsonify([
        {"station_id": r["station_id"], "station_name": r["station_name"]}
        for r in rows
    ])


@app.route("/api/pollutants")
def api_pollutants():
    """List all pollutants (for populating dropdown menus)."""
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT pollutant_name FROM pollutants ORDER BY pollutant_name")
    rows = cur.fetchall()
    conn.close()
    return jsonify([r["pollutant_name"] for r in rows])


if __name__ == "__main__":
    app.run(debug=True, port=5000)
