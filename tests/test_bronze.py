from campaignflow.bronze import load_raw
from campaignflow.db import connect
from campaignflow.generate import generate_raw
from campaignflow.landing import LandingZone


def test_load_raw_loads_every_row_as_text(tmp_path):
    con = connect(":memory:")
    csv_path = generate_raw(rows=100, seed=3, out_dir=tmp_path)
    n = load_raw(con, csv_path)
    assert n > 0
    data_type = con.execute(
        "select data_type from information_schema.columns "
        "where table_schema='bronze' and table_name='campaign_events_raw' and column_name='impressions'"
    ).fetchone()[0]
    assert data_type.upper() in ("VARCHAR", "TEXT")
    assert con.execute("select count(*) from bronze.campaign_events_raw").fetchone()[0] == n


def test_load_raw_reads_from_azurite_blob(azurite_conn, tmp_path):
    csv_path = generate_raw(rows=50, seed=5, out_dir=tmp_path)
    expected = load_raw(connect(":memory:"), csv_path)  # disk baseline

    lz = LandingZone(connection_string=azurite_conn, container="test-bronze")
    lz.ensure_container()
    blob_url = lz.upload(csv_path)
    con = connect(":memory:")
    n = load_raw(con, blob_url, connection_string=azurite_conn)

    assert n == expected and n > 0  # blob load matches disk load
    assert con.execute("select count(*) from bronze.campaign_events_raw").fetchone()[0] == n
