"""
Medical Device Competitive Intelligence Tool
Streamlit app — all API calls server-side (no CORS restrictions)
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

from modules.fda         import fetch_fei, fetch_510k, fetch_pma, fetch_maude, fetch_recalls
from modules.trials      import fetch_trials
from modules.payments    import fetch_payments
from modules.sec_spending import fetch_sec, fetch_spending, fetch_nih

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="MedDevice CI Tool",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@300;400;500;600&display=swap');

  html, body, [class*="css"] {
    font-family: 'IBM Plex Sans', sans-serif;
  }
  .stApp { background: #0f1117; }

  /* Sidebar */
  [data-testid="stSidebar"] {
    background: #13151f;
    border-right: 1px solid #1e2235;
  }
  [data-testid="stSidebar"] * { color: #c8cde0 !important; }

  /* Cards */
  .ci-card {
    background: #161b2e;
    border: 1px solid #1e2235;
    border-radius: 10px;
    padding: 20px 24px;
    margin-bottom: 16px;
  }
  .ci-card-title {
    font-size: 11px;
    font-weight: 600;
    letter-spacing: .1em;
    text-transform: uppercase;
    color: #4a6fa5;
    margin-bottom: 4px;
  }
  .ci-card-value {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 26px;
    font-weight: 600;
    color: #e2e8f8;
  }
  .ci-card-sub {
    font-size: 11px;
    color: #5a6585;
    margin-top: 2px;
  }

  /* Section headers */
  .section-header {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 12px 0 8px 0;
    border-bottom: 1px solid #1e2235;
    margin-bottom: 16px;
  }
  .section-header-num {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 11px;
    color: #4a6fa5;
    min-width: 24px;
  }
  .section-header-title {
    font-size: 14px;
    font-weight: 600;
    color: #e2e8f8;
  }
  .section-header-sub {
    font-size: 11px;
    color: #5a6585;
    margin-left: auto;
  }

  /* Badges */
  .badge {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 600;
    font-family: 'IBM Plex Mono', monospace;
  }
  .badge-green  { background: #0d2e1a; color: #4ade80; border: 1px solid #166534; }
  .badge-red    { background: #2e0d0d; color: #f87171; border: 1px solid #991b1b; }
  .badge-yellow { background: #2e2210; color: #fbbf24; border: 1px solid #92400e; }
  .badge-blue   { background: #0d1e3a; color: #60a5fa; border: 1px solid #1e3a6e; }
  .badge-gray   { background: #1a1e2e; color: #9ca3af; border: 1px solid #374151; }

  /* Comparison header */
  .compare-banner {
    background: linear-gradient(135deg, #0d1e3a 0%, #13151f 100%);
    border: 1px solid #1e3a6e;
    border-radius: 10px;
    padding: 16px 24px;
    margin-bottom: 20px;
    display: flex;
    align-items: center;
    gap: 16px;
  }

  /* Analyst note box */
  .analyst-note-label {
    font-size: 10px;
    font-weight: 600;
    letter-spacing: .1em;
    text-transform: uppercase;
    color: #4a6fa5;
    margin-bottom: 4px;
  }

  /* Streamlit overrides */
  .stDataFrame { border: 1px solid #1e2235; border-radius: 8px; }
  div[data-testid="metric-container"] {
    background: #161b2e;
    border: 1px solid #1e2235;
    border-radius: 8px;
    padding: 12px 16px;
  }
  div[data-testid="metric-container"] label { color: #5a6585 !important; font-size: 11px !important; }
  div[data-testid="metric-container"] div[data-testid="stMetricValue"] {
    font-family: 'IBM Plex Mono', monospace;
    color: #e2e8f8 !important;
    font-size: 22px !important;
  }
  .stTabs [data-baseweb="tab"] {
    font-size: 12px;
    color: #5a6585;
  }
  .stTabs [aria-selected="true"] {
    color: #60a5fa !important;
    border-bottom-color: #60a5fa !important;
  }
  h1, h2, h3, h4 { color: #e2e8f8 !important; }
  p, li, span { color: #c8cde0; }
  .stMarkdown p { color: #9ca3af; font-size: 13px; }
  a { color: #60a5fa !important; }
  .stAlert { border-radius: 8px; }
</style>
""", unsafe_allow_html=True)


