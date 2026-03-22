"""
CMS Open Payments module.
Server-side Python requests — no CORS restrictions.
Strategy:
  1. SQL name search to resolve numeric company ID
  2. Query all payment records by company ID across multiple dataset years
  3. Aggregate: total by year, by payment type, top KOLs, state breakdown
"""
import requests
from collections import defaultdict

TIMEOUT = 20
BASE = "https://openpaymentsdata.cms.gov/api/1/datastore"

# Dataset IDs by program year — update each June when CMS publishes new year
DATASETS = {
    2024: "5ia3-vtt7",
    2023: "fb3a65aa-c901-4a38-a813-b04b00dfa2a9",
}


def _sql(dataset_id: str, sql: str) -> list:
    """Run a DKAN SQL query against a dataset."""
    try:
        r = requests.get(
            f"{BASE}/sql",
            params={"query": sql, "show_db_columns": "true"},
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        d = r.json()
        return d if isinstance(d, list) else []
    except Exception:
        return []


def _query(dataset_id: str, conditions: list, limit=500) -> list:
    """Run a DKAN conditions query against a dataset."""
    params = {
        "results_format": "objects",
        "keys": "true",
        "limit": limit,
        "offset": 0,
        "sort[0][property]": "total_amount_of_payment_usdollars",
        "sort[0][order]": "desc",
    }
    for i, c in enumerate(conditions):
        params[f"conditions[{i}][property]"] = c["property"]
        params[f"conditions[{i}][value]"]    = c["value"]
        params[f"conditions[{i}][operator]"] = c.get("operator", "=")
    try:
        r = requests.get(
            f"{BASE}/query/{dataset_id}/0",
            params=params,
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        d = r.json()
        rows = d.get("results") or d.get("data") or (d if isinstance(d, list) else [])
        return rows
    except Exception:
        return []


def resolve_company_id(company_name: str) -> tuple[str | None, str]:
    """Return (company_id, resolved_name) or (None, company_name)."""
    escaped = company_name.replace("'", "''")
    for year, ds_id in DATASETS.items():
        sql = (
            f"[SELECT applicable_manufacturer_or_applicable_gpo_making_payment_id,"
            f"applicable_manufacturer_or_applicable_gpo_making_payment_name "
            f"FROM {ds_id}]"
            f"[WHERE applicable_manufacturer_or_applicable_gpo_making_payment_name "
            f"LIKE \"%{escaped}%\"][LIMIT 5]"
        )
        rows = _sql(ds_id, sql)
        if rows:
            row = rows[0]
            cid  = row.get("applicable_manufacturer_or_applicable_gpo_making_payment_id")
            name = row.get("applicable_manufacturer_or_applicable_gpo_making_payment_name", company_name)
            if cid:
                return str(cid), name
    return None, company_name


def _field(row: dict, *keys):
    """Try multiple field name variants, return first non-empty."""
    for k in keys:
        v = row.get(k) or row.get(k.lower()) or row.get(k.title())
        if v:
            return v
    return ""


def fetch_payments(company_name: str) -> dict:
    """
    Fetch and aggregate Open Payments data for a company.
    Returns rich summary: yearly totals, payment type breakdown,
    top 20 KOLs, state distribution.
    """
    company_id, resolved_name = resolve_company_id(company_name)
    if not company_id:
        return {
            "error": f"Company '{company_name}' not found in Open Payments. "
                     "Try the exact legal name as it appears on CMS.",
            "resolved_name": company_name,
            "company_id": None,
        }

    all_rows = []
    for year, ds_id in DATASETS.items():
        rows = _query(
            ds_id,
            [{"property": "applicable_manufacturer_or_applicable_gpo_making_payment_id",
              "value": company_id,
              "operator": "="}],
            limit=500,
        )
        for r in rows:
            r["_program_year"] = year
        all_rows.extend(rows)

    if not all_rows:
        return {
            "error": f"Found company ID {company_id} but no payment records returned.",
            "resolved_name": resolved_name,
            "company_id": company_id,
        }

    # ── Aggregate ──────────────────────────────────────────────────────────────
    total_paid   = 0.0
    by_year      = defaultdict(float)
    by_type      = defaultdict(float)
    by_state     = defaultdict(float)
    physicians   = defaultdict(lambda: {"total": 0.0, "count": 0, "specialty": "", "state": ""})

    for p in all_rows:
        amt = float(_field(p, "total_amount_of_payment_usdollars") or 0)
        total_paid += amt

        year = p.get("_program_year") or _field(p, "program_year") or "Unknown"
        by_year[str(year)] += amt

        ptype = _field(p,
            "nature_of_payment_or_transfer_of_value",
            "Nature_of_Payment_or_Transfer_of_Value") or "Other"
        by_type[ptype] += amt

        state = _field(p, "recipient_state", "Recipient_State") or "Unknown"
        by_state[state] += amt

        first = _field(p, "covered_recipient_first_name", "Covered_Recipient_First_Name",
                       "physician_first_name")
        last  = _field(p, "covered_recipient_last_name",  "Covered_Recipient_Last_Name",
                       "physician_last_name")
        name  = f"{first} {last}".strip()
        if len(name) > 2:
            specialty = _field(p, "covered_recipient_specialty_1",
                               "Covered_Recipient_Specialty_1", "physician_specialty")
            physicians[name]["total"]   += amt
            physicians[name]["count"]   += 1
            if not physicians[name]["specialty"] and specialty:
                physicians[name]["specialty"] = specialty
            if not physicians[name]["state"] and state:
                physicians[name]["state"] = state

    top_kols = sorted(physicians.items(), key=lambda x: x[1]["total"], reverse=True)[:20]

    return {
        "resolved_name": resolved_name,
        "company_id":    company_id,
        "total_paid":    total_paid,
        "record_count":  len(all_rows),
        "by_year":       dict(sorted(by_year.items())),
        "by_type":       dict(sorted(by_type.items(), key=lambda x: x[1], reverse=True)),
        "by_state":      dict(sorted(by_state.items(), key=lambda x: x[1], reverse=True)),
        "top_kols":      top_kols,
        "cms_url":       f"https://openpaymentsdata.cms.gov/company/{company_id}",
    }
