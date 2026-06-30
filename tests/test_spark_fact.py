from campaignflow.bronze import load_raw
from campaignflow.db import connect
from campaignflow.generate import generate_raw
from campaignflow.gold import build_gold
from campaignflow.silver import build_silver
from campaignflow.spark_fact import build_fact_spark, read_gold_inputs

_FACT_SELECT = (
    "select date_key, channel_key, campaign_key, impressions, clicks, spend_dkk, conversions "
    "from gold.fact_campaign_performance"
)


def _seed(tmp_path):
    con = connect(":memory:")
    load_raw(con, generate_raw(rows=600, seed=11, out_dir=tmp_path))
    build_silver(con)
    build_gold(con)
    return con


def _index(rows):
    """Key a fact row set by grain; measures as ints (spend in integer cents)."""
    out = {}
    for date_key, channel_key, campaign_key, impressions, clicks, spend, conversions in rows:
        out[(int(date_key), int(channel_key), int(campaign_key))] = (
            int(impressions),
            int(clicks),
            int(round(float(spend) * 100)),
            int(conversions),
        )
    return out


def test_spark_fact_matches_duckdb_fact(spark, tmp_path):
    con = _seed(tmp_path)

    silver_df, dim_channel_df, dim_campaign_df = read_gold_inputs(spark, con)
    spark_fact = build_fact_spark(silver_df, dim_channel_df, dim_campaign_df)
    spark_rows = [tuple(r) for r in spark_fact.collect()]

    duck_rows = con.execute(_FACT_SELECT).fetchall()

    spark_index = _index(spark_rows)
    duck_index = _index(duck_rows)

    assert len(duck_index) > 0
    assert spark_index == duck_index


def test_spark_fact_grain_is_unique(spark, tmp_path):
    con = _seed(tmp_path)

    silver_df, dim_channel_df, dim_campaign_df = read_gold_inputs(spark, con)
    spark_fact = build_fact_spark(silver_df, dim_channel_df, dim_campaign_df)

    total = spark_fact.count()
    distinct = spark_fact.select("date_key", "channel_key", "campaign_key").distinct().count()
    assert total == distinct and total > 0
