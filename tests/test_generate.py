import csv

from campaignflow.config import CAMPAIGNS
from campaignflow.generate import generate_raw


def test_generate_is_deterministic(tmp_path):
    a = generate_raw(rows=500, seed=1, out_dir=tmp_path / "a")
    b = generate_raw(rows=500, seed=1, out_dir=tmp_path / "b")
    assert a.read_text() == b.read_text()


def test_generate_has_expected_header_and_known_campaigns(tmp_path):
    path = generate_raw(rows=200, seed=7, out_dir=tmp_path)
    with path.open() as fh:
        reader = csv.DictReader(fh)
        assert reader.fieldnames == [
            "event_date", "channel", "campaign_id", "campaign_name",
            "impressions", "clicks", "spend", "conversions", "currency",
        ]
        ids = {row["campaign_id"] for row in reader}
    assert ids <= {c["campaign_id"] for c in CAMPAIGNS}
