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
