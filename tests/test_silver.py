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
    bad = con.execute(
        "select count(*) from silver.campaign_events "
        "where channel != trim(channel) or channel = upper(channel)"
    ).fetchone()[0]
    assert bad == 0
    assert con.execute(
        "select count(*) from silver.campaign_events "
        "where impressions < 0 or clicks < 0 or conversions < 0 or spend_dkk <= 0"
    ).fetchone()[0] == 0


def test_silver_removes_exact_duplicates(tmp_path):
    con = _seed_silver(tmp_path)
    dups = con.execute(
        """
        select count(*) from (
          select event_date, channel, campaign_id, impressions, clicks, spend_dkk, conversions, count(*) c
          from silver.campaign_events
          group by 1, 2, 3, 4, 5, 6, 7 having count(*) > 1
        )
        """
    ).fetchone()[0]
    assert dups == 0