# ── Helpers ───────────────────────────────────────────────────────────────────
def fmt_date(s: str) -> str:
    if not s or s == "—":
        return "—"
    s = str(s).replace("-", "")
    if len(s) >= 8:
        return f"{s[4:6]}/{s[6:8]}/{s[:4]}"
    return s


def fmt_usd(n) -> str:
    try:
        n = float(n)
        if n >= 1_000_000:
            return f"${n/1_000_000:.1f}M"
        if n >= 1_000:
            return f"${n/1_000:.0f}K"
        return f"${n:.0f}"
    except Exception:
        return "—"


def section_header(num: int, icon: str, title: str, subtitle: str = ""):
    st.markdown(f"""
    <div class="section-header">
      <span class="section-header-num">{num:02d}</span>
      <span style="font-size:16px">{icon}</span>
      <span class="section-header-title">{title}</span>
      <span class="section-header-sub">{subtitle}</span>
    </div>""", unsafe_allow_html=True)


def metric_row(metrics: list):
    """metrics = list of (label, value, delta=None)"""
    cols = st.columns(len(metrics))
    for col, (label, value, *rest) in zip(cols, metrics):
        delta = rest[0] if rest else None
        col.metric(label, value, delta)


def badge(text: str, color: str = "blue") -> str:
    return f'<span class="badge badge-{color}">{text}</span>'


def plotly_dark_config():
    return dict(
        plot_bgcolor="#161b2e",
        paper_bgcolor="#161b2e",
        font=dict(family="IBM Plex Sans", color="#9ca3af", size=11),
        title_font=dict(color="#e2e8f8", size=13),
        xaxis=dict(gridcolor="#1e2235", linecolor="#1e2235", tickcolor="#5a6585"),
        yaxis=dict(gridcolor="#1e2235", linecolor="#1e2235", tickcolor="#5a6585"),
        legend=dict(bgcolor="#13151f", bordercolor="#1e2235"),
        margin=dict(t=40, b=20, l=20, r=20),
    )


@st.cache_data(ttl=3600, show_spinner=False)
def load_all_data(company_name: str, company_type: str, cik: str = "", sections: tuple = ()):
    data = {}
    if "fei"      in sections: data["fei"]      = fetch_fei(company_name)
    if "510k"     in sections: data["510k"]      = fetch_510k(company_name)
    if "pma"      in sections: data["pma"]       = fetch_pma(company_name)
    if "maude"    in sections: data["maude"]     = fetch_maude(company_name)
    if "recalls"  in sections: data["recalls"]   = fetch_recalls(company_name)
    if "trials"   in sections: data["trials"]    = fetch_trials(company_name)
    if "payments" in sections: data["payments"]  = fetch_payments(company_name)
    if "sec"      in sections and cik:
        data["sec"] = fetch_sec(cik)
    if "spending" in sections and company_type == "private":
        data["spending"] = fetch_spending(company_name)
        data["nih"]      = fetch_nih(company_name)
    return data


# ── Section renderers ─────────────────────────────────────────────────────────

def render_fei(data: dict, num: int):
    section_header(num, "🏢", "FDA Company Identity", "Registration & Listing")
    d = data.get("fei", {})
    if d.get("error"):
        st.warning(f"FDA Registration: {d['error']}")
        return
    ests = d.get("establishments", [])
    prods = d.get("products", [])
    if not ests:
        st.info("No FDA establishment records found.")
        return
    metric_row([
        ("Establishments", len(ests)),
        ("Product Lines",  len(prods)),
        ("Total Registrations", d.get("total", "—")),
    ])
    st.markdown("**Establishments**")
    df = pd.DataFrame(ests)
    df.columns = ["FEI", "Name", "City/Country", "Status"]
    st.dataframe(df, use_container_width=True, hide_index=True)
    if prods:
        st.markdown("**Product Codes**")
        dfp = pd.DataFrame(prods[:15])
        dfp.columns = ["Product Code", "Device Name", "Class"]
        st.dataframe(dfp, use_container_width=True, hide_index=True)


