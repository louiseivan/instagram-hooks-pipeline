"""Classify scraped outliers against the fixed taxonomy, write latest.md,
rebuild trends.md from the last 8 weeks of classified archives.
"""

import json
import os
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import anthropic

ROOT = Path(__file__).resolve().parent.parent
WINDOW_DAYS = 56  # 8 weeks
CANDIDATE_MIN_ACCOUNTS = 3
MODEL = "claude-sonnet-4-6"


def latest_raw():
    files = sorted((ROOT / "signals" / "raw").glob("*.json"))
    if not files:
        raise SystemExit("No raw scrape files. Run instagram_scrape.py first.")
    return files[-1]


def classify(outliers, taxonomy):
    client = anthropic.Anthropic()
    items = [{"i": i, "handle": o["handle"], "caption": o["caption"]} for i, o in enumerate(outliers)]
    prompt = (
        "Classify each Instagram post below. For each, pick exactly one framework from "
        f"{taxonomy['frameworks']} (or null if none fits) and exactly one niche from "
        f"{taxonomy['niches']}. Set voice_compatible to false if the hook relies on any of "
        f"these banned phrases or their close variants: {taxonomy['banned_phrases']}. "
        "Set fits_framework to false when framework is null and describe the structure in "
        "new_pattern (short label) instead. Respond with ONLY a JSON array, one object per "
        "post: {\"i\": int, \"framework\": str|null, \"niche\": str, \"fits_framework\": bool, "
        "\"voice_compatible\": bool, \"new_pattern\": str|null}. No preamble, no markdown.\n\n"
        + json.dumps(items)
    )
    resp = client.messages.create(model=MODEL, max_tokens=4000,
                                  messages=[{"role": "user", "content": prompt}])
    text = resp.content[0].text.replace("```json", "").replace("```", "").strip()
    tags = {t["i"]: t for t in json.loads(text)}
    for i, o in enumerate(outliers):
        o.update({k: tags.get(i, {}).get(k) for k in
                  ("framework", "niche", "fits_framework", "voice_compatible", "new_pattern")})
    return outliers


def write_latest(outliers, date_str):
    lines = [f"# Instagram signals: {date_str}", "",
             "| outlier | handle | framework | niche | voice ok | hook (caption start) | url |",
             "|---|---|---|---|---|---|---|"]
    for o in outliers:
        hook = (o["caption"] or "").split("\n")[0][:90].replace("|", "/")
        lines.append(f"| {o['outlier']}x | @{o['handle']} | {o['framework'] or o['new_pattern'] or '?'} "
                     f"| {o['niche']} | {'yes' if o['voice_compatible'] else 'NO'} | {hook} | {o['url']} |")
    (ROOT / "signals" / "latest.md").write_text("\n".join(lines) + "\n")


def write_trends():
    cutoff = datetime.now(timezone.utc) - timedelta(days=WINDOW_DAYS)
    fw_hits, fw_accounts = defaultdict(int), defaultdict(set)
    for f in sorted((ROOT / "signals" / "classified").glob("*.json")):
        data = json.loads(f.read_text())
        if datetime.fromisoformat(data["scraped_at"]) < cutoff:
            continue
        for o in data["outliers"]:
            key = o.get("framework") or o.get("new_pattern")
            if key:
                fw_hits[key] += 1
                fw_accounts[key].add(o["handle"])
    ranked = sorted(fw_hits, key=fw_hits.get, reverse=True)
    lines = ["# Instagram framework trends (8-week window)", "",
             "| framework / pattern | outlier hits | distinct accounts | status |", "|---|---|---|---|"]
    for k in ranked:
        n_acc = len(fw_accounts[k])
        status = "CANDIDATE" if n_acc >= CANDIDATE_MIN_ACCOUNTS else "signal"
        lines.append(f"| {k} | {fw_hits[k]} | {n_acc} | {status} |")
    lines += ["", "CANDIDATE = hit outlier status on "
              f"{CANDIDATE_MIN_ACCOUNTS}+ distinct accounts in the window. "
              "Unproven until it beats Louise's own baseline. Gaps between manual runs are gaps, not zero activity."]
    (ROOT / "signals" / "trends.md").write_text("\n".join(lines) + "\n")


def main():
    taxonomy = json.loads((ROOT / "scripts" / "instagram_taxonomy.json").read_text())
    raw_path = latest_raw()
    data = json.loads(raw_path.read_text())
    data["outliers"] = classify(data["outliers"], taxonomy)
    out_dir = ROOT / "signals" / "classified"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / raw_path.name).write_text(json.dumps(data, indent=2))
    write_latest(data["outliers"], raw_path.stem)
    write_trends()
    print(f"Classified {len(data['outliers'])} outliers -> signals/latest.md, signals/trends.md")


if __name__ == "__main__":
    main()
