# CampaignFlow handoff

## Goal
Marketing-campaign ELT pipeline + star schema, built for the Arla "Entry IT Developer, IT Product for Marketing" application and interview. Must be runnable, public, and fully explainable.

## Status: core + four extensions shipped; docker-compose is the last ladder item, now shipped
- Public repo: https://github.com/Reblayzer/campaignflow (branch `main`, CI on GitHub Actions).
- Core: 15 tests green, ruff clean. Runs via `python -m campaignflow run` then `python -m campaignflow report`.
- **Extension #1 shipped (PR #1, merged):** PySpark silver->gold fact in `spark_fact.py`, parity-tested cent-exact against the DuckDB fact. Needs a JRE (Java 17/21); CI runs Temurin 21.
- **Extension #2 shipped (PR #2, merged):** Terraform Azure blob landing zone under `infra/terraform/` (`azure/` prod via azurerm, `local/` Azurite emulator). `bronze.load_raw` reads `az://` via DuckDB's azure extension; `pipeline.run`/CLI gain `--landing-zone`. 22 tests green; CI starts Azurite + validates Terraform.
- **Extension #3 shipped (PR #3, merged):** Static Next.js/TypeScript dashboard over the gold marts under `dashboard/`. `campaignflow export` writes `marts.json` (blended totals + by-channel + monthly), reconciled against the fact; the app renders KPI cards, a by-channel bar chart, and a monthly line chart with a metric toggle. CI gained a `dashboard` job (Vitest + build). Spec/plan: `docs/superpowers/{specs,plans}/2026-06-30-dashboard*.md`.
- **Extension #4 shipped (PR #4, merged):** `docker compose up` runs the whole stack —
  a `pipeline` service builds the warehouse and exports the marts into a shared volume,
  then a `dashboard` service builds and serves the Next.js app over them. Ordering via
  `depends_on: service_completed_successfully` satisfies the dashboard's build-time marts
  import. CI gained a `compose` smoke-test job (`docker compose up --wait`, then page 200
  + served `/data/marts.json` contains `"seed": 42`); all three jobs (test, dashboard,
  compose) green on `main`. Spec/plan: `docs/superpowers/{specs,plans}/2026-07-01-docker-compose*.md`.
- Docker/Terraform/Node 22 are all available on this machine now (the old "Docker off" note below is obsolete).

## What shipped (the core)
- ELT: `generate` (synthetic) -> `bronze` (raw verbatim) -> `silver` (typed, trimmed, FX-normalised to DKK, deduped) -> `gold` (star schema: `fact_campaign_performance` + `dim_date` / `dim_channel` / `dim_campaign`).
- Data-quality gate (`quality.py`): key uniqueness, fact grain uniqueness, non-negative measures, referential integrity. The run fails on any violation.
- Example analytics (`report.py`): spend / CTR / cost-per-conversion by channel.
- Implementation plan: `docs/superpowers/plans/2026-06-30-campaignflow-core.md`.

## Key decisions
- DuckDB (embedded) instead of Docker/Postgres for the warehouse: one-command run, no server to stand up. (Docker is used separately by extension #4 to package and serve the whole stack.)
- ELT not ETL: load raw first, transform in-warehouse with SQL.
- Deterministic (fixed seed) + idempotent (rebuild derived tables from raw) so tests and demos are stable.
- Fixed FX map to DKK in `config.py` (documented simplification).

## Next steps (extension ladder, each its own branch + PR)
1. ~~PySpark transform stage~~ — shipped (PR #1).
2. ~~Terraform blob landing zone~~ — shipped (PR #2, Azurite).
3. ~~Next.js / TypeScript dashboard~~ — shipped (PR #3, merged to `main`).
4. ~~docker-compose~~ — shipped.

## On resume

The extension ladder is complete. Future work is open-ended — pick from the README roadmap's "later" items or pursue other directions as needed. Read the README roadmap and `git log --oneline` to orient, then branch from `main`.

## On resume for any OTHER work
1. Read this file, then `git log --oneline` and `gh run list` to confirm state.
2. `. .venv/bin/activate` (recreate if gone), confirm green: `ruff check . && pytest -q`.
3. Pick the next extension, branch `feat/<slug>`, TDD, open a PR, keep CI green.

## Interview notes
Be able to explain: the medallion layering (bronze/silver/gold), the star-schema grain (one fact row per date x channel x campaign), why ELT over ETL, the data-quality checks, and how a PySpark/Databricks job would slot into the same silver->gold step. The README roadmap shows what a production version adds.
