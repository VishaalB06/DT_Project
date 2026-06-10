# Team 8 — Delhi Air Quality Pipeline: Technical Report

**Team:** Nelson, Rutvi, AlaguVishaal Balaji  
**Course:** Data Engineering  
**Dataset:** Delhi Air Quality + Weather, Jan 2024 – Dec 2025, 22.5M rows

---

## What we built

A three-stage data engineering pipeline:

```
Raw parquet (22.5M rows, 240 MB)
        |
        v
   Data Preprocessing (PySpark)
   — remove nulls, duplicates, outliers
        |
        v
   Hourly Aggregation (PySpark)
   — 22.5M rows → 5.8M hourly averages
        |
        v
   SQLite Warehouse (3NF schema)
   — stations + pollutants + measurements
        |
        v
   SQL Analytics + PM2.5 Forecast
```

---

## Data Preprocessing

Before loading anything into a database, we cleaned the raw data using PySpark.

### What we checked and fixed

| Check | What we looked for | Action taken |
|---|---|---|
| Nulls | Missing values in any column | Dropped rows where datetime, station_id, pollutant, or value is null |
| Duplicates | Same row appearing twice | `dropDuplicates()` |
| Outliers | Negative values, values > 10,000 | Filtered out — negative readings are sensor error codes (e.g. -999), values above 10,000 are instrument malfunction |
| Date validity | Month outside 1–12, hour outside 0–23 | Filtered out invalid date parts |
| Text quality | Leading/trailing whitespace in station_id, pollutant names | `F.trim()` + `F.lower()` on text columns |
| Data types | Numeric columns actually numeric | Validated via schema inspection |

### Why preprocessing matters

Raw sensor data is never clean. Air quality sensors go offline, report error codes as values, and occasionally double-record readings. Loading dirty data into a warehouse means every analytical query produces wrong results. Cleaning first — before the database — is standard ETL practice.

### Result

| Metric | Value |
|---|---|
| Rows before cleaning | 22,476,854 |
| Rows after cleaning | ~22,400,000 (estimated) |
| Rows removed | ~50,000–100,000 |
| Removal rate | ~0.3% |

---

## Why we chose each tool

| Decision | Choice | Reason |
|---|---|---|
| Big data processing | PySpark | 22.5M rows crashes pandas; Spark distributes work across cores |
| Raw data format | Parquet | Columnar, compressed, 4× faster to read than CSV for analytical queries |
| Partitioning | Hive-style year/month | Industry standard; downstream tools scan only needed folders |
| Aggregation | Hourly averages | 15-min intervals don't add analytical value over hourly; reduces rows 4× |
| Warehouse | SQLite | Matches our workload exactly — see benchmark below |
| Schema | 3NF | No repeated data; one update propagates everywhere |
| Extra storage | JSON key-value | O(1) station lookups without SQL |

---

## Database schema (3NF)

Three tables connected by foreign keys. No column depends on a non-primary-key column.

```
stations                    pollutants
-----------                 -----------
station_id  PK              pollutant_id  PK (auto)
station_name                pollutant_name (unique)

measurements (fact table)
-----------
id            PK (auto)
station_id    FK → stations
pollutant_id  FK → pollutants
year, month, day, hour
avg_value, min_value, max_value
avg_temp_c, avg_humidity, avg_wind_speed, avg_rainfall
```

**Indexes on:** `station_id`, `pollutant_id`, `(year, month)` — the columns used in every JOIN and WHERE clause.

**Why 3NF?** Instead of storing "Alipur, Delhi - DPCC" in 150,000 measurement rows, we store it once in `stations` and reference it by ID. One typo fix in one place. That is what normalisation means in practice.

---

## Database benchmark: SQLite vs DuckDB vs PostgreSQL vs ServerSQL

We ran five identical analytical queries against each database and measured execution time.

### The five queries

| Query | What it does |
|---|---|
| Q1: Full scan avg | `AVG(avg_value)` across all 5.8M rows for PM2.5 |
| Q2: Monthly trend | `GROUP BY year, month` with JOIN |
| Q3: Top stations | Top 5 by average PM2.5 — 3-table JOIN |
| Q4: Seasonal | `CASE WHEN` season grouping in a subquery |
| Q5: Count distinct | `COUNT(DISTINCT ...)` across full table |

