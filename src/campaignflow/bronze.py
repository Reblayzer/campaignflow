from pathlib import Path

import duckdb

_COLUMNS = [
    "event_date", "channel", "campaign_id", "campaign_name",
    "impressions", "clicks", "spend", "conversions", "currency",
]


def _configure_azure(con: duckdb.DuckDBPyConnection, connection_string: str) -> None:
    """Enable DuckDB's azure extension and register the blob connection secret."""
    con.execute("install azure")
    con.execute("load azure")
    safe_conn = connection_string.replace("'", "''")
    con.execute(
        f"create or replace secret campaignflow_az (type azure, connection_string '{safe_conn}')"
    )


def load_raw(
    con: duckdb.DuckDBPyConnection,
    source: Path | str,
    connection_string: str | None = None,
) -> int:
    """Load a raw campaign CSV verbatim (all columns as text) into the bronze layer.

    ``source`` is either a local path or an ``az://container/blob`` URL; blob
    reads need ``connection_string``. ELT: no casting or cleaning here. That is
    silver's job.
    """
    source = str(source)
    if source.startswith("az://"):
        if not connection_string:
            raise ValueError("connection_string is required to read an az:// source")
        _configure_azure(con, connection_string)
    safe_path = source.replace("'", "''")
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
