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
from src.budget import (DEFAULT_WEIGHTS, PLAN_DAYS, allocate, default_budget, excluded_complaints, map_open_complaints,
                        open_issues, road_risk)
from src.data import load_all
from src.scorecard import contractor_scorecard, scorecard_text, ward_scorecard

st.set_page_config(page_title="NagarLens", page_icon="🔎", layout="wide")
INK, BLUE, ORANGE, GREEN, GREY = "#16181D", "#1E4FD8", "#C2410C", "#1E7B34", "#8A8F98"

st.markdown("""<style>
.block-container{padding-top:4rem}
.kpi,.step,.verdict,.flag{color:#16181D}
.kpi{background:#FFFFFF;border:1px solid #D5D6D0;border-radius:14px;padding:14px 18px}
.kpi .l{font-size:13px;color:#454952;font-weight:600}.kpi .v{font-size:28px;font-weight:700;color:#16181D}.kpi .s{font-size:12px;color:#454952}
.steps{display:flex;gap:8px;flex-wrap:wrap;margin:6px 0 14px}
.step{flex:1 1 140px;border-radius:12px;padding:10px 12px;border:1px solid #D5D6D0;background:#FFFFFF}
.step .n{font-size:11px;font-weight:700;letter-spacing:.05em;text-transform:uppercase;color:#454952}
.step .t{font-size:15px;font-weight:700;margin-top:2px;color:#16181D}.step .d{font-size:12px;color:#2A2D33;margin-top:2px}
.ok{border-top:6px solid #1E7B34}.bad{border-top:6px solid #B4380A}.warn{border-top:6px solid #B07A00}.na{border-top:6px solid #8A8F98}
.verdict{background:#EEF3FD;border:1px solid #A9BEF0;border-radius:14px;padding:16px 18px}
.verdict p{color:#16181D}
.flag{background:#FFF3EC;border:1px solid #E9A988;border-radius:12px;padding:12px 14px;margin-bottom:8px}
.badge{display:inline-block;padding:2px 9px;border-radius:999px;font-size:11px;font-weight:700;background:#E4E4DE;color:#2A2D33}
.rc-chips{display:flex;gap:8px;margin:4px 0 10px}.rc-chip{flex:1;background:#FFFFFF;border:2px solid;border-radius:12px;padding:8px 10px;font-size:13px;color:#16181D}
.rc-chip .lab{font-size:11px;font-weight:700;text-transform:uppercase;color:#454952}
.hero{background:#16181D;color:#F6F6F3;border-radius:16px;padding:18px 24px;margin:0 0 14px;display:flex;flex-wrap:wrap;gap:10px 28px;align-items:center}
.hero .big{font-size:30px;font-weight:800;line-height:1.1}.hero .lab{font-size:12px;color:#C9CBD1}
.hero .arrow{font-size:26px;color:#8A8F98}.hero .accent{color:#FF9B6A}.hero .green{color:#7FD99A}
.pcard{display:flex;gap:12px;background:#FFFFFF;border:1px solid #D5D6D0;border-radius:12px;padding:10px 14px;margin-bottom:8px;color:#16181D}
.pcard .rank{font-size:22px;font-weight:800;color:#1E4FD8;min-width:26px}.pcard .pt{font-weight:700;font-size:15px}
.pcard .pm{font-size:12px;color:#454952;margin:2px 0 6px}
.chip{display:inline-block;font-size:11.5px;padding:2px 8px;border-radius:999px;background:#EEF3FD;color:#17306E;margin:0 4px 4px 0;border:1px solid #C9D7F5}
.st{font-size:11px;padding:2px 8px;border-radius:999px;margin-left:6px;font-weight:700}
.st-funded{background:#E5F4E4;color:#1E5B1F}.st-deferred{background:#F9EEDA;color:#7A4B00}.st-warranty{background:#EFEDFF;color:#3A2E8C}.st-excluded{background:#EDEDE8;color:#3B3F47}
</style>""", unsafe_allow_html=True)


@st.cache_data(show_spinner="Loading the dataset…")
def data():
    t = load_all()
    return t, run_audit(t)


@st.cache_data(show_spinner=False)
def scorecards(_t, _findings):
    return contractor_scorecard(_t, _findings), ward_scorecard(_t, _findings)


