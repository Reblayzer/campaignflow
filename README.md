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

## Blob landing zone (Terraform + Azurite)

Bronze can ingest raw campaign files from an Azure Blob **landing zone** instead
of local disk. The landing zone is infrastructure-as-code under `infra/terraform/`:

- `infra/terraform/azure/` — the **production** landing zone (`azurerm`): resource
  group, storage account, and a private blob container.
- `infra/terraform/local/` — the same container on the **Azurite** emulator.
  `azurerm` targets the Azure control plane, which Azurite does not emulate, so the
  container is created through the blob data plane; `terraform apply` here stands up
  a runnable landing zone with no cloud account.

End-to-end locally:

```bash
docker run -d -p 10000:10000 mcr.microsoft.com/azure-storage/azurite \
  azurite-blob --blobHost 0.0.0.0 --skipApiVersionCheck
terraform -chdir=infra/terraform/local init && terraform -chdir=infra/terraform/local apply

pip install -e ".[dev]"          # brings in azure-storage-blob
python -m campaignflow run --landing-zone   # upload raw to blob, read bronze from az://
```

The pipeline uploads the generated CSV to the container and bronze reads it back
via DuckDB's `azure` extension (`read_csv('az://…')`), producing an identical
warehouse to the on-disk path. The blob tests skip when Azurite is unreachable, so
the suite stays green without Docker; CI starts Azurite and runs them for real. The
Azurite connection string is the well-known public emulator account; override it
for real Azure with `AZURE_STORAGE_CONNECTION_STRING`.

## Dashboard

A static Next.js + TypeScript dashboard over the gold marts lives in `dashboard/`.
The Python side exports the marts to JSON; the app renders them with Recharts —
no database or server at runtime.

```bash
python -m campaignflow run                 # build the warehouse
python -m campaignflow export              # -> dashboard/public/data/marts.json
cd dashboard && npm ci && npm run dev      # http://localhost:3000
```

Tests: `cd dashboard && npm test` (Vitest + Testing Library) run against a committed
fixture, so the Node suite needs no Python. CI builds and tests the app in its own job.

## One command with docker compose

The whole stack runs with a single command — no local Python or Node needed:

```bash
docker compose up --build      # builds the warehouse, exports marts, serves the app
# open http://localhost:3000
docker compose down -v         # stop and clean up
```

The `pipeline` service builds the DuckDB warehouse and exports the gold marts into
a shared volume, then exits; the `dashboard` service waits for it to finish, then
builds and serves the Next.js app over the fresh marts. Azurite (the blob landing
zone) is not part of this default stack — see *Blob landing zone* above to exercise
that path.

## Roadmap

The core above is complete and stands alone. Shipped extensions:

1. ~~**PySpark transform stage**~~ — done (see *PySpark parity* above).
2. ~~**Terraform blob landing zone (Azurite)**~~ — done (see *Blob landing zone* above).
3. ~~**Next.js / TypeScript dashboard**~~ — done (see *Dashboard* above).
4. ~~**docker-compose**~~ — done (see *One command with docker compose* above).

## Development

Built test-first (pytest), linted with ruff, CI on GitHub Actions. See `docs/superpowers/plans/` for the implementation plan.
