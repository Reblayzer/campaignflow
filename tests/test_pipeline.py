from campaignflow.pipeline import run


def test_run_builds_all_layers_and_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # raw data lands under tmp
    db = str(tmp_path / "cf.duckdb")
    first = run(db_path=db, rows=800, seed=21)
    assert first["bronze"] > 0 and first["silver"] > 0
    assert first["gold"]["fact_campaign_performance"] > 0
    second = run(db_path=db, rows=800, seed=21)
    assert first["gold"] == second["gold"]  # deterministic + idempotent


def test_run_lands_raw_in_blob_and_reads_it_back(azurite_conn, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # raw data lands under tmp
    local = run(db_path=":memory:", rows=300, seed=7)
    blob = run(db_path=":memory:", rows=300, seed=7, use_landing_zone=True)
    # Routing raw through the blob landing zone yields the same warehouse.
    assert blob["bronze"] == local["bronze"]
    assert blob["gold"] == local["gold"]
    assert blob["gold"]["fact_campaign_performance"] > 0
