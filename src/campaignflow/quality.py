from dataclasses import dataclass

import duckdb


@dataclass(frozen=True)
class CheckResult:
    name: str
    passed: bool
    detail: str


class DataQualityError(Exception):
    pass


def _count(con: duckdb.DuckDBPyConnection, sql: str) -> int:
    return con.execute(sql).fetchone()[0]


def run_checks(con: duckdb.DuckDBPyConnection) -> list[CheckResult]:
    checks: list[CheckResult] = []

    def add(name: str, bad: int) -> None:
        checks.append(CheckResult(name, bad == 0, f"{bad} offending row(s)"))

    add("silver_not_empty", 0 if _count(con, "select count(*) from silver.campaign_events") > 0 else 1)
    add("fact_not_empty", 0 if _count(con, "select count(*) from gold.fact_campaign_performance") > 0 else 1)
    add("dim_date_key_unique", _count(con, "select count(*) - count(distinct date_key) from gold.dim_date"))
    add("dim_channel_key_unique", _count(con, "select count(*) - count(distinct channel_key) from gold.dim_channel"))
    add("dim_campaign_key_unique", _count(con, "select count(*) - count(distinct campaign_key) from gold.dim_campaign"))
    add(
        "fact_grain_unique",
        _count(
            con,
            "select count(*) from (select 1 from gold.fact_campaign_performance "
            "group by date_key, channel_key, campaign_key having count(*) > 1)",
        ),
    )
    add(
        "fact_measures_non_negative",
        _count(
            con,
            "select count(*) from gold.fact_campaign_performance "
            "where impressions < 0 or clicks < 0 or spend_dkk < 0 or conversions < 0",
        ),
    )
    add(
        "fact_refs_resolve",
        _count(
            con,
            """
            select count(*) from gold.fact_campaign_performance f
            left join gold.dim_date d on f.date_key = d.date_key
            left join gold.dim_channel c on f.channel_key = c.channel_key
            left join gold.dim_campaign p on f.campaign_key = p.campaign_key
            where d.date_key is null or c.channel_key is null or p.campaign_key is null
            """,
        ),
    )
    return checks


def assert_quality(con: duckdb.DuckDBPyConnection) -> None:
    failures = [c for c in run_checks(con) if not c.passed]
    if failures:
        lines = "\n".join(f"  - {c.name}: {c.detail}" for c in failures)
        raise DataQualityError(f"{len(failures)} data-quality check(s) failed:\n{lines}")
