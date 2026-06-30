# CampaignFlow

A marketing-campaign **ELT pipeline and analytics warehouse**. CampaignFlow ingests raw campaign-event data, lands it untouched, cleans and conforms it, and models it into a **star schema** you can query for spend, reach, and conversion by channel, campaign, and date.

Python + DuckDB, one command, no infrastructure to stand up.

> **Synthetic data only.** This is a portfolio project. It ships a deterministic data generator and never touches real data.

## Architecture

ELT, not ETL: raw rows are loaded first (bronze), then transformed in the warehouse with SQL (silver, then gold).

```
raw CSV (synthetic)
   |  extract + load (verbatim, all text)
   v
[ bronze ]  bronze.campaign_events_raw
   |  type-cast, trim, FX-normalise to DKK, de-duplicate
   v
[ silver ]  silver.campaign_events
   |  build conformed dimensions + fact
   v
[ gold ]   star schema
             fact_campaign_performance
             dim_date . dim_channel . dim_campaign
   |
   v  example query: spend / CTR / cost-per-conversion by channel
```

Data-quality checks gate the gold layer; the run fails if any check fails.

## Quickstart

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"

python -m campaignflow run        # build the warehouse (campaignflow.duckdb)
python -m campaignflow report     # spend / CTR / cost-per-conversion by channel
```

Run the tests and linter:

```bash
ruff check .
pytest -q
```

## Data model (star schema)

Grain of the fact: one row per (event_date, channel, campaign).

| Table | Keys | Columns |
|---|---|---|
| `fact_campaign_performance` | date_key + channel_key + campaign_key | impressions, clicks, spend_dkk, conversions |
| `dim_date` | date_key (YYYYMMDD) | full_date, year, quarter, month, month_name, day, iso_week, day_of_week, is_weekend |
| `dim_channel` | channel_key | channel_name, channel_group (Paid / Owned / Earned) |
| `dim_campaign` | campaign_key | campaign_id, campaign_name |

## Data quality

Checks run after the gold build and fail the pipeline on any violation: silver and fact non-empty, dimension surrogate keys unique, fact grain unique, fact measures non-negative, and every fact foreign key resolves to its dimension (referential integrity).

## Design decisions

- **ELT, not ETL.** Raw data is loaded verbatim into bronze first, so the original is always recoverable; all shaping happens in the warehouse with SQL.
- **Idempotent and deterministic.** A fixed seed drives the generator, and derived tables are rebuilt from raw on every run, so the same inputs always produce the same warehouse.
- **DuckDB.** An embedded analytical database: the whole star schema builds in-process with standard SQL, no server or containers to run.
- **Fixed FX rates.** Spend is normalised to DKK with a small reference-rate map. A real system would source live rates; the map is a documented simplification.
- **Dependency-light.** One runtime dependency (DuckDB). Tests use an in-memory database, so the suite is fast and hermetic.

## PySpark parity

The silver-to-gold fact build is also expressed as a PySpark job in
`campaignflow/spark_fact.py` — the same DataFrame engine Databricks runs. It
consumes the silver events and the conformed dimensions and recomputes the fact
grain, so the two engines are compared on the aggregation, not on key assignment.
A parity test (`tests/test_spark_fact.py`) asserts the PySpark fact is cent-exact
identical to the DuckDB fact. This needs a JRE (`sudo apt-get install -y
default-jre`, or any Java 17/21); `pyspark` is a dev dependency, so it is exercised
by the test suite but not required to `run` the DuckDB pipeline.

## Roadmap

The core above is complete and stands alone. Shipped extensions:

1. ~~**PySpark transform stage**~~ — done (see *PySpark parity* above).

Planned extensions:

2. **Terraform (Azurite / LocalStack):** provision a local blob landing zone for bronze as infrastructure-as-code.
3. **Next.js / TypeScript dashboard:** charts over the gold marts (spend / CTR / cost-per-conversion by channel over time).
4. **docker-compose:** run the whole stack with one command.

## Development

Built test-first (pytest), linted with ruff, CI on GitHub Actions. See `docs/superpowers/plans/` for the implementation plan.
