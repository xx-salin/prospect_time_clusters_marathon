# Prospect theory, time clusters and marathon nationality

Tests whether bunching of marathon finishing times just before round numbers
(Allen, Dechow, Pope and Wu 2017, *Management Science*) differs by runner
nationality. The study data has no runner identifiers, so runner country is
scraped from official results archives and linked back to the study rows on
finishing time (to the second), age and gender.

## Layout

```
original_data/            study supplement (data, Stata .do files, paper PDF)
src/                      all Python code (scripts import each other)
scraped_data/
  boston/                 BAA archive (country of residence), 2004-07, 2013
  nyc/                    NYRR API (citizenship and residence), 1999-2013
    <race>_<year>.csv           one file per year, every finisher
    <race>_matched_all_years.csv  study rows with the country attached
    <race>_fractional_*.csv     fractional assignment (row x country, weight)
    scrape_check.csv            per-year completeness check
    scrape_log.txt              scraper log
    pilot/                      pilot scrape and match
    raw_windows/                time-window pieces + manifest.csv (for resuming)
output/
  replication/            excess mass by race region and race country
  boston/                 Boston match report, drops, error, clusters
  nyc/                    NYC match report, drops, error, clusters
reports/                  progress reports
*.ipynb                   exploratory notebooks (read original_data/ directly)
```

`raw_windows/manifest.csv` records each scraped time window: runners the
archive reported and runners collected. It replaces the old one-number
`.count` files. For NYC, `reported` can exceed `collected` because the API
counts runners in a window's boundary second in both halves of a split
window; `scrape_check.csv` confirms each year against NYRR's official total.

## Run order

All scripts run from the repository root, e.g. `python3 src/scrape_nyc.py`.

| Step | Boston | NYC |
|---|---|---|
| Pilot scrape | `scrape_boston_pilot.py` | `scrape_nyc.py pilot` |
| Pilot match | `run_boston_pilot_match.py` | `run_nyc_pilot_match.py` |
| Full scrape (resumes) | `scrape_boston.py [years]` | `scrape_nyc.py [years]` |
| Match to study | `run_boston_match.py` | `run_nyc_match.py` |
| Clusters and match report | `boston_nationality_clusters.py` | `nyc_nationality_clusters.py` |

Shared modules: `country_clusters.py` (excess-mass template; run alone for
the replication tables) and `match_nationality.py` (record linkage).

## Notes

- Two ways to assign a country when several runners share a match key:
  *exact* (only if they all share one country; mixed keys are dropped) and
  *fractional* (each study row is split across the key's countries by their
  shares, held in a `weight` column that every function in
  `country_clusters.py` respects). Exact assignment drops more runners
  where finishers pile up near round numbers, so it understates bunching
  (clearly in NYC); fractional is the default for both races, with exact
  results kept alongside (`*_fractional.csv` vs the plain file names).
- No names, cities or runner IDs are stored.
- Boston lists country of residence only; NYC lists citizenship (`iaaf`)
  and residence.
- NYC 1999-2005 are not matched: NYRR lists only gun times for those
  years, while the study has chip times.
- Chicago, Berlin and London archives list citizenship but their
  robots.txt forbids crawling, so they are not scraped.
