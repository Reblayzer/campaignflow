import duckdb

_SPEND_BY_CHANNEL = """
select
    ch.channel_group,
    ch.channel_name,
    d.year,
    d.month,
    round(sum(f.spend_dkk), 2)                                      as spend_dkk,
    sum(f.clicks)                                                   as clicks,
    sum(f.conversions)                                             as conversions,
    round(100.0 * sum(f.clicks) / nullif(sum(f.impressions), 0), 2) as ctr_pct,
    round(sum(f.spend_dkk) / nullif(sum(f.conversions), 0), 2)      as cost_per_conversion
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
    print("  ".join(f"{h:>12}" for h in header))
    for r in rows:
        print("  ".join(f"{('' if v is None else v)!s:>12}" for v in r))
