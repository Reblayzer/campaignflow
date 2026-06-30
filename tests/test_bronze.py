from campaignflow.bronze import load_raw
from campaignflow.db import connect
from campaignflow.generate import generate_raw


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
