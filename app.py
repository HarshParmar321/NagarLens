"""NagarLens: follow every rupee from a citizen complaint to a fix that held.

Run:  .venv/Scripts/python -m streamlit run app.py
Data: organizer's synthetic dataset (data/raw/data). Set ANTHROPIC_API_KEY for live Claude; otherwise the
AI steps use cached answers or deterministic fallbacks.
"""
import html
import re

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src import ai
from src.audit import RULE_LABEL, recovery_summary, run_audit
from src.budget import DEFAULT_WEIGHTS, allocate, open_issues, road_risk
from src.data import load_all

st.set_page_config(page_title="NagarLens", page_icon="🔎", layout="wide")
INK, BLUE, ORANGE, GREEN, GREY = "#16181D", "#1E4FD8", "#C2410C", "#1E7B34", "#8A8F98"

st.markdown("""<style>
.block-container{padding-top:1.2rem}
.kpi{background:#fff;border:1px solid #E3E3DE;border-radius:14px;padding:14px 18px}
.kpi .l{font-size:13px;color:#565A63}.kpi .v{font-size:28px;font-weight:700}.kpi .s{font-size:12px;color:#565A63}
.steps{display:flex;gap:8px;flex-wrap:wrap;margin:6px 0 14px}
.step{flex:1 1 140px;border-radius:12px;padding:10px 12px;border:1px solid #E3E3DE;background:#fff}
.step .n{font-size:11px;font-weight:700;letter-spacing:.05em;text-transform:uppercase;color:#565A63}
.step .t{font-size:15px;font-weight:700;margin-top:2px}.step .d{font-size:12px;color:#3B3F47;margin-top:2px}
.ok{border-top:5px solid #1E7B34}.bad{border-top:5px solid #C2410C}.warn{border-top:5px solid #D99A00}.na{border-top:5px solid #B9BCC2}
.verdict{background:#F3F6FD;border:1px solid #C3D3F7;border-radius:14px;padding:16px 18px}
.flag{background:#FFF6F1;border:1px solid #F4C9B3;border-radius:12px;padding:12px 14px;margin-bottom:8px}
.badge{display:inline-block;padding:2px 9px;border-radius:999px;font-size:11px;font-weight:700;background:#EDEDE8;color:#3B3F47}
</style>""", unsafe_allow_html=True)


@st.cache_data(show_spinner="Loading the dataset…")
def data():
    t = load_all()
    return t, run_audit(t)


t, findings = data()
wo, comp, wards, roads = t["work_orders"], t["complaints"], t["wards"], t["roads"]
gazetteer = list(t["localities"].locality) + [a.strip() for s in t["localities"].aliases.dropna() for a in s.split(";")]


def kpi(col, label, value, sub=""):
    col.markdown(f'<div class="kpi"><div class="l">{label}</div><div class="v">{value}</div><div class="s">{sub}</div></div>',
                 unsafe_allow_html=True)


def esc(s) -> str:
    """Escape model output and dataset text before it goes into HTML-styled cards."""
    return html.escape(str(s)).replace("\n", "<br>")


def inr(x):
    return f"₹{x/1e7:.2f} Cr" if abs(x) >= 1e7 else f"₹{x/1e5:.1f} L" if abs(x) >= 1e5 else f"₹{x:,.0f}"


# ---------------- sidebar ----------------
st.sidebar.markdown("## 🔎 NagarLens")
st.sidebar.caption("Follow every rupee from a complaint to a fix that held.")
ward = st.sidebar.selectbox("Ward", wards.ward_code, index=int(np.where(wards.ward_code == "L")[0][0]),
                            format_func=lambda c: f"{c} · {wards.set_index('ward_code').ward_name[c]}")
wrow = wards.set_index("ward_code").loc[ward]
W = wo[wo.ward_code == ward]
st.sidebar.markdown(f"**AI:** {'🟢 ' + ai.engine_name() if ai.available() else '🟡 offline: cached answers + rule fallbacks'}")
st.sidebar.markdown('<span class="badge">Synthetic (organizer)</span> data · all contractors fictional', unsafe_allow_html=True)

tabs = st.tabs(["① Follow a case", "② Ward overview", "③ AI inbox", "④ Recovery ledger", "⑤ Scorecards",
                "⑥ Next rupee", "⑦ Ask NagarLens", "Data quality"])

