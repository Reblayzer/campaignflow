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
