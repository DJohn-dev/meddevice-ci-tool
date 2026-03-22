"""SEC EDGAR and federal spending modules."""
import requests
from collections import defaultdict

TIMEOUT = 12


# ── SEC EDGAR ──────────────────────────────────────────────────────────────────

def fetch_sec(cik: str) -> dict:
    """Fetch recent SEC filings for a company by CIK."""
    cik_clean = str(cik).strip().lstrip("0")
    cik_padded = cik_clean.zfill(10)
    try:
        r = requests.get(
            f"https://data.sec.gov/submissions/CIK{cik_padded}.json",
            headers={"User-Agent": "MedDevice CI Tool analyst@example.com"},
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        d = r.json()
    except Exception as e:
        return {"error": str(e)}

    entity_name = d.get("name", "Unknown")
    recent = d.get("filings", {}).get("recent", {})

    forms       = recent.get("form", [])
    dates       = recent.get("filingDate", [])
    accessions  = recent.get("accessionNumber", [])
    descriptions= recent.get("primaryDocument", [])
    periods     = recent.get("reportDate", [])

    items = []
    priority = {"10-K", "10-Q", "8-K", "DEF 14A", "4", "S-1", "424B4"}
    for i, form in enumerate(forms):
        if form in priority:
            acc = accessions[i].replace("-", "") if i < len(accessions) else ""
            items.append({
                "form":   form,
                "date":   dates[i] if i < len(dates) else "—",
                "period": periods[i] if i < len(periods) else "—",
                "url":    f"https://www.sec.gov/Archives/edgar/data/{cik_clean}/{acc}/{descriptions[i]}"
                          if acc and i < len(descriptions) else
                          f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik_clean}&type={form}&owner=include&count=5",
            })
        if len(items) >= 20:
            break

    links = {
        "All Filings":   f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik_clean}&type=&owner=include&count=40",
        "10-K Annual":   f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik_clean}&type=10-K&owner=include&count=5",
        "10-Q Quarterly":f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik_clean}&type=10-Q&owner=include&count=5",
        "8-K Current":   f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik_clean}&type=8-K&owner=include&count=10",
        "DEF 14A Proxy": f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik_clean}&type=DEF+14A&owner=include&count=5",
        "Form 4 Insider":f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik_clean}&type=4&owner=include&count=20",
    }
    return {
        "entity_name": entity_name,
        "cik":         cik_clean,
        "items":       items,
        "links":       links,
    }


# ── USASpending + NIH (private companies) ─────────────────────────────────────

def fetch_spending(company_name: str) -> dict:
    """Federal contracts and grants from USASpending.gov."""
    try:
        r = requests.post(
            "https://api.usaspending.gov/api/v2/search/spending_by_award/",
            json={
                "filters": {
                    "recipient_search_text": [company_name],
                    "award_type_codes": ["A", "B", "C", "D"],
                    "time_period": [{"start_date": "2019-01-01", "end_date": "2024-12-31"}],
                },
                "fields": ["Award ID", "Recipient Name", "Award Amount",
                           "Awarding Agency", "Award Type", "Description",
                           "Start Date", "End Date"],
                "sort": "Award Amount",
                "order": "desc",
                "limit": 25,
                "page": 1,
            },
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        contracts = r.json().get("results", [])
    except Exception as e:
        contracts = []

    try:
        rg = requests.post(
            "https://api.usaspending.gov/api/v2/search/spending_by_award/",
            json={
                "filters": {
                    "recipient_search_text": [company_name],
                    "award_type_codes": ["02", "03", "04", "05"],
                    "time_period": [{"start_date": "2019-01-01", "end_date": "2024-12-31"}],
                },
                "fields": ["Award ID", "Recipient Name", "Award Amount",
                           "Awarding Agency", "Award Type", "Description",
                           "Start Date", "End Date"],
                "sort": "Award Amount",
                "order": "desc",
                "limit": 25,
                "page": 1,
            },
            timeout=TIMEOUT,
        )
        rg.raise_for_status()
        grants = rg.json().get("results", [])
    except Exception:
        grants = []

    contract_total = sum(float(c.get("Award Amount") or 0) for c in contracts)
    grant_total    = sum(float(g.get("Award Amount") or 0) for g in grants)

    return {
        "contracts":       contracts,
        "grants":          grants,
        "contract_total":  contract_total,
        "grant_total":     grant_total,
    }


def fetch_nih(company_name: str) -> dict:
    """NIH RePORTER grants."""
    try:
        r = requests.post(
            "https://api.reporter.nih.gov/v2/projects/search",
            json={
                "criteria": {
                    "org_names": [company_name],
                    "fiscal_years": [2020, 2021, 2022, 2023, 2024],
                },
                "offset": 0,
                "limit": 25,
                "sort_field": "award_amount",
                "sort_order": "desc",
            },
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        d = r.json()
        items = d.get("results", [])
        total = sum(float(i.get("award_amount") or 0) for i in items)
        return {"items": items, "total": total}
    except Exception as e:
        return {"items": [], "total": 0, "error": str(e)}
