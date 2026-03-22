"""
Medical Device CI Tool — Data Modules
All API calls are server-side (no CORS). Uses requests library.
"""
import requests
from collections import defaultdict

TIMEOUT = 15
BASE = "https://api.fda.gov"


# ── Shared helper ─────────────────────────────────────────────────────────────

def _get(url, params):
    try:
        r = requests.get(url, params=params, timeout=TIMEOUT)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"error": str(e)}


def _fda_name_variants(company_name: str) -> list[str]:
    """
    OpenFDA stores names in unpredictable formats (ALL CAPS, with/without Inc., etc.)
    Try progressively looser queries: quoted exact → first word only → first two words.
    """
    parts = company_name.replace(",", "").replace(".", "").split()
    variants = [
        f'"{company_name}"',          # exact quoted
        company_name,                  # unquoted (partial match)
        " ".join(parts[:2]) if len(parts) >= 2 else parts[0],  # first two words
        parts[0],                      # first word only
    ]
    # deduplicate while preserving order
    seen = set()
    return [v for v in variants if not (v in seen or seen.add(v))]


def _fda_query_with_fallback(url: str, field: str, company_name: str, extra_params: dict) -> dict:
    """Try multiple name variants until we get results."""
    for variant in _fda_name_variants(company_name):
        params = {**extra_params, "search": f"{field}:{variant}"}
        d = _get(url, params)
        if not d.get("error") and d.get("results"):
            return d
    return {"error": f"No results found for '{company_name}'", "results": [], "meta": {}}


# ── FDA Registration / FEI ────────────────────────────────────────────────────

def fetch_fei(company_name: str) -> dict:
    d = _fda_query_with_fallback(
        f"{BASE}/device/registrationlisting.json",
        "registration.name",
        company_name,
        {"limit": 10},
    )
    results = d.get("results", [])
    establishments, products = [], []
    for r in results:
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
            products.append({
                "code":  p.get("product_code", "—"),
                "name":  openfda.get("device_name", ["—"])[0] if openfda.get("device_name") else p.get("product_code", "—"),
                "class": cls[0] if cls else "—",
            })
    return {
        "total":          d.get("meta", {}).get("results", {}).get("total", 0),
        "establishments": establishments[:8],
        "products":       products[:20],
        "error":          d.get("error") if not results else None,
    }


# ── FDA 510(k) ────────────────────────────────────────────────────────────────

