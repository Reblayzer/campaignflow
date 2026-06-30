from campaignflow import bronze, gold, quality, silver
from campaignflow.config import RAW_DIR, SEED
from campaignflow.db import connect
from campaignflow.generate import generate_raw


def run(db_path: str = "campaignflow.duckdb", rows: int = 5000, seed: int = SEED) -> dict:
    """Run the full ELT: generate -> bronze -> silver -> gold -> quality gate.

    Deterministic for a given seed and idempotent: derived tables are rebuilt
    from raw on every run, so re-running yields the same gold row counts.
    """
    csv_path = generate_raw(rows=rows, seed=seed, out_dir=RAW_DIR)
    con = connect(db_path)
    try:
        bronze_rows = bronze.load_raw(con, csv_path)
        silver_rows = silver.build_silver(con)
        gold_counts = gold.build_gold(con)
        quality.assert_quality(con)
    finally:
        con.close()
    summary = {"bronze": bronze_rows, "silver": silver_rows, "gold": gold_counts}
    print(_format_summary(summary))
    return summary


def _format_summary(summary: dict) -> str:
    g = summary["gold"]
    return (
        "campaignflow run complete:\n"
        f"  bronze.campaign_events_raw     : {summary['bronze']:>7} rows\n"
        f"  silver.campaign_events         : {summary['silver']:>7} rows\n"
        f"  gold.dim_date                  : {g['dim_date']:>7} rows\n"
        f"  gold.dim_channel               : {g['dim_channel']:>7} rows\n"
        f"  gold.dim_campaign              : {g['dim_campaign']:>7} rows\n"
        f"  gold.fact_campaign_performance : {g['fact_campaign_performance']:>7} rows\n"
        "  data-quality checks            : all passed"
    )
