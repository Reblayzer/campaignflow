from pathlib import Path

import duckdb

_COLUMNS = [
    "event_date", "channel", "campaign_id", "campaign_name",
    "impressions", "clicks", "spend", "conversions", "currency",
]


def load_raw(con: duckdb.DuckDBPyConnection, csv_path: Path) -> int:
    """Load a raw campaign CSV verbatim (all columns as text) into the bronze layer.

    ELT: no casting or cleaning here. That is silver's job.
    """
    safe_path = str(csv_path).replace("'", "''")
    select_text = ", ".join(f'"{c}"' for c in _COLUMNS)
    con.execute("drop table if exists bronze.campaign_events_raw")
    con.execute(
        f"""
        create table bronze.campaign_events_raw as
        select {select_text}, now() as _ingested_at, '{safe_path}' as _source_file
        from read_csv('{safe_path}', header=true, all_varchar=true)
        """
    )
    return con.execute("select count(*) from bronze.campaign_events_raw").fetchone()[0]
