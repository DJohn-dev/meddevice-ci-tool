"""
Medical Device CI Tool — Data Modules
All API calls are server-side via Python requests (no CORS restrictions).
"""
import requests
from collections import defaultdict

TIMEOUT = 15
BASE = "https://api.fda.gov"


# ── Shared helpers ────────────────────────────────────────────────────────────

def _get(url, params):
    try:
        r = requests.get(url, params=params, timeout=TIMEOUT)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"error": str(e)}


def _fda_search(url, field, company_name, extra_params):
    """
    Try progressively looser name queries against OpenFDA.
    FDA stores names inconsistently (ALL CAPS, truncated, no punctuation).
    Strategy: first word only is most reliable for tokenized fields.
    """
    parts = company_name.replace(",", "").replace(".", "").split()
    first = parts[0]
    two   = " ".join(parts[:2]) if len(parts) >= 2 else first

    for variant in [first, two, company_name]:
        params = {**extra_params, "search": f"{field}:{variant}"}
        d = _get(url, params)
        if not d.get("error") and d.get("results"):
            return d
    return {"error": f"No results found for '{company_name}'", "results": [], "meta": {}}


# ── FDA Registration / FEI ────────────────────────────────────────────────────

def fetch_fei(company_name: str) -> dict:
    d = _fda_search(
        f"{BASE}/device/registrationlisting.json",
        "registration.name",
        company_name,
        {"limit": 10},
    )
    establishments, products = [], []
    for r in d.get("results", []):
        reg = r.get("registration", {})
        establishments.append({
            "fei":    reg.get("fei_number", "—"),
            "name":   reg.get("name", "—"),
            "city":   reg.get("city_state_and_country", "—"),
            "status": reg.get("registration_status_code", "—"),
        })
        for p in r.get("products", []):
            openfda = p.get("openfda", {})
            cls = openfda.get("device_class", [])
            names = openfda.get("device_name", [])
            products.append({
                "code":  p.get("product_code", "—"),
                "name":  names[0] if names else p.get("product_code", "—"),
                "class": cls[0] if cls else "—",
            })
    return {
        "total":          d.get("meta", {}).get("results", {}).get("total", 0),
        "establishments": establishments[:8],
        "products":       products[:20],
        "error":          d.get("error") if not establishments else None,
    }


# ── FDA 510(k) ────────────────────────────────────────────────────────────────

def fetch_510k(company_name: str) -> dict:
    d = _fda_search(
        f"{BASE}/device/510k.json",
        "applicant",
        company_name,
        {"limit": 25, "sort": "decision_date:desc"},
    )
    items = []
    for r in d.get("results", []):
        k = r.get("k_number", "")
        items.append({
            "k_number":      k,
            "device_name":   r.get("device_name", "—"),
            "decision_date": r.get("decision_date", "—"),
            "decision_code": r.get("decision_code", "—"),
            "product_code":  r.get("product_code", "—"),
            "url": f"https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfpmn/pmn.cfm?ID={k}" if k else "",
        })
    return {
        "total": d.get("meta", {}).get("results", {}).get("total", 0),
        "items": items,
        "error": d.get("error") if not items else None,
    }


# ── FDA PMA ───────────────────────────────────────────────────────────────────

def fetch_pma(company_name: str) -> dict:
    d = _fda_search(
        f"{BASE}/device/pma.json",
        "applicant",
        company_name,
        {"limit": 10, "sort": "decision_date:desc"},
    )
    items = []
    for r in d.get("results", []):
        pma = r.get("pma_number", "")
        items.append({
            "pma_number":    pma,
            "device_name":   r.get("device_name", "—"),
            "decision_date": r.get("decision_date", "—"),
            "decision_code": r.get("decision_code", "—"),
            "url": f"https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfpma/pma.cfm?id={pma}" if pma else "",
        })
    return {"items": items, "error": d.get("error") if not items else None}


# ── FDA MAUDE ─────────────────────────────────────────────────────────────────

def fetch_maude(company_name: str) -> dict:
    # Try manufacturer_d_name first, then device.manufacturer_d_name
    d = _fda_search(
        f"{BASE}/device/event.json",
        "manufacturer_d_name",
        company_name,
        {"limit": 25, "sort": "date_received:desc"},
    )
    if not d.get("results"):
        d = _fda_search(
            f"{BASE}/device/event.json",
            "device.manufacturer_d_name",
            company_name,
            {"limit": 25, "sort": "date_received:desc"},
        )
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
        "error": d.get("error") if not items else None,
    }


# ── FDA Recalls ───────────────────────────────────────────────────────────────

def fetch_recalls(company_name: str) -> dict:
    # recalling_firm is a tokenized field — first word gives best results
    d = _fda_search(
        f"{BASE}/device/recall.json",
        "recalling_firm",
        company_name,
        {"limit": 20, "sort": "recall_initiation_date:desc"},
    )
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
        "error": d.get("error") if not items else None,
    }


