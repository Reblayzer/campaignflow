# CampaignFlow Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A Docker-free, fully tested Python ELT pipeline that ingests synthetic marketing-campaign data and models it into a bronze/silver/gold star schema in DuckDB, runnable with one command and green in CI.

**Architecture:** ELT, not ETL: raw CSVs are loaded verbatim into a `bronze` schema, then transformed in-warehouse (DuckDB SQL) into a cleaned `silver` table, then into a `gold` star schema (one fact + three conformed dimensions). Data-quality checks gate every layer. All DB access goes through one connection helper; each layer is a pure function taking a DuckDB connection (dependency injection), so tests run against an in-memory database. The pipeline is deterministic (fixed seed) and idempotent (derived tables are rebuilt from raw each run).

**Tech Stack:** Python 3.12, DuckDB (embedded, no server), argparse CLI, pytest, ruff. Runtime dependency is DuckDB only.

## Global Constraints

- Python 3.12; runtime dependency limited to `duckdb`. Dev dependencies: `pytest`, `ruff`.
- No Docker required to run or test the core. `python -m campaignflow run` is the single entrypoint.
- Synthetic / generated data only. Never real Arla data.
- Star schema grain: one fact row per (event_date, channel, campaign). Measures: impressions, clicks, spend (normalised to DKK), conversions.
- Surrogate keys: `date_key` = YYYYMMDD integer; `channel_key` and `campaign_key` = stable integers assigned by `ROW_NUMBER()` over the natural key ordered deterministically.
- Currency normalisation to DKK uses a fixed reference-rate map (documented as a simplification): `{"DKK": 1.0, "EUR": 7.46, "SEK": 0.64}`.
- Follow `~/dev/CLAUDE.md`: TDD (red/green/refactor), files under ~300 lines, names reveal intent, conventional commits, stage specific files (never `git add .`), one logical change per commit.
- Every part must be interview-defensible: prefer clear SQL and small functions over cleverness.

---

## File Structure

```
~/dev/campaignflow/
  pyproject.toml                 # package metadata, deps, ruff + pytest config
  README.md                      # what/why, architecture diagram, how to run
  .gitignore                     # venv, __pycache__, *.duckdb, data/raw/*
  .github/workflows/ci.yml       # ruff + pytest on push/PR
  docs/superpowers/plans/2026-06-30-campaignflow-core.md
  src/campaignflow/
    __init__.py                  # version
    __main__.py                  # `python -m campaignflow` -> cli.main()
    cli.py                       # argparse: run / report subcommands
    config.py                    # paths, SEED, FX rates, channel/campaign catalogs
    db.py                        # connect(path) -> duckdb connection; schema bootstrap
    generate.py                  # synthetic raw CSV generator (deterministic)
    bronze.py                    # load raw CSV -> bronze.campaign_events_raw
    silver.py                    # bronze -> silver.campaign_events (typed, cleaned, deduped)
    gold.py                      # silver -> gold dims + fact (star schema)
    quality.py                   # data-quality checks across layers
    report.py                    # example analytics queries on the gold marts
    pipeline.py                  # run(): orchestrates generate->bronze->silver->gold->checks
  tests/
    conftest.py                  # in-memory db fixture, tiny sample frames
    test_generate.py
    test_bronze.py
    test_silver.py
    test_gold.py
    test_quality.py
    test_report.py
    test_pipeline.py
  data/raw/.gitkeep              # landing zone for generated CSVs (contents gitignored)
```

Each module has one responsibility; SQL lives as named constants inside its layer module so the transform and its tests sit together.

---

### Task 1: Project scaffold, tooling, public repo, CI

**Files:**
- Create: `pyproject.toml`, `.gitignore`, `.github/workflows/ci.yml`, `README.md` (stub), `src/campaignflow/__init__.py`, `src/campaignflow/__main__.py`, `src/campaignflow/cli.py`, `tests/test_smoke.py`, `data/raw/.gitkeep`

**Interfaces:**
- Produces: `cli.main(argv: list[str] | None = None) -> int`; `python -m campaignflow` calls it. `__init__.py` exposes `__version__: str`.

- [ ] **Step 1: Write the failing smoke test**

```python
# tests/test_smoke.py
from campaignflow import __version__
from campaignflow.cli import main


def test_version_is_set():
    assert isinstance(__version__, str) and __version__


def test_cli_no_args_prints_help_and_returns_zero(capsys):
    code = main([])
    out = capsys.readouterr().out
    assert code == 0
    assert "campaignflow" in out.lower()
```

- [ ] **Step 2: Run it, verify it fails** (`pytest -q`, expect import error / no module).

- [ ] **Step 3: Implement scaffold**

`pyproject.toml` (setuptools, src layout, ruff + pytest config):
```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "campaignflow"
version = "0.1.0"
description = "Marketing-campaign ELT pipeline and analytics warehouse (bronze/silver/gold star schema)."
requires-python = ">=3.12"
dependencies = ["duckdb>=1.1"]

[project.optional-dependencies]
dev = ["pytest>=8", "ruff>=0.6"]

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]

[tool.ruff]
line-length = 100
src = ["src", "tests"]

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B"]
```