def fetch_510k(company_name: str) -> dict:
    d = _fda_query_with_fallback(
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
    d = _fda_query_with_fallback(
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
    # MAUDE uses manufacturer_d_name (device manufacturer) — try both fields
    d = _fda_query_with_fallback(
        f"{BASE}/device/event.json",
        "manufacturer_d_name",
        company_name,
        {"limit": 25, "sort": "date_received:desc"},
    )
    if not d.get("results"):
        d = _fda_query_with_fallback(
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
    d = _fda_query_with_fallback(
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

DATASETS = {
    2024: "5ia3-vtt7",
    2023: "fb3a65aa-c901-4a38-a813-b04b00dfa2a9",
}
OP_BASE = "https://openpaymentsdata.cms.gov/api/1/datastore"


def _op_sql(dataset_id: str, sql: str) -> list:
    try:
        r = requests.get(f"{OP_BASE}/sql",
                         params={"query": sql, "show_db_columns": "true"},
                         timeout=TIMEOUT)
        r.raise_for_status()
        d = r.json()
        return d if isinstance(d, list) else []
    except Exception:
        return []


def _op_query(dataset_id: str, conditions: list, limit=500) -> list:
    params = {
        "results_format": "objects", "keys": "true",
        "limit": limit, "offset": 0,
        "sort[0][property]": "total_amount_of_payment_usdollars",
        "sort[0][order]": "desc",
    }
    for i, c in enumerate(conditions):
        params[f"conditions[{i}][property]"] = c["property"]
        params[f"conditions[{i}][value]"]    = c["value"]
        params[f"conditions[{i}][operator]"] = c.get("operator", "=")
    try:
        r = requests.get(f"{OP_BASE}/query/{dataset_id}/0",
                         params=params, timeout=TIMEOUT)
        r.raise_for_status()
        d = r.json()
        return d.get("results") or d.get("data") or (d if isinstance(d, list) else [])
    except Exception:
        return []


def _op_field(row, *keys):
    for k in keys:
        for candidate in [k, k.lower(), k.title()]:
            v = row.get(candidate)
            if v:
                return v
    return ""


def resolve_company_id(company_name: str):
    escaped = company_name.replace("'", "''")
    for year, ds_id in DATASETS.items():
        sql = (
            f"[SELECT applicable_manufacturer_or_applicable_gpo_making_payment_id,"
            f"applicable_manufacturer_or_applicable_gpo_making_payment_name "
            f"FROM {ds_id}]"
            f"[WHERE applicable_manufacturer_or_applicable_gpo_making_payment_name "
            f'LIKE "%{escaped}%"][LIMIT 5]'
        )
        rows = _op_sql(ds_id, sql)
        if rows:
            row  = rows[0]
            cid  = row.get("applicable_manufacturer_or_applicable_gpo_making_payment_id")
            name = row.get("applicable_manufacturer_or_applicable_gpo_making_payment_name", company_name)
            if cid:
                return str(cid), name
    return None, company_name


def fetch_payments(company_name: str) -> dict:
    company_id, resolved_name = resolve_company_id(company_name)
    if not company_id:
        return {
            "error": f"'{company_name}' not found in Open Payments. Try the exact legal name.",
            "resolved_name": company_name, "company_id": None,
        }

    all_rows = []
    for year, ds_id in DATASETS.items():
        rows = _op_query(ds_id, [{
            "property": "applicable_manufacturer_or_applicable_gpo_making_payment_id",
            "value": company_id, "operator": "=",
        }], limit=500)
        for r in rows:
            r["_program_year"] = year
        all_rows.extend(rows)

    if not all_rows:
        return {
            "error": f"Found company ID {company_id} but no payment records returned.",
            "resolved_name": resolved_name, "company_id": company_id,
        }

    total_paid = 0.0
    by_year    = defaultdict(float)
    by_type    = defaultdict(float)
    by_state   = defaultdict(float)
    physicians = defaultdict(lambda: {"total": 0.0, "count": 0, "specialty": "", "state": ""})

    for p in all_rows:
        amt = float(_op_field(p, "total_amount_of_payment_usdollars") or 0)
        total_paid += amt
        year  = str(p.get("_program_year") or _op_field(p, "program_year") or "Unknown")
        by_year[year] += amt
        ptype = _op_field(p, "nature_of_payment_or_transfer_of_value") or "Other"
        by_type[ptype] += amt
        state = _op_field(p, "recipient_state") or "Unknown"
        by_state[state] += amt
        first = _op_field(p, "covered_recipient_first_name", "physician_first_name")
        last  = _op_field(p, "covered_recipient_last_name",  "physician_last_name")
        name  = f"{first} {last}".strip()
        if len(name) > 2:
            spec  = _op_field(p, "covered_recipient_specialty_1", "physician_specialty")
            physicians[name]["total"]   += amt
            physicians[name]["count"]   += 1
            if not physicians[name]["specialty"] and spec:
                physicians[name]["specialty"] = spec
            if not physicians[name]["state"] and state != "Unknown":
                physicians[name]["state"] = state

    return {
        "resolved_name": resolved_name,
        "company_id":    company_id,
        "total_paid":    total_paid,
        "record_count":  len(all_rows),
        "by_year":       dict(sorted(by_year.items())),
        "by_type":       dict(sorted(by_type.items(), key=lambda x: x[1], reverse=True)),
        "by_state":      dict(sorted(by_state.items(), key=lambda x: x[1], reverse=True)),
        "top_kols":      sorted(physicians.items(), key=lambda x: x[1]["total"], reverse=True)[:20],
        "cms_url":       f"https://openpaymentsdata.cms.gov/company/{company_id}",
    }


# ── SEC EDGAR ─────────────────────────────────────────────────────────────────

def fetch_sec(cik: str) -> dict:
    cik_clean  = str(cik).strip().lstrip("0")
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
    recent      = d.get("filings", {}).get("recent", {})
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
        d     = r.json()
        items = d.get("results", [])
        return {"items": items, "total": sum(float(i.get("award_amount") or 0) for i in items)}
    except Exception as e:
        return {"items": [], "total": 0, "error": str(e)}
