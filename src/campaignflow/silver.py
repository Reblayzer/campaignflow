import duckdb

from campaignflow.config import FX_TO_DKK

# Title-case a channel without relying on initcap (not in DuckDB): split on
# spaces, upper-case the first letter of each word, rejoin.
_CANONICAL_CHANNEL = (
    "array_to_string("
    "list_transform(string_split(trim(lower(channel)), ' '), "
    "x -> upper(left(x, 1)) || substr(x, 2)), ' ')"
)


def build_silver(con: duckdb.DuckDBPyConnection) -> int:
    """Type, clean, FX-normalise, and de-duplicate bronze into the silver layer."""
    fx_cases = " ".join(
        f"when upper(trim(currency)) = '{code}' then {rate}" for code, rate in FX_TO_DKK.items()
    )
    con.execute("drop table if exists silver.campaign_events")
    con.execute(
        f"""
        create table silver.campaign_events as
        with typed as (
            select
                cast(trim(event_date) as date)                        as event_date,
                {_CANONICAL_CHANNEL}                                  as channel,
                trim(campaign_id)                                     as campaign_id,
                trim(campaign_name)                                   as campaign_name,
                cast(trim(impressions) as integer)                    as impressions,
                cast(trim(clicks) as integer)                         as clicks,
                round(cast(trim(spend) as double) * (case {fx_cases} else 1.0 end), 2) as spend_dkk,
                cast(trim(conversions) as integer)                    as conversions
            from bronze.campaign_events_raw
        )
        select distinct
            event_date, channel, campaign_id, campaign_name,
            impressions, clicks, cast(spend_dkk as decimal(14, 2)) as spend_dkk, conversions
        from typed
        where impressions >= 0 and clicks >= 0 and conversions >= 0 and spend_dkk > 0
        """
    )
    return con.execute("select count(*) from silver.campaign_events").fetchone()[0]