t, findings = data()
wo, comp, wards, roads = t["work_orders"], t["complaints"], t["wards"], t["roads"]
gazetteer = list(t["localities"].locality) + [a.strip() for s in t["localities"].aliases.dropna() for a in s.split(";")]


def kpi(col, label, value, sub=""):
    col.markdown(f'<div class="kpi"><div class="l">{label}</div><div class="v">{value}</div><div class="s">{sub}</div></div>',
                 unsafe_allow_html=True)


PLAN_COLS = {"road_name": "Road", "category_reported": "Problem", "risk_score": st.column_config.ProgressColumn("Risk", min_value=0, max_value=100, format="%.0f"),
             "est_cost_inr": st.column_config.NumberColumn("Est. cost (₹)", format="₹%,d"), "reason": "Why"}
LEAD_COLS = {"finding_id": "Lead", "rule": "Rule", "work_order_id": "Work order", "ward_code": "Ward", "contractor": "Contractor",
             "amount_billed_inr": st.column_config.NumberColumn("Billed (₹)", format="₹%,d"),
             "amount_at_risk_inr": st.column_config.NumberColumn("At risk (₹)", format="₹%,d"),
             "reason": st.column_config.TextColumn("Why flagged", width="large"), "review_action": "Next step"}


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

_rs = recovery_summary(findings)
_fw = findings[findings.ward_code == ward]
_wr = recovery_summary(_fw)["total_at_risk_inr"] if len(_fw) else 0
st.markdown(f'''<div class="hero">
  <div><div class="lab">Billed for 2025 monsoon road repairs</div><div class="big">{inr(wo.cost_inr.sum())}</div></div>
  <div class="arrow">→</div>
  <div><div class="lab">Needs a second look (3 rules, de-duplicated)</div><div class="big accent">{inr(_rs["total_at_risk_inr"])}</div></div>
  <div class="arrow">→</div>
  <div><div class="lab">Ward {esc(ward)}: recover {inr(_wr)}, then reinvest by risk</div><div class="big green">Next rupee plan</div></div>
  <div style="flex:1;min-width:200px;font-size:12px;color:#C9CBD1;text-align:right">NagarLens · Team 11<br>Synthetic organizer data · leads for review, not accusations</div>
</div>''', unsafe_allow_html=True)

# Tabs follow the brief's questions; the machinery (AI inbox, data quality) sits under "How it works".
T = st.tabs(["Where did the money go?", "Follow one case", "What doesn't add up?", "Who is responsible?",
             "Where should the next rupee go?", "Ask about my complaint", "How it works"])
with T[6]:
    H = st.tabs(["AI inbox: complaints in, issues out", "Data quality and match rates"])