`src/campaignflow/__init__.py`:
```python
__version__ = "0.1.0"
```

`src/campaignflow/cli.py`:
```python
import argparse


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="campaignflow", description="Marketing-campaign ELT pipeline.")
    sub = parser.add_subparsers(dest="command")
    run_p = sub.add_parser("run", help="Generate data and build the bronze/silver/gold warehouse.")
    run_p.add_argument("--db", default="campaignflow.duckdb", help="DuckDB file path.")
    run_p.add_argument("--rows", type=int, default=5000, help="Approx raw rows to generate.")
    run_p.add_argument("--seed", type=int, default=42, help="Deterministic seed.")
    report_p = sub.add_parser("report", help="Print example analytics from the gold marts.")
    report_p.add_argument("--db", default="campaignflow.duckdb")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 0
    if args.command == "run":
        from campaignflow.pipeline import run

        run(db_path=args.db, rows=args.rows, seed=args.seed)
        return 0
    if args.command == "report":
        from campaignflow.report import print_report

        print_report(db_path=args.db)
        return 0
    parser.print_help()
    return 0
```

`src/campaignflow/__main__.py`:
```python
import sys

from campaignflow.cli import main

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
```

`.gitignore`:
```
__pycache__/
*.pyc
.venv/
venv/
*.duckdb
data/raw/*
!data/raw/.gitkeep
.pytest_cache/
.ruff_cache/
```

`.github/workflows/ci.yml`:
```yaml
name: ci
on:
  push:
    branches: [main]
  pull_request:
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: python -m pip install --upgrade pip
      - run: pip install -e ".[dev]"
      - run: ruff check .
      - run: pytest -q
```

- [ ] **Step 4: Create venv, install, run tests + ruff**
```bash
cd ~/dev/campaignflow
python3 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
ruff check . && pytest -q
```
Expected: ruff clean, smoke tests PASS.

- [ ] **Step 5: Git init, create the public repo, push**
```bash
cd ~/dev/campaignflow
git init -b main
git add pyproject.toml .gitignore .github/workflows/ci.yml README.md src tests data/raw/.gitkeep docs
git commit -m "chore: scaffold campaignflow package, tooling, and CI"
gh repo create campaignflow --public --source=. --remote=origin --description "Marketing-campaign ELT pipeline and analytics warehouse (bronze/silver/gold star schema) in Python + DuckDB." --push
```
Expected: repo live at github.com/Reblayzer/campaignflow, CI run starts.

---

### Task 2: Config and DB connection

**Files:**
- Create: `src/campaignflow/config.py`, `src/campaignflow/db.py`, `tests/conftest.py`
- Test: `tests/test_db.py` (folded into conftest usage; smoke-tested via later tasks)

**Interfaces:**
- Produces:
  - `config.SEED: int`, `config.FX_TO_DKK: dict[str, float]`, `config.CHANNELS: list[dict]`, `config.CAMPAIGNS: list[dict]`, `config.RAW_DIR: Path`, `config.SCHEMAS: tuple[str, ...]`.
  - `db.connect(path: str = ":memory:") -> duckdb.DuckDBPyConnection` (creates schemas bronze/silver/gold).

- [ ] **Step 1: Write the failing test**
```python
# tests/conftest.py
import duckdb
import pytest

from campaignflow.db import connect


@pytest.fixture
def con():
    connection = duckdb.connect(":memory:")
    yield connection
    connection.close()


# tests/test_db.py
from campaignflow.db import connect


def test_connect_creates_layer_schemas():
    con = connect(":memory:")
    schemas = {r[0] for r in con.execute("select schema_name from information_schema.schemata").fetchall()}
    assert {"bronze", "silver", "gold"} <= schemas
```

- [ ] **Step 2: Run, verify it fails.**

- [ ] **Step 3: Implement**
```python
# src/campaignflow/config.py
from pathlib import Path

SEED = 42
RAW_DIR = Path("data/raw")
SCHEMAS = ("bronze", "silver", "gold")
FX_TO_DKK = {"DKK": 1.0, "EUR": 7.46, "SEK": 0.64}

CHANNELS = [
    {"name": "Paid Search", "group": "Paid"},
    {"name": "Paid Social", "group": "Paid"},
    {"name": "Display", "group": "Paid"},
    {"name": "Email", "group": "Owned"},
    {"name": "Organic Social", "group": "Earned"},
    {"name": "Affiliate", "group": "Paid"},
]

# Each campaign runs on exactly one channel in this dataset.
CAMPAIGNS = [
    {"campaign_id": f"CMP-{1000 + i}", "name": name, "channel": channel}
    for i, (name, channel) in enumerate([
        ("Spring Skyr Launch", "Paid Search"),
        ("Protein Pudding Awareness", "Paid Social"),
        ("Organic Milk Always-On", "Paid Search"),
        ("Cheese Lovers Retargeting", "Display"),
        ("Barista Edition Teaser", "Paid Social"),
        ("Recipe Newsletter", "Email"),
        ("Summer Smoothie UGC", "Organic Social"),
        ("Lactose-Free Affiliate Push", "Affiliate"),
        ("Kids Yogurt Back-to-School", "Display"),
        ("Sustainability Story", "Organic Social"),
    ])
]
```
```python
# src/campaignflow/db.py
import duckdb

from campaignflow.config import SCHEMAS


def connect(path: str = ":memory:") -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(path)
    for schema in SCHEMAS:
        con.execute(f"create schema if not exists {schema}")
    return con
```

