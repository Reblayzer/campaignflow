import duckdb

from campaignflow.config import SCHEMAS


def connect(path: str = ":memory:") -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(path)
    for schema in SCHEMAS:
        con.execute(f"create schema if not exists {schema}")
    return con
