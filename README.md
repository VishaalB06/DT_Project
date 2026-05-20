# Team 8 — Delhi Air Quality Data Pipeline

A data engineering project that ingests, partitions, and analyzes **22.5 million rows** of Delhi air quality and weather data spanning Jan 2024 – Dec 2025.

We built a two-layer pipeline using **PySpark** for big-data processing and **SQLite** as a relational data warehouse, with analytics done in **SQL**.

---

## Architecture

```
                     team_8.parquet  (22.5M rows, 240 MB)
                            |
                            v
                       PySpark
                       /        \
                      /          \
                     v            v
        Hive-partitioned    Hourly aggregation
        data lake           (5.8M rows)
        (year=YYYY/                |
         month=MM/)                v
                          SQLite warehouse
                          (3NF schema)
                                   |
                                   v
                          SQL analytics queries
```

**Two-layer design:**
- **Data lake** (raw parquet, partitioned by year/month) — keeps full-resolution data ready for big-data tools
- **Data warehouse** (SQLite, normalized to 3NF) — aggregated to hourly granularity for fast SQL analytics

---

## The data

Each row of the raw parquet is **one pollutant reading from one monitoring station at one moment in time**.

| Detail | Value |
|---|---|
| Source | Delhi air quality monitoring network |
| Time span | January 2024 – December 2025 |
| Rows | 22,476,854 |
| Columns | 22 |
| Stations | 37 |
| Pollutants tracked | 13 (PM2.5, PM10, NO2, SO2, O3, CO, NH3, benzene, toluene, xylene, ethylbenzene, NO, m,p-xylene) |
| Weather variables | Temperature, humidity, wind speed/direction, rainfall, solar radiation, pressure |
| Sampling rate | Every 15 minutes |

---

## Database schema

A normalized **third normal form (3NF)** schema with three tables connected by foreign keys.

### `stations`
| Column | Type | Constraints |
|---|---|---|
| station_id | TEXT | PRIMARY KEY |
| station_name | TEXT | NOT NULL |

### `pollutants`
| Column | Type | Constraints |
|---|---|---|
| pollutant_id | INTEGER | PRIMARY KEY, AUTOINCREMENT |
| pollutant_name | TEXT | UNIQUE, NOT NULL |

### `measurements` (fact table)
| Column | Type | Constraints |
|---|---|---|
| id | INTEGER | PRIMARY KEY, AUTOINCREMENT |
| station_id | TEXT | FOREIGN KEY → stations |
| pollutant_id | INTEGER | FOREIGN KEY → pollutants |
| year, month, day, hour | INTEGER | NOT NULL |
| avg_value, min_value, max_value | REAL | hourly pollutant statistics |
| avg_temp_c, avg_humidity, avg_wind_speed, avg_rainfall | REAL | weather context |

Indexes on `station_id`, `pollutant_id`, and `(year, month)` for fast analytical queries.

---

## SQL analytics — questions answered

1. **Monthly PM2.5 trend** — how pollution varies across all 24 months
2. **Top 5 most polluted stations** — by average PM2.5
3. **Worst hour of day** — when is air quality worst
4. **Seasonal comparison** — winter vs summer vs monsoon vs post-monsoon, across 5 pollutants
5. **Humidity correlation** — how PM2.5 levels relate to humidity buckets
6. **Hazardous-air days** — count of station-days exceeding WHO's hazardous threshold (PM2.5 > 250 µg/m³)

### Key findings
- **Winter (Nov–Jan)** is by far the worst pollution season in Delhi
- Pollution **peaks at night and early morning**, dips in the afternoon
- Some stations consistently show worse PM2.5 than others — concentrated in specific neighborhoods
- Higher humidity correlates with higher PM2.5, especially in winter
- Hazardous-air days are heavily clustered in November–January

---

## How to run

### On Kaggle (recommended)
1. **Add the parquet as a Kaggle Dataset:** Right sidebar → Input → + Add Input → Upload `team_8.parquet` → name it `team8-parquet`
2. **Turn on Internet:** Right sidebar → Settings → Internet → On
3. **Open the notebook** and click Run All

The notebook takes about 15–20 minutes end to end and writes the final database to `/kaggle/working/delhi_air_quality.db`.

### On Google Colab
Adjust the parquet path to where you uploaded the file, then run all cells. Colab's lower RAM (~12 GB) may require the High-RAM runtime.

---

## Files in this repo

```
.
├── README.md                          ← this file
├── notebooks/
│   └── team8_pipeline.ipynb           ← full pipeline (Kaggle-ready)
├── sql/
│   ├── schema.sql                     ← CREATE TABLE statements
│   └── queries.sql                    ← all 6 analytics queries
├── docs/
│   └── schema_diagram.png             ← ER diagram of the warehouse
└── .gitignore
```

The raw `team_8.parquet` file and the populated `delhi_air_quality.db` are excluded via `.gitignore` because of GitHub's file size limits. Re-run the notebook to regenerate them.

---

## Tech stack

| Tool | Used for | Why |
|---|---|---|
| **PySpark** | Reading parquet, partitioning, aggregating | Distributes work in parallel — handles 22M rows without crashing |
| **Parquet** | Raw data file format | Columnar, compressed, fast to read |
| **SQLite** | Data warehouse | File-based RDBMS, zero-configuration, portable |
| **SQL** | Analytics queries | Declarative language designed for asking questions of data |
| **pandas** | Bridge between Spark and SQLite | Loading aggregated data into the database |
| **matplotlib** | Charts for the analytics results | Standard Python plotting library |

---

## Team

| Member | Responsibility |
|---|---|
| **Nelson** | Ingestion & partitioning (PySpark setup, raw data load, Hive-style partitioning) |
| **Rutvi** | Aggregation & schema design (hourly rollup, 3NF schema, SQLite loading) |
| **Vishaal** | SQL analytics & documentation (6 analytical queries, visualizations, README) |

---

## Concepts demonstrated

- **Data lake vs data warehouse** — two-layer architecture pattern
- **Hive-style partitioning** — industry-standard `key=value` folder convention
- **ETL** — Extract from parquet, Transform via Spark aggregation, Load into SQLite
- **Normalization (3NF)** — eliminating data duplication via foreign keys
- **Indexes** — speeding up filter and join operations
- **OLAP workloads** — bulk-load-then-query, optimized for analytics not transactions
