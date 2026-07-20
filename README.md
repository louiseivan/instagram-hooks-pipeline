# Instagram Hooks Pipeline by Louise

Outlier scrape and classification pipeline that feeds the [instagram creating-hooks skill](https://github.com/louiseivan/creating-hooks-skill). Runs on manual trigger only.

## What it does

1. `scripts/instagram_scrape.py` pulls the last 12 posts from every account in `scripts/instagram_accounts.json` via the Apify `instagram-scraper` actor, computes each account's own median baseline, and keeps only posts at 3x+ their account's baseline, 14 days old or fresher. Output: `signals/raw/YYYY-MM-DD.json`.
2. `scripts/instagram_classify.py` classifies each surviving outlier against the fixed taxonomy in `scripts/instagram_taxonomy.json` (framework + niche + voice compatibility), writes `signals/latest.md`, and rebuilds `signals/trends.md` from the last 8 weeks of classified archives, flagging candidate patterns that hit on 3+ distinct accounts.

Outlier ranking is by overperformance vs the account's own median, never raw views. A 50K-follower account pulling 2M views is a hook signal. A 5M-follower account pulling 2M views is noise.

## Setup

1. Fill `scripts/instagram_accounts.json` with 30 to 50 seed accounts in your niches. This list decides the quality of everything downstream. Prune it quarterly.
2. Copy the 14 framework names from the skill's `frameworks.md` and the banned phrases from `voice.md` into `scripts/instagram_taxonomy.json`.
3. Add two repo secrets under Settings > Secrets and variables > Actions: `APIFY_TOKEN` and `ANTHROPIC_API_KEY`. Never commit tokens into the files.

## Running it

Actions tab > instagram-refresh-signals > Run workflow. Or from the terminal:

```bash
gh workflow run instagram-refresh-signals
```

Local run:

```bash
pip install -r requirements.txt
APIFY_TOKEN=... python scripts/instagram_scrape.py
ANTHROPIC_API_KEY=... python scripts/instagram_classify.py
```

## Syncing into the skill

After a run, copy the fresh output into the skill repo:

```bash
cp signals/latest.md signals/trends.md ../creating-hooks-skill/signals/
cd ../creating-hooks-skill && git add signals/ && git commit -m "signals refresh" && git push
```

Manual by design. If this gets old, switch to a cross-repo push with a fine-grained PAT scoped to creating-hooks-skill, stored as a third secret.

## Promotion rules

The pipeline writes signals. It never writes into the skill's `examples/` bank. A pattern earns bank entry only after it beats Louise's own baseline in published results. Curation stays human.