- [ ] **Step 4: Run tests, verify PASS.**
- [ ] **Step 5: Commit**
```bash
git add src/campaignflow/config.py src/campaignflow/db.py tests/conftest.py tests/test_db.py
git commit -m "feat(db): add config catalogs and DuckDB connection with layer schemas"
```

---

### Task 3: Synthetic raw data generator

**Files:** Create `src/campaignflow/generate.py`; Test `tests/test_generate.py`

**Interfaces:**
- Produces: `generate.generate_raw(rows: int, seed: int, out_dir: Path) -> Path` writes one CSV to `out_dir/campaign_events.csv` and returns the path. Columns: `event_date, channel, campaign_id, campaign_name, impressions, clicks, spend, conversions, currency`. Deterministic for a given seed. Intentionally includes a few exact duplicate rows and mixed currencies and stray whitespace, to give silver real cleaning to do.

- [ ] **Step 1: Failing test**
```python
# tests/test_generate.py
import csv

from campaignflow.config import CAMPAIGNS
from campaignflow.generate import generate_raw


def test_generate_is_deterministic(tmp_path):
    a = generate_raw(rows=500, seed=1, out_dir=tmp_path / "a")
    b = generate_raw(rows=500, seed=1, out_dir=tmp_path / "b")
    assert a.read_text() == b.read_text()


def test_generate_has_expected_header_and_known_campaigns(tmp_path):
    path = generate_raw(rows=200, seed=7, out_dir=tmp_path)
    with path.open() as fh:
        reader = csv.DictReader(fh)
        assert reader.fieldnames == [
            "event_date", "channel", "campaign_id", "campaign_name",
            "impressions", "clicks", "spend", "conversions", "currency",
        ]
        ids = {row["campaign_id"] for row in reader}
    assert ids <= {c["campaign_id"] for c in CAMPAIGNS}
```

- [ ] **Step 2: Run, verify fail.**

- [ ] **Step 3: Implement**
```python
# src/campaignflow/generate.py
import csv
import random
from datetime import date, timedelta
from pathlib import Path

from campaignflow.config import CAMPAIGNS

_HEADER = [
    "event_date", "channel", "campaign_id", "campaign_name",
    "impressions", "clicks", "spend", "conversions", "currency",
]
_CURRENCIES = ["DKK", "DKK", "DKK", "EUR", "SEK"]  # weighted toward DKK
_START = date(2026, 1, 1)
_DAYS = 120


def generate_raw(rows: int, seed: int, out_dir: Path) -> Path:
    rng = random.Random(seed)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "campaign_events.csv"
    records = [_make_row(rng) for _ in range(rows)]
    # inject a few exact duplicates so silver dedup has work to do
    for _ in range(max(1, rows // 100)):
        records.append(dict(rng.choice(records)))
    with out_path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=_HEADER)
        writer.writeheader()
        writer.writerows(records)
    return out_path


def _make_row(rng: random.Random) -> dict[str, str]:
    campaign = rng.choice(CAMPAIGNS)
    day = _START + timedelta(days=rng.randint(0, _DAYS - 1))
    impressions = rng.randint(500, 50_000)
    clicks = int(impressions * rng.uniform(0.005, 0.06))
    conversions = int(clicks * rng.uniform(0.01, 0.12))
    spend = round(clicks * rng.uniform(1.5, 9.0), 2)
    # stray whitespace and casing on channel to give silver real cleaning to do
    channel = rng.choice([campaign["channel"], f" {campaign['channel']} ", campaign["channel"].upper()])
    return {
        "event_date": day.isoformat(),
        "channel": channel,
        "campaign_id": campaign["campaign_id"],
        "campaign_name": campaign["name"],
        "impressions": str(impressions),
        "clicks": str(clicks),
        "spend": str(spend),
        "conversions": str(conversions),
        "currency": rng.choice(_CURRENCIES),
    }
```

- [ ] **Step 4: Run tests, PASS.**
- [ ] **Step 5: Commit** `feat(generate): deterministic synthetic campaign-event generator`

---

### Task 4: Bronze load

**Files:** Create `src/campaignflow/bronze.py`; Test `tests/test_bronze.py`

**Interfaces:**
- Consumes: a CSV produced by `generate_raw`; a connection from `db.connect`.
- Produces: `bronze.load_raw(con, csv_path: Path) -> int` truncates/creates `bronze.campaign_events_raw` (all columns VARCHAR + `_ingested_at TIMESTAMP`, `_source_file VARCHAR`), loads the CSV verbatim (no casting), returns row count.