def render_510k(data: dict, num: int):
    section_header(num, "🔵", "FDA Regulatory History", "510(k) Clearances & PMA Approvals")
    d510 = data.get("510k", {})
    dpma = data.get("pma", {})
    items_510 = d510.get("items", [])
    items_pma = dpma.get("items", [])
    metric_row([
        ("Total 510(k)s", f"{d510.get('total', 0):,}"),
        ("Shown",         len(items_510)),
        ("PMA Approvals", len(items_pma)),
    ])
    tab1, tab2 = st.tabs(["510(k) Clearances", "PMA Approvals"])
    with tab1:
        if items_510:
            rows = []
            for i in items_510:
                rows.append({
                    "Date":         fmt_date(i["decision_date"]),
                    "K#":           i["k_number"],
                    "Device":       i["device_name"][:60],
                    "Code":         i["product_code"],
                    "Decision":     i["decision_code"],
                    "Link":         i.get("url", ""),
                })
            df = pd.DataFrame(rows)
            st.dataframe(df, use_container_width=True, hide_index=True,
                         column_config={"Link": st.column_config.LinkColumn("Link", display_text="View")})
        else:
            st.info("No 510(k) records found.")
    with tab2:
        if items_pma:
            rows = [{"Date": fmt_date(i["decision_date"]), "PMA#": i["pma_number"],
                     "Device": i["device_name"][:60], "Decision": i["decision_code"],
                     "Link": i.get("url","")} for i in items_pma]
            df = pd.DataFrame(rows)
            st.dataframe(df, use_container_width=True, hide_index=True,
                         column_config={"Link": st.column_config.LinkColumn("Link", display_text="View")})
        else:
            st.info("No PMA records found.")


def render_maude(data: dict, num: int):
    section_header(num, "🔴", "Safety Profile", "MAUDE Adverse Event Reports")
    d = data.get("maude", {})
    items = d.get("items", [])
    metric_row([
        ("Total MAUDE Reports", f"{d.get('total', 0):,}"),
        ("Shown (recent)",      len(items)),
    ])
    if items:
        df = pd.DataFrame([{
            "Date":       fmt_date(i["date"]),
            "Event Type": i["event_type"],
            "Device":     i["brand_name"][:40],
            "Description":i["description"][:120],
        } for i in items])
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No MAUDE records found.")


def render_recalls(data: dict, num: int):
    section_header(num, "🟠", "Recall History", "FDA Device Recalls")
    d = data.get("recalls", {})
    items = d.get("items", [])
    metric_row([
        ("Total Recalls", f"{d.get('total', 0):,}"),
        ("Shown (recent)", len(items)),
    ])
    if items:
        df = pd.DataFrame([{
            "Date":    fmt_date(i["date"]),
            "Class":   i["class"],
            "Product": i["product"][:60],
            "Reason":  i["reason"][:80],
            "Status":  i["status"],
        } for i in items])
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No recall records found.")