# =============== ① FOLLOW A CASE ===============
with tabs[0]:
    st.markdown("### Follow one rupee: from complaint to fix to verdict")
    presets = {"Paid during warranty (Kurla)": "WO25-02068", "3 complaints, warranty road (Kurla)": "WO25-00268",
               "Possible duplicate bill (Dharavi)": "WO25-02472", "Billed 3.1× rate card (WEH)": "WO25-01576",
               "Fixed fast, failed in 30 days (Tilak Nagar)": "WO25-00646"}
    c1, c2 = st.columns([2, 3])
    pick = c1.radio("Start from a case", [*presets, "Any work order in this ward"], index=0)
    if pick == "Any work order in this ward":
        wid = c2.selectbox("Work order", W.sort_values("cost_inr", ascending=False).work_order_id)
    else:
        wid = presets[pick]
        c2.info(f"Case **{wid}**. Pick another on the left, or start from a complaint in ⑦ Ask NagarLens.")
    r = wo.set_index("work_order_id").loc[wid]
    cids = r.linked_complaint_ids.split("|") if isinstance(r.linked_complaint_ids, str) else []
    cc = comp[comp.complaint_id.isin(cids)].sort_values("received_at")
    road = roads.set_index("road_id").loc[r.road_id]
    f_here = findings[findings.work_order_id == wid]
    hist = wo[wo.road_id == r.road_id].sort_values("assigned_at")
    later = hist[(hist.assigned_at > r.completed_at) & (hist.assigned_at <= r.completed_at + pd.Timedelta(days=30))
                 & (hist.work_type == r.work_type)]
    start = cc.received_at.min() if len(cc) else r.assigned_at
    deadline = start + pd.Timedelta(hours=int(r.sla_hours))

    steps = [
        ("1 · Reported", f"{len(cc)} complaint(s)" if len(cc) else "No complaint",
         ", ".join(cc.channel.unique()[:2]) if len(cc) else "work order raised without a citizen complaint", "ok" if len(cc) else "bad"),
        ("2 · Assigned", r.contractor_name.replace(" (synthetic)", ""), f"{r.assigned_at:%d %b %H:%M} · SLA {r.sla_hours} h", "ok"),
        ("3 · Repaired", "On time" if r.sla_met == "Y" else "Late", f"done {r.completed_at:%d %b} · {r.hours_to_complete:.0f} h", "ok" if r.sla_met == "Y" else "warn"),
        ("4 · Billed", inr(r.cost_inr), f"{r.cost_ratio:.2f}× rate card", "bad" if r.cost_ratio > 1.4 else "ok"),
        ("5 · Did it hold?", "Held 30 days" if r.reopened_within_30d == "N" else "Failed", f"{len(later)} repeat job(s) within 30 days", "ok" if r.reopened_within_30d == "N" else "bad"),
        ("6 · Verdict", f"{len(f_here)} review lead(s)" if len(f_here) else "No flags", ", ".join(RULE_LABEL[x] for x in f_here.rule_id) or "within normal range", "bad" if len(f_here) else "ok"),
    ]
    st.markdown('<div class="steps">' + "".join(
        f'<div class="step {cls}"><div class="n">{n}</div><div class="t">{esc(tt)}</div><div class="d">{esc(d)}</div></div>'
        for n, tt, d, cls in steps) + "</div>", unsafe_allow_html=True)

    a, b = st.columns(2)
    with a:
        st.markdown("**Where:** complaints and the road segment")
        fig = go.Figure()
        fig.add_scattermap(lat=[road.start_lat, road.end_lat], lon=[road.start_lon, road.end_lon], mode="lines",
                           line=dict(width=7, color=ORANGE if road.under_dlp == "Y" else BLUE), name=f"{road.road_name} ({r.road_id})")
        g = cc.dropna(subset=["lat"])
        if len(g):
            fig.add_scattermap(lat=g.lat, lon=g.lon, mode="markers", marker=dict(size=12, color=INK), name="Complaint GPS",
                               text=g.complaint_id + " · " + g.description.str[:60])
        fh = t["flood_hotspots"]
        fig.add_scattermap(lat=fh.lat, lon=fh.lon, mode="markers", marker=dict(size=10, color=BLUE, opacity=.5),
                           name="Flood hotspots", text=fh.name)
        fig.update_layout(map=dict(style="carto-positron", center=dict(lat=road.mid_lat, lon=road.mid_lon), zoom=14),
                          height=340, margin=dict(l=0, r=0, t=0, b=0), legend=dict(orientation="h", y=0))
        st.plotly_chart(fig, width="stretch")
        if road.under_dlp == "Y":
            st.warning(f"{road.road_name} was resurfaced on {road.last_resurfaced} and is still under its Defect Liability Period.")
    with b:
        st.markdown("**When:** the SLA clock")
        ev = [dict(stage="Complaint → assigned", start=start, end=r.assigned_at),
              dict(stage="Assigned → work started", start=r.assigned_at, end=r.work_started_at),
              dict(stage="Work started → completed", start=r.work_started_at, end=r.completed_at)]
        tl = px.timeline(pd.DataFrame(ev), x_start="start", x_end="end", y="stage", color_discrete_sequence=[BLUE])
        tl.add_vline(x=deadline, line_dash="dash", line_color=ORANGE)
        tl.add_annotation(x=deadline, y=1.08, yref="paper", text=f"SLA deadline ({r.sla_hours} h)", showarrow=False, font_color=ORANGE)
        tl.update_yaxes(autorange="reversed", title=None)
        tl.update_layout(height=340, margin=dict(l=0, r=0, t=30, b=0))
        st.plotly_chart(tl, width="stretch")

    a, b = st.columns(2)
    with a:
        st.markdown("**How much:** bill against the rate card")
        cost = go.Figure()
        cost.add_bar(x=["Rate card", "Upper normal (1.3×)", "Billed"], y=[r.expected_cost_inr, 1.3 * r.expected_cost_inr, r.cost_inr],
                     marker_color=[GREY, "#C9CCD2", ORANGE if r.cost_ratio > 1.4 else GREEN],
                     text=[inr(v) for v in [r.expected_cost_inr, 1.3 * r.expected_cost_inr, r.cost_inr]], textposition="outside")
        cost.update_layout(height=300, margin=dict(l=0, r=0, t=10, b=0), yaxis_title="₹ (billed amount)")
        st.plotly_chart(cost, width="stretch")
        st.caption(f"{r.repair_method}: ₹{r.standard_rate_inr:,} {r.unit}" + (f" × {r.area_sqm} sqm" if r.unit == "per sqm" else ""))
    with b:
        st.markdown("**Did it hold?** Every repair on this road this monsoon")
        h = hist.assign(outcome=np.where(hist.reopened_within_30d == "Y", "Re-opened within 30 days", "Held"),
                        this=np.where(hist.work_order_id == wid, "this case", ""))
        hf = px.scatter(h, x="assigned_at", y="work_type", size="cost_inr", color="outcome", hover_name="work_order_id",
                        text="this", color_discrete_map={"Held": GREEN, "Re-opened within 30 days": ORANGE})
        hf.update_traces(textposition="top center")
        hf.update_layout(height=300, margin=dict(l=0, r=0, t=10, b=0), xaxis_title=None, yaxis_title=None,
                         legend=dict(orientation="h", y=-0.2))
        st.plotly_chart(hf, width="stretch")
        st.caption(f"{len(hist)} jobs on {road.road_name} ({r.road_id}), {inr(hist.cost_inr.sum())} billed in total.")

    st.markdown("**Verdict and next action**")
    case = {"work_order": {k: (v if not isinstance(v, pd.Timestamp) else str(v)) for k, v in r.to_dict().items()} | {"work_order_id": wid},
            "n_complaints": len(cc), "complaints": cc[["complaint_id", "channel", "description", "status"]].to_dict("records"),
            "findings": f_here.to_dict("records"), "repeat_jobs_within_30d": later.work_order_id.tolist()}
    text, src = ai.explain_case(case)
    st.markdown(f'<div class="verdict"><span class="badge">{"Written by Claude" if src in ("claude", "cache") else "Template (Claude offline)"}</span>'
                f'<p style="margin:8px 0 0;font-size:15px;line-height:1.55">{esc(text)}</p></div>', unsafe_allow_html=True)
    for fr in f_here.itertuples():
        st.markdown(f'<div class="flag"><b>{RULE_LABEL[fr.rule_id]}</b> · needs review · at risk <b>{inr(fr.amount_at_risk_inr)}</b><br>'
                    f'{esc(fr.reason)}<br><i>Fair context:</i> {esc(fr.fair_context)}<br><b>Next:</b> {esc(fr.review_action)}</div>', unsafe_allow_html=True)
    md = f"# Case file {wid}\n\n" + text + "\n\n## Complaints\n" + "\n".join(f"- {c.complaint_id} ({c.channel}): {c.description}" for c in cc.itertuples()) \
         + "\n\n## Audit leads\n" + ("\n".join(f"- {x.rule_id}: {x.reason} Next: {x.review_action}" for x in f_here.itertuples()) or "- none")
    st.download_button("⬇ Download case file", md, f"case_{wid}.md")

