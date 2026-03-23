"""
Medical Device Competitive Intelligence Tool
Streamlit — light theme, server-side API calls
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import urllib.parse

from data_modules import (
    fetch_fei, fetch_510k, fetch_pma, fetch_maude, fetch_recalls,
    fetch_trials, fetch_payments,
    fetch_sec, fetch_spending, fetch_nih,
)

st.set_page_config(
    page_title="MedDevice CI Tool",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');
  html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
  .sec-header {
    display: flex; align-items: center; gap: 10px;
    border-bottom: 2px solid #e2e8f0;
    padding-bottom: 8px; margin: 24px 0 16px 0;
  }
  .sec-num {
    background: #1e40af; color: white; font-size: 11px; font-weight: 700;
    border-radius: 4px; padding: 2px 7px;
  }
  .sec-title { font-size: 16px; font-weight: 600; color: #1e293b; }
  .sec-sub   { font-size: 12px; color: #94a3b8; margin-left: auto; }
  .empty-box {
    background: #f8fafc; border: 1px dashed #cbd5e1; border-radius: 8px;
    padding: 24px; text-align: center; color: #64748b; font-size: 13px; margin: 8px 0;
  }
  .tip-box {
    background: #eff6ff; border-left: 3px solid #3b82f6;
    border-radius: 0 6px 6px 0; padding: 10px 14px;
    font-size: 12px; color: #1e40af; margin: 8px 0 16px 0; line-height: 1.6;
  }
  .welcome {
    background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px;
    padding: 48px; text-align: center; margin-top: 40px;
  }
  div[data-testid="metric-container"] { background: #f8fafc; border-radius: 8px; }
  .stTabs [aria-selected="true"] { color: #1e40af !important; border-bottom-color: #1e40af !important; }
</style>
""", unsafe_allow_html=True)


# ── Helpers ───────────────────────────────────────────────────────────────────

def fmt_date(s):
    if not s or s == "—": return "—"
    s = str(s).replace("-", "")
    if len(s) >= 8: return f"{s[4:6]}/{s[6:8]}/{s[:4]}"
    return s

def fmt_usd(n):
    try:
        n = float(n)
        if n >= 1_000_000: return f"${n/1_000_000:.1f}M"
        if n >= 1_000:     return f"${n/1_000:.0f}K"
        return f"${n:.0f}"
    except Exception: return "—"

def section_header(num, icon, title, subtitle=""):
    st.markdown(f"""
    <div class="sec-header">
      <span class="sec-num">{num:02d}</span>
      <span style="font-size:18px">{icon}</span>
      <span class="sec-title">{title}</span>
      <span class="sec-sub">{subtitle}</span>
    </div>""", unsafe_allow_html=True)

def empty_state(msg, url=None, label=None):
    link = f'<br><a href="{url}" target="_blank" style="color:#3b82f6">{label} →</a>' if url else ""
    st.markdown(f'<div class="empty-box">{msg}{link}</div>', unsafe_allow_html=True)

def tip(msg):
    st.markdown(f'<div class="tip-box">💡 {msg}</div>', unsafe_allow_html=True)

def metric_row(metrics):
    cols = st.columns(len(metrics))
    for col, (label, value, *_) in zip(cols, metrics):
        col.metric(label, value)

def plotly_config():
    return dict(
        plot_bgcolor="white", paper_bgcolor="white",
        font=dict(family="Inter", color="#475569", size=11),
        title_font=dict(color="#1e293b", size=13),
        xaxis=dict(gridcolor="#f1f5f9", linecolor="#e2e8f0"),
        yaxis=dict(gridcolor="#f1f5f9", linecolor="#e2e8f0"),
        margin=dict(t=40, b=20, l=10, r=10),
    )


# ── Data loading ──────────────────────────────────────────────────────────────

