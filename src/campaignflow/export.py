import json
from pathlib import Path

import duckdb

from campaignflow.config import SEED

_TOTALS = """
select
    cast(round(sum(spend_dkk), 2) as double)                                  as spend_dkk,
    cast(round(100.0 * sum(clicks) / nullif(sum(impressions), 0), 2) as double) as ctr_pct,
    cast(round(sum(spend_dkk) / nullif(sum(conversions), 0), 2) as double)     as cost_per_conversion,
    cast(sum(conversions) as bigint)                                          as conversions
from gold.fact_campaign_performance
"""

_CHANNELS = """
select
    ch.channel_group,
    ch.channel_name,
    cast(round(sum(f.spend_dkk), 2) as double)                                    as spend_dkk,
    cast(sum(f.clicks) as bigint)                                                 as clicks,
    cast(sum(f.conversions) as bigint)                                            as conversions,
    cast(round(100.0 * sum(f.clicks) / nullif(sum(f.impressions), 0), 2) as double) as ctr_pct,
    cast(round(sum(f.spend_dkk) / nullif(sum(f.conversions), 0), 2) as double)     as cost_per_conversion
from gold.fact_campaign_performance f
join gold.dim_channel ch on f.channel_key = ch.channel_key
group by 1, 2
order by ch.channel_group, ch.channel_name
"""

_MONTHLY = """
select
    printf('%04d-%02d', d.year, d.month)                                          as year_month,
    cast(round(sum(f.spend_dkk), 2) as double)                                    as spend_dkk,
    cast(round(100.0 * sum(f.clicks) / nullif(sum(f.impressions), 0), 2) as double) as ctr_pct,
    cast(round(sum(f.spend_dkk) / nullif(sum(f.conversions), 0), 2) as double)     as cost_per_conversion
from gold.fact_campaign_performance f
join gold.dim_date d on f.date_key = d.date_key
group by 1
order by 1
"""


def build_marts(con: duckdb.DuckDBPyConnection, generated_at: str, seed: int) -> dict:
    """Read the gold marts into the dashboard contract (JSON-serialisable dict)."""
    t = con.execute(_TOTALS).fetchone()
    totals = {
        "spend_dkk": t[0],
        "ctr_pct": t[1],
        "cost_per_conversion": t[2],
        "conversions": t[3],
    }
    channels = [
        {
            "channel_group": r[0],
            "channel_name": r[1],
            "spend_dkk": r[2],
            "clicks": r[3],
            "conversions": r[4],
            "ctr_pct": r[5],
            "cost_per_conversion": r[6],
        }
        for r in con.execute(_CHANNELS).fetchall()
    ]
    monthly = [
        {"year_month": r[0], "spend_dkk": r[1], "ctr_pct": r[2], "cost_per_conversion": r[3]}
        for r in con.execute(_MONTHLY).fetchall()
    ]
    return {
        "generated_at": generated_at,
        "seed": seed,
        "totals": totals,
        "channels": channels,
        "monthly": monthly,
    }


def export_marts(
    db_path: str, out_path: str | Path, generated_at: str, seed: int = SEED
) -> dict:
    """Export the gold marts to a JSON file the dashboard reads at build time."""
    con = duckdb.connect(db_path, read_only=True)
    try:
        marts = build_marts(con, generated_at=generated_at, seed=seed)
    finally:
        con.close()
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(marts, indent=2) + "\n")
    return marts
