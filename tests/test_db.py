from campaignflow.db import connect


def test_connect_creates_layer_schemas():
    con = connect(":memory:")
    schemas = {r[0] for r in con.execute("select schema_name from information_schema.schemata").fetchall()}
    assert {"bronze", "silver", "gold"} <= schemas
