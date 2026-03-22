"""
FDA data module — Registration/FEI, 510(k), MAUDE, Recalls
All calls are server-side via requests (no CORS issues).
"""
import requests, urllib.parse

TIMEOUT = 12
BASE = "https://api.fda.gov"


def _get(url, params):
    try:
        r = requests.get(url, params=params, timeout=TIMEOUT)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"error": str(e)}


def fetch_fei(company_name: str) -> dict:
    """FDA establishment registration / FEI lookup."""
    q = f'firm_name:"{company_name}"'
    d = _get(f"{BASE}/device/registrationlisting.json",
             {"search": q, "limit": 10})
    if "error" in d:
        # fallback: unquoted
        d = _get(f"{BASE}/device/registrationlisting.json",
                 {"search": f"firm_name:{company_name}", "limit": 10})
    results = d.get("results", [])
    establishments = []
    products = []
    for r in results:
        establishments.append({
            "fei":     r.get("registration", {}).get("fei_number", "—"),
            "name":    r.get("registration", {}).get("name", "—"),
            "city":    r.get("registration", {}).get("city_state_and_country", "—"),
            "status":  r.get("registration", {}).get("registration_status_code", "—"),
        })
        for p in r.get("products", []):
            products.append({
                "code":  p.get("product_code", "—"),
                "name":  p.get("device", {}).get("device_name", "—"),
                "class": p.get("openfda", {}).get("device_class", ["—"])[0]
                         if p.get("openfda", {}).get("device_class") else "—",
            })
    return {
        "total":          d.get("meta", {}).get("results", {}).get("total", 0),
        "establishments": establishments[:5],
        "products":       products[:20],
    }


def fetch_510k(company_name: str) -> dict:
    """FDA 510(k) clearances."""
    q = f"applicant:{company_name}"
    d = _get(f"{BASE}/device/510k.json",
             {"search": q, "limit": 25, "sort": "decision_date:desc"})
    if "error" in d:
        return {"error": d["error"], "total": 0, "items": []}
    items = []
    for r in d.get("results", []):
        k = r.get("k_number", "")
        items.append({
            "k_number":     k,
            "device_name":  r.get("device_name", "—"),
            "decision_date":r.get("decision_date", "—"),
            "decision_code":r.get("decision_code", "—"),
            "product_code": r.get("product_code", "—"),
            "url": f"https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfpmn/pmn.cfm?ID={k}" if k else "",
        })
    return {
        "total": d.get("meta", {}).get("results", {}).get("total", 0),
        "items": items,
    }


def fetch_pma(company_name: str) -> dict:
    """FDA PMA approvals."""
    d = _get(f"{BASE}/device/pma.json",
             {"search": f"applicant:{company_name}", "limit": 10,
              "sort": "decision_date:desc"})
    if "error" in d:
        return {"error": d["error"], "items": []}
    items = []
    for r in d.get("results", []):
        pma = r.get("pma_number", "")
        items.append({
            "pma_number":   pma,
            "device_name":  r.get("device_name", "—"),
            "decision_date":r.get("decision_date", "—"),
            "decision_code":r.get("decision_code", "—"),
            "url": f"https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfpma/pma.cfm?id={pma}" if pma else "",
        })
    return {"items": items}


def fetch_maude(company_name: str) -> dict:
    """FDA MAUDE adverse event reports."""
    q = f"manufacturer_d_name:{company_name}"
    d = _get(f"{BASE}/device/event.json",
             {"search": q, "limit": 25, "sort": "date_received:desc"})
    if "error" in d or not d.get("results"):
        # fallback field
        d = _get(f"{BASE}/device/event.json",
                 {"search": f"manufacturer_name:{company_name}",
                  "limit": 25, "sort": "date_received:desc"})
    items = []
    for r in d.get("results", []):
        dev = r.get("device", [{}])
        txt = r.get("mdr_text", [{}])
        items.append({
            "date":        r.get("date_received", "—"),
            "event_type":  r.get("event_type", "—"),
            "brand_name":  dev[0].get("brand_name", "—") if dev else "—",
            "description": txt[0].get("text", "—")[:200] if txt else "—",
        })
    return {
        "total": d.get("meta", {}).get("results", {}).get("total", 0),
        "items": items,
    }


def fetch_recalls(company_name: str) -> dict:
    """FDA device recalls."""
    d = _get(f"{BASE}/device/recall.json",
             {"search": f"recalling_firm:{company_name}",
              "limit": 20, "sort": "recall_initiation_date:desc"})
    if "error" in d:
        return {"error": d["error"], "total": 0, "items": []}
    items = []
    for r in d.get("results", []):
        items.append({
            "date":    r.get("recall_initiation_date", "—"),
            "class":   r.get("res_text", "—"),
            "product": r.get("product_description", "—")[:80],
            "reason":  r.get("reason_for_recall", "—")[:120],
            "status":  r.get("status", "—"),
        })
    return {
        "total": d.get("meta", {}).get("results", {}).get("total", 0),
        "items": items,
    }
"""ClinicalTrials.gov v2 API module."""
import requests

TIMEOUT = 12


def fetch_trials(company_name: str) -> dict:
    try:
        r = requests.get(
            "https://clinicaltrials.gov/api/v2/studies",
            params={
                "query.spons": company_name,
                "pageSize": 25,
                "sort": "LastUpdatePostDate:desc",
                "fields": "NCTId,BriefTitle,Phase,OverallStatus,EnrollmentCount,StartDate,CompletionDate,Condition",
            },
            timeout=12,
        )
        r.raise_for_status()
        d = r.json()
    except Exception as e:
        return {"error": str(e), "total": 0, "items": []}

    items = []
    for s in d.get("studies", []):
        p = s.get("protocolSection", {})
        id_mod     = p.get("identificationModule", {})
        status_mod = p.get("statusModule", {})
        design_mod = p.get("designModule", {})
        cond_mod   = p.get("conditionsModule", {})
        items.append({
            "nct_id":     id_mod.get("nctId", "—"),
            "title":      id_mod.get("briefTitle", "—"),
            "phase":      ", ".join(design_mod.get("phases", [])) or "N/A",
            "status":     status_mod.get("overallStatus", "—"),
            "enrollment": design_mod.get("enrollmentInfo", {}).get("count", "—"),
            "start":      status_mod.get("startDateStruct", {}).get("date", "—"),
            "completion": status_mod.get("completionDateStruct", {}).get("date", "—"),
            "conditions": ", ".join(cond_mod.get("conditions", [])[:3]),
            "url":        f"https://clinicaltrials.gov/study/{id_mod.get('nctId','')}",
        })
    return {
        "total": d.get("totalCount", len(items)),
        "items": items,
    }
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