# =============== ② WARD OVERVIEW ===============
with tabs[1]:
    st.markdown(f"### Where did {wrow.ward_name}'s repair money go? <span class='badge'>Monsoon 2025</span>", unsafe_allow_html=True)
    budget, billed = wrow.monsoon_repair_budget_inr_2025, W.cost_inr.sum()
    fw = findings[findings.ward_code == ward]
    rs_w = recovery_summary(fw) if len(fw) else {"total_at_risk_inr": 0}
    k = st.columns(5)
    kpi(k[0], "Allocated budget", inr(budget), "Jun–Sep 2025")
    kpi(k[1], "Billed (work orders)", inr(billed), f"{billed/budget:.0%} of budget")
    kpi(k[2], "Spent on fixes that failed", inr(W[W.reopened_within_30d == 'Y'].cost_inr.sum()), "re-opened within 30 days")
    kpi(k[3], "Repairs on time", f"{(W.sla_met == 'Y').mean():.0%}", f"city {(wo.sla_met == 'Y').mean():.0%}")
    kpi(k[4], "To review / recover", inr(rs_w["total_at_risk_inr"]), "de-duplicated")
    st.markdown("#### Follow the rupee: contractor → method → outcome")
    flagged = set(fw.work_order_id)
    s = W.assign(outcome=np.where(W.work_order_id.isin(flagged), "Needs review",
                          np.where(W.reopened_within_30d == "Y", "Failed within 30 days", "Held")),
                 contractor=W.contractor_name.str.replace(" (synthetic)", ""))
    l1 = s.groupby(["contractor", "work_type"]).cost_inr.sum().reset_index()
    l2 = s.groupby(["work_type", "outcome"]).cost_inr.sum().reset_index()
    nodes = [f"Ward {ward} billed"] + sorted(s.contractor.unique()) + sorted(s.work_type.unique()) + ["Held", "Failed within 30 days", "Needs review"]
    ix = {n: i for i, n in enumerate(nodes)}
    src_, dst, val = [], [], []
    for c_, v in s.groupby("contractor").cost_inr.sum().items():
        src_.append(0); dst.append(ix[c_]); val.append(v)
    for row in l1.itertuples():
        src_.append(ix[row.contractor]); dst.append(ix[row.work_type]); val.append(row.cost_inr)
    for row in l2.itertuples():
        src_.append(ix[row.work_type]); dst.append(ix[row.outcome]); val.append(row.cost_inr)
    ncol = [INK] + [BLUE] * s.contractor.nunique() + [GREY] * s.work_type.nunique() + [GREEN, "#D99A00", ORANGE]
    sk = go.Figure(go.Sankey(node=dict(label=nodes, color=ncol, pad=14), link=dict(source=src_, target=dst, value=val,
                             hovertemplate="₹%{value:,.0f}<extra></extra>")))
    sk.update_layout(height=460, margin=dict(l=0, r=0, t=10, b=10))
    st.plotly_chart(sk, width="stretch")
    a, b = st.columns(2)
    with a:
        spend = wo.groupby("ward_code").cost_inr.sum()
        wm = wards.assign(billed_vs_budget=(wards.ward_code.map(spend) / wards.monsoon_repair_budget_inr_2025).round(2))
        m = px.choropleth_map(wm, geojson=t["wards_geo"], locations="ward_code", featureidkey="properties.ward_code",
                              color="billed_vs_budget", color_continuous_scale=["#E3E7EE", "#BCC8DC", "#F4B48E", "#C2410C"],
                              range_color=(0.7, 1.2), opacity=0.7, hover_name="ward_name", map_style="carto-positron",
                              center={"lat": 19.07, "lon": 72.87}, zoom=9.6, height=460)
        fh = t["flood_hotspots"]
        m.add_scattermap(lat=fh.lat, lon=fh.lon, text=fh.name, mode="markers", name="Flood hotspots",
                         marker=dict(size=fh.years_flagged_last_5 * 3 + 6, color=BLUE, opacity=.6))
        m.update_layout(margin=dict(l=0, r=0, t=30, b=0), title="Billed vs budget by ward, with flood hotspots")
        st.plotly_chart(m, width="stretch")
    with b:
        rain = t["rainfall_daily"].groupby("date").rainfall_mm.max()
        daily = W.groupby(W.assigned_at.dt.normalize()).cost_inr.sum()
        fig = go.Figure()
        fig.add_bar(x=rain.index, y=rain.values, name="Rainfall (mm, max of 2 stations)", marker_color="#9DB4EE")
        fig.add_scatter(x=daily.index, y=daily.values, name=f"Ward {ward} spend (₹)", yaxis="y2", mode="lines", line_color=ORANGE)
        fig.update_layout(height=460, title="Rain drives repair spending", margin=dict(l=0, r=0, t=30, b=0),
                          yaxis=dict(title="mm"), yaxis2=dict(title="₹", overlaying="y", side="right"), legend=dict(orientation="h", y=-0.15))
        st.plotly_chart(fig, width="stretch")