def render_trials(data: dict, num: int):
    section_header(num, "🟢", "Pipeline Intelligence", "ClinicalTrials.gov")
    d = data.get("trials", {})
    items = d.get("items", [])
    statuses = {}
    for i in items:
        s = i["status"]
        statuses[s] = statuses.get(s, 0) + 1
    metric_row([
        ("Total Studies",    f"{d.get('total', 0):,}"),
        ("Recruiting",       statuses.get("RECRUITING", 0)),
        ("Active",           statuses.get("ACTIVE_NOT_RECRUITING", 0)),
        ("Completed",        statuses.get("COMPLETED", 0)),
    ])
    if items:
        # Status breakdown bar
        if statuses:
            fig = px.bar(
                x=list(statuses.values()), y=list(statuses.keys()),
                orientation="h", labels={"x": "Count", "y": ""},
                color=list(statuses.keys()),
                color_discrete_sequence=["#3b82f6","#10b981","#f59e0b","#6b7280","#ef4444","#8b5cf6"],
            )
            fig.update_layout(**plotly_dark_config(), height=200, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

        df = pd.DataFrame([{
            "NCT ID":     i["nct_id"],
            "Title":      i["title"][:70],
            "Phase":      i["phase"],
            "Status":     i["status"],
            "Enrollment": i["enrollment"],
            "Start":      i["start"],
            "Conditions": i["conditions"][:60],
            "Link":       i["url"],
        } for i in items])
        st.dataframe(df, use_container_width=True, hide_index=True,
                     column_config={"Link": st.column_config.LinkColumn("ClinicalTrials", display_text="View")})
    else:
        st.info("No clinical trials found.")


def render_payments(data: dict, num: int):
    section_header(num, "🩺", "KOL & Commercial Intelligence", "CMS Open Payments")
    d = data.get("payments", {})

    if d.get("error"):
        st.warning(d["error"])
        st.markdown(f"[Search Open Payments manually →]({d.get('cms_url', 'https://openpaymentsdata.cms.gov')})")
        return

    total      = d.get("total_paid", 0)
    by_year    = d.get("by_year", {})
    by_type    = d.get("by_type", {})
    by_state   = d.get("by_state", {})
    top_kols   = d.get("top_kols", [])
    resolved   = d.get("resolved_name", "")
    cms_url    = d.get("cms_url", "")
    records    = d.get("record_count", 0)

    metric_row([
        ("Total Paid (sampled)",  fmt_usd(total)),
        ("Payment Records",       f"{records:,}"),
        ("Unique Physicians",     len(top_kols)),
        ("Payment Categories",    len(by_type)),
    ])
    if cms_url:
        st.markdown(f"Resolved as **{resolved}** · [View full profile on CMS →]({cms_url})")

    tab1, tab2, tab3, tab4 = st.tabs(["📈 Trend by Year", "💳 Payment Types", "🗺 Geography", "👨‍⚕️ Top KOLs"])

    with tab1:
        if by_year:
            fig = go.Figure(go.Bar(
                x=list(by_year.keys()),
                y=list(by_year.values()),
                marker_color="#3b82f6",
                text=[fmt_usd(v) for v in by_year.values()],
                textposition="outside",
            ))
            fig.update_layout(**plotly_dark_config(), title="Total Payments by Program Year",
                              xaxis_title="Year", yaxis_title="USD", height=320)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No yearly data available.")

    with tab2:
        if by_type:
            fig = px.pie(
                names=list(by_type.keys()),
                values=list(by_type.values()),
                hole=0.45,
                color_discrete_sequence=px.colors.qualitative.Set3,
            )
            fig.update_layout(**plotly_dark_config(), title="Payment Type Breakdown", height=380)
            st.plotly_chart(fig, use_container_width=True)
            df_type = pd.DataFrame([
                {"Payment Type": k, "Total": fmt_usd(v), "Raw": v}
                for k, v in by_type.items()
            ]).sort_values("Raw", ascending=False).drop(columns="Raw")
            st.dataframe(df_type, use_container_width=True, hide_index=True)
        else:
            st.info("No payment type data available.")

    with tab3:
        if by_state:
            # Filter to US states only
            us_states = {k: v for k, v in by_state.items()
                        if k and len(k) == 2 and k.isalpha() and k not in ("XX","PR","GU","VI","AS","MP")}
            if us_states:
                fig = go.Figure(go.Choropleth(
                    locations=list(us_states.keys()),
                    z=list(us_states.values()),
                    locationmode="USA-states",
                    colorscale=[[0, "#0d1e3a"], [0.5, "#1e4080"], [1, "#3b82f6"]],
                    colorbar=dict(title="USD", tickfont=dict(color="#9ca3af")),
                    marker_line_color="#1e2235",
                ))
                fig.update_layout(
                    geo=dict(scope="usa", bgcolor="#161b2e",
                             lakecolor="#0f1117", landcolor="#1a1f35",
                             showlakes=True, showframe=False),
                    **plotly_dark_config(),
                    title="KOL Payments by State",
                    height=420,
                )
                st.plotly_chart(fig, use_container_width=True)
            # State table
            df_state = pd.DataFrame([
                {"State": k, "Total Paid": fmt_usd(v), "Raw": v}
                for k, v in by_state.items() if k and k != "Unknown"
            ]).sort_values("Raw", ascending=False).drop(columns="Raw").head(20)
            st.dataframe(df_state, use_container_width=True, hide_index=True)
        else:
            st.info("No geographic data available.")

    with tab4:
        if top_kols:
            rows = []
            for name, info in top_kols:
                rows.append({
                    "Physician":    name,
                    "Specialty":    info["specialty"][:50] if info["specialty"] else "—",
                    "State":        info["state"] or "—",
                    "Total Paid":   fmt_usd(info["total"]),
                    "Transactions": info["count"],
                    "Raw":          info["total"],
                })
            df_kols = pd.DataFrame(rows).sort_values("Raw", ascending=False).drop(columns="Raw")
            st.dataframe(df_kols, use_container_width=True, hide_index=True)
            # Horizontal bar
            names  = [r["Physician"] for r in rows[:15]]
            totals = [r["Raw"]       for r in rows[:15]]
            fig = go.Figure(go.Bar(
                x=totals[::-1], y=names[::-1],
                orientation="h",
                marker_color="#3b82f6",
                text=[fmt_usd(v) for v in totals[::-1]],
                textposition="outside",
            ))
            fig.update_layout(**plotly_dark_config(), title="Top 15 KOL Recipients",
                              xaxis_title="Total Paid (USD)", height=500)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No KOL data available.")

    st.text_area("KOL Strategy — Analyst Note",
                 placeholder="Cross-reference top KOLs with ClinicalTrials.gov PIs. "
                             "Geographic concentration? Specialty alignment? YoY trend?",
                 height=80, key=f"note_payments_{resolved}")


def render_sec(data: dict, num: int, cik: str):
    section_header(num, "🟣", "Financial & Corporate", "SEC EDGAR Filings")
    d = data.get("sec", {})
    if not cik:
        st.info("Enter a CIK number in the sidebar to load SEC filings.")
        return
    if d.get("error"):
        st.warning(f"SEC EDGAR: {d['error']}")
        return
    st.markdown(f"**{d.get('entity_name','')}** · CIK: `{d.get('cik','')}`")
    links = d.get("links", {})
    cols = st.columns(len(links))
    for col, (label, url) in zip(cols, links.items()):
        col.markdown(f"[{label} →]({url})")
    items = d.get("items", [])
    if items:
        df = pd.DataFrame([{
            "Form":   i["form"],
            "Filed":  i["date"],
            "Period": i["period"],
            "Link":   i["url"],
        } for i in items])
        st.dataframe(df, use_container_width=True, hide_index=True,
                     column_config={"Link": st.column_config.LinkColumn("Filing", display_text="View")})
    st.text_area("Financial Intelligence — Analyst Note",
                 placeholder="Revenue trend, R&D spend %, gross margin, M&A activity, cash position, key risks...",
                 height=80, key=f"note_sec_{cik}")


def render_spending(data: dict, num: int):
    section_header(num, "💰", "Financial Intelligence", "Federal Contracts · Grants · NIH")
    contracts = data.get("spending", {}).get("contracts", [])
    grants    = data.get("spending", {}).get("grants", [])
    nih       = data.get("nih", {}).get("items", [])
    c_total   = data.get("spending", {}).get("contract_total", 0)
    g_total   = data.get("spending", {}).get("grant_total", 0)
    n_total   = data.get("nih", {}).get("total", 0)
    metric_row([
        ("Federal Contracts", fmt_usd(c_total)),
        ("Federal Grants",    fmt_usd(g_total)),
        ("NIH Awards",        fmt_usd(n_total)),
    ])
    tab1, tab2, tab3 = st.tabs(["Contracts", "Grants", "NIH RePORTER"])
    with tab1:
        if contracts:
            df = pd.DataFrame([{
                "Award ID":  c.get("Award ID","—"),
                "Amount":    fmt_usd(c.get("Award Amount",0)),
                "Agency":    str(c.get("Awarding Agency","—"))[:50],
                "Type":      c.get("Award Type","—"),
                "Start":     c.get("Start Date","—"),
            } for c in contracts])
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No federal contracts found.")
    with tab2:
        if grants:
            df = pd.DataFrame([{
                "Award ID":  g.get("Award ID","—"),
                "Amount":    fmt_usd(g.get("Award Amount",0)),
                "Agency":    str(g.get("Awarding Agency","—"))[:50],
                "Start":     g.get("Start Date","—"),
            } for g in grants])
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No federal grants found.")
    with tab3:
        if nih:
            df = pd.DataFrame([{
                "Year":    n.get("fiscal_year","—"),
                "Amount":  fmt_usd(n.get("award_amount",0)),
                "Title":   str(n.get("project_title","—"))[:80],
                "PI":      str(n.get("principal_investigators",[{}])[0].get("full_name","—"))
                           if n.get("principal_investigators") else "—",
            } for n in nih])
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No NIH grants found.")


def render_company(company_name: str, company_type: str, cik: str,
                   sections: tuple, data: dict, prefix: str = ""):
    """Render all enabled sections for one company."""
    num = 1
    if "fei"      in sections: render_fei(data, num);      num += 1
    if "510k"     in sections: render_510k(data, num);     num += 1; st.divider()
    if "maude"    in sections: render_maude(data, num);    num += 1; st.divider()
    if "recalls"  in sections: render_recalls(data, num);  num += 1; st.divider()
    if "trials"   in sections: render_trials(data, num);   num += 1; st.divider()
    if "payments" in sections: render_payments(data, num); num += 1; st.divider()
    if company_type == "public":
        if "sec" in sections:  render_sec(data, num, cik); num += 1
    else:
        if "spending" in sections: render_spending(data, num)


# ── Sidebar ───────────────────────────────────────────────────────────────────

def sidebar_company_form(prefix: str, label: str) -> tuple:
    """Returns (name, type, cik, sections)"""
    st.markdown(f"### {label}")
    name = st.text_input("Company Name", key=f"{prefix}_name",
                         placeholder="e.g. Intuitive Surgical, Inc.")
    ctype = st.radio("Type", ["Public", "Private"],
                     horizontal=True, key=f"{prefix}_type").lower()
    cik = ""
    if ctype == "public":
        cik = st.text_input("CIK (optional — for SEC filings)",
                            key=f"{prefix}_cik", placeholder="e.g. 1035267")
    st.markdown("**Sections**")
    sections = []
    cols = st.columns(2)
    checks = [
        ("fei",      "🏢 FDA Registration"),
        ("510k",     "🔵 510(k) / PMA"),
        ("maude",    "🔴 MAUDE"),
        ("recalls",  "🟠 Recalls"),
        ("trials",   "🟢 Trials"),
        ("payments", "🩺 Open Payments"),
        ("sec",      "🟣 SEC EDGAR") if ctype == "public" else ("spending", "💰 Fed Spending"),
    ]
    for i, (key, label_s) in enumerate(checks):
        col = cols[i % 2]
        if col.checkbox(label_s, value=True, key=f"{prefix}_{key}"):
            sections.append(key)
    return name, ctype, cik, tuple(sections)


# ── Main app ──────────────────────────────────────────────────────────────────

def main():
    # Header
    st.markdown("""
    <div style="padding: 24px 0 8px 0;">
      <div style="font-family:'IBM Plex Mono',monospace;font-size:11px;color:#4a6fa5;
                  letter-spacing:.15em;text-transform:uppercase;margin-bottom:4px;">
        Medical Device
      </div>
      <div style="font-size:28px;font-weight:600;color:#e2e8f8;line-height:1.2;">
        Competitive Intelligence Tool
      </div>
      <div style="font-size:13px;color:#5a6585;margin-top:4px;">
        FDA · ClinicalTrials · Open Payments · SEC EDGAR · USASpending · NIH
      </div>
    </div>
    """, unsafe_allow_html=True)

    # Sidebar
    with st.sidebar:
        st.markdown("## Configuration")
        mode = st.radio("Mode", ["Single Company", "Compare Two Companies"],
                        key="mode")
        st.divider()

        if mode == "Single Company":
            name1, type1, cik1, secs1 = sidebar_company_form("c1", "Company")
            run = st.button("▶ Run Analysis", type="primary", use_container_width=True)
        else:
            name1, type1, cik1, secs1 = sidebar_company_form("c1", "Company A")
            st.divider()
            name2, type2, cik2, secs2 = sidebar_company_form("c2", "Company B")
            run = st.button("▶ Run Comparison", type="primary", use_container_width=True)

        st.divider()
        st.markdown("""
        <div style="font-size:11px;color:#3a4565;line-height:1.7;">
        Sources: OpenFDA · ClinicalTrials.gov v2<br>
        CMS Open Payments · SEC EDGAR<br>
        USASpending.gov · NIH RePORTER<br><br>
        Data cached 1 hour per query.
        </div>""", unsafe_allow_html=True)

    # Main content
    if not run:
        # Welcome screen
        st.markdown("""
        <div style="background:#161b2e;border:1px solid #1e2235;border-radius:12px;
                    padding:40px;text-align:center;margin-top:40px;">
          <div style="font-size:40px;margin-bottom:16px;">🔬</div>
          <div style="font-size:18px;font-weight:600;color:#e2e8f8;margin-bottom:8px;">
            Enter a company name and click Run Analysis
          </div>
          <div style="font-size:13px;color:#5a6585;max-width:500px;margin:0 auto;line-height:1.7;">
            Pulls live data from FDA, ClinicalTrials.gov, CMS Open Payments, SEC EDGAR,
            USASpending, and NIH. All API calls run server-side — no CORS restrictions.
          </div>
        </div>
        """, unsafe_allow_html=True)
        return

    if mode == "Single Company":
        if not name1:
            st.error("Please enter a company name.")
            return
        with st.spinner(f"Fetching data for {name1}..."):
            data1 = load_all_data(name1, type1, cik1, secs1)
        st.markdown(f"## {name1}")
        render_company(name1, type1, cik1, secs1, data1)

    else:  # Compare
        if not name1 or not name2:
            st.error("Please enter both company names.")
            return

        # Shared sections = intersection
        shared = tuple(s for s in secs1 if s in secs2)

        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown(f"### 🅐 {name1}")
        with col_b:
            st.markdown(f"### 🅑 {name2}")

        with st.spinner(f"Fetching {name1} and {name2}..."):
            data1 = load_all_data(name1, type1, cik1, secs1)
            data2 = load_all_data(name2, type2, cik2, secs2)

        # Render side by side for each shared section
        section_order = ["fei","510k","maude","recalls","trials","payments","sec","spending"]
        num = 1
        for sec in section_order:
            if sec not in secs1 and sec not in secs2:
                continue
            with st.container():
                col_a, col_b = st.columns(2)
                with col_a:
                    if sec in secs1:
                        _render_one(sec, data1, num, name1, type1, cik1)
                with col_b:
                    if sec in secs2:
                        _render_one(sec, data2, num, name2, type2, cik2)
                st.divider()
            num += 1


def _render_one(sec: str, data: dict, num: int,
                name: str, ctype: str, cik: str):
    """Dispatch a single section render."""
    if sec == "fei":       render_fei(data, num)
    elif sec == "510k":    render_510k(data, num)
    elif sec == "maude":   render_maude(data, num)
    elif sec == "recalls": render_recalls(data, num)
    elif sec == "trials":  render_trials(data, num)
    elif sec == "payments":render_payments(data, num)
    elif sec == "sec":     render_sec(data, num, cik)
    elif sec == "spending":render_spending(data, num)


if __name__ == "__main__":
    main()