@st.cache_data(ttl=3600, show_spinner=False)
def load_all_data(company_name, company_type, cik, sections):
    data = {}
    if "fei"      in sections: data["fei"]      = fetch_fei(company_name)
    if "510k"     in sections:
        data["510k"] = fetch_510k(company_name)
        data["pma"]  = fetch_pma(company_name)
    if "maude"    in sections: data["maude"]    = fetch_maude(company_name)
    if "recalls"  in sections: data["recalls"]  = fetch_recalls(company_name)
    if "trials"   in sections: data["trials"]   = fetch_trials(company_name)
    if "payments" in sections: data["payments"] = fetch_payments(company_name)
    if "sec"      in sections and cik:
        data["sec"] = fetch_sec(cik)
    if "spending" in sections:
        data["spending"] = fetch_spending(company_name)
        data["nih"]      = fetch_nih(company_name)
    return data


# ── Section renderers ─────────────────────────────────────────────────────────

def render_fei(data, num):
    section_header(num, "🏢", "FDA Company Identity", "Registration & Listing")
    d    = data.get("fei", {})
    ests = d.get("establishments", [])
    prods= d.get("products", [])
    if not ests:
        name = st.session_state.get("company_name", "")
        empty_state(
            "No FDA establishment records found. FDA stores names in ALL CAPS — try searching directly:",
            f"https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfrl/rl.cfm?start_search=1&establishment_name={urllib.parse.quote(name)}",
            "Search FDA Establishment Registration Database",
        )
        return
    metric_row([("Establishments", len(ests)), ("Product Lines", len(prods)), ("Total Records", d.get("total","—"))])
    df = pd.DataFrame(ests)
    df.columns = ["FEI Number", "Name", "City / Country", "Status"]
    st.dataframe(df, use_container_width=True, hide_index=True)
    if prods:
        with st.expander(f"Product codes ({len(prods)} shown)"):
            dfp = pd.DataFrame(prods)
            dfp.columns = ["Product Code", "Device Name", "Class"]
            st.dataframe(dfp, use_container_width=True, hide_index=True)


def render_510k(data, num):
    section_header(num, "🔵", "FDA Regulatory History", "510(k) Clearances & PMA Approvals")
    d510   = data.get("510k", {})
    dpma   = data.get("pma",  {})
    items  = d510.get("items", [])
    pitems = dpma.get("items", [])
    metric_row([("Total 510(k)s", f"{d510.get('total',0):,}"), ("Shown", len(items)), ("PMA Approvals", len(pitems))])
    tab1, tab2 = st.tabs(["510(k) Clearances", "PMA Approvals"])
    with tab1:
        if items:
            df = pd.DataFrame([{"Date": fmt_date(i["decision_date"]), "K#": i["k_number"],
                "Device": i["device_name"][:65], "Code": i["product_code"],
                "Decision": i["decision_code"], "Link": i.get("url","")} for i in items])
            st.dataframe(df, use_container_width=True, hide_index=True,
                column_config={"Link": st.column_config.LinkColumn("Link", display_text="View →")})
        else:
            empty_state("No 510(k) records matched.",
                "https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfpmn/pmn.cfm",
                "Search 510(k) Database manually")
    with tab2:
        if pitems:
            df = pd.DataFrame([{"Date": fmt_date(i["decision_date"]), "PMA#": i["pma_number"],
                "Device": i["device_name"][:65], "Decision": i["decision_code"],
                "Link": i.get("url","")} for i in pitems])
            st.dataframe(df, use_container_width=True, hide_index=True,
                column_config={"Link": st.column_config.LinkColumn("Link", display_text="View →")})
        else:
            empty_state("No PMA approvals found.",
                "https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfpma/pma.cfm",
                "Search PMA Database manually")


