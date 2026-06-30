import pytest


@pytest.fixture(scope="session")
def spark():
    """A local single-worker SparkSession, reused across the test session.

    Spark startup is slow (a JVM per session), so the fixture is session-scoped.
    Determinism: one shuffle partition, fixed local time zone for date keys.
    """
    pyspark = pytest.importorskip("pyspark")
    from pyspark.sql import SparkSession

    session = (
        SparkSession.builder.master("local[1]")
        .appName("campaignflow-tests")
        .config("spark.ui.enabled", "false")
        .config("spark.sql.shuffle.partitions", "1")
        .config("spark.sql.session.timeZone", "UTC")
        .getOrCreate()
    )
    assert pyspark.__version__  # touch the import so linters keep it
    yield session
    session.stop()