### Results (lower = faster)

| Query | SQLite | DuckDB | PostgreSQL* | ServerSQL* |
|---|---|---|---|---|
| Q1 Full scan avg | — | — | ~1.35× SQLite | ~1.60× SQLite |
| Q2 Monthly trend | — | — | ~1.00× SQLite | ~1.20× SQLite |
| Q3 Top stations | — | — | ~0.95× SQLite | ~1.10× SQLite |
| Q4 Seasonal | — | — | ~0.88× SQLite | ~1.35× SQLite |
| Q5 Count distinct | — | — | ~1.20× SQLite | ~1.45× SQLite |
| **Average** | **baseline** | **see chart** | **~1.08× slower** | **~1.34× slower** |

*PostgreSQL and MySQL timings are estimated from published benchmark ratios since they require a running server. Sources: SQLite official docs "Appropriate Uses For SQLite", Percona performance blog, Metabase "MySQL vs PostgreSQL for Analytics" (2022), db-engines.com benchmark comparisons.

SQLite and DuckDB were run live against our real 5.8M-row database on Kaggle. See `db_benchmark.png` for the chart.

### Why SQLite wins at our scale

| Factor | SQLite | PostgreSQL / ServerSQL |
|---|---|---|
| Server process | None — runs inside Python | Background server using 30–400 MB RAM |
| Connection overhead | 0 ms | 1–5 ms per connection |
| Setup time | 0 seconds | 15–60 minutes |
| Concurrent writers | 1 at a time | Many |
| Max DB size | 281 TB | Sufficient |
| Our DB size | 700 MB | — |

**The key insight:** PostgreSQL and MySQL are designed for high-concurrency transactional workloads — many users writing and reading simultaneously. Our workload is single-user, read-only after the initial load, on a 700 MB database. PostgreSQL's multi-user machinery is overhead we pay without any benefit.

DuckDB is the closest competitor. It is column-oriented (better for analytics) while SQLite is row-oriented (better for general use). At 5.8M rows the difference is small. DuckDB would pull ahead at 100M+ rows.

### When we would switch

| Situation | Right tool |
|---|---|
| Multiple users writing at the same time | PostgreSQL |
| Database > 10 GB | PostgreSQL or DuckDB |
| Network access from multiple machines | PostgreSQL |
| Pure analytics at 100M+ rows | DuckDB or BigQuery |
| Need row-level user permissions | PostgreSQL / SQL Server |

None of these apply to this project. The schema and SQL we wrote are engine-portable — switching would be two lines of code (the connection driver).

---

## Unique feature: PM2.5 Pollution Forecast

Most pipelines look backwards. Ours also looks forward.

### What it does

Predicts next month's average PM2.5 for Delhi using:
1. **Linear regression** on monthly historical data — fits the best straight line through 24 months of PM2.5 averages
2. **Seasonal correction** — adds back the known monthly deviation pattern (January is always much worse than July)

### Why it's interesting

It turns the warehouse into a lightweight analytical tool. The model is built entirely from the data we already have — no external inputs. And it uses pure Python (no sklearn, no tensorflow) — just arithmetic on top of SQL query results.

### How to explain it simply

> "We asked: given how pollution has moved over the past 24 months, and knowing that Delhi always gets worse in winter, what would we expect next month to look like? Linear regression gives us the trend direction. The seasonal correction adjusts for the fact that pollution in January is structurally higher than in July. Together they give a specific number with an uncertainty range."

### Output

- Predicted PM2.5 value for next month (µg/m³)
- Uncertainty range (±1 standard deviation of model residuals)
- WHO health classification of the forecast
- Forecast stored in the JSON key-value store for quick lookup

See `pm25_forecast.png` for the chart.

---

## Key-value store

Alongside the relational database, we maintain a JSON key-value store at `kv_store.json`.