def render_maude(data, num):
    section_header(num, "🔴", "Safety Profile", "MAUDE Adverse Event Reports")
    d     = data.get("maude", {})
    items = d.get("items", [])
    if not items:
        empty_state("No MAUDE records matched. The manufacturer name in MAUDE may differ.",
            "https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfmaude/search.cfm",
            "Search MAUDE manually")
        return
    metric_row([("Total MAUDE Reports", f"{d.get('total',0):,}"), ("Shown (recent 25)", len(items))])
    df = pd.DataFrame([{"Date": fmt_date(i["date"]), "Event Type": i["event_type"],
        "Device": i["brand_name"][:45], "Description": i["description"][:130]} for i in items])
    st.dataframe(df, use_container_width=True, hide_index=True)


def render_recalls(data, num):
    section_header(num, "🟠", "Recall History", "FDA Device Recalls")
    d     = data.get("recalls", {})
    items = d.get("items", [])
    if not items:
        empty_state("No recall records found for this company name.",
            "https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfRES/res.cfm",
            "Search FDA Recall Database manually")
        return
    classes = {}
    for i in items:
        classes[i["class"]] = classes.get(i["class"], 0) + 1
    metric_row([("Total Recalls", f"{d.get('total',0):,}"),
        ("Class I (High)", classes.get("Class I",0)),
        ("Class II (Med)", classes.get("Class II",0)),
        ("Class III (Low)",classes.get("Class III",0))])
    df = pd.DataFrame([{"Date": fmt_date(i["date"]), "Class": i["class"],
        "Product": i["product"][:60], "Reason": i["reason"][:90], "Status": i["status"]} for i in items])
    st.dataframe(df, use_container_width=True, hide_index=True)


def render_trials(data, num):
    section_header(num, "🟢", "Pipeline Intelligence", "ClinicalTrials.gov")
    d     = data.get("trials", {})
    items = d.get("items", [])
    if not items:
        name = st.session_state.get("company_name", "")
        empty_state("No clinical trials found for this sponsor name.",
            f"https://clinicaltrials.gov/search?spons={urllib.parse.quote(name)}",
            "Search ClinicalTrials.gov manually")
        return
    statuses = {}
    for i in items:
        statuses[i["status"]] = statuses.get(i["status"], 0) + 1
    metric_row([("Total Studies", f"{d.get('total',0):,}"),
        ("Recruiting", statuses.get("RECRUITING",0)),
        ("Active", statuses.get("ACTIVE_NOT_RECRUITING",0)),
        ("Completed", statuses.get("COMPLETED",0))])
    if statuses:
        fig = px.bar(x=list(statuses.values()), y=list(statuses.keys()),
            orientation="h", text=list(statuses.values()),
            color_discrete_sequence=["#3b82f6"])
        fig.update_traces(textposition="outside")
        fig.update_layout(**plotly_config(), height=180, showlegend=False, xaxis_title="", yaxis_title="")
        st.plotly_chart(fig, use_container_width=True)
    df = pd.DataFrame([{"NCT ID": i["nct_id"], "Title": i["title"][:70],
        "Phase": i["phase"], "Status": i["status"], "Enrollment": i["enrollment"],
        "Start": i["start"], "Conditions": i["conditions"][:55], "Link": i["url"]} for i in items])
    st.dataframe(df, use_container_width=True, hide_index=True,
        column_config={"Link": st.column_config.LinkColumn("Link", display_text="View →")})


