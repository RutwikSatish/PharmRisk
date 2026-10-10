"""
PharmNet Risk — who is approved to make each US prescription drug, and how that
relates to shortages. Computation lives in analysis.py (unit-tested); this file
is presentation only.

Author: Rutwik Satish · MS Engineering Management, Northeastern University
"""

import os

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import analysis as A
from benchmarks import SOURCES

st.set_page_config(page_title="PharmNet Risk | US drug supply concentration",
                   page_icon="💊", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;700&display=swap');
html,body,[class*="css"]{font-family:'DM Sans',system-ui,sans-serif;}
.block-container{max-width:1400px;padding-top:1.5rem;}
[data-testid="stMetric"]{background:#0B1424;border:1px solid #1C2B44;border-radius:10px;padding:.9rem 1.1rem;}
[data-testid="stMetricLabel"]{color:#8BA4C0!important;font-size:11px!important;text-transform:uppercase;letter-spacing:.06em;}
[data-testid="stMetricValue"]{color:#EDF4FF!important;font-size:1.55rem!important;}
.note{background:#0B1424;border-left:3px solid #F59E0B;border-radius:6px;padding:10px 14px;
      font-size:13.5px;color:#C3D1E2;line-height:1.65;margin:4px 0 14px;}
.note b{color:#FCD34D;}
.read{font-size:13px;color:#9FB3CA;margin:-6px 0 18px;line-height:1.6;}
.read b{color:#E2EAF4;}
.card{background:#0B1424;border:1px solid #1C2B44;border-radius:10px;padding:14px 16px;height:100%;
      font-size:13.5px;color:#C3D1E2;line-height:1.6;}
.card h4{margin:0 0 6px;color:#EDF4FF;font-size:15px;}
</style>""", unsafe_allow_html=True)

PLOT = dict(plot_bgcolor="#0B1424", paper_bgcolor="#0B1424",
            font=dict(color="#A9BCD3", family="DM Sans, sans-serif"),
            margin=dict(l=0, r=10, t=30, b=0))
RED, ORANGE, AMBER, GREEN, BLUE, GREY, PURPLE = "#EF4444", "#F97316", "#F59E0B", "#10B981", "#3B82F6", "#64748B", "#8B5CF6"
TIER_COLORS = dict(zip(A.TIER_ORDER, [RED, ORANGE, AMBER, GREEN]))
ROUTE_COLORS = {"Injectable": RED, "Oral": BLUE, "Ophthalmic/Otic": PURPLE, "Respiratory/Nasal": GREEN,
                "Topical/Local": AMBER, "Irrigation": ORANGE, "Other": GREY}


def note(html: str):
    st.markdown(f'<div class="note">{html}</div>', unsafe_allow_html=True)


def how_to_read(html: str):
    st.markdown(f'<div class="read"><b>How to read:</b> {html}</div>', unsafe_allow_html=True)


def chart(fig, h):
    fig.update_layout(**PLOT, height=h)
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def rate_bar(t: pd.DataFrame, xcol: str, color=RED, xtitle=""):
    fig = go.Figure(go.Bar(
        x=t[xcol].astype(str), y=t["shortage_rate_%"], marker_color=color,
        text=[f"{r:.1f}%<br><span style='font-size:10px'>{s}/{n}</span>" if pd.notna(r) else ""
              for r, s, n in zip(t["shortage_rate_%"], t["in_shortage"], t["markets"])],
        textposition="outside", cliponaxis=False,
        hovertemplate="%{x}: %{y:.1f}% in shortage<extra></extra>"))
    fig.update_layout(yaxis_title="% of markets in shortage", xaxis_title=xtitle,
                      yaxis=dict(range=[0, max(1, np.nanmax(t["shortage_rate_%"].values)) * 1.35]))
    return fig


# ── Data ──────────────────────────────────────────────────────────────────────
DATA_DIR = os.environ.get("PHARMNET_DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
missing = A.missing_files(DATA_DIR)
if missing:
    st.error(f"Missing data files in `{DATA_DIR}`: **{', '.join(missing)}**. See README → Data.")
    st.stop()
manifest = A.load_manifest(DATA_DIR)


@st.cache_data(show_spinner="Building markets from the Orange Book…")
def get_results(data_dir: str, as_of):
    return A.build(A.load_raw(data_dir), as_of=as_of)


R = get_results(DATA_DIR, manifest.get("analysis_as_of"))
M, CUR, SD, CO = R.markets, R.current, R.shortage_drugs, R.companies
as_of_str = R.as_of.strftime("%b %d, %Y")
ob_date = manifest.get("orange_book", {}).get("downloaded", "not recorded")
sh_date = manifest.get("drug_shortages", {}).get("downloaded", "not recorded")

# Shared computed facts (used in takeaways, charts and the validation table)
sole = M[M["n_applicants"] == 1]
off_patent_sole = sole[sole["sole_source_type"] == "Off-patent sole source"]
matched = SD[SD["n_applicants"].notna()]
route_rep = A.route_representation(M, SD)
inj_share = route_rep.loc["Injectable", "share_of_shortage_drugs_%"] if "Injectable" in route_rep.index else np.nan
inj_ratio = route_rep.loc["Injectable", "over_representation"] if "Injectable" in route_rep.index else np.nan
AGE_BINS, AGE_LABELS = [0, 10, 20, 30, 40, 200], ["<10 yrs", "10–19", "20–29", "30–39", "40+ yrs"]
age_t = A.rate_by(M, "years_on_market", bins=AGE_BINS, labels=AGE_LABELS)
app_t = A.rate_by(M, "n_applicants", bins=[1, 2, 4, 6, 11, 10_000], labels=["1", "2–3", "4–5", "6–10", "11+"])
score_t = A.rate_by(M, "structural_score", off_patent_only=False)
r_old = age_t.loc[age_t["years_on_market"] == "40+ yrs", "shortage_rate_%"].iat[0]
r_young = 100 * age_t.loc[age_t["years_on_market"].isin(AGE_LABELS[:2]), "in_shortage"].sum() / \
          max(1, age_t.loc[age_t["years_on_market"].isin(AGE_LABELS[:2]), "markets"].sum())
r_s0 = score_t.loc[score_t["structural_score"] == 0, "shortage_rate_%"].iat[0]
r_s3 = score_t.loc[score_t["structural_score"] == score_t["structural_score"].max(), "shortage_rate_%"].iat[0]
prot_share = (sole["sole_source_type"] == "Protected (patent/exclusivity)").mean()

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### PharmNet Risk")
    st.caption("Who is approved to make each US prescription drug — and what that says about shortages")
    st.divider()
    st.markdown("**Data snapshot**")
    st.markdown(f"""
- Analysis as-of: **{as_of_str}**
- Orange Book downloaded: **{ob_date}**
- Shortage list downloaded: **{sh_date}**

Static snapshot, not a live feed.
""")
    st.divider()
    st.markdown("**Sources**")
    st.markdown("""
- [FDA Orange Book data files](https://www.fda.gov/drugs/drug-approvals-and-databases/orange-book-data-files)
- [FDA Drug Shortages Database](https://www.accessdata.fda.gov/scripts/drugshortages/)
""")
    st.divider()
    st.markdown("**Glossary**")
    st.markdown("""
- **Market** — one active ingredient by one route (e.g. *morphine, injectable*).
- **Applicant** — a company holding an FDA approval in that market.
- **Off-patent** — no unexpired Orange Book patent or exclusivity.
- **Presentation** — one strength/pack (NDC) on the shortage list.
""")

# ── Header ────────────────────────────────────────────────────────────────────
st.title("US prescription drug supply: concentration & shortage risk")
st.markdown("Built from public FDA data. Shows how many companies are approved to supply each drug, "
            "which drugs are on the FDA shortage list, and which structural features those shortages share.")

k = st.columns(6)
k[0].metric("RX markets", f"{len(M):,}", "ingredient × route", delta_color="off")
k[1].metric("Off-patent sole-source", f"{len(off_patent_sole):,}", f"of {len(sole):,} sole-source", delta_color="off")
k[2].metric("Drugs on FDA shortage list", f"{len(SD)}", f"{len(CUR):,} presentations", delta_color="off")
k[3].metric("Injectable share of shortages", f"{inj_share:.0f}%", f"{inj_ratio:.1f}× their share of markets", delta_color="off")
k[4].metric("Median time listed", f"{SD['days_in_shortage'].median() / 365.25:.1f} yrs", "current shortages", delta_color="off")
k[5].metric("Markets with discontinuation notice", f"{M['pending_discontinuation'].sum():,}", "FDA 'To Be Discontinued'", delta_color="off")

tabs = st.tabs(["Start here", "What drives shortages", "Early-warning watchlist", "Supplier concentration",
                "Current shortages", "Company exposure", "Validation & methods"])

# ════ 0 — START HERE ═════════════════════════════════════════════════════════
with tabs[0]:
    st.subheader("What this tool does")
    st.markdown(
        "PharmNet Risk joins two public FDA datasets. The **Orange Book** lists every approved prescription "
        "drug product and which company holds each approval. The **Drug Shortages Database** lists drugs FDA "
        "considers in shortage, plus products companies have said they will discontinue. For every drug "
        "*market* (one ingredient by one route), the tool counts approved suppliers, checks patent and "
        "exclusivity status, notes how long the drug has been on the market, and flags shortages and "
        "discontinuation notices. It then shows which of those features shortages tend to share."
    )

    st.subheader("How it helps")
    c = st.columns(3)
    c[0].markdown("""<div class="card"><h4>Hospital & health-system pharmacy</h4>
Look up any drug's supplier base before it becomes a problem. The watchlist highlights off-patent,
limited-competition injectables and markets where a company has filed a discontinuation notice —
candidates for buffer stock, alternate sourcing or therapeutic-substitution planning.</div>""",
                  unsafe_allow_html=True)
    c[1].markdown("""<div class="card"><h4>Policy, procurement & research</h4>
See which structural factors line up with shortages in current FDA data, with every number traceable
to a public file and reproducible from the code. Useful for framing questions about generic market
sustainability, priority review targets, and where supplier-count metrics fall short.</div>""",
                  unsafe_allow_html=True)
    c[2].markdown("""<div class="card"><h4>Journalists, students & the public</h4>
Fact-check claims like "only one company makes this drug" in seconds, and see why that is often
less alarming than it sounds (it is usually a patented brand) — and where it really matters
(old, off-patent injectables).</div>""", unsafe_allow_html=True)

    st.subheader("Key takeaways from this snapshot")
    st.markdown(f"""
1. **"Only one manufacturer" usually means "still on patent."** {prot_share:.0%} of sole-source markets are
   protected by a patent or exclusivity. The {len(off_patent_sole):,} off-patent sole-source markets are the
   structurally fragile group.
2. **Shortages are concentrated in injectables.** They are {inj_share:.0f}% of route-matched drugs on the shortage list
   but {route_rep.loc['Injectable', 'share_of_markets_%']:.0f}% of RX markets.
3. **Older drugs are more exposed.** Among off-patent markets, {r_old:.1f}% of those first approved 40+ years
   ago are in shortage, versus {r_young:.1f}% of those approved within the last 20 years.
4. **Supplier count alone is a weak signal.** Across off-patent markets, shortage rates only range from
   {app_t['shortage_rate_%'].min():.1f}% to {app_t['shortage_rate_%'].max():.1f}% by applicant count, with no clear downward
   trend. Approved applicants ≠ companies actually shipping, and volume is often concentrated in one or two
   firms (IMS, 2012).
5. **Combining factors works better.** Markets with all three structural flags (injectable, ≤3 applicants,
   mature off-patent) show a shortage rate of {r_s3:.1f}%, versus {r_s0:.1f}% with none.
""")

    st.subheader("From all drugs to the ones worth watching")
    fn = A.funnel(M)
    fig = go.Figure(go.Funnel(y=[s for s, _ in fn], x=[n for _, n in fn], textinfo="value+percent initial",
                              marker=dict(color=[BLUE, GREEN, AMBER, ORANGE, RED])))
    chart(fig, 330)
    how_to_read("each step narrows the previous one. The last bar is a short list of off-patent, limited-competition "
                "injectable markets that are already in shortage or have a discontinuation notice.")

    st.subheader("How this compares with other resources")
    st.dataframe(pd.DataFrame([
        ["FDA Drug Shortages Database", "Official FDA list of shortages and discontinuations", "Free", "No supplier counts or risk context"],
        ["ASHP / Univ. of Utah shortage list", "Broader clinical definition of shortage; counts more shortages than FDA", "Free to view", "Not linked to approval or market-structure data"],
        ["USP Medicine Supply Map", "Predictive vulnerability score using 100+ factors incl. price, API sites and complexity", "Commercial", "Proprietary method and data"],
        ["PharmNet Risk (this tool)", "Supplier structure + patent status + shortage/discontinuation flags, fully reproducible", "Free, open code", "No prices, volumes or manufacturing sites; not a prediction model"],
    ], columns=["Resource", "What it offers", "Access", "Main gap"]), use_container_width=True, hide_index=True)

    st.subheader("How to use it")
    st.markdown("""
- **Checking one drug?** Go to *Supplier concentration* → search the ingredient.
- **Want the risk list?** Go to *Early-warning watchlist* and filter by score and route.
- **Want the evidence?** *What drives shortages* shows each factor against the shortage rate.
- **Want to know if you can trust it?** *Validation & methods* compares results with published research.
""")
    note("<b>What this is not:</b> a forecast, a market-share analysis, or clinical guidance. It cannot see prices, "
         "sales volumes, manufacturing sites or API sources — the factors research identifies as most predictive.")

# ════ 1 — WHAT DRIVES SHORTAGES ══════════════════════════════════════════════
with tabs[1]:
    note("Each chart compares the <b>share of markets currently in shortage</b> across one factor. Unless stated, "
         "patent-protected markets are excluded so brand monopolies do not distort the comparison. Small numbers "
         "under each bar are <i>shortage markets / all markets</i>. Descriptive only — one snapshot, not causal.")

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("1 · Route: injectables are over-represented")
        rr = route_rep[route_rep["share_of_markets_%"] > 0].reset_index(names="route")
        fig = go.Figure()
        fig.add_bar(name="Share of all RX markets", y=rr["route"], x=rr["share_of_markets_%"], orientation="h", marker_color=GREY)
        fig.add_bar(name="Share of shortage drugs", y=rr["route"], x=rr["share_of_shortage_drugs_%"], orientation="h", marker_color=RED)
        fig.update_layout(barmode="group", yaxis=dict(autorange="reversed"), xaxis_title="%",
                          legend=dict(orientation="h", y=1.12))
        chart(fig, 340)
        how_to_read("a red bar longer than its grey bar means that route appears on the shortage list more often than "
                    "its share of the market would suggest. Consistent with USP's 'manufacturing complexity' factor.")
    with c2:
        st.subheader("2 · Product age: older drugs short more often")
        chart(rate_bar(age_t, "years_on_market", ORANGE, "Years since first approval in the market"), 340)
        how_to_read("product age stands in for price, which this data lacks. Old generics tend to be the cheapest, and "
                    "FDA's 2019 task force tied shortages to weak financial incentives for exactly these products.")

    c3, c4 = st.columns(2)
    with c3:
        st.subheader("3 · Approved applicants: a weak signal on its own")
        inj_only = st.toggle("Injectables only", value=False, key="inj_toggle")
        base = M[M["route_family"] == "Injectable"] if inj_only else M
        chart(rate_bar(A.rate_by(base, "n_applicants", bins=[1, 2, 4, 6, 11, 10_000],
                                 labels=["1", "2–3", "4–5", "6–10", "11+"]), "n_applicants", AMBER,
                       "Approved applicants in the market"), 340)
        how_to_read("if fewer suppliers meant more shortages, bars would fall from left to right. They mostly don't. "
                    "Approval counts overstate active suppliers, and one firm often makes most of the volume — "
                    "so this is where volume data would change the picture most.")
    with c4:
        st.subheader("4 · Factors combined")
        fig = rate_bar(score_t.assign(structural_score=score_t["structural_score"].astype(str) + " flags"),
                       "structural_score", RED, "Structural flags present (0–3)")
        chart(fig, 340)
        how_to_read("flags are injectable, ≤3 approved applicants, and off-patent ≥20 years. All markets included. The "
                    "rising bars show the factors add up. This is in-sample: it describes today's list, it does not "
                    "predict tomorrow's.")

    st.subheader("5 · Every shortage drug, by supplier count and size")
    fig = go.Figure()
    for rf in matched["route"].fillna("Unknown").str.replace(r" \(.*\)", "", regex=True).unique():
        s = matched[matched["route"].fillna("Unknown").str.replace(r" \(.*\)", "", regex=True) == rf]
        fig.add_scatter(x=s["n_applicants"], y=s["presentations"], mode="markers", name=rf,
                        marker=dict(size=(s["days_in_shortage"] / 365.25 * 3 + 7).clip(7, 30),
                                    color=ROUTE_COLORS.get(rf, GREY), opacity=.8, line=dict(width=1, color="#0B1424")),
                        text=s["Generic Name"], customdata=(s["days_in_shortage"] / 365.25).round(1),
                        hovertemplate="<b>%{text}</b><br>Applicants: %{x}<br>Presentations: %{y}"
                                      "<br>Listed: %{customdata} yrs<extra></extra>")
    fig.update_layout(xaxis=dict(title="Approved applicants (same route, log scale)", type="log"),
                      yaxis_title="Presentations on shortage list", legend=dict(orientation="h", y=1.1))
    chart(fig, 420)
    how_to_read("each bubble is one drug; bigger bubbles have been listed longer. Most sit to the right — many "
                "approved suppliers, still short. Hover for details.")

    with st.expander(f"Matching quality — {len(matched)}/{len(SD)} shortage drugs linked to the Orange Book"):
        st.dataframe(SD["match"].value_counts().rename_axis("Match").reset_index(name="Drugs"),
                     use_container_width=True, hide_index=True)
        st.dataframe(SD[SD["n_applicants"].isna()][["Generic Name", "match"]], use_container_width=True, hide_index=True)
        st.caption("'Only discontinued approvals' = every Orange Book listing for that ingredient is discontinued.")

# ════ 2 — WATCHLIST ══════════════════════════════════════════════════════════
with tabs[2]:
    note("A transparent checklist, not a fitted model. Each market gets one point per flag below; flags come from "
         "factors named in FDA (2019) and USP research that can be observed in public FDA data. Price, API "
         "geography and quality history — also major factors — are not available here.")
    fl = pd.DataFrame({"Flag": list(A.FLAG_LABELS.values()),
                       "Markets flagged": [int(M[c].sum()) for c in A.FLAG_LABELS],
                       "…of which in shortage": [int((M[c] & M["in_shortage"]).sum()) for c in A.FLAG_LABELS]})
    fl["Shortage rate %"] = (100 * fl["…of which in shortage"] / fl["Markets flagged"]).round(1)
    c1, c2 = st.columns([3, 2])
    with c1:
        fig = go.Figure(go.Bar(y=fl["Flag"], x=fl["Shortage rate %"], orientation="h", marker_color=ORANGE,
                               text=[f"{v:.1f}%" for v in fl["Shortage rate %"]], textposition="outside"))
        fig.add_vline(x=100 * M["in_shortage"].mean(), line_dash="dot", line_color=GREY,
                      annotation_text="all markets", annotation_position="top")
        fig.update_layout(yaxis=dict(autorange="reversed"), xaxis_title="% of flagged markets in shortage")
        chart(fig, 280)
    with c2:
        st.dataframe(fl, use_container_width=True, hide_index=True)
        st.caption("The discontinuation flag uses the same FDA database as the shortage list, so its rate partly "
                   "reflects overlap rather than independent risk.")

    st.subheader("Watchlist")
    f1, f2, f3, f4 = st.columns([1, 1, 1, 2])
    min_score = f1.slider("Minimum score", 0, 4, 3)
    route_pick = f2.selectbox("Route", ["All routes"] + sorted(M["route_family"].unique()))
    hide_short = f3.toggle("Hide drugs already in shortage", value=False)
    qw = f4.text_input("Search ingredient", key="wq", placeholder="e.g. potassium chloride")
    w = M[M["watch_score"] >= min_score]
    if route_pick != "All routes":
        w = w[w["route_family"] == route_pick]
    if hide_short:
        w = w[~w["in_shortage"]]
    if qw:
        w = w[w["Ingredient"].str.contains(qw.strip().upper(), regex=False, na=False)]
    wv = w.assign(flags=w.apply(lambda r: " · ".join(lbl.split(" (")[0] for c, lbl in A.FLAG_LABELS.items() if r[c]), axis=1))
    wv = wv.sort_values(["watch_score", "n_applicants", "years_on_market"], ascending=[False, True, False])
    out = wv[["Ingredient", "route_family", "watch_score", "n_applicants", "n_applicants_any_salt", "years_on_market",
              "in_shortage", "discontinuing_names", "flags", "applicants"]].rename(columns={
        "route_family": "Route", "watch_score": "Score", "n_applicants": "Applicants",
        "n_applicants_any_salt": "Applicants (any salt)", "years_on_market": "Years on market",
        "in_shortage": "In shortage now", "discontinuing_names": "Discontinuation notice from",
        "flags": "Flags", "applicants": "Approved applicants"})
    st.dataframe(out, use_container_width=True, height=420, hide_index=True)
    st.caption(f"{len(out):,} markets. A discontinuation notice may cover only some strengths or packs, not a full exit. "
               "'Applicants (any salt)' pools salt forms of the same molecule and route (e.g. methotrexate and "
               "methotrexate sodium) — when it is much higher than 'Applicants', alternatives may exist.")
    st.download_button("Download watchlist CSV", out.to_csv(index=False), "watchlist.csv", "text/csv")

    st.subheader("Discontinuation notices in limited-competition markets")
    dl = M[M["pending_discontinuation"] & M["limited_competition"]].sort_values("n_applicants")
    fig = go.Figure()
    for flag, colr, name in [(True, GREY, "Patent/exclusivity-protected"), (False, RED, "Off-patent")]:
        s = dl[dl["any_protected"] == flag]
        fig.add_scatter(x=s["years_on_market"], y=s["n_applicants"] + np.random.default_rng(0).uniform(-.15, .15, len(s)),
                        mode="markers", name=name, marker=dict(size=11, color=colr, opacity=.85),
                        text=s["Ingredient"] + " · " + s["route_family"],
                        hovertemplate="<b>%{text}</b><br>Years on market: %{x}<extra></extra>")
    fig.update_layout(xaxis_title="Years since first approval", yaxis=dict(title="Approved applicants", dtick=1),
                      legend=dict(orientation="h", y=1.12))
    chart(fig, 320)
    how_to_read("red points in the upper-right are old, off-patent drugs with few suppliers where someone is leaving — "
                "the classic setup for a generic shortage. Grey points are usually brands replacing an old formulation.")

# ════ 3 — SUPPLIER CONCENTRATION ═════════════════════════════════════════════
with tabs[3]:
    note(f"<b>Why split sole-source markets?</b> {prot_share:.0%} of single-applicant markets are on-patent or "
         "exclusivity-protected brands — a monopoly by design that rarely produces shortages. <b>Off-patent sole-source</b> "
         "markets, where generic entry is legal but hasn't happened, are the structurally fragile group.")
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Markets by approved applicants")
        tier = M.groupby(["tier", "route_family"]).size().unstack(fill_value=0).reindex(A.TIER_ORDER)
        fig = go.Figure()
        for rf in tier.columns:
            fig.add_bar(name=rf, x=tier.index, y=tier[rf], marker_color=ROUTE_COLORS.get(rf, GREY))
        fig.update_layout(barmode="stack", legend=dict(orientation="h", y=1.15), yaxis_title="Markets")
        chart(fig, 340)
    with c2:
        st.subheader("Sole-source: protected vs off-patent")
        split = sole.groupby(["route_family", "sole_source_type"]).size().unstack(fill_value=0)
        fig = go.Figure()
        for col, colr in [("Protected (patent/exclusivity)", GREY), ("Off-patent sole source", RED)]:
            if col in split:
                fig.add_bar(name=col, y=split.index, x=split[col], orientation="h", marker_color=colr)
        fig.update_layout(barmode="stack", legend=dict(orientation="h", y=1.15), xaxis_title="Markets")
        chart(fig, 340)

    st.subheader("Generic entry over a drug's life")
    gm = M[~M["any_protected"]].copy()
    gm["age"] = pd.cut(gm["years_on_market"], AGE_BINS, labels=AGE_LABELS, right=False)
    box = go.Figure()
    for lbl in AGE_LABELS:
        box.add_box(y=gm.loc[gm["age"] == lbl, "n_applicants"], name=lbl, marker_color=BLUE, boxmean=True)
    box.update_layout(yaxis=dict(title="Approved applicants (log)", type="log"), showlegend=False)
    chart(box, 300)
    how_to_read("for off-patent markets, how many companies hold approvals by product age. A low box for old drugs "
                "would suggest generic makers exit as prices fall; a high box means competition persists on paper.")

    st.subheader("Look up a drug")
    cs, ct, cr = st.columns([3, 1, 1])
    q = cs.text_input("Search ingredient", placeholder="e.g. bupivacaine", label_visibility="collapsed")
    tf = ct.selectbox("Tier", ["All tiers"] + A.TIER_ORDER, label_visibility="collapsed")
    rf = cr.selectbox("Route", ["All routes"] + sorted(M["route_family"].unique()), label_visibility="collapsed", key="r2")
    d = M
    if q:
        d = d[d["Ingredient"].str.contains(q.strip().upper(), regex=False, na=False)]
    if tf != "All tiers":
        d = d[d["tier"] == tf]
    if rf != "All routes":
        d = d[d["route_family"] == rf]
    out = d[["Ingredient", "route_family", "n_applicants", "n_generic_holders", "hhi_equal_share", "sole_source_type",
             "years_on_market", "in_shortage", "pending_discontinuation", "applicants"]].rename(columns={
        "route_family": "Route", "n_applicants": "Applicants", "n_generic_holders": "Generic (ANDA) holders",
        "hhi_equal_share": "Equal-share HHI (proxy)", "sole_source_type": "Sole-source type",
        "years_on_market": "Years on market", "in_shortage": "In shortage",
        "pending_discontinuation": "Discontinuation notice", "applicants": "Approved applicants"}).sort_values("Applicants")
    st.dataframe(out, use_container_width=True, height=380, hide_index=True)
    st.caption("Equal-share HHI = 10,000 ÷ applicants. The Orange Book has no sales data, so this is a scale reference, "
               "not a true HHI.")
    st.download_button("Download CSV", out.to_csv(index=False), "markets.csv", "text/csv")

# ════ 4 — CURRENT SHORTAGES ═════════════════════════════════════════════════
with tabs[4]:
    note(f"A <b>presentation</b> is one NDC-level row (a specific strength/pack from one company). <b>{len(CUR):,}</b> "
         f"presentations cover <b>{len(SD)}</b> drugs. Presentation counts reflect how many SKUs a drug has, not severity.")
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Drugs by therapeutic category")
        cats = (CUR.drop_duplicates("Generic Name")["Therapeutic Category"].fillna("Not reported")
                .str.split(";").explode().str.strip().replace("", "Not reported").value_counts().head(14))
        fig = go.Figure(go.Bar(x=cats.values, y=cats.index, orientation="h", marker_color=RED,
                               text=cats.values, textposition="outside"))
        fig.update_layout(yaxis=dict(autorange="reversed"), xaxis=dict(showticklabels=False))
        chart(fig, 400)
        st.caption("Drugs listed under several categories are counted in each.")
    with c2:
        st.subheader("How long have they been listed?")
        yrs = SD["days_in_shortage"] / 365.25
        fig = go.Figure(go.Histogram(x=yrs, xbins=dict(size=1), marker_color=ORANGE))
        fig.add_vline(x=yrs.median(), line_dash="dash", line_color="#EDF4FF",
                      annotation_text=f"median {yrs.median():.1f} yrs")
        fig.update_layout(xaxis_title="Years since initial posting", yaxis_title="Drugs")
        chart(fig, 400)
        st.caption("Long durations mean these are mostly chronic, unresolved shortages rather than new disruptions.")

    c3, c4 = st.columns(2)
    with c3:
        st.subheader("Reported reason")
        reasons = CUR["Reason for Shortage"].replace("", pd.NA).fillna("Not reported").value_counts()
        fig = go.Figure(go.Bar(x=reasons.values, y=reasons.index, orientation="h",
                               marker_color=[GREY if r == "Not reported" else AMBER for r in reasons.index],
                               text=reasons.values, textposition="outside"))
        fig.update_layout(yaxis=dict(autorange="reversed"), xaxis=dict(showticklabels=False))
        chart(fig, 340)
        nr = (CUR["Reason for Shortage"].replace("", pd.NA).isna()).mean()
        st.caption(f"{nr:.0%} of presentations have no reason recorded, so the rest are not a national root-cause breakdown.")
    with c4:
        st.subheader("Which companies' products are listed?")
        top = CUR["Company Name"].value_counts()
        cum = 100 * top.cumsum() / top.sum()
        fig = go.Figure()
        fig.add_bar(x=list(range(1, 16)), y=top.values[:15], marker_color=ORANGE, name="Presentations",
                    text=top.index[:15].str[:22], hovertemplate="%{text}: %{y}<extra></extra>")
        fig.add_scatter(x=list(range(1, 16)), y=cum.values[:15], yaxis="y2", mode="lines+markers", name="Cumulative %",
                        line=dict(color="#EDF4FF"))
        fig.update_layout(xaxis=dict(title="Company rank"), yaxis_title="Presentations",
                          yaxis2=dict(overlaying="y", side="right", range=[0, 100], title="Cumulative %"),
                          legend=dict(orientation="h", y=1.12))
        chart(fig, 340)
        st.caption(f"Top 5 companies: {cum.iat[min(4, len(cum) - 1)]:.0f}% of presentations. Big sterile-injectable "
                   "portfolios mean more SKUs to list — this is not a reliability ranking.")

    st.subheader("All shortage drugs")
    show = SD.rename(columns={"Generic Name": "Drug", "route": "Route matched", "n_applicants": "Applicants",
                              "n_applicants_any_salt": "Applicants (any salt)", "protected": "Protected",
                              "presentations": "Presentations", "companies": "Companies listed",
                              "days_in_shortage": "Days listed", "category": "Category", "reason": "Main reason",
                              "match": "Match"})
    cols = ["Drug", "Route matched", "Applicants", "Applicants (any salt)", "Protected", "Presentations",
            "Companies listed", "Days listed", "Category", "Main reason", "Match"]
    st.dataframe(show[cols], use_container_width=True, height=380, hide_index=True)
    st.download_button("Download CSV", show[cols].to_csv(index=False), "shortage_drugs.csv", "text/csv")

# ════ 5 — COMPANY EXPOSURE ═════════════════════════════════════════════════
with tabs[5]:
    note("If one application holder stopped supplying, how many markets would lose their <b>only</b> approved source? "
         "Off-patent and injectable sole-source markets are separated because they have no branded fallback. "
         "Parent consolidation uses explicit rules only (analysis.PARENT_RULES).")
    top = CO[CO["off_patent_sole"] > 0].head(20)
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Off-patent sole-source markets by holder")
        fig = go.Figure()
        fig.add_bar(name="Injectable", y=top["parent"].str.title().str[:38], x=top["off_patent_injectable"],
                    orientation="h", marker_color=RED)
        fig.add_bar(name="Other routes", y=top["parent"].str.title().str[:38],
                    x=top["off_patent_sole"] - top["off_patent_injectable"], orientation="h", marker_color=ORANGE)
        fig.update_layout(barmode="stack", yaxis=dict(autorange="reversed"), legend=dict(orientation="h", y=1.08))
        chart(fig, 520)
    with c2:
        st.subheader("Portfolio size vs sole-source share")
        p = CO[CO["total_markets"] >= 5].copy()
        p["pct"] = 100 * p["sole_source_markets"] / p["total_markets"]
        fig = go.Figure(go.Scatter(
            x=p["total_markets"], y=p["pct"], mode="markers",
            marker=dict(size=(p["off_patent_sole"] * 3).clip(6, 30), color=p["off_patent_sole"],
                        colorscale=[[0, GREY], [.5, ORANGE], [1, RED]], showscale=True,
                        colorbar=dict(title="Off-patent<br>sole")),
            text=p["parent"].str.title(),
            hovertemplate="<b>%{text}</b><br>Markets: %{x}<br>Sole-source: %{y:.0f}%<extra></extra>"))
        fig.update_layout(xaxis=dict(title="Markets in portfolio (log)", type="log"),
                          yaxis_title="% of portfolio that is sole-source")
        chart(fig, 520)
        how_to_read("top-left are small, mostly-brand portfolios; large bubbles far right are big generic makers whose "
                    "disruption would leave several off-patent markets with no approved alternative.")
    q2 = st.text_input("Search holder", placeholder="e.g. fresenius", label_visibility="collapsed")
    dc = CO if not q2 else CO[CO["parent"].str.contains(q2.strip().upper(), regex=False, na=False)]
    dc = dc.rename(columns={"parent": "Holder", "total_markets": "Markets", "sole_source_markets": "Sole-source",
                            "off_patent_sole": "Off-patent sole", "off_patent_injectable": "Off-patent sole (inj.)",
                            "protected_sole": "Protected sole"})
    cols = ["Holder", "Markets", "Sole-source", "Off-patent sole", "Off-patent sole (inj.)", "Protected sole"]
    st.dataframe(dc[cols], use_container_width=True, height=380, hide_index=True)
    st.download_button("Download CSV", dc[cols].to_csv(index=False), "holder_exposure.csv", "text/csv")

# ════ 6 — VALIDATION & METHODS ═════════════════════════════════════════════
with tabs[6]:
    st.subheader("Do these results agree with published research?")
    st.markdown("Each row compares a published finding with the closest number this tool can compute. "
                "Definitions differ, so 'consistent' means the same direction and rough size, not identical values.")
    med = matched["n_applicants"].median()
    q1, q3 = matched["n_applicants"].quantile([.25, .75])
    disc_classified = SD.set_index("Generic Name")["match"]
    cef = disc_classified.filter(like="Cefotaxime").iat[0] if disc_classified.filter(like="Cefotaxime").size else "n/a"
    tri = disc_classified.filter(like="Triamcinolone Hexacetonide").iat[0] if disc_classified.filter(like="Triamcinolone Hexacetonide").size else "n/a"
    rows = [
        ["Injectables dominate shortages", "About two-thirds of FDA-listed shortages (June 2023) were injectable",
         f"{inj_share:.0f}% of route-matched shortage drugs are injectable", "Consistent", "iqvia2023"],
        ["Older, low-price generics are most exposed", "Shortages linked to low prices and weak incentives for older generics",
         f"Off-patent 40+ yr markets: {r_old:.1f}% in shortage vs {r_young:.1f}% for <20 yrs", "Consistent", "fda2019"],
        ["Combined risk factors", "Price, complexity, geographic concentration and quality act together",
         f"0 flags: {r_s0:.1f}% → 3 flags: {r_s3:.1f}% in shortage", "Consistent (subset of factors)", "usp2024"],
        ["Fewer suppliers → more shortages", "Canadian markets with a single generic maker were most likely to be short",
         "Weak, non-monotonic gradient by approved-applicant count", "Partly inconsistent — likely the approved vs active supplier gap", "cmaj2020"],
        ["Volume concentration behind 'many suppliers'", "Half of shortage drugs had ≤2 suppliers by volume; one firm often makes most of a sterile injectable",
         "Not measurable (no volume data) — explains row above", "Explains gap", "ims2012"],
        ["Supplier count of shortage drugs", "Median 3 Orange Book manufacturers (IQR 2–6), counted over strengths in shortage",
         f"Median {med:.0f} applicants (IQR {q1:.0f}–{q3:.0f}), counted over all strengths in the route", "Consistent given broader definition", "pmc2024"],
        ["Unlinkable drugs", "Same study set aside cefotaxime (discontinued) and triamcinolone hexacetonide (not in Orange Book)",
         f"Cefotaxime → '{cef}'; triamcinolone hexacetonide → '{tri}'", "Same classification", "pmc2024"],
        ["How many shortages exist", "ASHP counted 227 active shortages in Q2 2026",
         f"{len(SD)} drugs on FDA's current list in this snapshot", "Expected difference — ASHP uses a broader definition", "ashp2026"],
    ]
    vt = pd.DataFrame(rows, columns=["Check", "Published finding (paraphrased)", "This tool", "Verdict", "src"])
    vt["Source"] = vt["src"].map(lambda s: SOURCES[s][0])
    st.dataframe(vt.drop(columns="src"), use_container_width=True, hide_index=True, height=360)
    st.markdown("**Sources**\n" + "\n".join(f"- [{t}]({u})" for t, u in SOURCES.values()))

    st.divider()
    readme = os.path.join(os.path.dirname(os.path.abspath(__file__)), "README.md")
    if os.path.exists(readme):
        txt = open(readme, encoding="utf-8").read()
        start, end = txt.find("## Methodology"), txt.find("## Suggested extensions")
        st.markdown(txt[start:end if end > start else None] if start >= 0 else txt)

st.divider()
st.caption(f"PharmNet Risk · FDA Orange Book + FDA Drug Shortages snapshot (as of {as_of_str}) · Built by Rutwik Satish, "
           "MS Engineering Management, Northeastern University · Not affiliated with or endorsed by FDA. "
           "Not for clinical or procurement decisions.")
