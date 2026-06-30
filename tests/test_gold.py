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
        "from gold.fact_campaign_performance group by 1, 2, 3 having count(*) > 1)"
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
    fact_spend = con.execute("select round(sum(spend_dkk), 2) from gold.fact_campaign_performance").fetchone()[0]
    silver_spend = con.execute("select round(sum(spend_dkk), 2) from silver.campaign_events").fetchone()[0]
    assert fact_spend == silver_spend
