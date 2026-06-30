from campaignflow.landing import LandingZone


def _containers(conn):
    from azure.storage.blob import BlobServiceClient

    svc = BlobServiceClient.from_connection_string(conn)
    return [c["name"] for c in svc.list_containers()]


def test_ensure_container_is_idempotent(azurite_conn):
    lz = LandingZone(connection_string=azurite_conn, container="test-ensure")
    lz.ensure_container()
    lz.ensure_container()  # second call must not raise
    assert "test-ensure" in _containers(azurite_conn)


def test_upload_returns_az_url_and_lands_blob(azurite_conn, tmp_path):
    csv = tmp_path / "raw.csv"
    csv.write_text("a,b\n1,2\n")
    lz = LandingZone(connection_string=azurite_conn, container="test-upload")
    lz.ensure_container()

    url = lz.upload(csv)

    assert url == "az://test-upload/raw.csv"
    from azure.storage.blob import BlobServiceClient

    svc = BlobServiceClient.from_connection_string(azurite_conn)
    landed = svc.get_blob_client("test-upload", "raw.csv").download_blob().readall().decode()
    assert landed == "a,b\n1,2\n"
