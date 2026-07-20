"""Pull recent posts from seed accounts via Apify, keep only true outliers.

Outlier = post at OUTLIER_MIN x its own account's median metric,
posted within MAX_AGE_DAYS. Ranking is overperformance, never raw views.
"""

import json
import os
import statistics
from datetime import datetime, timezone
from pathlib import Path

from apify_client import ApifyClient

ROOT = Path(__file__).resolve().parent.parent
POSTS_PER_ACCOUNT = 12
OUTLIER_MIN = 3.0
MAX_AGE_DAYS = 14


def post_metric(item):
    """Best available engagement metric for a post."""
    for key in ("videoPlayCount", "videoViewCount"):
        v = item.get(key)
        if v:
            return int(v), "views"
    return int(item.get("likesCount") or 0), "likes"


def main():
    token = os.environ["APIFY_TOKEN"]
    cfg = json.loads((ROOT / "scripts" / "instagram_accounts.json").read_text())
    accounts = [a for a in cfg["accounts"] if not a["handle"].startswith("example_")]
    if not accounts:
        raise SystemExit("instagram_accounts.json still has only example entries. Fill the seed list first.")

    niche_by_handle = {a["handle"].lower(): a["niche"] for a in accounts}
    client = ApifyClient(token)
    run = client.actor("apify/instagram-scraper").call(
        run_input={
            "directUrls": [f"https://www.instagram.com/{a['handle']}/" for a in accounts],
            "resultsType": "posts",
            "resultsLimit": POSTS_PER_ACCOUNT,
        }
    )

    by_account = {}
    for item in client.dataset(run["defaultDatasetId"]).iterate_items():
        handle = (item.get("ownerUsername") or "").lower()
        if handle in niche_by_handle:
            by_account.setdefault(handle, []).append(item)

    now = datetime.now(timezone.utc)
    outliers = []
    for handle, items in by_account.items():
        metrics = [post_metric(i)[0] for i in items]
        metrics = [m for m in metrics if m > 0]
        if len(metrics) < 5:
            continue  # not enough posts for a trustworthy baseline
        baseline = statistics.median(metrics)
        if baseline <= 0:
            continue
        for item in items:
            value, metric_type = post_metric(item)
            ts = item.get("timestamp")
            if not ts or value <= 0:
                continue
            posted = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            age_days = max((now - posted).total_seconds() / 86400, 0.25)
            ratio = value / baseline
            if ratio >= OUTLIER_MIN and age_days <= MAX_AGE_DAYS:
                outliers.append({
                    "handle": handle,
                    "niche": niche_by_handle[handle],
                    "url": item.get("url"),
                    "caption": (item.get("caption") or "")[:500],
                    "metric": value,
                    "metric_type": metric_type,
                    "baseline": round(baseline),
                    "outlier": round(ratio, 2),
                    "age_days": round(age_days, 1),
                    "velocity_per_day": round(value / age_days),
                    "posted": ts,
                })

    outliers.sort(key=lambda o: o["outlier"], reverse=True)
    out_dir = ROOT / "signals" / "raw"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{now:%Y-%m-%d}.json"
    out_path.write_text(json.dumps({"scraped_at": now.isoformat(), "outliers": outliers}, indent=2))
    print(f"{len(outliers)} outliers from {len(by_account)} accounts -> {out_path}")


if __name__ == "__main__":
    main()