- [ ] **Step 1: Failing test**
```python
# tests/test_bronze.py
from campaignflow.bronze import load_raw
from campaignflow.db import connect
from campaignflow.generate import generate_raw


def test_load_raw_loads_every_row_as_text(tmp_path):
    con = connect(":memory:")
    csv_path = generate_raw(rows=100, seed=3, out_dir=tmp_path)
    n = load_raw(con, csv_path)
    assert n > 0
    cols = con.execute(
        "select data_type from information_schema.columns "
        "where table_schema='bronze' and table_name='campaign_events_raw' and column_name='impressions'"
    ).fetchone()
    assert cols[0].upper() in ("VARCHAR", "TEXT")
    assert con.execute("select count(*) from bronze.campaign_events_raw").fetchone()[0] == n
```

- [ ] **Step 2: Run, fail.**
- [ ] **Step 3: Implement**
```python
# src/campaignflow/bronze.py
from pathlib import Path

import duckdb

_COLUMNS = [
    "event_date", "channel", "campaign_id", "campaign_name",
    "impressions", "clicks", "spend", "conversions", "currency",
]


def load_raw(con: duckdb.DuckDBPyConnection, csv_path: Path) -> int:
    con.execute("drop table if exists bronze.campaign_events_raw")
    select_text = ", ".join(f'"{c}"' for c in _COLUMNS)
    con.execute(
        f"""
        create table bronze.campaign_events_raw as
        select {select_text}, now() as _ingested_at, ? as _source_file
        from read_csv(?, header=true, all_varchar=true)
        """,
        [str(csv_path), str(csv_path)],
    )
    return con.execute("select count(*) from bronze.campaign_events_raw").fetchone()[0]
```

- [ ] **Step 4: Run, PASS.**
- [ ] **Step 5: Commit** `feat(bronze): load raw campaign CSV verbatim into bronze layer`

---

### Task 5: Silver transform (clean, type, normalise, dedup)

**Files:** Create `src/campaignflow/silver.py`; Test `tests/test_silver.py`

**Interfaces:**
- Consumes: `bronze.campaign_events_raw`; `config.FX_TO_DKK`.
- Produces: `silver.build_silver(con) -> int` creates `silver.campaign_events` typed as: `event_date DATE, channel VARCHAR (trimmed + canonical title case), campaign_id VARCHAR, campaign_name VARCHAR, impressions INTEGER, clicks INTEGER, spend_dkk DECIMAL(14,2), conversions INTEGER`. Exact duplicates removed; spend converted to DKK via FX map. Returns row count.

- [ ] **Step 1: Failing test**
```python
# tests/test_silver.py
from campaignflow.bronze import load_raw
from campaignflow.db import connect
from campaignflow.generate import generate_raw
from campaignflow.silver import build_silver


def _seed_silver(tmp_path):
    con = connect(":memory:")
    load_raw(con, generate_raw(rows=400, seed=5, out_dir=tmp_path))
    build_silver(con)
    return con


def test_silver_is_typed_and_canonical(tmp_path):
    con = _seed_silver(tmp_path)
    # channels are trimmed + title-cased: no leading spaces, no all-caps survivors
    bad = con.execute(
        "select count(*) from silver.campaign_events where channel != trim(channel) or channel = upper(channel)"
    ).fetchone()[0]
    assert bad == 0
    # measures are non-negative integers, spend is positive
    assert con.execute(
        "select count(*) from silver.campaign_events where impressions < 0 or clicks < 0 or conversions < 0 or spend_dkk <= 0"
    ).fetchone()[0] == 0


def test_silver_removes_exact_duplicates(tmp_path):
    con = _seed_silver(tmp_path)
    dups = con.execute(
        """
        select count(*) from (
          select event_date, channel, campaign_id, impressions, clicks, spend_dkk, conversions, count(*) c
          from silver.campaign_events
          group by 1,2,3,4,5,6,7 having count(*) > 1
        )
        """
    ).fetchone()[0]
    assert dups == 0
```

- [ ] **Step 2: Run, fail.**
- [ ] **Step 3: Implement**
```python
# src/campaignflow/silver.py
import duckdb

from campaignflow.config import FX_TO_DKK


def build_silver(con: duckdb.DuckDBPyConnection) -> int:
    cases = " ".join(f"when upper(trim(currency)) = '{code}' then {rate}" for code, rate in FX_TO_DKK.items())
    con.execute("drop table if exists silver.campaign_events")
    con.execute(
        f"""
        create table silver.campaign_events as
        with typed as (
            select
                cast(trim(event_date) as date)                       as event_date,
                -- canonical channel: collapse whitespace, title case
                regexp_replace(initcap(lower(trim(channel))), '\\s+', ' ', 'g') as channel,
                trim(campaign_id)                                    as campaign_id,
                trim(campaign_name)                                  as campaign_name,
                cast(trim(impressions) as integer)                   as impressions,
                cast(trim(clicks) as integer)                        as clicks,
                round(cast(trim(spend) as double) * (case {cases} else 1.0 end), 2) as spend_dkk,
                cast(trim(conversions) as integer)                   as conversions
            from bronze.campaign_events_raw
        )
        select distinct
            event_date, channel, campaign_id, campaign_name,
            impressions, clicks, cast(spend_dkk as decimal(14,2)) as spend_dkk, conversions
        from typed
        where impressions >= 0 and clicks >= 0 and conversions >= 0 and spend_dkk > 0
        """
    )
    return con.execute("select count(*) from silver.campaign_events").fetchone()[0]
```
Note: `initcap` may not exist in all DuckDB builds; if `ruff`/runtime flags it, replace with a title-case expression. Verified expression alternative if needed:
```sql
-- alternative title-case without initcap:
list_aggregate(list_transform(string_split(lower(trim(channel)), ' '),
  x -> upper(x[1]) || x[2:]), 'string_agg', ' ')
```

