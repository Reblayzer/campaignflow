import duckdb

from campaignflow.config import CHANNELS

_CHANNEL_GROUP_CASE = " ".join(
    f"when channel_name = '{c['name']}' then '{c['group']}'" for c in CHANNELS
)


def build_gold(con: duckdb.DuckDBPyConnection) -> dict[str, int]:
    """Build the star schema: three conformed dimensions and the performance fact."""
    _build_dim_date(con)
    _build_dim_channel(con)
    _build_dim_campaign(con)
    _build_fact(con)
    tables = ("dim_date", "dim_channel", "dim_campaign", "fact_campaign_performance")
    return {t: con.execute(f"select count(*) from gold.{t}").fetchone()[0] for t in tables}


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
            row_number() over (order by channel_name) as channel_key,
            channel_name,
            case {_CHANNEL_GROUP_CASE} else 'Other' end as channel_group
        from (select distinct channel as channel_name from silver.campaign_events)
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
            cast(sum(s.spend_dkk) as decimal(14, 2))          as spend_dkk,
            sum(s.conversions)                                as conversions
        from silver.campaign_events s
        join gold.dim_channel ch on ch.channel_name = s.channel
        join gold.dim_campaign cp on cp.campaign_id = s.campaign_id
        group by 1, 2, 3
        """
    )