# ── ClinicalTrials.gov v2 ─────────────────────────────────────────────────────

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
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        d = r.json()
    except Exception as e:
        return {"error": str(e), "total": 0, "items": []}

    items = []
    for s in d.get("studies", []):
        p          = s.get("protocolSection", {})
        id_mod     = p.get("identificationModule", {})
        status_mod = p.get("statusModule", {})
        design_mod = p.get("designModule", {})
        cond_mod   = p.get("conditionsModule", {})
        nct        = id_mod.get("nctId", "")
        items.append({
            "nct_id":     nct,
            "title":      id_mod.get("briefTitle", "—"),
            "phase":      ", ".join(design_mod.get("phases", [])) or "N/A",
            "status":     status_mod.get("overallStatus", "—"),
            "enrollment": design_mod.get("enrollmentInfo", {}).get("count", "—"),
            "start":      status_mod.get("startDateStruct", {}).get("date", "—"),
            "completion": status_mod.get("completionDateStruct", {}).get("date", "—"),
            "conditions": ", ".join(cond_mod.get("conditions", [])[:3]),
            "url":        f"https://clinicaltrials.gov/study/{nct}" if nct else "",
        })
    return {"total": d.get("totalCount", len(items)), "items": items}


# ── CMS Open Payments ─────────────────────────────────────────────────────────
#
# CONFIRMED WORKING (tested 2026-03-23):
#   Base:    https://openpaymentsdata.cms.gov/api/1/datastore/query/{dataset_id}/0
#   2023 ID: fb3a65aa-c901-4a38-a813-b04b00dfa2a9  (14.7M records)
#   Filter:  filter[applicable_manufacturer_or_applicable_gpo_making_payment_name]=
#            "Intuitive Surgical, Inc."
#   Fields:  all lowercase, e.g. applicable_manufacturer_or_applicable_gpo_making_payment_name
#            covered_recipient_first_name, covered_recipient_last_name
#            total_amount_of_payment_usdollars, nature_of_payment_or_transfer_of_value
#            recipient_state, covered_recipient_specialty_1, program_year
#
# The filter key must be lowercase even though the URL example showed Title_Case.

OPAY_BASE = "https://openpaymentsdata.cms.gov/api/1/datastore/query"
OPAY_DATASETS = [
    "fb3a65aa-c901-4a38-a813-b04b00dfa2a9",  # 2023 general payments — confirmed working
]
OPAY_NAME_FIELD = "applicable_manufacturer_or_applicable_gpo_making_payment_name"
OPAY_ID_FIELD   = "applicable_manufacturer_or_applicable_gpo_making_payment_id"


def _opay_query(dataset_id: str, filters: dict, limit: int = 500, offset: int = 0) -> dict:
    """Query the Open Payments DKAN datastore with confirmed working syntax."""
    params = {
        "limit":          limit,
        "offset":         offset,
        "count":          "true",
        "results":        "true",
        "keys":           "true",
        "format":         "json",
        "sort":           "total_amount_of_payment_usdollars",
        "sort-order":     "desc",
    }
    for k, v in filters.items():
        params[f"filter[{k}]"] = v
    try:
        r = requests.get(
            f"{OPAY_BASE}/{dataset_id}/0",
            params=params,
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"error": str(e), "results": [], "count": 0}


def fetch_payments(company_name: str) -> dict:
    """
    Fetch Open Payments data using the confirmed working DKAN endpoint.
    Dataset: fb3a65aa-c901-4a38-a813-b04b00dfa2a9 (2023 general payments)
    Filter field: applicable_manufacturer_or_applicable_gpo_making_payment_name (lowercase)
    """
    all_rows  = []
    company_id = ""

    for ds_id in OPAY_DATASETS:
        d = _opay_query(ds_id, {OPAY_NAME_FIELD: company_name}, limit=500)

        if d.get("error"):
            continue

        rows = d.get("results", [])
        if not rows:
            # Company name not found — return clear error
            return {
                "error": f"'{company_name}' not found in Open Payments. "
                         "The name must match exactly as registered with CMS. "
                         f"Check openpaymentsdata.cms.gov to confirm the legal name.",
                "resolved_name": company_name,
                "company_id": None,
            }

        # Grab company ID from first row
        if not company_id and rows:
            company_id = rows[0].get(OPAY_ID_FIELD, "")

        for row in rows:
            row["_ds_id"] = ds_id
        all_rows.extend(rows)

    if not all_rows:
        return {
            "error": f"No payment records found for '{company_name}'.",
            "resolved_name": company_name,
            "company_id": None,
        }

    # Aggregate
    total_paid = 0.0
    by_year    = defaultdict(float)
    by_type    = defaultdict(float)
    by_state   = defaultdict(float)
    physicians = defaultdict(lambda: {"total": 0.0, "count": 0, "specialty": "", "state": ""})

    for p in all_rows:
        amt   = float(p.get("total_amount_of_payment_usdollars") or 0)
        total_paid += amt

        year  = str(p.get("program_year") or "Unknown")
        by_year[year] += amt

        ptype = p.get("nature_of_payment_or_transfer_of_value") or "Other"
        by_type[ptype] += amt

        state = p.get("recipient_state") or "Unknown"
        by_state[state] += amt

        first = p.get("covered_recipient_first_name") or ""
        last  = p.get("covered_recipient_last_name")  or ""
        name  = f"{first} {last}".strip()
        if len(name) > 2:
            spec  = p.get("covered_recipient_specialty_1") or ""
            physicians[name]["total"]   += amt
            physicians[name]["count"]   += 1
            if not physicians[name]["specialty"] and spec:
                physicians[name]["specialty"] = spec
            if not physicians[name]["state"] and state != "Unknown":
                physicians[name]["state"] = state

    return {
        "resolved_name": company_name,
        "company_id":    company_id,
        "total_paid":    total_paid,
        "record_count":  len(all_rows),
        "by_year":       dict(sorted(by_year.items())),
        "by_type":       dict(sorted(by_type.items(), key=lambda x: x[1], reverse=True)),
        "by_state":      dict(sorted(by_state.items(), key=lambda x: x[1], reverse=True)),
        "top_kols":      sorted(physicians.items(), key=lambda x: x[1]["total"], reverse=True)[:20],
        "cms_url":       f"https://openpaymentsdata.cms.gov/company/{company_id}" if company_id else "",
    }