- [ ] **Step 4: Run, PASS.** (If `initcap` errors, switch to the alternative and re-run.)
- [ ] **Step 5: Commit** `feat(silver): type, clean, FX-normalise, and dedupe into silver layer`

---

### Task 6: Gold star schema (dimensions + fact)

**Files:** Create `src/campaignflow/gold.py`; Test `tests/test_gold.py`

**Interfaces:**
- Consumes: `silver.campaign_events`; `config.CHANNELS` (for channel group).
- Produces: `gold.build_gold(con) -> dict[str, int]` creates and populates `gold.dim_date`, `gold.dim_channel`, `gold.dim_campaign`, `gold.fact_campaign_performance`; returns row counts per table. Fact grain: (date_key, channel_key, campaign_key).

- [ ] **Step 1: Failing test**
```python
# tests/test_gold.py
from campaignflow.bronze import load_raw
from campaignflow.db import connect
from campaignflow.generate import generate_raw
from campaignflow.gold import build_gold
from campaignflow.silver import build_silver


def _seed_gold(tmp_path):
    con = connect(":memory:")
    load_raw(con, generate_raw(rows=600, seed=11, out_dir=tmp_path))
    build_silver(con)
    build_gold(con)
    return con


def test_dim_keys_unique(tmp_path):
    con = _seed_gold(tmp_path)
    for table, key in [("dim_date", "date_key"), ("dim_channel", "channel_key"), ("dim_campaign", "campaign_key")]:
        total, distinct = con.execute(
            f"select count(*), count(distinct {key}) from gold.{table}"
        ).fetchone()
        assert total == distinct and total > 0


def test_fact_grain_is_unique_and_refs_resolve(tmp_path):
    con = _seed_gold(tmp_path)
    dup = con.execute(
        "select count(*) from (select date_key, channel_key, campaign_key, count(*) c "
        "from gold.fact_campaign_performance group by 1,2,3 having count(*)>1)"
    ).fetchone()[0]
    assert dup == 0
    orphans = con.execute(
        """
        select count(*) from gold.fact_campaign_performance f
        left join gold.dim_date d on f.date_key = d.date_key
        left join gold.dim_channel c on f.channel_key = c.channel_key
        left join gold.dim_campaign p on f.campaign_key = p.campaign_key
        where d.date_key is null or c.channel_key is null or p.campaign_key is null
        """
    ).fetchone()[0]
    assert orphans == 0


def test_fact_measures_aggregate_to_silver(tmp_path):
    con = _seed_gold(tmp_path)
    fact_spend = con.execute("select round(sum(spend_dkk),2) from gold.fact_campaign_performance").fetchone()[0]
    silver_spend = con.execute("select round(sum(spend_dkk),2) from silver.campaign_events").fetchone()[0]
    assert fact_spend == silver_spend
```

