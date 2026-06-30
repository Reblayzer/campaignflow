import os

import pytest


@pytest.fixture(scope="session")
def azurite_conn():
    """Connection string for a reachable Azurite blob endpoint, else skip.

    Keeps the suite green on machines without the emulator running; CI starts
    Azurite as a service container so these tests execute for real.
    """
    pytest.importorskip("azure.storage.blob")
    from azure.storage.blob import BlobServiceClient

    from campaignflow.config import AZURITE_CONNECTION_STRING

    conn = os.environ.get("AZURE_STORAGE_CONNECTION_STRING", AZURITE_CONNECTION_STRING)
    try:
        # Fail fast (no retries) so the skip is instant when Azurite is absent.
        client = BlobServiceClient.from_connection_string(conn, retry_total=0, connection_timeout=2)
        list(client.list_containers(results_per_page=1, timeout=2))
    except Exception:
        pytest.skip("Azurite blob endpoint not reachable")
    return conn


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