# ── SEC EDGAR ─────────────────────────────────────────────────────────────────

def fetch_sec(cik: str) -> dict:
    cik_clean  = str(cik).strip().lstrip("0")
    cik_padded = cik_clean.zfill(10)
    try:
        r = requests.get(
            f"https://data.sec.gov/submissions/CIK{cik_padded}.json",
            headers={"User-Agent": "MedDevice CI Tool research@example.com"},
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        d = r.json()
    except Exception as e:
        return {"error": str(e)}

    entity_name  = d.get("name", "Unknown")
    recent       = d.get("filings", {}).get("recent", {})
    forms        = recent.get("form", [])
    dates        = recent.get("filingDate", [])
    accessions   = recent.get("accessionNumber", [])
    descriptions = recent.get("primaryDocument", [])
    periods      = recent.get("reportDate", [])

    priority = {"10-K", "10-Q", "8-K", "DEF 14A", "4", "S-1"}
    items = []
    for i, form in enumerate(forms):
        if form in priority:
            acc = accessions[i].replace("-", "") if i < len(accessions) else ""
            doc = descriptions[i] if i < len(descriptions) else ""
            items.append({
                "form":   form,
                "date":   dates[i] if i < len(dates) else "—",
                "period": periods[i] if i < len(periods) else "—",
                "url":    f"https://www.sec.gov/Archives/edgar/data/{cik_clean}/{acc}/{doc}"
                          if acc and doc else
                          f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik_clean}&type={form}&owner=include&count=5",
            })
        if len(items) >= 20:
            break

    return {
        "entity_name": entity_name,
        "cik":         cik_clean,
        "items":       items,
        "links": {
            "All Filings":    f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik_clean}&type=&owner=include&count=40",
            "10-K Annual":    f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik_clean}&type=10-K&owner=include&count=5",
            "10-Q Quarterly": f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik_clean}&type=10-Q&owner=include&count=5",
            "8-K Current":    f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik_clean}&type=8-K&owner=include&count=10",
            "DEF 14A Proxy":  f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik_clean}&type=DEF+14A&owner=include&count=5",
            "Form 4 Insider": f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik_clean}&type=4&owner=include&count=20",
        },
    }


# ── USASpending + NIH ─────────────────────────────────────────────────────────

def fetch_spending(company_name: str) -> dict:
    def _spend(award_types):
        try:
            r = requests.post(
                "https://api.usaspending.gov/api/v2/search/spending_by_award/",
                json={
                    "filters": {
                        "recipient_search_text": [company_name],
                        "award_type_codes": award_types,
                        "time_period": [{"start_date": "2019-01-01", "end_date": "2024-12-31"}],
                    },
                    "fields": ["Award ID", "Recipient Name", "Award Amount",
                               "Awarding Agency", "Award Type", "Description",
                               "Start Date", "End Date"],
                    "sort": "Award Amount", "order": "desc",
                    "limit": 25, "page": 1,
                },
                timeout=TIMEOUT,
            )
            return r.json().get("results", [])
        except Exception:
            return []

    contracts = _spend(["A", "B", "C", "D"])
    grants    = _spend(["02", "03", "04", "05"])
    return {
        "contracts":      contracts,
        "grants":         grants,
        "contract_total": sum(float(c.get("Award Amount") or 0) for c in contracts),
        "grant_total":    sum(float(g.get("Award Amount") or 0) for g in grants),
    }


def fetch_nih(company_name: str) -> dict:
    try:
        r = requests.post(
            "https://api.reporter.nih.gov/v2/projects/search",
            json={
                "criteria": {
                    "org_names": [company_name],
                    "fiscal_years": [2020, 2021, 2022, 2023, 2024],
                },
                "offset": 0, "limit": 25,
                "sort_field": "award_amount", "sort_order": "desc",
            },
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        items = r.json().get("results", [])
        return {"items": items, "total": sum(float(i.get("award_amount") or 0) for i in items)}
    except Exception as e:
        return {"items": [], "total": 0, "error": str(e)}
