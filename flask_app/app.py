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

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "delhi_air_quality.db")
KV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kv_store.json")


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


# ── NOVELTY FEATURE 1: DATA QUALITY / CONFIDENCE SCORING ─────────────────────

@app.route("/api/confidence/<station_id>")
def api_confidence(station_id):
    """Confidence score for a station — how much to trust its averages."""
    if not os.path.exists(KV_PATH):
        return jsonify({"error": "key-value store not found"}), 404
    with open(KV_PATH) as f:
        kv = json.load(f)
    if station_id not in kv:
        return jsonify({"error": "station not found"}), 404
    station = kv[station_id]
    return jsonify({
        "station_id": station_id,
        "station_name": station.get("station_name"),
        "avg_pm25": station.get("avg_pm25"),
        "confidence_score": station.get("confidence_score", "not computed"),
        "confidence_label": station.get("confidence_label", "unknown"),
    })


@app.route("/api/confidence-all")
def api_confidence_all():
    """Confidence scores for every station — for the dashboard table."""
    if not os.path.exists(KV_PATH):
        return jsonify({"error": "key-value store not found"}), 404
    with open(KV_PATH) as f:
        kv = json.load(f)
    results = []
    for sid, data in kv.items():
        if sid.startswith("__"):
            continue
        if "confidence_score" in data:
            results.append({
                "station_id": sid,
                "station_name": data.get("station_name"),
                "avg_pm25": data.get("avg_pm25"),
                "confidence_score": data.get("confidence_score"),
                "confidence_label": data.get("confidence_label"),
            })
    results.sort(key=lambda x: x["confidence_score"])
    return jsonify(results)


# ── NOVELTY FEATURE 2: WIND-SPEED "WHAT-IF" REGRESSION (all pollutants) ──────

@app.route("/api/wind-model/<pollutant>")
def api_wind_model(pollutant):
    """The fitted wind-speed regression model parameters for a given pollutant."""
    if not os.path.exists(KV_PATH):
        return jsonify({"error": "key-value store not found"}), 404
    with open(KV_PATH) as f:
        kv = json.load(f)
    models = kv.get("__wind_models__", {})
    if pollutant not in models:
        return jsonify({"error": f"no wind model for '{pollutant}'"}), 404
    return jsonify(models[pollutant])


@app.route("/api/wind-models")
def api_wind_models_all():
    """All available wind models, keyed by pollutant — used to populate the dropdown."""
    if not os.path.exists(KV_PATH):
        return jsonify({"error": "key-value store not found"}), 404
    with open(KV_PATH) as f:
        kv = json.load(f)
    return jsonify(kv.get("__wind_models__", {}))


@app.route("/api/wind-predict/<pollutant>/<wind_speed>")
def api_wind_predict(pollutant, wind_speed):
    """Live prediction: given a pollutant and wind speed, what value does the model predict?"""
    try:
        wind_speed = float(wind_speed)
    except ValueError:
        return jsonify({"error": "wind_speed must be a number"}), 400

    if not os.path.exists(KV_PATH):
        return jsonify({"error": "key-value store not found"}), 404
    with open(KV_PATH) as f:
        kv = json.load(f)
    models = kv.get("__wind_models__", {})
    model = models.get(pollutant)
    if not model:
        return jsonify({"error": f"no wind model for '{pollutant}'"}), 404

    predicted = model["slope"] * wind_speed + model["intercept"]
    predicted = max(0, round(predicted, 2))

    # WHO-style classification only really applies to PM2.5/PM10; for other
    # pollutants we just report the predicted value without a health label
    classification = None
    if pollutant == "pm25":
        if predicted > 250:   classification = "HAZARDOUS"
        elif predicted > 150: classification = "VERY UNHEALTHY"
        elif predicted > 55:  classification = "UNHEALTHY"
        elif predicted > 35:  classification = "MODERATE"
        else:                 classification = "GOOD"

    return jsonify({
        "pollutant": pollutant,
        "wind_speed": wind_speed,
        "predicted_value": predicted,
        "who_classification": classification,
        "model_r_squared": model.get("r_squared"),
        "direction": model.get("direction"),
    })


if __name__ == "__main__":
    app.run(debug=True, port=5000)