# =============== ③ AI INBOX (automation) ===============
with tabs[2]:
    st.markdown("### AI inbox: messy complaints and posts in, actionable issues out")
    st.caption("Pipeline: Claude triage (category, place, severity, noise) → merge duplicates → match to a road → "
               "risk score → recommended action. Claude reads the text; every number and decision rule is deterministic.")
    op = comp[comp.status.isin(["Open", "In Progress"]) & (comp.ward_code == ward)]
    locs = set(op.locality_text.dropna())
    posts = t["social_posts"][t["social_posts"].text.apply(lambda x: any(l.lower() in x.lower() for l in locs))]
    n = st.slider("Items to process", 5, 40, 15)
    inbox = pd.concat([op.head(n).assign(kind="complaint", text=op.description, ref=op.complaint_id, reported=op.category_reported),
                       posts.head(max(3, n // 3)).assign(kind="social post", ref=posts.post_id, reported="")], ignore_index=True)
    if st.button("▶ Run AI pipeline", type="primary") or st.session_state.get("ran_inbox") == ward:
        st.session_state["ran_inbox"] = ward
        bar = st.progress(0.0, "Claude is triaging…")
        rows = []
        for i, it in enumerate(inbox.itertuples()):
            tri = ai.triage(it.text, gazetteer)
            rows.append(dict(kind=it.kind, ref=it.ref, text=it.text, reported=it.reported, **tri))
            bar.progress((i + 1) / len(inbox), f"Triaged {i+1}/{len(inbox)}")
        bar.empty()
        res = pd.DataFrame(rows)
        res["category_changed"] = (res.kind == "complaint") & (res.reported != res.category) & (res.category != "Not a road issue")
        clean = res[~res.is_noise & (res.category != "Not a road issue")]
        issues = clean.assign(locality=clean.locality.replace("", np.nan).fillna("unknown")).groupby(["locality", "category"]).size()
        plan = allocate(road_risk(t, open_issues(t, ward), DEFAULT_WEIGHTS), 1_000_000)
        k = st.columns(5)
        kpi(k[0], "Items read", len(res), f"{(res.kind=='social post').sum()} social posts")
        kpi(k[1], "Noise filtered", int(res.is_noise.sum() + (res.category == 'Not a road issue').sum()), "forwards, thanks, not roads")
        kpi(k[2], "Categories corrected", int(res.category_changed.sum()), "citizen picked wrong/vague")
        kpi(k[3], "Merged into issues", len(issues), "same place + problem")
        kpi(k[4], "Triage engine", res.source.mode()[0], "claude / cache / rules")
        fun = go.Figure(go.Funnel(y=["Received", "Real road issues", "Merged issues", "Matched to a road (ward)", "Funded in plan", "Sent to warranty contractor"],
                                  x=[len(res), len(clean), len(issues), len(plan["selected"]) + len(plan["deferred"]) + len(plan["dlp_routed"]),
                                     len(plan["selected"]), len(plan["dlp_routed"])], marker_color=[GREY, BLUE, BLUE, BLUE, GREEN, "#6D5BD0"]))
        fun.update_layout(height=330, margin=dict(l=0, r=0, t=10, b=0))
        st.plotly_chart(fun, width="stretch")
        st.caption("The last three stages use the whole ward's open complaints from ⑥ Next rupee.")
        show = res[["kind", "ref", "text", "reported", "category", "locality", "road_name", "severity", "is_noise", "source"]]
        st.dataframe(show.style.apply(lambda c: ["background:#FFF6F1" if v else "" for v in res.category_changed], subset=["category"]),
                     width="stretch", hide_index=True, height=360)
    else:
        st.dataframe(inbox[["kind", "ref", "text", "reported"]], width="stretch", hide_index=True, height=300)

# =============== ④ RECOVERY LEDGER ===============
with tabs[3]:
    rs = recovery_summary(findings)
    st.markdown(f"### {inr(rs['total_at_risk_inr'])} of {inr(wo.cost_inr.sum())} billed needs a second look")
    st.caption("Three deterministic rules. De-duplicated: a job caught by two rules counts once. Leads for review, not findings of wrongdoing.")
    k = st.columns(3)
    for col, (rid, row) in zip(k, rs["by_rule"].sort_values("at_risk_inr", ascending=False).iterrows()):
        kpi(col, RULE_LABEL[rid], inr(row.at_risk_inr), f"{row.jobs} jobs")
    a, b = st.columns([3, 2])
    with a:
        tm = findings.assign(contractor=findings.contractor.str.replace(" (synthetic)", ""), rule=findings.rule_id.map(RULE_LABEL))
        st.plotly_chart(px.treemap(tm, path=["rule", "contractor"], values="amount_at_risk_inr", color="rule",
                                   color_discrete_sequence=[ORANGE, BLUE, "#6D5BD0"], height=420,
                                   title="Money at risk by rule and contractor"), width="stretch")
    with b:
        dist = wo.assign(band=pd.cut(wo.cost_ratio, [0, .8, 1, 1.2, 1.3, 1.4, 2, 4]).astype(str))
        st.plotly_chart(px.histogram(wo, x="cost_ratio", nbins=60, height=420, color_discrete_sequence=[GREY],
                                     title="Bill ÷ rate card: normal variation vs outliers").add_vline(
            x=1.4, line_dash="dash", line_color=ORANGE, annotation_text="flag above 1.4×"), width="stretch")
    only = st.toggle(f"Only ward {ward}", value=True)
    f = findings[findings.ward_code == ward] if only else findings
    st.dataframe(f.sort_values("amount_at_risk_inr", ascending=False)[["finding_id", "rule_id", "work_order_id", "ward_code", "contractor",
                 "amount_billed_inr", "amount_at_risk_inr", "reason", "fair_context", "review_action"]], width="stretch", hide_index=True, height=300)
    c1, c2 = st.columns(2)
    c1.download_button("⬇ Export leads (CSV)", f.to_csv(index=False), "leads.csv")
    if c2.button("✍ Write ward officer brief"):
        risk = road_risk(t, open_issues(t, ward), DEFAULT_WEIGHTS)
        pl = allocate(risk, 1_000_000)
        payload = {"ward": ward, "leads": f.sort_values("amount_at_risk_inr", ascending=False).head(3).to_dict("records"),
                   "recoverable_inr": recovery_summary(f)["total_at_risk_inr"] if len(f) else 0, "n_leads": len(f),
                   "plan": [{k: s[k] for k in ["road_name", "category_reported", "risk_score", "est_cost_inr"]} for s in pl["selected"]]}
        brief, src = ai.officer_brief(payload)
        st.markdown(f'<span class="badge">{"Claude" if src in ("claude","cache") else "Template"}</span>', unsafe_allow_html=True)
        st.markdown(brief)
        st.download_button("⬇ Download brief", brief, f"brief_ward_{ward.replace('/', '-')}.md")

# =============== ⑤ SCORECARDS ===============
with tabs[4]:
    st.info("**System problem, not a contractor problem:** 24-hour SLAs are missed on almost every job by everyone, and "
            "warranty-period payments are spread across all contractors. Compare like with like below.")
    sc = wo.groupby("contractor_name").agg(jobs=("work_order_id", "size"), billed=("cost_inr", "sum"),
                                           on_time=("sla_met", lambda x: (x == "Y").mean()),
                                           reopened=("reopened_within_30d", lambda x: (x == "Y").mean()),
                                           over=("cost_ratio", lambda x: (x > 1.4).mean())).reset_index()
    sc["contractor"] = sc.contractor_name.str.replace(" (synthetic)", "")
    a, b = st.columns(2)
    with a:
        bub = px.scatter(sc, x="reopened", y="over", size="jobs", color="on_time", text="contractor", height=440,
                         color_continuous_scale="RdYlGn", labels={"reopened": "Fixes re-opened within 30 days",
                         "over": "Share of bills over 1.4× rate card", "on_time": "On time"},
                         title="Durability vs billing (bubble = jobs)")
        bub.update_traces(textposition="top center"); bub.update_xaxes(tickformat=".0%"); bub.update_yaxes(tickformat=".0%")
        st.plotly_chart(bub, width="stretch")
    with b:
        hm = wo.assign(contractor=wo.contractor_name.str.replace(" (synthetic)", "")).pivot_table(
            index="contractor", columns="sla_hours", values="sla_met", aggfunc=lambda x: (x == "Y").mean())
        st.plotly_chart(px.imshow(hm, text_auto=".0%", color_continuous_scale="RdYlGn", aspect="auto", height=440,
                                  labels=dict(x="SLA tier (hours)", color="On time"),
                                  title="On time within each SLA tier: the fair comparison"), width="stretch")
    pick_c = st.selectbox("Contractor report card", sc.contractor)
    row = sc.set_index("contractor").loc[pick_c]
    cm = wo[(wo.contractor_name.str.startswith(pick_c)) & (wo.repair_method == "Cold mix patch")]
    k = st.columns(4)
    kpi(k[0], "Jobs · billed", f"{row.jobs}", inr(row.billed)); kpi(k[1], "On time", f"{row.on_time:.0%}", f"peers {sc.on_time.min():.0%}–{sc.on_time.max():.0%}")
    kpi(k[2], "Re-opened", f"{row.reopened:.0%}", f"cold mix {(cm.reopened_within_30d=='Y').mean():.0%}")
    kpi(k[3], "Bills over 1.4×", f"{row.over:.0%}", f"peers {sc.over.min():.0%}–{sc.over.max():.0%}")

# =============== ⑥ NEXT RUPEE ===============
with tabs[5]:
    st.markdown(f"### Where should ward {ward}'s next rupee go?")
    rec = findings[(findings.ward_code == ward) & (findings.rule_id == "dlp_paid_by_bmc")].amount_at_risk_inr.sum()
    st.success(f"**Recover first:** {inr(rec)} of this ward's 2025 repairs were billed on roads still under warranty.")
    c1, c2 = st.columns([1, 3])
    with c1:
        budget_in = st.number_input("Budget to allocate (₹)", value=1_000_000, step=100_000, min_value=0)
        with st.expander("Risk weights", expanded=True):
            wts = {k: st.slider(k.capitalize(), 0, 10, v) for k, v in DEFAULT_WEIGHTS.items()}
    risk = road_risk(t, open_issues(t, ward), wts)
    if risk.empty:
        c2.info("No open complaints in this ward.")
    else:
        plan = allocate(risk, budget_in)
        status = {**{s["issue_id"]: "Funded" for s in plan["selected"]}, **{s["issue_id"]: "Deferred" for s in plan["deferred"]},
                  **{s["issue_id"]: "Warranty: ₹0 to BMC" for s in plan["dlp_routed"]}, **{s["issue_id"]: "Excluded" for s in plan["excluded"]}}
        risk["status"] = risk.issue_id.map(status)
        with c2:
            k = st.columns(4)
            kpi(k[0], "Planned (estimate)", inr(plan["total_inr"]), f"of {inr(budget_in)}")
            kpi(k[1], "Issues funded", len(plan["selected"]), f"{len(plan['deferred'])} deferred")
            kpi(k[2], "Sent to warranty", len(plan["dlp_routed"]), "₹0 to BMC")
            kpi(k[3], "Vs. complaint-count ranking", f"{plan['baseline_overlap']}/{len(plan['selected'])}", "same picks; rest are risk-driven")
            cmap = {"Funded": GREEN, "Deferred": "#D99A00", "Warranty: ₹0 to BMC": "#6D5BD0", "Excluded": GREY}
            top = risk.head(15).assign(label=lambda d: d.road_name + " · " + d.category_reported)
            st.plotly_chart(px.bar(top[::-1], x="risk_score", y="label", color="status", orientation="h", height=430,
                                   color_discrete_map=cmap, hover_data=["why", "method", "est_cost_inr"],
                                   title="Top issues by risk score (0–100)"), width="stretch")
        a, b = st.columns([3, 2])
        with a:
            mp = px.scatter_map(risk, lat="lat", lon="lon", color="status", size="risk_score", hover_name="road_name",
                                hover_data=["category_reported", "why"], color_discrete_map=cmap, zoom=13, height=420,
                                map_style="carto-positron")
            mp.update_layout(margin=dict(l=0, r=0, t=0, b=0), legend=dict(orientation="h", y=0))
            st.plotly_chart(mp, width="stretch")
        with b:
            st.markdown("**Funded, in priority order**")
            st.dataframe(pd.DataFrame(plan["selected"])[["road_name", "category_reported", "method", "est_cost_inr", "why"]]
                         if plan["selected"] else pd.DataFrame(), width="stretch", hide_index=True, height=360)
        with st.expander("Deferred, warranty-routed and excluded items, with reasons"):
            for name in ["deferred", "dlp_routed", "excluded"]:
                if plan[name]:
                    st.markdown(f"**{name.replace('_', ' ').title()}**")
                    st.dataframe(pd.DataFrame(plan[name])[["road_name", "category_reported", "risk_score", "est_cost_inr", "reason"]],
                                 width="stretch", hide_index=True)
        st.caption("Assumptions: " + " · ".join(plan["assumptions"]) + ". A recommendation for the ward officer, not a funding approval.")
        st.download_button("⬇ Export plan (CSV)", pd.DataFrame(plan["selected"]).to_csv(index=False), "next_rupee_plan.csv")

# =============== ⑦ ASK NAGARLENS ===============
with tabs[6]:
    st.markdown("### What happened to my complaint?")
    st.caption("Ask in English, Hindi, Marathi or Hinglish. Claude answers in your language using only the linked records.")
    q = st.text_input("Your question", "माझी तक्रार BMC25-001690 चं काय झालं?")
    m = re.search(r"BMC25-\d{6}", q)
    if not m:
        st.warning("Include your complaint number, e.g. BMC25-001690.")
    else:
        c = comp[comp.complaint_id == m.group(0)]
        if c.empty:
            st.error("No complaint with that number.")
        else:
            c = c.iloc[0]
            w_ = wo[wo.work_order_id == c.work_order_id]
            recs = {"complaint": c[["complaint_id", "received_at", "channel", "category_reported", "description", "status", "resolved_at"]].to_dict(),
                    "work_order": w_.iloc[0][["work_order_id", "contractor_name", "repair_method", "cost_inr", "expected_cost_inr",
                                              "sla_hours", "sla_met", "completed_at", "reopened_within_30d", "road_name"]].to_dict() if len(w_) else None}
            ans, src = ai.answer_citizen(q, recs)
            st.markdown(f'<div class="verdict"><span class="badge">{"Claude" if src in ("claude","cache") else "Template (Claude offline)"}</span>'
                        f'<p style="font-size:17px;line-height:1.7;margin:8px 0 0">{esc(ans)}</p></div>', unsafe_allow_html=True)
            if len(w_):
                x = w_.iloc[0]
                k = st.columns(4)
                kpi(k[0], "Complaint", c.complaint_id, f"{c.received_at:%d %b %Y}")
                kpi(k[1], "Work order", x.work_order_id, x.repair_method)
                kpi(k[2], "Billed", inr(x.cost_inr), f"rate card {inr(x.expected_cost_inr)}")
                kpi(k[3], "Outcome", "Re-opened" if x.reopened_within_30d == "Y" else "Held", "on time" if x.sla_met == "Y" else "late")

# =============== DATA QUALITY ===============
with tabs[7]:
    ids = wo.linked_complaint_ids.dropna().str.split("|").explode()
    iss = open_issues(t, ward)
    dq = pd.DataFrame([
        ["Complaint → work order", "exact", ids.isin(comp.complaint_id).sum() / len(comp)],
        ["Work order → complaint", "exact", (wo.n_linked_complaints > 0).mean()],
        ["Work order → road / rate card", "exact", wo.road_name.notna().mean()],
        [f"Open issue → road (ward {ward})", "candidate", (iss.match_class == "candidate").mean() if len(iss) else 0],
        ["Complaints with GPS", "data", comp.lat.notna().mean()],
        ["Complaints with ward", "data", comp.ward_code.notna().mean()]], columns=["link", "match_class", "coverage"])
    st.plotly_chart(px.bar(dq, x="coverage", y="link", color="match_class", orientation="h", height=360, text_auto=".0%",
                           color_discrete_map={"exact": GREEN, "candidate": "#D99A00", "data": GREY},
                           title="How complete is the trail?").update_xaxes(tickformat=".0%", range=[0, 1.05]), width="stretch")
    st.markdown('<span class="badge">Synthetic (organizer)</span> scored core &nbsp; <span class="badge" style="background:#E7F1FB">Live BMC</span> '
                'awaiting export into data/live/ &nbsp; <span class="badge" style="background:#EFEDFF">Synthetic (NagarLens)</span> our extensions',
                unsafe_allow_html=True)
