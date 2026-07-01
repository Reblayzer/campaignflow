import json
from pathlib import Path

from campaignflow.bronze import load_raw
from campaignflow.db import connect
from campaignflow.export import build_marts, export_marts
from campaignflow.generate import generate_raw
from campaignflow.gold import build_gold
from campaignflow.pipeline import run
from campaignflow.silver import build_silver


def _seed_warehouse(tmp_path):
    con = connect(":memory:")
    load_raw(con, generate_raw(rows=600, seed=11, out_dir=tmp_path))
    build_silver(con)
    build_gold(con)
    return con


def test_build_marts_shape_and_reconciliation(tmp_path):
    con = _seed_warehouse(tmp_path)
    marts = build_marts(con, generated_at="2026-06-30T12:00:00Z", seed=11)

    assert set(marts) == {"generated_at", "seed", "totals", "channels", "monthly"}
    assert marts["generated_at"] == "2026-06-30T12:00:00Z"
    assert marts["seed"] == 11

    # channel spend reconciles to totals (to the cent)
    channel_spend = round(sum(c["spend_dkk"] for c in marts["channels"]), 2)
    assert channel_spend == marts["totals"]["spend_dkk"]

    # monthly is ascending and non-empty
    months = [m["year_month"] for m in marts["monthly"]]
    assert months == sorted(months) and len(months) > 0

    # JSON-serialisable primitives only (no Decimal)
    assert isinstance(marts["totals"]["spend_dkk"], float)
    assert isinstance(marts["totals"]["conversions"], int)


def test_export_marts_writes_file_and_matches_fact(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    db = str(tmp_path / "cf.duckdb")
    run(db_path=db, rows=800, seed=21)

    out = tmp_path / "marts.json"
    marts = export_marts(db, out, generated_at="2026-06-30T00:00:00Z", seed=21)

    on_disk = json.loads(Path(out).read_text())
    assert on_disk == marts
    assert on_disk["totals"]["conversions"] > 0
    assert len(on_disk["channels"]) == 6  # six channels in config
