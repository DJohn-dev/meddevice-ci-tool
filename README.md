# Medical Device Competitive Intelligence Search Tool

A Streamlit app for medical device market intelligence. Pulls live data from six public APIs entirely server-side — no browser CORS restrictions, no API keys required.

**Live app:** [meddevice-ci-tool-j4rrqunw2xuigljvattzwi.streamlit.app](https://meddevice-ci-tool-j4rrqunw2xuigljvattzwi.streamlit.app)

---

## Data Sources

| Section | Source | What It Returns |
|---|---|---|
| 🏢 FDA Company Identity | OpenFDA Registration & Listing | FEI numbers, establishment locations, product codes |
| 🔵 FDA Regulatory History | OpenFDA 510(k) & PMA | Clearance/approval history with direct links |
| 🔴 Safety Profile | OpenFDA MAUDE | Adverse event reports, event types, device names |
| 🟠 Recall History | OpenFDA Recalls | Recall class, product, reason, status |
| 🟢 Pipeline Intelligence | ClinicalTrials.gov v2 | Active studies, phases, enrollment, status breakdown |
| 🩺 KOL & Commercial Intelligence | CMS Open Payments (CSV) | Total payments by year and type (2022–2024) |
| 🟣 Financial & Corporate | SEC EDGAR | Filing links (10-K, 10-Q, 8-K, DEF 14A, Form 4) |
| 💰 Financial Intelligence | USASpending.gov + NIH RePORTER | Federal contracts, grants, NIH awards (private companies) |

---

## Features

- **Single company profile** — runs all enabled sections in one click
- **Public / Private toggle** — public companies get SEC EDGAR; private companies get USASpending + NIH
- **Analyst notes** — freetext note box on each section for your own observations
- **1-hour data cache** — repeat queries don't hit the APIs again
- **Direct links** — 510(k), PMA, and SEC filings all link to the original source documents
- **CIK lookup** — "Find CIK on EDGAR" link pre-fills your company name in the EDGAR search

---

## Open Payments Notes

CMS blocks direct browser-based API calls (CORS). This tool works around that by running all calls server-side in Python. However, the CMS DKAN query API does not enforce filters reliably on large datasets, so the tool downloads pre-built summary CSV files from `download.cms.gov` and filters locally. This returns:

- Total payments by program year (2022, 2023, 2024)
- Breakdown by payment type (consulting, food & beverage, travel, education, etc.)

Individual KOL-level records (physician names, specialties, states) require bulk data download and are not included. Use the CMS company profile link in the section to view those.

---

## Project Structure

```
meddevice-ci-tool/
├── app.py              ← Streamlit UI, all section renderers, main()
├── data_modules.py     ← All API calls (FDA, ClinicalTrials, Open Payments, SEC, USASpending, NIH)
├── requirements.txt
└── README.md
```

---

## Run Locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

---

## Deploy to Streamlit Cloud

1. Fork or clone this repo to your GitHub account
2. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with GitHub
3. Click **New app** → select your repo → Branch: `main` → Main file: `app.py`
4. Click **Deploy**

Streamlit Cloud installs `requirements.txt` automatically. Auto-deploys on every push to `main`.

---

## Known Limitations

| Area | Limitation |
|---|---|
| OpenFDA name matching | FDA stores company names in ALL CAPS with inconsistent punctuation. The tool tries multiple name variants but may miss some records. Search manually via the fallback links if needed. |
| Open Payments | Only summary totals (by year and payment type) — not individual physician records. DKAN filter API does not enforce filters on the 14M-row detail dataset. |
| SEC EDGAR | Requires manual CIK entry. Use the pre-filled EDGAR search link to look it up. |
| Data freshness | All data cached 1 hour per query. Reboot the app (Manage app → Reboot) to clear cache. |
| OpenFDA rate limits | 1,000 requests/day without an API key. For heavy use, add a free key at [open.fda.gov/apis/authentication](https://open.fda.gov/apis/authentication/). |

---


