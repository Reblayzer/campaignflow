"""PySpark implementation of the silver -> gold fact transform.

This mirrors ``gold._build_fact`` exactly, but runs on Spark instead of DuckDB.
It exists to show how the in-warehouse aggregation step would slot into a
Spark/Databricks job, and is parity-tested against the DuckDB fact.

The conformed dimensions stay the source of surrogate keys: this stage consumes
``dim_channel`` / ``dim_campaign`` and recomputes only the fact grain, so the two
engines are compared on the aggregation, not on key assignment.
"""

import duckdb
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F

# Output column order, matching gold.fact_campaign_performance.
FACT_COLUMNS = (
    "date_key",
    "channel_key",
    "campaign_key",
    "impressions",
    "clicks",
    "spend_dkk",
    "conversions",
)


def read_gold_inputs(
    spark: SparkSession, con: duckdb.DuckDBPyConnection
) -> tuple[DataFrame, DataFrame, DataFrame]:
    """Pull the silver events and conformed dimensions from DuckDB into Spark.

    ``spend_dkk`` is carried as text and re-cast to ``decimal(14, 2)`` in Spark so
    the money column never round-trips through a float, keeping cent-exact parity.
    """
    silver_pdf = con.execute(
        """
        select
            cast(event_date as varchar) as event_date,
            channel, campaign_id,
            impressions, clicks,
            cast(spend_dkk as varchar) as spend_dkk,
            conversions
        from silver.campaign_events
        """
    ).df()
    dim_channel_pdf = con.execute("select channel_key, channel_name from gold.dim_channel").df()
    dim_campaign_pdf = con.execute("select campaign_key, campaign_id from gold.dim_campaign").df()

    silver_df = spark.createDataFrame(silver_pdf).withColumn(
        "spend_dkk", F.col("spend_dkk").cast("decimal(14, 2)")
    )
    dim_channel_df = spark.createDataFrame(dim_channel_pdf)
    dim_campaign_df = spark.createDataFrame(dim_campaign_pdf)
    return silver_df, dim_channel_df, dim_campaign_df


def build_fact_spark(
    silver_df: DataFrame, dim_channel_df: DataFrame, dim_campaign_df: DataFrame
) -> DataFrame:
    """Aggregate silver events into the campaign-performance fact using Spark.

    One row per (date_key, channel_key, campaign_key) with summed measures, the
    same grain and measures as ``gold._build_fact``.
    """
    channel_keys = dim_channel_df.select("channel_name", "channel_key")
    campaign_keys = dim_campaign_df.select("campaign_id", "campaign_key")

    return (
        silver_df.withColumn(
            "date_key", F.date_format(F.to_date("event_date"), "yyyyMMdd").cast("int")
        )
        .join(channel_keys, silver_df["channel"] == channel_keys["channel_name"], "inner")
        .join(campaign_keys, "campaign_id", "inner")
        .groupBy("date_key", "channel_key", "campaign_key")
        .agg(
            F.sum("impressions").alias("impressions"),
            F.sum("clicks").alias("clicks"),
            F.sum("spend_dkk").cast("decimal(14, 2)").alias("spend_dkk"),
            F.sum("conversions").alias("conversions"),
        )
        .select(*FACT_COLUMNS)
    )