def render_payments(data, num):
    section_header(num, "🩺", "KOL & Commercial Intelligence", "CMS Open Payments")
    d = data.get("payments", {})
    if d.get("error"):
        empty_state(d["error"])
        name = st.session_state.get("company_name", "")
        tip(f'Search Open Payments directly: <a href="https://openpaymentsdata.cms.gov/search?searchType=Company&Name={urllib.parse.quote(name)}" target="_blank">openpaymentsdata.cms.gov →</a>')
        return

    total    = d.get("total_paid", 0)
    by_year  = d.get("by_year",  {})
    by_type  = d.get("by_type",  {})
    by_state = d.get("by_state", {})
    top_kols = d.get("top_kols", [])
    resolved = d.get("resolved_name", "")
    cms_url  = d.get("cms_url", "")

    metric_row([("Total Paid (sampled)", fmt_usd(total)),
        ("Payment Records", f"{d.get('record_count',0):,}"),
        ("Physicians", len(top_kols)),
        ("Payment Categories", len(by_type))])
    if cms_url:
        st.caption(f"Resolved as **{resolved}** · [Full profile on CMS Open Payments →]({cms_url})")

    tab1, tab2, tab3, tab4 = st.tabs(["📈 Trend by Year", "💳 Payment Types", "🗺 Geography", "👨‍⚕️ Top KOLs"])

    with tab1:
        if by_year:
            fig = go.Figure(go.Bar(x=list(by_year.keys()), y=list(by_year.values()),
                marker_color="#3b82f6", text=[fmt_usd(v) for v in by_year.values()], textposition="outside"))
            fig.update_layout(**plotly_config(), title="Total Payments by Program Year",
                xaxis_title="Year", yaxis_title="USD", height=320)
            st.plotly_chart(fig, use_container_width=True)

    with tab2:
        if by_type:
            fig = px.pie(names=list(by_type.keys()), values=list(by_type.values()),
                hole=0.4, color_discrete_sequence=px.colors.qualitative.Pastel)
            fig.update_layout(**plotly_config(), height=360)
            st.plotly_chart(fig, use_container_width=True)
            df_t = pd.DataFrame([{"Payment Type": k, "Total": fmt_usd(v), "_r": v}
                for k,v in by_type.items()]).sort_values("_r", ascending=False).drop(columns="_r")
            st.dataframe(df_t, use_container_width=True, hide_index=True)

    with tab3:
        us_states = {k:v for k,v in by_state.items()
            if k and len(k)==2 and k.isalpha() and k not in ("XX","PR","GU","VI","AS","MP")}
        if us_states:
            fig = go.Figure(go.Choropleth(locations=list(us_states.keys()),
                z=list(us_states.values()), locationmode="USA-states",
                colorscale="Blues", colorbar_title="USD"))
            fig.update_layout(geo=dict(scope="usa", showlakes=True, lakecolor="white"),
                **plotly_config(), title="KOL Payments by State", height=420)
            st.plotly_chart(fig, use_container_width=True)
        if not us_states and not by_state:
            st.info("Geographic breakdown requires individual payment records. "
                    "View the full breakdown at the CMS Open Payments link above.")
        else:
            df_s = pd.DataFrame([{"State": k, "Total Paid": fmt_usd(v), "_r": v}
                for k,v in by_state.items() if k and k != "Unknown"]
                ).sort_values("_r", ascending=False).drop(columns="_r").head(20)
            if not df_s.empty:
                st.dataframe(df_s, use_container_width=True, hide_index=True)

    with tab4:
        if top_kols:
            rows = [{"Physician": n, "Specialty": i["specialty"][:50] or "—",
                "State": i["state"] or "—", "Total Paid": fmt_usd(i["total"]),
                "Transactions": i["count"], "_r": i["total"]} for n,i in top_kols]
            df_k = pd.DataFrame(rows).sort_values("_r", ascending=False).drop(columns="_r")
            st.dataframe(df_k, use_container_width=True, hide_index=True)
            names  = [r["Physician"] for r in rows[:15]]
            totals = [r["_r"] for r in sorted(rows, key=lambda x: x["_r"], reverse=True)[:15]]
            fig = go.Figure(go.Bar(x=totals[::-1], y=names[::-1], orientation="h",
                marker_color="#3b82f6", text=[fmt_usd(v) for v in totals[::-1]], textposition="outside"))
            fig.update_layout(**plotly_config(), title="Top 15 KOL Recipients",
                height=480, xaxis_title="Total Paid (USD)")
            st.plotly_chart(fig, use_container_width=True)
        else:
            name = st.session_state.get("company_name", "")
            cms_url = d.get("cms_url", "")
            st.info("Individual KOL records are not available in the summary dataset.")
            if cms_url:
                st.markdown(f"[View individual physician payments on CMS Open Payments →]({cms_url})")

    # Data note (summary files don't include individual KOL records)
    note = d.get("data_note")
    if note:
        st.info(f"ℹ️ {note}")

    st.text_area("KOL Strategy — Analyst Note",
        placeholder="Cross-reference top KOLs with ClinicalTrials.gov PIs. Geographic concentration? Specialty alignment? YoY trend?",
        height=80, key=f"note_payments_{resolved}")


