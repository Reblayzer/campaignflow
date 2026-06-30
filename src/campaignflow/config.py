from pathlib import Path

SEED = 42
RAW_DIR = Path("data/raw")
SCHEMAS = ("bronze", "silver", "gold")
FX_TO_DKK = {"DKK": 1.0, "EUR": 7.46, "SEK": 0.64}

CHANNELS = [
    {"name": "Paid Search", "group": "Paid"},
    {"name": "Paid Social", "group": "Paid"},
    {"name": "Display", "group": "Paid"},
    {"name": "Email", "group": "Owned"},
    {"name": "Organic Social", "group": "Earned"},
    {"name": "Affiliate", "group": "Paid"},
]

# Each campaign runs on exactly one channel in this dataset.
_CAMPAIGN_SEED = [
    ("Spring Skyr Launch", "Paid Search"),
    ("Protein Pudding Awareness", "Paid Social"),
    ("Organic Milk Always-On", "Paid Search"),
    ("Cheese Lovers Retargeting", "Display"),
    ("Barista Edition Teaser", "Paid Social"),
    ("Recipe Newsletter", "Email"),
    ("Summer Smoothie UGC", "Organic Social"),
    ("Lactose-Free Affiliate Push", "Affiliate"),
    ("Kids Yogurt Back-to-School", "Display"),
    ("Sustainability Story", "Organic Social"),
]

CAMPAIGNS = [
    {"campaign_id": f"CMP-{1000 + i}", "name": name, "channel": channel}
    for i, (name, channel) in enumerate(_CAMPAIGN_SEED)
]