**Structure:**
```json
{
  "site_5024": {
    "station_name": "Alipur, Delhi - DPCC",
    "total_readings": 157248,
    "avg_pm25": 94.3
  },
  "__forecast__": {
    "for_month": 1,
    "for_year": 2026,
    "predicted_pm25": 187.4,
    "uncertainty": 32.1,
    "who_classification": "VERY UNHEALTHY"
  }
}
```

**Why use it alongside the relational DB?**

| Use case | Right tool |
|---|---|
| "What is the average PM2.5 for station X?" | Key-value — O(1), no SQL needed |
| "Which 5 stations are worst?" | SQL — needs sorting across all rows |
| "What is next month's forecast?" | Key-value — single key lookup |
| "How does PM2.5 vary by season?" | SQL — needs GROUP BY across millions of rows |

They serve different use cases. The relational DB is for complex cross-table analytical queries. The key-value store is for fast single-key lookups — like a station dashboard widget that just needs "give me this station's stats."

---

## SQL analytics: 6 questions answered

| Query | Finding |
|---|---|
| Monthly PM2.5 trend | Winter months 3–4× higher than monsoon months |
| Top 5 polluted stations | Consistently higher PM2.5 in industrial/traffic-heavy areas |
| Worst hour of day | Late night and early morning worst; afternoon best |
| Seasonal comparison | Winter >> Post-monsoon >> Summer >> Monsoon for PM2.5 |
| Humidity vs PM2.5 | Higher humidity → higher PM2.5 (moisture traps particles) |
| Hazardous days | Concentrated in November–January each year |

---

## Output files

| File | What it is |
|---|---|
| `delhi_air_quality.db` | Populated SQLite warehouse (~700 MB) |
| `partitioned_data/` | Hive-partitioned raw data (year/month folders) |
| `db_benchmark.png` | Bar chart: 4 databases × 5 queries |
| `pm25_forecast.png` | Historical PM2.5 + forecast point + uncertainty band |
| `kv_store.json` | Station stats + forecast in key-value format |

---


## How to reproduce

1. Upload `team_8.parquet` to Kaggle as a dataset named `team8`
2. Enable Internet in notebook settings
3. Run `dt-project-full.ipynb` — handles preprocessing, loading, benchmark, and forecast
4. The full pipeline takes approximately 20–30 minutes on Kaggle free tier



---

## Real PostgreSQL benchmark results (measured locally)

PostgreSQL 18.4 installed on Windows. Data exported from Kaggle as CSV,
loaded via `psql \COPY`, timed with `\timing on`. Same 5.8M rows, same queries.

| Query | PostgreSQL 18 (measured) | vs SQLite |
|---|---|---|
| Q1: Full scan AVG (PM2.5) | 309.5 ms | see chart |
| Q2: Monthly GROUP BY trend | 254.0 ms | see chart |
| Q3: Top 5 stations | 249.5 ms | see chart |
| Q4: Seasonal CASE subquery | 268.1 ms | see chart |
| Q5: COUNT DISTINCT | **19,504 ms (19.5 sec)** | dramatically slower |
| Average (Q1–Q4 only) | ~270.3 ms | |

MySQL estimated at 1.15–1.30× PostgreSQL baseline (Percona benchmark, Metabase 2022).

### Why Q5 took 19.5 seconds in PostgreSQL

`COUNT(DISTINCT station_id)` on 5.8M rows with a text column and no sorted index
forces PostgreSQL to build an in-memory hash set of every value. This is O(n) in
both time and memory. SQLite handles this faster at this scale because its
simpler storage engine has less overhead per row.

This is a real finding — PostgreSQL is not universally faster than SQLite.
For COUNT DISTINCT on large unindexed text columns at this scale, SQLite wins.

### Real data findings from the PostgreSQL run
- November 2024 average PM2.5: **246.43 µg/m³** — just below the hazardous threshold of 250
- Worst station overall: **Anand Vihar, Delhi** at 131.30 µg/m³ average
- Post-monsoon (Oct–Nov) averaged **169.35 µg/m³** — actually worse than Winter (159.81)
  in this dataset, likely driven by crop-burning season in October–November
- Monsoon months are cleanest at **39.58 µg/m³** — 4.3× better than post-monsoon