def render_sec(data, num, cik):
    section_header(num, "🟣", "Financial & Corporate", "SEC EDGAR Filings")
    if not cik:
        empty_state("No CIK entered — SEC filings require a CIK number.")
        tip('Find your company\'s CIK: <a href="https://www.sec.gov/cgi-bin/browse-edgar?company=&CIK=&type=10-K&action=getcompany" target="_blank">EDGAR company search →</a><br>'
            'Search by company name, then look for the 10-digit CIK in the results.')
        return
    d = data.get("sec", {})
    if d.get("error"):
        st.error(f"SEC EDGAR error: {d['error']}")
        return
    st.markdown(f"**{d.get('entity_name','')}** &nbsp;·&nbsp; CIK: `{d.get('cik','')}`")
    links = d.get("links", {})
    cols  = st.columns(len(links))
    for col, (label, url) in zip(cols, links.items()):
        col.link_button(label, url, use_container_width=True)
    items = d.get("items", [])
    if items:
        st.markdown("**Recent Filings**")
        df = pd.DataFrame([{"Form": i["form"], "Filed": i["date"],
            "Period": i["period"], "Link": i["url"]} for i in items])
        st.dataframe(df, use_container_width=True, hide_index=True,
            column_config={"Link": st.column_config.LinkColumn("Filing", display_text="View →")})
    st.text_area("Financial Intelligence — Analyst Note",
        placeholder="Revenue trend, R&D spend %, gross margin, M&A activity, cash position, key risks...",
        height=80, key=f"note_sec_{cik}")


def render_spending(data, num):
    section_header(num, "💰", "Financial Intelligence", "Federal Contracts · Grants · NIH")
    contracts = data.get("spending", {}).get("contracts", [])
    grants    = data.get("spending", {}).get("grants",    [])
    nih_items = data.get("nih",      {}).get("items",     [])
    c_total   = data.get("spending", {}).get("contract_total", 0)
    g_total   = data.get("spending", {}).get("grant_total",    0)
    n_total   = data.get("nih",      {}).get("total",          0)
    metric_row([("Federal Contracts", fmt_usd(c_total)),
        ("Federal Grants", fmt_usd(g_total)), ("NIH Awards", fmt_usd(n_total))])
    tab1, tab2, tab3 = st.tabs(["Contracts", "Grants", "NIH RePORTER"])
    with tab1:
        if contracts:
            df = pd.DataFrame([{"Award ID": c.get("Award ID","—"), "Amount": fmt_usd(c.get("Award Amount",0)),
                "Agency": str(c.get("Awarding Agency","—"))[:50], "Type": c.get("Award Type","—"),
                "Start": c.get("Start Date","—")} for c in contracts])
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            empty_state("No federal contracts found.")
    with tab2:
        if grants:
            df = pd.DataFrame([{"Award ID": g.get("Award ID","—"), "Amount": fmt_usd(g.get("Award Amount",0)),
                "Agency": str(g.get("Awarding Agency","—"))[:50], "Start": g.get("Start Date","—")} for g in grants])
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            empty_state("No federal grants found.")
    with tab3:
        if nih_items:
            df = pd.DataFrame([{"Year": n.get("fiscal_year","—"), "Amount": fmt_usd(n.get("award_amount",0)),
                "Title": str(n.get("project_title","—"))[:80],
                "PI": (n.get("principal_investigators") or [{}])[0].get("full_name","—")} for n in nih_items])
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            empty_state("No NIH grants found.")


