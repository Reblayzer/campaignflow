# CampaignFlow handoff

## Goal
Marketing-campaign ELT pipeline + star schema, built for the Arla "Entry IT Developer, IT Product for Marketing" application and interview. Must be runnable, public, and fully explainable.

## Status: core + two extensions shipped; dashboard (#3) spec+plan ready
- Public repo: https://github.com/Reblayzer/campaignflow (branch `main`, CI on GitHub Actions).
- Core: 15 tests green, ruff clean. Runs via `python -m campaignflow run` then `python -m campaignflow report`.
- **Extension #1 shipped (PR #1, merged):** PySpark silver->gold fact in `spark_fact.py`, parity-tested cent-exact against the DuckDB fact. Needs a JRE (Java 17/21); CI runs Temurin 21.
- **Extension #2 shipped (PR #2, merged):** Terraform Azure blob landing zone under `infra/terraform/` (`azure/` prod via azurerm, `local/` Azurite emulator). `bronze.load_raw` reads `az://` via DuckDB's azure extension; `pipeline.run`/CLI gain `--landing-zone`. 22 tests green; CI starts Azurite + validates Terraform.
- **Extension #3 (next): NOT yet built.** Spec + full implementation plan are committed on branch `feat/dashboard`:
  - Spec: `docs/superpowers/specs/2026-06-30-dashboard-design.md`
  - Plan: `docs/superpowers/plans/2026-06-30-dashboard.md` (13 bite-sized TDD tasks, full code)
- Docker/Terraform/Node 22 are all available on this machine now (the old "Docker off" note below is obsolete).

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
1. ~~PySpark transform stage~~ — shipped (PR #1).
2. ~~Terraform blob landing zone~~ — shipped (PR #2, Azurite).
3. **Next.js / TypeScript dashboard** — spec+plan ready on `feat/dashboard`; BUILD NEXT (see resume).
4. **docker-compose** to run the whole stack (makes the CV "runs locally via docker compose" line literally true).

## On resume — build the dashboard (#3) in a FRESH session
1. `cd ~/dev/campaignflow && git checkout feat/dashboard && git pull`.
2. Read `docs/superpowers/plans/2026-06-30-dashboard.md` (the plan) and `docs/superpowers/specs/2026-06-30-dashboard-design.md` (the spec).
3. If `.venv` is gone: `python3 -m venv .venv && . .venv/bin/activate && pip install -e ".[dev]"`.
4. Confirm green: `ruff check . && pytest -q`.
5. Execute the plan task-by-task (TDD), using the `superpowers:subagent-driven-development` or `superpowers:executing-plans` skill. Commit per task; open the PR (Task 13) and keep BOTH CI jobs (`test`, `dashboard`) green.

## On resume for any OTHER work
1. Read this file, then `git log --oneline` and `gh run list` to confirm state.
2. `. .venv/bin/activate` (recreate if gone), confirm green: `ruff check . && pytest -q`.
3. Pick the next extension, branch `feat/<slug>`, TDD, open a PR, keep CI green.

## Interview notes
Be able to explain: the medallion layering (bronze/silver/gold), the star-schema grain (one fact row per date x channel x campaign), why ELT over ETL, the data-quality checks, and how a PySpark/Databricks job would slot into the same silver->gold step. The README roadmap shows what a production version adds.