- [ ] **Step 2: Run, fail.**
- [ ] **Step 3: Implement**
```python
# src/campaignflow/gold.py
import duckdb

from campaignflow.config import CHANNELS

_CHANNEL_GROUP_CASE = " ".join(
    f"when channel = '{c['name']}' then '{c['group']}'" for c in CHANNELS
)


def build_gold(con: duckdb.DuckDBPyConnection) -> dict[str, int]:
    _build_dim_date(con)
    _build_dim_channel(con)
    _build_dim_campaign(con)
    _build_fact(con)
    return {
        t: con.execute(f"select count(*) from gold.{t}").fetchone()[0]
        for t in ("dim_date", "dim_channel", "dim_campaign", "fact_campaign_performance")
    }


def _build_dim_date(con: duckdb.DuckDBPyConnection) -> None:
    con.execute("drop table if exists gold.dim_date")
    con.execute(
        """
        create table gold.dim_date as
        select distinct
            cast(strftime(event_date, '%Y%m%d') as integer) as date_key,
            event_date                                       as full_date,
            extract(year from event_date)                    as year,
            extract(quarter from event_date)                 as quarter,
            extract(month from event_date)                   as month,
            strftime(event_date, '%B')                       as month_name,
            extract(day from event_date)                     as day,
            extract(week from event_date)                    as iso_week,
            extract(dow from event_date)                     as day_of_week,
            (extract(dow from event_date) in (0, 6))         as is_weekend
        from silver.campaign_events
        """
    )


def _build_dim_channel(con: duckdb.DuckDBPyConnection) -> None:
    con.execute("drop table if exists gold.dim_channel")
    con.execute(
        f"""
        create table gold.dim_channel as
        select
            row_number() over (order by channel) as channel_key,
            channel                               as channel_name,
            case {_CHANNEL_GROUP_CASE} else 'Other' end as channel_group
        from (select distinct channel from silver.campaign_events)
        """
    )


def _build_dim_campaign(con: duckdb.DuckDBPyConnection) -> None:
    con.execute("drop table if exists gold.dim_campaign")
    con.execute(
        """
        create table gold.dim_campaign as
        select
            row_number() over (order by campaign_id) as campaign_key,
            campaign_id,
            any_value(campaign_name)                 as campaign_name
        from silver.campaign_events
        group by campaign_id
        """
    )


def _build_fact(con: duckdb.DuckDBPyConnection) -> None:
    con.execute("drop table if exists gold.fact_campaign_performance")
    con.execute(
        """
        create table gold.fact_campaign_performance as
        select
            cast(strftime(s.event_date, '%Y%m%d') as integer) as date_key,
            ch.channel_key,
            cp.campaign_key,
            sum(s.impressions)                                as impressions,
            sum(s.clicks)                                     as clicks,
            cast(sum(s.spend_dkk) as decimal(14,2))           as spend_dkk,
            sum(s.conversions)                                as conversions
        from silver.campaign_events s
        join gold.dim_channel ch on ch.channel_name = s.channel
        join gold.dim_campaign cp on cp.campaign_id = s.campaign_id
        group by 1, 2, 3
        """
    )
```

- [ ] **Step 4: Run, PASS.**
- [ ] **Step 5: Commit** `feat(gold): build conformed dimensions and campaign-performance fact`

---

### Task 7: Data-quality checks

**Files:** Create `src/campaignflow/quality.py`; Test `tests/test_quality.py`

**Interfaces:**
- Produces:
  - `quality.CheckResult` dataclass: `name: str`, `passed: bool`, `detail: str`.
  - `quality.run_checks(con) -> list[CheckResult]` runs all gold-layer checks.
  - `quality.assert_quality(con) -> None` raises `quality.DataQualityError` listing failures if any check fails.

- [ ] **Step 1: Failing test**
```python
# tests/test_quality.py
import pytest

from campaignflow.bronze import load_raw
from campaignflow.db import connect
from campaignflow.generate import generate_raw
from campaignflow.gold import build_gold
from campaignflow.quality import DataQualityError, assert_quality, run_checks
from campaignflow.silver import build_silver


def _seed(tmp_path):
    con = connect(":memory:")
    load_raw(con, generate_raw(rows=600, seed=13, out_dir=tmp_path))
    build_silver(con)
    build_gold(con)
    return con


def test_all_checks_pass_on_clean_build(tmp_path):
    con = _seed(tmp_path)
    results = run_checks(con)
    assert results and all(r.passed for r in results)
    assert_quality(con)  # does not raise


def test_assert_quality_raises_on_orphan_fact_row(tmp_path):
    con = _seed(tmp_path)
    con.execute(
        "insert into gold.fact_campaign_performance values (99999999, -1, -1, 0, 0, 0.00, 0)"
    )
    with pytest.raises(DataQualityError):
        assert_quality(con)
```

- [ ] **Step 2: Run, fail.**
- [ ] **Step 3: Implement**
```python
# src/campaignflow/quality.py
from dataclasses import dataclass

import duckdb


@dataclass(frozen=True)
class CheckResult:
    name: str
    passed: bool
    detail: str


class DataQualityError(Exception):
    pass


def _count(con: duckdb.DuckDBPyConnection, sql: str) -> int:
    return con.execute(sql).fetchone()[0]


def run_checks(con: duckdb.DuckDBPyConnection) -> list[CheckResult]:
    checks: list[CheckResult] = []

    def add(name: str, bad: int) -> None:
        checks.append(CheckResult(name, bad == 0, f"{bad} offending row(s)"))

    add("silver_not_empty", 0 if _count(con, "select count(*) from silver.campaign_events") > 0 else 1)
    add("fact_not_empty", 0 if _count(con, "select count(*) from gold.fact_campaign_performance") > 0 else 1)
    add("dim_date_key_unique", _count(con, "select count(*)-count(distinct date_key) from gold.dim_date"))
    add("dim_channel_key_unique", _count(con, "select count(*)-count(distinct channel_key) from gold.dim_channel"))
    add("dim_campaign_key_unique", _count(con, "select count(*)-count(distinct campaign_key) from gold.dim_campaign"))
    add("fact_grain_unique", _count(con,
        "select count(*) from (select 1 from gold.fact_campaign_performance "
        "group by date_key, channel_key, campaign_key having count(*)>1)"))
    add("fact_measures_non_negative", _count(con,
        "select count(*) from gold.fact_campaign_performance "
        "where impressions<0 or clicks<0 or spend_dkk<0 or conversions<0"))
    add("fact_refs_resolve", _count(con,
        """
        select count(*) from gold.fact_campaign_performance f
        left join gold.dim_date d on f.date_key=d.date_key
        left join gold.dim_channel c on f.channel_key=c.channel_key
        left join gold.dim_campaign p on f.campaign_key=p.campaign_key
        where d.date_key is null or c.channel_key is null or p.campaign_key is null
        """))
    return checks


def assert_quality(con: duckdb.DuckDBPyConnection) -> None:
    failures = [c for c in run_checks(con) if not c.passed]
    if failures:
        lines = "\n".join(f"  - {c.name}: {c.detail}" for c in failures)
        raise DataQualityError(f"{len(failures)} data-quality check(s) failed:\n{lines}")
```

