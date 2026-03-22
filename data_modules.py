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
#
# The 2024 dataset (5ia3-vtt7) is a SOCRATA/SODA endpoint.
# Correct base URL: https://openpaymentsdata.cms.gov/resource/{id}.json
# Query syntax: standard SoQL ($where, $limit, $order, $select)
# NOT the DKAN /api/1/datastore/sql format (that was the bug all along).
#
# Dataset IDs (Socrata resource IDs, updated each June):
#   2024: 5ia3-vtt7
#   2023: wjm5-k45b   (general payments 2023)
#
# Field: applicable_manufacturer_or_applicable_gpo_making_payment_name

SODA_BASE = "https://openpaymentsdata.cms.gov/resource"
SODA_DATASETS = ["5ia3-vtt7", "wjm5-k45b"]  # 2024, 2023


def _soda_get(dataset_id: str, params: dict) -> list:
    """Query a Socrata/SODA endpoint."""
    try:
        r = requests.get(
            f"{SODA_BASE}/{dataset_id}.json",
            params=params,
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        d = r.json()
        return d if isinstance(d, list) else []
    except Exception:
        return []



def fetch_payments(company_name: str) -> dict:
    # DEBUG — testing API connectivity and field names
    r1 = requests.get(
        "https://openpaymentsdata.cms.gov/resource/5ia3-vtt7.json",
        params={"$limit": "2"},
        timeout=20
    )

    r2 = requests.get(
        "https://openpaymentsdata.cms.gov/resource/5ia3-vtt7.json",
        params={
            "$where": "applicable_manufacturer_or_applicable_gpo_making_payment_name='Intuitive Surgical, Inc.'",
            "$limit": "2"
        },
        timeout=20
    )

    sample = r1.json() if r1.ok else []
    return {
        "error": "DEBUG MODE",
        "test1_status": r1.status_code,
        "test1_fields": list(sample[0].keys()) if sample else "no rows",
        "test1_sample_name": sample[0].get(
            "applicable_manufacturer_or_applicable_gpo_making_payment_name", "FIELD NOT FOUND"
        ) if sample else "n/a",
        "test2_status": r2.status_code,
        "test2_count": len(r2.json()) if r2.ok else "error",
        "test2_body": r2.text[:300],
    }
    # Step 2: Pull up to 500 records per dataset year using resolved name
    all_rows = []
    safe_name = resolved_name.replace("'", "''")
    for ds_id in SODA_DATASETS:
        rows = _soda_get(ds_id, {
            "$where":  f"applicable_manufacturer_or_applicable_gpo_making_payment_name="
                       f"'{safe_name}'",
            "$order":  "total_amount_of_payment_usdollars DESC",
            "$limit":  "500",
            "_source": ds_id,  # carried through for year tagging
        })
        # Tag with dataset year (first 4 chars of id aren't year — use index)
        year = "2024" if ds_id == SODA_DATASETS[0] else "2023"
        for r in rows:
            r["_year"] = year
        all_rows.extend(rows)

    if not all_rows:
        return {
            "error": f"Found '{resolved_name}' in name lookup but no payment records returned.",
            "resolved_name": resolved_name,
            "company_id": company_id,
        }

    # Step 3: Aggregate
    total_paid = 0.0
    by_year    = {}
    by_type    = {}
    by_state   = {}
    physicians = {}

    for p in all_rows:
        amt = float(p.get("total_amount_of_payment_usdollars") or 0)
        total_paid += amt

        year = p.get("program_year") or p.get("_year", "Unknown")
        by_year[str(year)] = by_year.get(str(year), 0.0) + amt

        ptype = p.get("nature_of_payment_or_transfer_of_value") or "Other"
        by_type[ptype] = by_type.get(ptype, 0.0) + amt

        state = p.get("recipient_state") or "Unknown"
        by_state[state] = by_state.get(state, 0.0) + amt

        first = p.get("covered_recipient_first_name") or p.get("physician_first_name") or ""
        last  = p.get("covered_recipient_last_name")  or p.get("physician_last_name")  or ""
        name  = f"{first} {last}".strip()
        if len(name) > 2:
            spec  = p.get("covered_recipient_specialty_1") or p.get("physician_specialty") or ""
            if name not in physicians:
                physicians[name] = {"total": 0.0, "count": 0, "specialty": spec, "state": state}
            physicians[name]["total"] += amt
            physicians[name]["count"] += 1

    return {
        "resolved_name": resolved_name,
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
