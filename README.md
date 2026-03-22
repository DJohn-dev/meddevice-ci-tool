# Medical Device Competitive Intelligence Tool

A Streamlit-based CI tool for medical device market intelligence. Pulls live data from six public APIs server-side — no CORS restrictions, no API keys required.

## Data Sources

| Source | Data |
|---|---|
| OpenFDA | FDA Registration/FEI, 510(k) clearances, PMA approvals, MAUDE adverse events, Recalls |
| ClinicalTrials.gov v2 | Clinical pipeline, study status, enrollment |
| CMS Open Payments | KOL payments by year, type, state, physician (requires server-side — CORS blocked in browsers) |
| SEC EDGAR | Annual/quarterly filings, insider activity (public companies) |
| USASpending.gov | Federal contracts and grants (private companies) |
| NIH RePORTER | Research grants (private companies) |

## Features

- **Single company** full profile across all six sources
- **Side-by-side comparison** of two companies
- Open Payments: trend chart, payment type breakdown, US state heatmap, top 20 KOL table
- Analyst notes boxes on each section
- 1-hour data caching (no redundant API calls)
- Public/private company toggle (swaps SEC for federal spending)

## Deploy to Streamlit Cloud (Free)

### Step 1 — Push to GitHub

```bash
git init
git add .
git commit -m "Initial commit — MedDevice CI Tool"
git remote add origin https://github.com/YOUR_USERNAME/meddevice-ci-tool.git
git push -u origin main
```

### Step 2 — Deploy on Streamlit Cloud

1. Go to [share.streamlit.io](https://share.streamlit.io)
2. Sign in with GitHub
3. Click **New app**
4. Select your repo → Branch: `main` → Main file: `app.py`
5. Click **Deploy**

That's it. Streamlit Cloud installs `requirements.txt` automatically. Your app will be live at `https://YOUR_USERNAME-meddevice-ci-tool-app-XXXX.streamlit.app`.

### Step 3 — Updating

```bash
git add .
git commit -m "Update"
git push
```
Streamlit Cloud auto-deploys on every push.

## Run Locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Project Structure

```
meddevice-ci-tool/
├── app.py                  ← Main Streamlit app
├── requirements.txt
├── README.md
└── modules/
    ├── fda.py              ← FDA Registration, 510(k), MAUDE, Recalls
    ├── trials.py           ← ClinicalTrials.gov
    ├── payments.py         ← CMS Open Payments
    └── sec_spending.py     ← SEC EDGAR + USASpending + NIH
```

## Notes

- **Open Payments**: CMS blocks browser-based API calls (CORS). This tool calls the API server-side via Python `requests`, which has no such restriction. This is why Open Payments works here but not in the standalone HTML version.
- **Data freshness**: All data is cached for 1 hour per query. Restart the app to clear cache.
- **Rate limits**: OpenFDA has a 1,000 requests/day limit without an API key. For heavy use, add a free API key to `modules/fda.py`.

## GitHub Portfolio Notes

This project demonstrates:
- Server-side API orchestration (6 public health data APIs)
- Python data aggregation and transformation
- Streamlit UI with Plotly visualizations
- Real-world medical device market intelligence workflow
