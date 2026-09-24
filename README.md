# Macro Tape

A phone-friendly macro dashboard built in the spirit of Stan Druckenmiller's daily scan.
Druckenmiller has said he looks at roughly 200 charts a day but has never published the list.
This project rebuilds a comparable universe (about 245 series) from what he has said he watches:

- **Liquidity & the Fed**: balance sheet, TGA, reverse repo, net liquidity, reserves, financial conditions
- **Rates**: the curve, real yields, breakevens, mortgage rates, bond volatility (MOVE)
- **Credit & stress**: HY/IG/CCC spreads, junk vs Treasuries, VIX term structure
- **Dollar & FX**: DXY, yen, yuan, EM currencies, AUD/JPY
- **Commodities**: oil, copper, gold, grains, uranium; copper/gold and gold/silver ratios
- **Economy**: claims, payrolls, CPI/PCE, housing, sentiment
- **Equity leadership**: sectors and ~35 industries vs the S&P, breadth, factors, 30+ foreign markets
- **Bellwether stocks**: how the tape treats NVDA, TSM, JPM, CAT, FDX, HD, WMT and others

Every series gets a 1-day to 1-year change, a 200-day trend state, its 1-month move in standard
deviations, and an **acceleration** score (the change in its rate of change). Each series also has a
polarity: rising yields, oil or credit spreads count as bad for risk, while rising copper/gold or
breadth count as good. That turns "accelerating" into a good or bad call.

## Layout

The page opens with:
1. **The read**: headline and summary (written in `site/notes.json`)
2. **Trade ideas**: long, short and pair trades, each with a trigger, a stop condition and linked live charts
3. **Good vs bad** for risk assets
4. **What's turning**: on the come / rolling over / accelerating, generated from the data every day
5. **The charts**: all ~245, filterable by group and sortable by move, acceleration or relative strength

## How it updates

- `pipeline/universe.py` defines the chart list
- `pipeline/fetch.py` pulls Yahoo Finance + FRED (no API keys), computes signals, and writes `site/data.json`
- `.github/workflows/update.yml` runs it every weekday after the close and every morning, commits the data, and deploys to GitHub Pages
- `site/notes.json` holds the written read and trade ideas. Edit it by hand, or ask Claude to refresh it.

## Getting the public URL (GitHub Pages)

1. Create a new **public** GitHub repo (for example `macro-tape`) and push this project to its `main` branch.
2. In the repo, go to **Settings → Pages → Build and deployment → Source** and pick **GitHub Actions**.
3. In `.github/workflows/update.yml`, change the `push: branches:` entry to `main`.
4. Run the workflow once from **Actions → Update dashboard data → Run workflow**.
5. The site is live at `https://<your-user>.github.io/macro-tape/`. On a phone, use **Add to Home Screen**.

## Local preview

```bash
pip install -r pipeline/requirements.txt
python pipeline/fetch.py          # needs internet access to Yahoo + FRED
python pipeline/build_site.py     # writes _site/
cd _site && python -m http.server
```

For idea generation only. This is not investment advice.