# ── Render dispatcher ─────────────────────────────────────────────────────────

def render_section(sec, data, num, cik=""):
    if   sec == "fei":      render_fei(data, num)
    elif sec == "510k":     render_510k(data, num)
    elif sec == "maude":    render_maude(data, num)
    elif sec == "recalls":  render_recalls(data, num)
    elif sec == "trials":   render_trials(data, num)
    elif sec == "payments": render_payments(data, num)
    elif sec == "sec":      render_sec(data, num, cik)
    elif sec == "spending": render_spending(data, num)


def render_company(company_name, company_type, cik, sections, data):
    section_order = ["fei","510k","maude","recalls","trials","payments","sec","spending"]
    num = 1
    for sec in section_order:
        if sec not in sections: continue
        if sec == "sec"      and company_type == "private": continue
        if sec == "spending" and company_type == "public":  continue
        render_section(sec, data, num, cik)
        st.divider()
        num += 1


# ── Sidebar ───────────────────────────────────────────────────────────────────

def company_form(prefix, label):
    st.markdown(f"#### {label}")
    name  = st.text_input("Company Name", key=f"{prefix}_name",
                           placeholder="e.g. Intuitive Surgical, Inc.")
    ctype = st.radio("Company Type", ["Public","Private"],
                     horizontal=True, key=f"{prefix}_type").lower()
    cik = ""
    if ctype == "public":
        cik = st.text_input("CIK (for SEC filings)", key=f"{prefix}_cik",
                             placeholder="e.g. 1035267")
        if not cik:
            st.caption("[Find CIK on EDGAR →](https://www.sec.gov/cgi-bin/browse-edgar?company=&CIK=&type=10-K&action=getcompany)")
    st.markdown("**Include sections:**")
    cols = st.columns(2)
    section_opts = [
        ("fei",      "🏢 FDA Registration"),
        ("510k",     "🔵 510(k) / PMA"),
        ("maude",    "🔴 MAUDE"),
        ("recalls",  "🟠 Recalls"),
        ("trials",   "🟢 Trials"),
        ("payments", "🩺 Open Payments"),
        ("sec",      "🟣 SEC EDGAR") if ctype == "public" else ("spending", "💰 Fed Spending"),
    ]
    sections = []
    for i, (key, lbl) in enumerate(section_opts):
        if cols[i % 2].checkbox(lbl, value=True, key=f"{prefix}_{key}"):
            sections.append(key)
    return name, ctype, cik, tuple(sections)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    st.title("🔬 Medical Device CI Tool")
    st.caption("FDA · ClinicalTrials.gov · CMS Open Payments · SEC EDGAR · USASpending · NIH")

    with st.sidebar:
        st.header("Configuration")
        name1, type1, cik1, secs1 = company_form("c1", "Company")
        run = st.button("▶ Run Analysis", type="primary", use_container_width=True)
        st.divider()
        st.caption("Data cached 1 hour · All calls server-side")

    if not run:
        st.markdown("""
        <div class="welcome">
          <div style="font-size:48px;margin-bottom:16px">🔬</div>
          <h3 style="color:#1e293b;margin-bottom:8px">Enter a company name to begin</h3>
          <p style="color:#64748b;max-width:480px;margin:0 auto">
            Pulls live data from FDA, ClinicalTrials.gov, CMS Open Payments, SEC EDGAR,
            USASpending, and NIH. All API calls run server-side.
          </p>
        </div>""", unsafe_allow_html=True)
        return

    if not name1:
        st.error("Please enter a company name.")
        return

    st.session_state["company_name"] = name1

    with st.spinner(f"Fetching data for **{name1}**…"):
        data1 = load_all_data(name1, type1, cik1, secs1)
    st.subheader(name1)
    render_company(name1, type1, cik1, secs1, data1)


if __name__ == "__main__":
    main()
