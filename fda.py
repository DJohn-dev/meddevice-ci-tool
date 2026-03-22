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
