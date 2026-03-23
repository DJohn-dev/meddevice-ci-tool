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
    # Use device/enforcement.json — this is the correct openFDA endpoint for device recalls.
    # device/recall.json covers a different (narrower) dataset.
    # recalling_firm is tokenized so first word works best.
    d = _fda_search(
        f"{BASE}/device/enforcement.json",
        "recalling_firm",
        company_name,
        {"limit": 20, "sort": "recall_initiation_date:desc"},
    )
    items = []
    for r in d.get("results", []):
        items.append({
            "date":    r.get("recall_initiation_date", "—"),
            "class":   r.get("classification", "—"),
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
    # Use first two meaningful words — punctuation in full name causes missed results
    # e.g. "Intuitive Surgical, Inc." -> "Intuitive Surgical"
    parts = company_name.replace(",", "").replace(".", "").replace("Inc", "").replace("LLC", "").replace("Corp", "").split()
    short_name = " ".join(parts[:2]) if len(parts) >= 2 else parts[0] if parts else company_name
    try:
        r = requests.get(
            "https://clinicaltrials.gov/api/v2/studies",
            params={
                "query.spons": short_name,
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
# CONFIRMED WORKING APPROACH (tested 2026-03-23):
# The DKAN /api/1/datastore/query endpoint accepts filter params but ignores them.
# The only reliable approach: download the pre-built summary CSV files from
# download.cms.gov, which are already aggregated by company.
#
# Summary CSV: "payments grouped by reporting entities and nature of payments"
# Fields: amgpo_id, amgpo_name, nature_of_payment_type_code, number_of_transaction, total_amount
# Size: ~6,484 rows total (all companies) — very small, fast to download
#
# Nature of payment type codes (from CMS data dictionary):
PAYMENT_TYPE_CODES = {
    "1":  "Consulting Fees",
    "2":  "Compensation for Services Other Than Consulting",
    "3":  "Honoraria",
    "4":  "Gift",
    "5":  "Entertainment",
    "6":  "Food and Beverage",
    "7":  "Travel and Lodging",
    "8":  "Education",
    "9":  "Research",
    "10": "Charitable Contribution",
    "11": "Royalty or License",
    "12": "Current or Prospective Ownership or Investment Interest",
    "13": "Compensation for Serving as Faculty or as a Speaker for a Medical Education Program",
    "14": "Grant",
    "15": "Space Rental or Facility Fees",
    "16": "Services: Other",
    "17": "Medical Device Loan",
    "18": "Non-Research Related Items",
}

# Dataset identifiers from the metastore catalog (confirmed via /api/1/metastore/schemas/dataset/items)
SUMMARY_DATASETS = {
    2024: {
        "csv_url": "https://download.cms.gov/openpayments/SMRY_RPTS_P01232026_01102026/PBLCTN_SMRY_BY_AMGPO_BY_NTR_OF_PYMT_PGYR2024_P01232026_01102026.csv",
    },
    2023: {
        "csv_url": "https://download.cms.gov/openpayments/SMRY_RPTS_P01232026_01102026/PBLCTN_SMRY_BY_AMGPO_BY_NTR_OF_PYMT_PGYR2023_P01232026_01102026.csv",
    },
    2022: {
        "csv_url": "https://download.cms.gov/openpayments/SMRY_RPTS_P01232026_01102026/PBLCTN_SMRY_BY_AMGPO_BY_NTR_OF_PYMT_PGYR2022_P01232026_01102026.csv",
    },
}

# KOL summary: one row per physician per company — fields confirmed from API schema:
# amgpo_id, covered_recipient_profile_first_name, covered_recipient_profile_last_name,
# covered_recipient_npi, total_amount, number_of_transaction, payment_type
KOL_DATASETS = {
    2023: "https://download.cms.gov/openpayments/SMRY_RPTS_P01232026_01102026/PBLCTN_SMRY_BY_CR_BY_AMGPO_PGYR2023_P01232026_01102026.csv",
    2024: "https://download.cms.gov/openpayments/SMRY_RPTS_P01232026_01102026/PBLCTN_SMRY_BY_CR_BY_AMGPO_PGYR2024_P01232026_01102026.csv",
}


def _fetch_summary_csv(csv_url: str, company_id: str) -> list:
    """
    Download the summary CSV and filter rows for the given company ID.
    Returns list of dicts with keys: nature_of_payment_type_code, total_amount, number_of_transaction
    """
    import io, csv
    try:
        r = requests.get(csv_url, timeout=30, stream=True)
        r.raise_for_status()
        # Read the CSV content
        content = r.content.decode("utf-8-sig")  # handle BOM
        reader = csv.DictReader(io.StringIO(content))
        rows = []
        for row in reader:
            # Field names vary slightly — try both cases
            # Summary CSV uses lowercase "amgpo_id" (confirmed from API response)
            # Try all variants for safety
            rid = (
                row.get("amgpo_id") or
                row.get("AMGPO_ID") or
                row.get("AMGPO_Making_Payment_ID") or
                row.get("Applicable_Manufacturer_or_Applicable_GPO_Making_Payment_ID") or ""
            ).strip()
            # Last resort: scan all values
            if not rid:
                rid = company_id if company_id in row.values() else ""
            if rid == company_id:
                rows.append(row)
        return rows
    except Exception as e:
        return []


def _fetch_kol_csv(csv_url: str, company_id: str) -> list:
    """
    Download the covered-recipient-by-company summary CSV and filter by company ID.
    Fields: amgpo_id, covered_recipient_profile_first_name, covered_recipient_profile_last_name,
            covered_recipient_npi, recipient_state, total_amount, number_of_transaction
    """
    import io, csv
    try:
        r = requests.get(csv_url, timeout=45)
        r.raise_for_status()
        content = r.content.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(content))
        rows = []
        for row in reader:
            rid = (row.get("amgpo_id") or row.get("AMGPO_ID") or
                   row.get("AMGPO_Making_Payment_ID") or "").strip()
            if not rid:
                rid = company_id if company_id in row.values() else ""
            if rid == company_id:
                rows.append(row)
        return rows
    except Exception:
        return []


def _lookup_company_id(company_name: str) -> tuple:
    """
    Look up numeric company ID from the reporting entity profile CSV.
    Confirmed field names (from debug 2026-03-23):
      AMGPO_Making_Payment_ID, AMGPO_Making_Payment_Name
    Stored names are ALL CAPS so we do case-insensitive matching.
    Also checks alternate name fields (1-5).
    Returns (company_id, resolved_name) or (None, company_name)
    """
    import io, csv
    profile_url = "https://download.cms.gov/openpayments/SMRY_RPTS_P01232026_01102026/PBLCTN_RPTG_ORG_PRFL_SRCH_P01232026_01102026.csv"
    try:
        r = requests.get(profile_url, timeout=30)
        r.raise_for_status()
        content = r.content.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(content))
        name_lower = company_name.lower().strip()
        best_match = None

        name_fields = [
            "AMGPO_Making_Payment_Name",
            "AMGPO_Making_Payment_Alternate_Name1",
            "AMGPO_Making_Payment_Alternate_Name2",
            "AMGPO_Making_Payment_Alternate_Name3",
            "AMGPO_Making_Payment_Alternate_Name4",
            "AMGPO_Making_Payment_Alternate_Name5",
        ]

        for row in reader:
            cid = row.get("AMGPO_Making_Payment_ID", "").strip()
            for field in name_fields:
                stored = row.get(field, "").strip()
                if not stored:
                    continue
                if stored.lower() == name_lower:
                    # Exact match (case-insensitive)
                    return cid, stored
                if name_lower in stored.lower() and best_match is None:
                    best_match = (cid, stored)

        if best_match:
            return best_match

    except Exception:
        pass
    return None, company_name


def fetch_payments(company_name: str) -> dict:
    """
    Fetch Open Payments summary data by downloading pre-built CMS summary CSVs.
    These are small files (~6K rows) aggregated by company and payment type.
    Uses the company numeric ID (amgpo_id) for reliable filtering.

    If no CIK provided, looks up company ID from the reporting entity profile CSV.
    """
    import io, csv

    # Step 1: resolve company ID
    # Intuitive Surgical's known ID is 100000005384 — but we look it up dynamically
    company_id, resolved_name = _lookup_company_id(company_name)

    if not company_id:
        return {
            "error": (f"Could not find '{company_name}' in Open Payments company registry. "
                      "Check the exact legal name at openpaymentsdata.cms.gov."),
            "resolved_name": company_name,
        }

    # Step 2: fetch summary rows for each year
    by_year  = {}
    by_type  = {}
    total_paid = 0.0
    record_count = 0

    for year, info in SUMMARY_DATASETS.items():
        rows = _fetch_summary_csv(info["csv_url"], company_id)
        year_total = 0.0
        for row in rows:
            # Field names vary by file version
            amt = float(
                row.get("Total_Amount") or row.get("total_amount") or
                row.get("TOTAL_AMOUNT") or 0
            )
            code = (row.get("Nature_Of_Payment_Type_Code") or
                    row.get("nature_of_payment_type_code") or
                    row.get("NATURE_OF_PAYMENT_TYPE_CODE") or "").strip()
            n = int(
                row.get("Number_of_Transaction") or row.get("number_of_transaction") or
                row.get("NUMBER_OF_TRANSACTION") or 0
            )
            year_total   += amt
            total_paid   += amt
            record_count += n
            ptype = PAYMENT_TYPE_CODES.get(code, f"Type {code}")
            by_type[ptype] = by_type.get(ptype, 0.0) + amt

        if year_total > 0:
            by_year[str(year)] = year_total

    if not by_year:
        return {
            "error": (f"Found company ID {company_id} but no payment records in summary files. "
                      "The company may not have reportable payments in 2022-2024."),
            "resolved_name": resolved_name,
            "company_id": company_id,
        }

    # Step 3: fetch KOL data from covered-recipient summary CSV
    top_kols = []
    by_state  = {}
    physicians = {}

    for year, kol_url in KOL_DATASETS.items():
        rows = _fetch_kol_csv(kol_url, company_id)
        for row in rows:
            first = (row.get("covered_recipient_profile_first_name") or
                     row.get("Covered_Recipient_Profile_First_Name") or "").strip()
            last  = (row.get("covered_recipient_profile_last_name") or
                     row.get("Covered_Recipient_Profile_Last_Name") or "").strip()
            name  = f"{first} {last}".strip()
            amt   = float(row.get("total_amount") or row.get("Total_Amount") or 0)
            n     = int(row.get("number_of_transaction") or row.get("Number_of_Transaction") or 0)
            state = (row.get("recipient_state") or row.get("Recipient_State") or "Unknown").strip()

            if len(name) > 2:
                if name not in physicians:
                    physicians[name] = {"total": 0.0, "count": 0, "specialty": "", "state": state}
                physicians[name]["total"] += amt
                physicians[name]["count"] += n

            if state and state != "Unknown":
                by_state[state] = by_state.get(state, 0.0) + amt

    top_kols = sorted(physicians.items(), key=lambda x: x[1]["total"], reverse=True)[:20]

    return {
        "resolved_name":  resolved_name,
        "company_id":     company_id,
        "total_paid":     total_paid,
        "record_count":   record_count,
        "by_year":        dict(sorted(by_year.items())),
        "by_type":        dict(sorted(by_type.items(), key=lambda x: x[1], reverse=True)),
        "by_state":       dict(sorted(by_state.items(), key=lambda x: x[1], reverse=True)),
        "top_kols":       top_kols,
        "cms_url":        f"https://openpaymentsdata.cms.gov/company/{company_id}",
        "data_note":      None,
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
