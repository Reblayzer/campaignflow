# CampaignFlow handoff

## Goal
Marketing-campaign ELT pipeline + star schema, built for the Arla "Entry IT Developer, IT Product for Marketing" application and interview. Must be runnable, public, and fully explainable.

## Status: core complete and live
- Public repo: https://github.com/Reblayzer/campaignflow (branch `main`, CI on GitHub Actions).
- 15 tests green, ruff clean. Runs via `python -m campaignflow run` then `python -m campaignflow report`.
- Built Docker-free (DuckDB embedded). 10 conventional commits, one per layer.

## What shipped (the core)
- ELT: `generate` (synthetic) -> `bronze` (raw verbatim) -> `silver` (typed, trimmed, FX-normalised to DKK, deduped) -> `gold` (star schema: `fact_campaign_performance` + `dim_date` / `dim_channel` / `dim_campaign`).
- Data-quality gate (`quality.py`): key uniqueness, fact grain uniqueness, non-negative measures, referential integrity. The run fails on any violation.
- Example analytics (`report.py`): spend / CTR / cost-per-conversion by channel.
- Implementation plan: `docs/superpowers/plans/2026-06-30-campaignflow-core.md`.

## Key decisions
- DuckDB (embedded) instead of Docker/Postgres: one-command run, no infra to stand up. Docker Desktop WSL integration is currently off on this machine.
- ELT not ETL: load raw first, transform in-warehouse with SQL.
- Deterministic (fixed seed) + idempotent (rebuild derived tables from raw) so tests and demos are stable.
- Fixed FX map to DKK in `config.py` (documented simplification).

## Next steps (extension ladder, each its own branch + PR)
1. **PySpark transform stage** (silver -> gold fact, parity-tested against the DuckDB fact). Needs a JRE: `sudo apt-get install -y default-jre`; add `pyspark` to dev deps.
2. **Terraform (Azurite / LocalStack)** bronze landing zone. Needs Docker (turn on Docker Desktop WSL integration).
3. **Next.js / TypeScript dashboard** over the gold marts (spend / CTR / CPA charts). Separate Node app; Vitest.
4. **docker-compose** to run the whole stack (makes the CV "runs locally via docker compose" line literally true).

## On resume (in a WSL Claude session: `cd ~/dev/campaignflow`)
1. Read this file, then `git log --oneline` and `gh run list` to confirm state.
2. If `.venv` is gone: `python3 -m venv .venv && . .venv/bin/activate && pip install -e ".[dev]"`.
3. Confirm green: `ruff check . && pytest -q`.
4. Pick the next extension, branch `feat/<slug>`, TDD, open a PR, keep CI green.

## Interview notes
Be able to explain: the medallion layering (bronze/silver/gold), the star-schema grain (one fact row per date x channel x campaign), why ELT over ETL, the data-quality checks, and how a PySpark/Databricks job would slot into the same silver->gold step. The README roadmap shows what a production version adds.