# Index map kept from the original layout: 0 case, 1 overview, 2 AI inbox, 3 ledger, 4 scorecards, 5 next rupee, 6 ask, 7 data quality
tabs = [T[1], T[0], H[0], T[2], T[3], T[4], T[5], H[1]]

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
        ("5 · Did it hold?", "Held 30 days" if r.reopened_within_30d == "N" else "Re-opened within 30 days",
         "no failure recorded" if r.reopened_within_30d == "N" else
         (f"{len(later)} follow-up job(s) logged on this road" if len(later) else "marked re-opened; no follow-up job logged yet"),
         "ok" if r.reopened_within_30d == "N" else "bad"),
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
        ev = [dict(stage="Complaint → assigned", start=min(start, r.assigned_at), end=max(start, r.assigned_at)),
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
    st.markdown("#### Follow the rupee: where every billed rupee ended up")
    # Each job lands in exactly one outcome: its largest review lead, else failed within 30 days, else held.
    lead = fw.sort_values("amount_at_risk_inr", ascending=False).drop_duplicates("work_order_id").set_index("work_order_id").rule_id
    outcome = W.work_order_id.map(lead).map(RULE_LABEL).fillna(
        pd.Series(np.where(W.reopened_within_30d == "Y", "Failed within 30 days", "Held, no flag"), index=W.index))
    by = W.assign(outcome=outcome).groupby("outcome").cost_inr.sum()
    OUT_COL = {"Held, no flag": GREEN, "Failed within 30 days": "#D99A00", "Paid during warranty": "#6D5BD0",
               "Above rate card": ORANGE, "Possible duplicate bill": "#9A3208"}
    unspent = max(budget - billed, 0)
    nodes = [f"Ward budget {inr(budget)}", f"Billed {inr(billed)}"] + ([f"Unspent {inr(unspent)}"] if unspent else []) \
        + [f"{o} {inr(v)}" for o, v in by.items()]
    src_ = [0] + ([0] if unspent else []) + [1] * len(by)
    dst = [1] + ([2] if unspent else []) + list(range(2 + bool(unspent), 2 + bool(unspent) + len(by)))
    val = [min(billed, budget)] + ([unspent] if unspent else []) + list(by.values)
    ncol = [INK, BLUE] + ([GREY] if unspent else []) + [OUT_COL.get(o, GREY) for o in by.index]
    lcol = ["rgba(30,79,216,.25)"] + (["rgba(138,143,152,.25)"] if unspent else []) + \
           [OUT_COL.get(o, GREY) + "55" for o in by.index]
    sk = go.Figure(go.Sankey(node=dict(label=nodes, color=ncol, pad=18, thickness=22), textfont=dict(color=INK, size=14),
                             link=dict(source=src_, target=dst, value=val, color=lcol, hovertemplate="₹%{value:,.0f}<extra></extra>")))
    sk.update_layout(height=380, margin=dict(l=0, r=0, t=10, b=10))
    st.plotly_chart(sk, width="stretch")
    if billed > budget:
        st.caption(f"Billed exceeds the ward budget by {inr(billed - budget)}.")
    a, b = st.columns(2)
    with a:
        spend = wo.groupby("ward_code").cost_inr.sum()
        wm = wards.assign(billed_vs_budget=(wards.ward_code.map(spend) / wards.monsoon_repair_budget_inr_2025).round(2))
        m = px.choropleth_map(wm, geojson=t["wards_geo"], locations="ward_code", featureidkey="properties.ward_code",
                              color="billed_vs_budget", color_continuous_scale=["#E3E7EE", "#BCC8DC", "#F4B48E", "#C2410C"],
                              range_color=(0.7, 1.2), opacity=0.7, hover_name="ward_name", map_style="carto-positron",
                              labels={"billed_vs_budget": "Billed ÷ budget"},
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
        fig.add_scatter(x=daily.index, y=daily.values / 1e5, name=f"Ward {ward} billed (₹ lakh)", yaxis="y2", mode="lines", line_color=ORANGE)
        fig.update_layout(height=460, title="Rain drives repair spending", margin=dict(l=0, r=0, t=30, b=0),
                          yaxis=dict(title="mm"), yaxis2=dict(title="₹ lakh billed", overlaying="y", side="right", rangemode="tozero"), legend=dict(orientation="h", y=-0.15))
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
            tri = ai.triage(it.text, gazetteer, it.reported if isinstance(it.reported, str) else "")
            rows.append(dict(kind=it.kind, ref=it.ref, text=it.text, reported=it.reported, **tri))
            bar.progress((i + 1) / len(inbox), f"Triaged {i+1}/{len(inbox)}")
        bar.empty()
        res = pd.DataFrame(rows)
        res["category_changed"] = (res.kind == "complaint") & (res.reported != res.category) & (res.category != "Not a road issue")
        clean = res[~res.is_noise & (res.category != "Not a road issue")]
        placed = clean[(clean.locality != "") | (clean.road_name != "")]
        issues = placed.assign(place=placed.locality.where(placed.locality != "", placed.road_name)).groupby(["place", "category"]).size()
        k = st.columns(5)
        kpi(k[0], "Items read", len(res), f"{(res.kind=='social post').sum()} social posts")
        kpi(k[1], "Noise filtered", len(res) - len(clean), "forwards, thanks, not roads")
        kpi(k[2], "Categories corrected", int(res.category_changed.sum()), "citizen picked wrong/vague")
        kpi(k[3], "Merged into issues", len(issues), "same place + problem")
        kpi(k[4], "Triage engine", res.source.mode()[0], "claude / ollama / cache / rules")
        a, b = st.columns([3, 2])
        fun = go.Figure(go.Funnel(y=["Received", "Real road issues", "Place identified", "Merged issues"],
                                  x=[len(res), len(clean), len(placed), len(issues)], marker_color=[GREY, BLUE, BLUE, GREEN],
                                  textfont=dict(color="#FFFFFF", size=14)))
        fun.update_layout(height=300, margin=dict(l=0, r=0, t=30, b=0), title="This batch")
        a.plotly_chart(fun, width="stretch")
        _b, _ = default_budget(t, ward, findings)
        plan = allocate(road_risk(t, open_issues(t, ward), DEFAULT_WEIGHTS), _b, int(wrow.engineering_crews) * PLAN_DAYS)
        with b:
            st.markdown(f"**Whole ward {ward}: where the open issues end up** (default plan, see \"Where should the next rupee go?\")")
            kpi(st, "Funded in plan", len(plan["selected"]), f"{inr(plan['total_inr'])} estimated")
            kpi(st, "Sent to warranty contractor", len(plan["dlp_routed"]), "₹0 to BMC")
            kpi(st, "Deferred or manual review", len(plan["deferred"]) + len(plan["excluded"]), "over budget / no road match")
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
    c1, c2 = st.columns([1, 3])
    only = c1.toggle(f"Only ward {ward}", value=True)
    rules_pick = c2.segmented_control("Rule", [RULE_LABEL[r] for r in ["dlp_paid_by_bmc", "overbilled_vs_rate_card", "duplicate_bill"]],
                                      selection_mode="multi", default=[RULE_LABEL[r] for r in ["dlp_paid_by_bmc", "overbilled_vs_rate_card", "duplicate_bill"]])
    f = findings[findings.ward_code == ward] if only else findings
    f = f[f.rule_id.map(RULE_LABEL).isin(rules_pick or [])]
    st.dataframe(f.assign(rule=f.rule_id.map(RULE_LABEL), contractor=f.contractor.str.replace(" (synthetic)", ""))
                 .sort_values("amount_at_risk_inr", ascending=False)[list(LEAD_COLS)],
                 column_config=LEAD_COLS, width="stretch", hide_index=True, height=320)
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
    st.caption("Like for like: speed is compared with peers on the same SLA tier and flood exposure; durability with peers "
               "using the same repair method. A chip only moves off 'in line' when the gap is at least 3 points and "
               "more than twice its statistical uncertainty.")
    kind = st.segmented_control("Scorecards for", ["Contractors", "Wards"], default="Contractors")
    cs, ws = scorecards(t, findings)
    S = cs if kind != "Wards" else ws
    name_col = "contractor" if kind != "Wards" else "ward_label"
    if kind == "Wards":
        S = S.assign(ward_label=S.ward_code + " · " + S.ward_name)
    CHIP = {"better than peers": "#1E7B34", "in line with peers": "#5B6472", "below peers": "#B4380A"}
    a, b = st.columns([3, 2])
    with a:
        d = S.sort_values("reopen_gap")
        fig = go.Figure()
        for r_ in d.itertuples():
            fig.add_scatter(x=[r_.expected_reopen_rate, r_.reopen_rate], y=[getattr(r_, name_col)] * 2, mode="lines",
                            line=dict(color="#C9CCD2", width=3), showlegend=False, hoverinfo="skip")
        fig.add_scatter(x=d.expected_reopen_rate, y=d[name_col], mode="markers", name="Expected for the same methods",
                        marker=dict(size=11, color="#FFFFFF", line=dict(color=INK, width=2)))
        fig.add_scatter(x=d.reopen_rate, y=d[name_col], mode="markers", name="Actual",
                        marker=dict(size=13, color=[CHIP[c] for c in d.durability_chip]))
        fig.update_layout(height=max(320, 26 * len(d) + 120), margin=dict(l=0, r=0, t=40, b=0),
                          title="Fixes re-opened within 30 days: actual vs expected", legend=dict(orientation="h", y=-0.12))
        fig.update_xaxes(tickformat=".0%", title=None)
        st.plotly_chart(fig, width="stretch")
    with b:
        opts = list(S[name_col])
        default_i = next((i for i, o in enumerate(opts) if kind == "Wards" and o.startswith(ward + " ·")), 0)
        pick = st.selectbox("Report card", opts, index=default_i)
        row = S[S[name_col] == pick].iloc[0]
        chips = "".join(f'<div class="rc-chip" style="border-color:{CHIP[row[c]]}"><div class="lab">{lab}</div>'
                        f'<div style="color:{CHIP[row[c]]};font-weight:800">{esc(row[c])}</div></div>'
                        for lab, c in [("Speed", "speed_chip"), ("Durability", "durability_chip"), ("Cost", "cost_chip")])
        text, src = ai.scorecard_narrative(row.to_dict(), scorecard_text(row))
        st.markdown(f'<div class="rc-chips">{chips}</div><div class="verdict"><span class="badge">'
                    f'{"Written by Claude" if src in ("claude", "ollama", "cache") else "Plain-language summary"}</span>'
                    f'<p style="margin:8px 0 0;font-size:14.5px;line-height:1.55">{esc(text)}</p></div>', unsafe_allow_html=True)
        if row.get("small_sample"):
            st.caption("Small sample: read with care.")
    with st.expander(f"All {len(S)} {kind.lower()}: the numbers behind the chips"):
        cols = [name_col, "jobs", "billed_inr", "on_time_rate", "expected_on_time_rate", "reopen_rate", "expected_reopen_rate",
                "over_rate_card_jobs", "billing_review_inr", "speed_chip", "durability_chip", "cost_chip"]
        st.dataframe(S[cols], width="stretch", hide_index=True, column_config={
            name_col: "Name", "jobs": "Jobs", "billed_inr": st.column_config.NumberColumn("Billed (₹)", format="₹%,d"),
            "on_time_rate": st.column_config.NumberColumn("On time", format="percent"),
            "expected_on_time_rate": st.column_config.NumberColumn("Expected on time", format="percent"),
            "reopen_rate": st.column_config.NumberColumn("Re-opened", format="percent"),
            "expected_reopen_rate": st.column_config.NumberColumn("Expected re-opened", format="percent"),
            "over_rate_card_jobs": "Bills > 1.4×", "billing_review_inr": st.column_config.NumberColumn("Billing review (₹)", format="₹%,d"),
            "speed_chip": "Speed", "durability_chip": "Durability", "cost_chip": "Cost"})

# =============== ⑥ NEXT RUPEE ===============
with tabs[5]:
    st.markdown(f"### Where should ward {ward}'s next rupee go?")
    def_budget, budget_why = default_budget(t, ward, findings)
    crews = int(wrow.engineering_crews) * PLAN_DAYS
    c1, c2, c3 = st.columns([1, 1, 2])
    budget_in = c1.number_input("Budget to allocate (₹)", value=int(def_budget), step=100_000, min_value=0, key=f"bud_{ward}")
    c1.caption(f"Default: {budget_why}.")
    kpi(c2, "Crew capacity", f"{crews} jobs", f"{wrow.engineering_crews} crews × {PLAN_DAYS} days")
    with c3.popover("⚖ Adjust risk weights", width="stretch"):
        wcols = st.columns(2)
        wts = {k: wcols[i % 2].slider(k.capitalize(), 0, 10, v, key=f"w_{k}") for i, (k, v) in enumerate(DEFAULT_WEIGHTS.items())}
    c3.caption("Weights: " + " · ".join(f"{k} {v}" for k, v in wts.items()))
    risk = road_risk(t, open_issues(t, ward), wts)
    exc_c = excluded_complaints(t, ward)
    if risk.empty:
        st.info("No open road-repair issues in this ward.")
    else:
        plan = allocate(risk, budget_in, crews)
        backlog = risk[risk.under_dlp != "Y"].est_cost_inr.sum()
        status = {**{s["issue_id"]: "Funded" for s in plan["selected"]}, **{s["issue_id"]: "Deferred" for s in plan["deferred"]},
                  **{s["issue_id"]: "Warranty: ₹0 to BMC" for s in plan["dlp_routed"]}, **{s["issue_id"]: "Excluded" for s in plan["excluded"]}}
        risk["status"] = risk.issue_id.map(status)
        rank_cmp = risk[risk.est_cost_inr.notna()].reset_index(drop=True)
        top_risk = set(rank_cmp.head(10).issue_id)
        top_count = set(rank_cmp.sort_values(["complaints", "upvotes"], ascending=False).head(10).issue_id)
        if backlog <= budget_in:
            st.success(f"**Recover, then reinvest:** fixing every open road issue in this ward is estimated at **{inr(backlog)}**, "
                       f"within the {inr(budget_in)} available. The ranking below is the order crews should work in.")
        else:
            st.warning(f"Open backlog is estimated at {inr(backlog)}, more than the {inr(budget_in)} available: "
                       f"the lowest-risk items are deferred.")
        k = st.columns(4)
        kpi(k[0], "Planned (estimate)", inr(plan["total_inr"]), f"of {inr(budget_in)} available")
        kpi(k[1], "Issues funded", len(plan["selected"]), f"{len(plan['deferred'])} deferred")
        kpi(k[2], "Sent to warranty contractor", len(plan["dlp_routed"]), "₹0 to BMC")
        kpi(k[3], "Risk vs complaint-count ranking", f"{len(top_risk - top_count)} of top 10 differ",
            "issues a complaint count alone would rank lower")
        cmap = {"Funded": GREEN, "Deferred": "#D99A00", "Warranty: ₹0 to BMC": "#6D5BD0", "Excluded": GREY}
        a, b = st.columns([3, 2])
        with a:
            st.markdown("**Priority list**")
            cards = []
            for i, row in enumerate(risk.head(8).itertuples(), 1):
                chips = "".join(f'<span class="chip">{esc(x.strip())}</span>' for x in row.why.split(";"))
                cost = "₹0 (warranty)" if row.status.startswith("Warranty") else (inr(row.est_cost_inr) if pd.notna(row.est_cost_inr) else "no cost history")
                cards.append(f'<div class="pcard"><div class="rank">{i}</div><div style="flex:1">'
                             f'<div class="pt">{esc(row.road_name)} · {esc(row.category_reported)} '
                             f'<span class="st st-{esc(row.status.split(":")[0].lower())}">{esc(row.status)}</span></div>'
                             f'<div class="pm">{esc(row.locality_text)} · risk {row.risk_score:.0f}/100 · {esc(row.method or "")} · {cost} · {esc(row.match_class)}</div>'
                             f'<div>{chips}</div></div></div>')
            st.markdown("".join(cards), unsafe_allow_html=True)
        with b:
            pts = risk.dropna(subset=["lat", "lon"])
            mp = px.scatter_map(pts, lat="lat", lon="lon", color="status", size="risk_score", hover_name="road_name",
                                hover_data={"category_reported": True, "why": True, "lat": False, "lon": False},
                                color_discrete_map=cmap, zoom=13, height=520, size_max=22, map_style="carto-positron",
                                center={"lat": float(pts.lat.mean()), "lon": float(pts.lon.mean())})
            mp.update_layout(margin=dict(l=0, r=0, t=0, b=0), legend=dict(orientation="h", y=0, title=None))
            st.plotly_chart(mp, width="stretch")
        with st.expander(f"Deferred, warranty-routed and excluded: {len(plan['deferred']) + len(plan['dlp_routed']) + len(exc_c)} items, with reasons"):
            for name in ["deferred", "dlp_routed"]:
                if plan[name]:
                    st.markdown(f"**{'Deferred' if name == 'deferred' else 'Sent to warranty contractor'}**")
                    st.dataframe(pd.DataFrame(plan[name])[["road_name", "category_reported", "risk_score", "est_cost_inr", "reason"]],
                                 width="stretch", hide_index=True, column_config=PLAN_COLS)
            if len(exc_c):
                st.markdown("**Complaints not turned into a funded issue**")
                st.dataframe(exc_c[["complaint_id", "category", "locality", "description", "reason"]], width="stretch", hide_index=True)
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
                kpi(k[0], "Complaint", c.complaint_id, f"{c.received_at:%d %b %Y} · {c.status}")
                kpi(k[1], "Work order", x.work_order_id, x.repair_method)
                kpi(k[2], "Billed", inr(x.cost_inr), f"rate card {inr(x.expected_cost_inr)}")
                kpi(k[3], "Outcome", "Re-opened" if x.reopened_within_30d == "Y" else "Held", "on time" if x.sla_met == "Y" else "late")
                if c.status == "Closed - Duplicate":
                    st.info(f"Your complaint was merged with {x.n_linked_complaints - 1} other complaint(s) about the same problem into work order {x.work_order_id}.")
            elif c.status in ("Open", "In Progress"):
                if "_open_map" not in t:
                    t["_open_map"] = map_open_complaints(t)
                placed, exc_all = t["_open_map"]
                p = placed[placed.complaint_id == c.complaint_id]
                if len(p):
                    pw = p.iloc[0]
                    rk = road_risk(t, open_issues(t, pw.ward_code), DEFAULT_WEIGHTS).reset_index(drop=True)
                    hit = rk[(rk.road_id == pw.road_id) & (rk.category_reported == pw.category)]
                    pos = int(hit.index[0]) + 1 if len(hit) else None
                    k = st.columns(3)
                    kpi(k[0], "Status", c.status, f"logged {c.received_at:%d %b %Y}")
                    kpi(k[1], "Matched to", hit.road_name.iloc[0] if len(hit) else pw.road_id, pw.match_note)
                    kpi(k[2], f"Priority in ward {pw.ward_code}", f"#{pos} of {len(rk)}" if pos else "–",
                        hit.why.iloc[0] if len(hit) else "")
                else:
                    e = exc_all[exc_all.complaint_id == c.complaint_id]
                    st.warning("Not yet in a repair plan: " + (e.reason.iloc[0] if len(e) else "not matched to a road") + ".")
            else:
                st.info({"Forwarded to MMRDA/PWD": "This road is maintained by MMRDA/PWD, not BMC, so BMC forwarded your complaint to them.",
                         "Forwarded to SWM dept": "This was a solid-waste issue, so it went to BMC's SWM department, not the roads department.",
                         "Rejected - Not BMC road": "BMC rejected this complaint because the road is not a BMC road.",
                         "Rejected - Not road issue": "BMC rejected this complaint as not a road issue."}.get(c.status, f"Status: {c.status}"))

# =============== DATA QUALITY ===============
with tabs[7]:
    ids = wo.linked_complaint_ids.dropna().str.split("|").explode()
    if "_open_map" not in t:
        t["_open_map"] = map_open_complaints(t)
    placed, exc_all = t["_open_map"]
    n_open = len(placed) + len(exc_all)
    dq = pd.DataFrame([
        ["Complaint → work order", "exact", ids.isin(comp.complaint_id).sum() / len(comp)],
        ["Work order → complaint", "exact", (wo.n_linked_complaints > 0).mean()],
        ["Work order → road / rate card", "exact", wo.road_name.notna().mean()],
        ["Open complaint → road segment by GPS", "gps (validated 96%)", (placed.match_class == "gps").sum() / n_open],
        ["Open complaint → road named in text", "candidate", (placed.match_class == "road named").sum() / n_open],
        ["Open complaint → excluded, with reason", "unlinked", len(exc_all) / n_open],
        ["Complaints with GPS", "data", comp.lat.notna().mean()],
        ["Complaints with ward", "data", comp.ward_code.notna().mean()]], columns=["link", "match_class", "coverage"])
    st.caption(f"All {n_open} open complaints are accounted for. GPS matching was validated on the 4,948 linked complaints, "
               "where the true road is known from the work order: 96% land on the right segment. Locality-only matching was 28% "
               "accurate, so it is never used to fund a repair.")
    st.plotly_chart(px.bar(dq, x="coverage", y="link", color="match_class", orientation="h", height=360, text_auto=".0%",
                           color_discrete_map={"exact": GREEN, "gps (validated 96%)": "#3E9B57", "candidate": "#D99A00", "unlinked": "#B4380A", "data": GREY},
                           title="How complete is the trail?").update_xaxes(tickformat=".0%", range=[0, 1.05]), width="stretch")
    st.markdown('<span class="badge">Synthetic (organizer)</span> scored core &nbsp; <span class="badge" style="background:#E7F1FB">Live BMC</span> '
                'awaiting export into data/live/ &nbsp; <span class="badge" style="background:#EFEDFF">Synthetic (NagarLens)</span> our extensions',
                unsafe_allow_html=True)
