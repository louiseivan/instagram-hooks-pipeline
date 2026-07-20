# Signals output

Written by the pipeline, never by hand.

- `raw/YYYY-MM-DD.json` : every outlier that survived the scrape filters, unclassified
- `classified/YYYY-MM-DD.json` : same posts with framework, niche, and voice tags
- `latest.md` : this run's outliers as a readable table
- `trends.md` : 8-week framework rollup with CANDIDATE flags

After each run, copy `latest.md` and `trends.md` into `creating-hooks-skill/signals/` and push. The skill reads them from there.
