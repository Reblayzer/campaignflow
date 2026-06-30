import csv
import random
from datetime import date, timedelta
from pathlib import Path

from campaignflow.config import CAMPAIGNS

_HEADER = [
    "event_date", "channel", "campaign_id", "campaign_name",
    "impressions", "clicks", "spend", "conversions", "currency",
]
_CURRENCIES = ["DKK", "DKK", "DKK", "EUR", "SEK"]  # weighted toward DKK
_START = date(2026, 1, 1)
_DAYS = 120


def generate_raw(rows: int, seed: int, out_dir: Path) -> Path:
    rng = random.Random(seed)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "campaign_events.csv"
    records = [_make_row(rng) for _ in range(rows)]
    # inject a few exact duplicates so silver dedup has real work to do
    for _ in range(max(1, rows // 100)):
        records.append(dict(rng.choice(records)))
    with out_path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=_HEADER)
        writer.writeheader()
        writer.writerows(records)
    return out_path


def _make_row(rng: random.Random) -> dict[str, str]:
    campaign = rng.choice(CAMPAIGNS)
    day = _START + timedelta(days=rng.randint(0, _DAYS - 1))
    impressions = rng.randint(500, 50_000)
    clicks = int(impressions * rng.uniform(0.005, 0.06))
    conversions = int(clicks * rng.uniform(0.01, 0.12))
    spend = round(clicks * rng.uniform(1.5, 9.0), 2)
    # stray whitespace and casing on channel to give silver real cleaning to do
    channel_variants = [campaign["channel"], f" {campaign['channel']} ", campaign["channel"].upper()]
    return {
        "event_date": day.isoformat(),
        "channel": rng.choice(channel_variants),
        "campaign_id": campaign["campaign_id"],
        "campaign_name": campaign["name"],
        "impressions": str(impressions),
        "clicks": str(clicks),
        "spend": str(spend),
        "conversions": str(conversions),
        "currency": rng.choice(_CURRENCIES),
    }