- [ ] **Step 4: Run, PASS.**
- [ ] **Step 5: Commit** `feat(quality): add gold-layer data-quality checks and gate`

---

### Task 8: Pipeline orchestration + CLI run

**Files:** Create `src/campaignflow/pipeline.py`; Test `tests/test_pipeline.py`

**Interfaces:**
- Consumes: generate, db, bronze, silver, gold, quality.
- Produces: `pipeline.run(db_path: str = "campaignflow.duckdb", rows: int = 5000, seed: int = 42) -> dict` runs the full ELT, asserts quality, returns a summary dict `{"bronze": int, "silver": int, "gold": {...}}`. Idempotent: a second run on the same db yields the same gold row counts.

- [ ] **Step 1: Failing test**
```python
# tests/test_pipeline.py
from campaignflow.pipeline import run


def test_run_builds_all_layers_and_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # raw data lands under tmp
    db = str(tmp_path / "cf.duckdb")
    first = run(db_path=db, rows=800, seed=21)
    assert first["bronze"] > 0 and first["silver"] > 0
    assert first["gold"]["fact_campaign_performance"] > 0
    second = run(db_path=db, rows=800, seed=21)
    assert first["gold"] == second["gold"]  # deterministic + idempotent
```

- [ ] **Step 2: Run, fail.**
- [ ] **Step 3: Implement**
```python
# src/campaignflow/pipeline.py
from campaignflow import bronze, gold, quality, silver
from campaignflow.config import RAW_DIR, SEED
from campaignflow.db import connect
from campaignflow.generate import generate_raw


def run(db_path: str = "campaignflow.duckdb", rows: int = 5000, seed: int = SEED) -> dict:
    csv_path = generate_raw(rows=rows, seed=seed, out_dir=RAW_DIR)
    con = connect(db_path)
    try:
        bronze_rows = bronze.load_raw(con, csv_path)
        silver_rows = silver.build_silver(con)
        gold_counts = gold.build_gold(con)
        quality.assert_quality(con)
    finally:
        con.close()
    summary = {"bronze": bronze_rows, "silver": silver_rows, "gold": gold_counts}
    print(_format_summary(summary))
    return summary


def _format_summary(summary: dict) -> str:
    g = summary["gold"]
    return (
        "campaignflow run complete:\n"
        f"  bronze.campaign_events_raw : {summary['bronze']:>7} rows\n"
        f"  silver.campaign_events     : {summary['silver']:>7} rows\n"
        f"  gold.dim_date              : {g['dim_date']:>7} rows\n"
        f"  gold.dim_channel           : {g['dim_channel']:>7} rows\n"
        f"  gold.dim_campaign          : {g['dim_campaign']:>7} rows\n"
        f"  gold.fact_campaign_performance : {g['fact_campaign_performance']:>7} rows\n"
        "  data-quality checks        : all passed"
    )
```

- [ ] **Step 4: Run, PASS. Then run for real:** `python -m campaignflow run --db campaignflow.duckdb` and eyeball the summary.
- [ ] **Step 5: Commit** `feat(pipeline): orchestrate end-to-end ELT run with quality gate and CLI`

---

### Task 9: Report / example analytics on the gold marts

**Files:** Create `src/campaignflow/report.py`; Test `tests/test_report.py`

**Interfaces:**
- Produces: `report.spend_by_channel(con) -> list[tuple]` returns monthly spend/clicks/conversions plus CTR and CPA by channel group + channel; `report.print_report(db_path: str) -> None` opens the db read-only and prints a small table. Proves the star schema answers a real marketing question by joining fact to dims.

- [ ] **Step 1: Failing test**
```python
# tests/test_report.py
from campaignflow.bronze import load_raw
from campaignflow.db import connect
from campaignflow.generate import generate_raw
from campaignflow.gold import build_gold
from campaignflow.report import spend_by_channel
from campaignflow.silver import build_silver


def test_spend_by_channel_returns_rows_with_derived_metrics(tmp_path):
    con = connect(":memory:")
    load_raw(con, generate_raw(rows=900, seed=31, out_dir=tmp_path))
    build_silver(con)
    build_gold(con)
    rows = spend_by_channel(con)
    assert rows
    # each row: (channel_group, channel_name, year, month, spend, clicks, conversions, ctr, cpa)
    for row in rows:
        assert row[4] >= 0  # spend
        assert row[7] is None or row[7] >= 0  # ctr
```

