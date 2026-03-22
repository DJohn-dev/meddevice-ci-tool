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
