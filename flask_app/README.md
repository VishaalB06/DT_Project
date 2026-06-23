# Delhi Air Quality Dashboard — Flask App

Serves the SQLite warehouse as a live web dashboard with charts, plus a JSON API.

## Setup

1. Copy your `delhi_air_quality.db` and `kv_store.json` files into this folder
   (same folder as `app.py`).

2. Install Flask:
   ```
   pip install -r requirements.txt
   ```

3. Run the app:
   ```
   python app.py
   ```

4. Open your browser to:
   ```
   http://localhost:5000
   ```

## What you'll see

- Summary cards: total stations, pollutants, measurements
- A pollutant dropdown — switch between PM2.5, PM10, NO2, etc.
- Monthly trend line chart
- Top 5 most polluted stations
- Pollution by hour of day (bar chart)
- Seasonal comparison (Winter / Summer / Monsoon / Post-monsoon)
- Next month's PM2.5 forecast with WHO classification badge

## API endpoints (for the "REST API" part of your demo)

| Endpoint | Returns |
|---|---|
| `/api/summary` | Row counts for stations, pollutants, measurements |
| `/api/trend/<pollutant>` | Monthly average for a pollutant, e.g. `/api/trend/pm25` |
| `/api/top-stations/<pollutant>` | Top 5 worst stations for a pollutant |
| `/api/hourly/<pollutant>` | Average value by hour of day |
| `/api/seasonal/<pollutant>` | Average value by season |
| `/api/station/<station_id>` | Single station lookup (served from key-value store) |
| `/api/forecast` | Next month's PM2.5 forecast (served from key-value store) |
| `/api/stations` | List of all stations |
| `/api/pollutants` | List of all pollutants |

Try visiting `/api/trend/pm25` directly in your browser to see the raw JSON response —
useful for showing the prof that this is a real API, not just a static page.

## For the presentation

This demonstrates the **serving layer** of the pipeline:
- SQL queries run live against SQLite when you load the dashboard
- The key-value store (`kv_store.json`) powers the fast station/forecast lookups
- Chart.js renders the visuals client-side from the JSON the API returns

Talking point: "Our Flask app exposes the warehouse as both a human-readable
dashboard and a machine-readable JSON API — the same data can be consumed by
a browser or by another program."