- [ ] **Step 2: Run, fail.**
- [ ] **Step 3: Implement**
```python
# src/campaignflow/report.py
import duckdb

_SPEND_BY_CHANNEL = """
select
    ch.channel_group,
    ch.channel_name,
    d.year,
    d.month,
    round(sum(f.spend_dkk), 2)                                          as spend_dkk,
    sum(f.clicks)                                                       as clicks,
    sum(f.conversions)                                                  as conversions,
    round(100.0 * sum(f.clicks) / nullif(sum(f.impressions), 0), 2)     as ctr_pct,
    round(sum(f.spend_dkk) / nullif(sum(f.conversions), 0), 2)          as cost_per_conversion
from gold.fact_campaign_performance f
join gold.dim_channel ch on f.channel_key = ch.channel_key
join gold.dim_date d on f.date_key = d.date_key
group by 1, 2, 3, 4
order by ch.channel_group, ch.channel_name, d.year, d.month
"""


def spend_by_channel(con: duckdb.DuckDBPyConnection) -> list[tuple]:
    return con.execute(_SPEND_BY_CHANNEL).fetchall()


def print_report(db_path: str) -> None:
    con = duckdb.connect(db_path, read_only=True)
    try:
        rows = spend_by_channel(con)
    finally:
        con.close()
    header = ("group", "channel", "year", "month", "spend_dkk", "clicks", "conv", "ctr%", "cost/conv")
    print("  ".join(f"{h:>10}" for h in header))
    for r in rows:
        print("  ".join(f"{('' if v is None else v)!s:>10}" for v in r))
```

- [ ] **Step 4: Run, PASS.** Then `python -m campaignflow report` after a run.
- [ ] **Step 5: Commit** `feat(report): example spend/CTR/CPA-by-channel query on gold marts`

---

### Task 10: README, architecture doc, final green CI

**Files:** Modify `README.md`; (no code)

**Interfaces:** none (docs only — fast-track: research then commit).

- [ ] **Step 1: Write `README.md`** with: one-paragraph what/why; the bronze→silver→gold + star-schema ASCII diagram (reuse the brainstorm's); quickstart (`python -m venv`, `pip install -e ".[dev]"`, `python -m campaignflow run`, `python -m campaignflow report`); a short "data model" section describing the fact grain and each dimension; a "data quality" section listing the checks; an "ELT not ETL / design decisions" section (load raw first, idempotent rebuild, DuckDB choice, fixed FX rates as a simplification, synthetic data); and a "roadmap" section naming the extensions (PySpark stage, Terraform on Azurite/LocalStack, Next.js dashboard, docker-compose).
- [ ] **Step 2: Run the whole gate** `ruff check . && pytest -q` -> all green.
- [ ] **Step 3: Commit + push, confirm CI green**
```bash
git add README.md
git commit -m "docs: add architecture, quickstart, data model, and roadmap"
git push
gh run watch --exit-status || gh run view --log-failed
```
- [ ] **Step 4: Update `~/dev/PROJECTS.md`**: mark `campaignflow` status `done (core)` with the repo link `https://github.com/Reblayzer/campaignflow`.

---

## Follow-up plans (separate subsystems, build after the core is green)

Each is its own plan/PR; the core stands alone without them.

1. **PySpark transform stage** — re-express the silver→gold `fact` build as a PySpark job (same DataFrame API Databricks runs), reading silver as Parquet and writing the fact, with a parity test asserting it matches the DuckDB fact. Needs a JRE in WSL.
2. **Terraform (Azurite/LocalStack)** — IaC that provisions a local blob container + queue; the bronze landing zone writes there. Needs Docker (Docker Desktop WSL integration on).
3. **Next.js / TypeScript dashboard** — reads the gold marts (via a thin FastAPI or DuckDB-wasm) and renders spend/CTR/CPA-by-channel charts. Vitest for the data hooks.
4. **docker-compose** — wrap the pipeline + dashboard so `docker compose up` runs the whole stack (makes the CV's "runs locally via docker compose" literally true once Docker is available).

---

## Self-Review

**Spec coverage:** Python ELT (Tasks 3-8), bronze/silver/gold (4-6), star schema fact + 3 dims (6), data-quality checks (7), single `python -m campaignflow run` (8), pytest TDD (every task), ruff (1), README (10), public repo + CI (1, 10), idempotent + deterministic (3, 8). PySpark/Terraform/Next.js/docker-compose deferred to follow-up plans with a reason (Docker/JRE availability). Covered.

**Placeholder scan:** no TBD/TODO; every code step has real code. The only conditional is the `initcap` fallback in Task 5, which includes the exact alternative expression. Acceptable.

**Type consistency:** `silver.campaign_events.spend_dkk` (DECIMAL) is used consistently in gold and report; fact columns `date_key/channel_key/campaign_key/impressions/clicks/spend_dkk/conversions` match across gold, quality, and report; `CheckResult(name, passed, detail)` used consistently. Consistent.
