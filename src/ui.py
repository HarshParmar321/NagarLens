"""Reusable UI pieces: evidence cards, the ward map and the SLA heatmap. Owner: UI / story lead.

Pure functions only: each returns an HTML string or a Plotly figure and leaves layout to app.py.
Every value interpolated into HTML goes through html.escape, because the app renders with unsafe_allow_html.
Colour meaning is the same everywhere: green = held, amber = failed, orange = needs review, purple = warranty.
"""
import base64
import html
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go

from .audit import RULE_LABEL, TOLERANCE_RATIO, recovery_summary

INK, MUTED, LINE, PAPER = "#16181D", "#454952", "#D5D6D0", "#FFFFFF"
BLUE, ORANGE, GREEN, AMBER, PURPLE, GREY = "#1E4FD8", "#C2410C", "#1E7B34", "#B07A00", "#5B4BC4", "#8A8F98"
RULE_COLOR = {"overbilled_vs_rate_card": ORANGE, "duplicate_bill": BLUE, "dlp_paid_by_bmc": PURPLE,
              "reopened_fix": AMBER, "sla_missed": GREY}
REVIEW_SCALE = ["#FDF3EC", "#F9D2B8", "#F0A070", "#D9662B", "#A8340A"]   # single hue: more to review = darker
HERO_IMAGE = Path(__file__).resolve().parent.parent / "docs" / "assets" / "hero.png"


def esc(v) -> str:
    """Escape any value for use inside HTML text or attribute values."""
    return html.escape("" if v is None or (isinstance(v, float) and pd.isna(v)) else str(v), quote=True)


def inr(x) -> str:
    x = float(x)
    return f"₹{x / 1e7:.2f} Cr" if abs(x) >= 1e7 else f"₹{x / 1e5:.1f} L" if abs(x) >= 1e5 else f"₹{x:,.0f}"


def _clean(name) -> str:
    return str(name).replace(" (synthetic)", "")


def _when(ts) -> str:
    return "" if pd.isna(ts) else f"{pd.Timestamp(ts):%d %b %Y, %H:%M}"


def _wo(t: dict, work_order_id: str):
    w = t["work_orders"]
    hit = w[w.work_order_id == work_order_id]
    return None if hit.empty else hit.iloc[0]


# ---------------------------------------------------------------- evidence cards
_CARD = f"background:{PAPER};border:1px solid {LINE};border-radius:14px;padding:16px 18px;color:{INK};font-size:14px;line-height:1.5"
_LAB = f"font-size:11px;font-weight:700;letter-spacing:.05em;text-transform:uppercase;color:{MUTED}"
_PILL = "display:inline-block;padding:2px 10px;border-radius:999px;font-size:11.5px;font-weight:700"


def _pill(text: str, color: str, bg: str) -> str:
    return f'<span style="{_PILL};color:{color};background:{bg}">{esc(text)}</span>'


def _header(f: dict) -> str:
    color = RULE_COLOR.get(f.get("rule_id"), GREY)
    status = "For context" if f.get("severity") == "informational" else "Needs review"
    at_risk = f.get("amount_at_risk_inr") or 0
    right = (f'<div style="text-align:right"><div style="{_LAB}">To review</div>'
             f'<div style="font-size:24px;font-weight:800;color:{color}">{esc(inr(at_risk))}</div></div>') if at_risk else ""
    return (f'<div style="display:flex;justify-content:space-between;gap:16px;align-items:flex-start;'
            f'border-left:5px solid {color};padding-left:12px;margin-bottom:12px">'
            f'<div><div style="font-size:17px;font-weight:800">{esc(RULE_LABEL.get(f.get("rule_id"), f.get("rule_id")))}'
            f' <span style="font-weight:500;color:{MUTED}">· {esc(f.get("work_order_id"))}</span></div>'
            f'<div style="margin-top:4px">{_pill(status, INK, "#E4E4DE")} '
            f'{_pill("Synthetic (organizer)", MUTED, "#F1F1EC")}'
            f' <span style="font-size:12px;color:{MUTED}">{esc(f.get("finding_id"))} · ward {esc(f.get("ward_code"))}'
            f' · {esc(_clean(f.get("contractor")))}</span></div></div>{right}</div>')


def _footer(f: dict) -> str:
    return (f'<div style="margin-top:14px;padding-top:12px;border-top:1px solid {LINE};display:grid;'
            f'grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px">'
            f'<div><div style="{_LAB}">Why it was flagged</div>{esc(f.get("reason"))}</div>'
            f'<div><div style="{_LAB}">Fair context</div>{esc(f.get("fair_context"))}</div>'
            f'<div><div style="{_LAB}">Next action</div><b>{esc(f.get("review_action"))}</b></div></div>'
            f'<div style="margin-top:8px;font-size:11.5px;color:{MUTED}">Evidence: {esc(str(f.get("evidence_ids", "")).replace("|", " · "))}'
            f' · amounts are billed amounts (not payments) from work_orders.csv · a lead for review, not a finding of wrongdoing</div>')


def _bill_column(title: str, tone: str, r, same: dict) -> str:
    """One bill in the side-by-side duplicate view. `same` marks the fields that match the other bill."""
    def row(label, value, key=None):
        tick = (f'<span title="matches the other bill" style="color:{ORANGE};font-weight:800"> =</span>'
                if key and same.get(key) else "")
        return (f'<div style="display:flex;justify-content:space-between;gap:10px;padding:4px 0;border-bottom:1px dashed {LINE}">'
                f'<span style="color:{MUTED}">{esc(label)}</span><span style="text-align:right;font-weight:600">{esc(value)}{tick}</span></div>')
    n = int(r.n_linked_complaints)
    complaints = (f'<span style="color:{GREEN};font-weight:700">{n} citizen complaint{"s" if n != 1 else ""} linked</span>'
                  if n else f'<span style="color:{ORANGE};font-weight:700">No complaint linked</span>')
    return (f'<div style="flex:1 1 260px;border:1px solid {LINE};border-top:5px solid {tone};border-radius:12px;padding:12px 14px">'
            f'<div style="{_LAB}">{esc(title)}</div>'
            f'<div style="font-size:16px;font-weight:800;margin:2px 0 2px">{esc(r.work_order_id)}</div>'
            f'<div style="margin-bottom:6px">{complaints}</div>'
            + row("Road", f"{r.road_name} ({r.road_id})", "road") + row("Work type", r.work_type, "work_type")
            + row("Method", r.repair_method, "method") + row("Contractor", _clean(r.contractor_name), "contractor")
            + row("Area", f"{r.area_sqm:g} sqm", "area") + row("Assigned", _when(r.assigned_at))
            + row("Completed", _when(r.completed_at))
            + f'<div style="display:flex;justify-content:space-between;padding-top:8px"><span style="color:{MUTED}">Billed</span>'
              f'<span style="font-size:20px;font-weight:800">₹{esc(f"{r.cost_inr:,.0f}")}</span></div></div>')


def _duplicate_body(f: dict, t: dict) -> str:
    ids = str(f.get("evidence_ids", "")).split("|")[:2]
    me, twin = _wo(t, f.get("work_order_id")), (_wo(t, ids[1]) if len(ids) > 1 else None)
    if me is None or twin is None:
        return ""
    same = {"road": me.road_id == twin.road_id, "work_type": me.work_type == twin.work_type,
            "method": me.repair_method == twin.repair_method, "contractor": me.contractor_id == twin.contractor_id,
            "area": me.area_sqm == twin.area_sqm}
    first, second = (twin, me) if twin.assigned_at <= me.assigned_at else (me, twin)
    days = abs((me.assigned_at - twin.assigned_at).total_seconds()) / 86400
    diff = abs(me.cost_inr / twin.cost_inr - 1)
    label = lambda r: "This bill (flagged)" if r.work_order_id == me.work_order_id else "The matching bill"
    tone = lambda r: ORANGE if r.work_order_id == me.work_order_id else GREEN
    middle = (f'<div style="flex:0 0 auto;align-self:center;text-align:center;color:{MUTED};font-size:12px">'
              f'<div style="font-size:22px;font-weight:800;color:{INK}">{days:.0f} day{"s" if round(days) != 1 else ""}</div>apart'
              f'<div style="font-size:22px;font-weight:800;color:{INK};margin-top:6px">{diff:.1%}</div>cost difference'
              f'<div style="margin-top:6px"><span style="color:{ORANGE};font-weight:800">=</span> same in both</div></div>')
    return (f'<div style="display:flex;gap:14px;flex-wrap:wrap">{_bill_column(label(first), tone(first), first, same)}'
            f'{middle}{_bill_column(label(second), tone(second), second, same)}</div>')


def _bar(label: str, value: float, vmax: float, color: str, note: str = "") -> str:
    pct = max(2.0, min(100.0, 100 * value / vmax)) if vmax else 0
    return (f'<div style="display:grid;grid-template-columns:150px 1fr 110px;gap:10px;align-items:center;margin:6px 0">'
            f'<div style="color:{MUTED};font-size:13px">{esc(label)}</div>'
            f'<div style="background:#EFEFEA;border-radius:6px;height:22px"><div style="width:{pct:.1f}%;height:22px;'
            f'border-radius:6px;background:{color}"></div></div>'
            f'<div style="text-align:right;font-weight:700">₹{esc(f"{value:,.0f}")}'
            f'<div style="font-size:11px;font-weight:500;color:{MUTED}">{esc(note)}</div></div></div>')


def _overbilled_body(f: dict, t: dict) -> str:
    r = _wo(t, f.get("work_order_id"))
    if r is None:
        return ""
    exp, tol, billed = float(r.expected_cost_inr), TOLERANCE_RATIO * float(r.expected_cost_inr), float(r.cost_inr)
    basis = (f"{r.repair_method}: ₹{r.standard_rate_inr:,.0f} per sqm × {r.area_sqm:g} sqm" if r.unit == "per sqm"
             else f"{r.repair_method}: ₹{r.standard_rate_inr:,.0f} per job")
    borderline = "borderline" in str(f.get("observed", "")).lower()
    note = (f'<div style="margin-top:10px;background:#FFF8E6;border:1px solid #E8CF8A;border-radius:10px;padding:8px 12px">'
            f'<b>Borderline.</b> Only just above the 1.4× line and below the main group of outliers. '
            f'Check the measurement book first; this may be normal variation.</div>') if borderline else ""
    return (f'<div style="{_LAB}">Bill against the rate card</div>'
            + _bar("Rate card cost", exp, billed, GREY, "1.00×")
            + _bar("Upper end of normal", tol, billed, "#B9BDC6", f"{TOLERANCE_RATIO:.2f}×")
            + _bar("Billed", billed, billed, ORANGE, f"{r.cost_ratio:.2f}×")
            + f'<div style="font-size:12.5px;color:{MUTED};margin-top:4px">{esc(basis)}. Normal jobs fall between 0.75× and '
              f'1.3×. Amount to review = billed minus the upper end of normal = <b style="color:{INK}">'
              f'₹{esc(f"{max(billed - tol, 0):,.0f}")}</b>.</div>' + note)


def _dlp_body(f: dict, t: dict) -> str:
    r = _wo(t, f.get("work_order_id"))
    if r is None:
        return ""
    roads = t["roads"]
    road = roads[roads.road_id == r.road_id].iloc[0]
    wo = t["work_orders"]
    on_road = wo[wo.road_id == r.road_id]
    surface = str(f.get("dlp_scope", "")).startswith("surface")
    scope = (_pill("Surface defect: inside a resurfacing warranty", "#3A2E8C", "#EFEDFF") if surface else
             _pill("Drainage / manhole work: verify the warranty scope", "#7A4B00", "#F9EEDA"))
    cell = lambda label, value: (f'<div style="flex:1 1 150px"><div style="{_LAB}">{esc(label)}</div>'
                                 f'<div style="font-size:15px;font-weight:700">{esc(value)}</div></div>')
    return (f'<div style="display:flex;gap:14px;flex-wrap:wrap">'
            + cell("Road", f"{road.road_name} ({road.road_id})") + cell("Surface", road.surface)
            + cell("Last resurfaced", f"{pd.Timestamp(road.last_resurfaced):%d %b %Y}")
            + cell("Warranty (DLP) status", "Still under warranty" if road.under_dlp == "Y" else "Expired")
            + cell("This job", f"{r.work_type} · {r.repair_method}") + "</div>"
            + f'<div style="margin:12px 0 4px">{scope}</div>'
            + f'<div style="display:flex;gap:14px;flex-wrap:wrap;margin-top:8px">'
            + cell("Billed to BMC for this job", f"₹{r.cost_inr:,.0f}")
            + cell("Expected under warranty", "₹0 (original contractor repairs)" if surface else "Depends on the DLP contract")
            + cell("All jobs billed on this road this monsoon", f"{len(on_road)} jobs · {inr(on_road.cost_inr.sum())}") + "</div>")


def _generic_body(f: dict, t: dict) -> str:
    return (f'<div style="display:flex;gap:24px;flex-wrap:wrap"><div><div style="{_LAB}">Observed</div>'
            f'<div style="font-size:15px;font-weight:700">{esc(f.get("observed"))}</div></div>'
            f'<div><div style="{_LAB}">Baseline</div><div style="font-size:15px;font-weight:700">{esc(f.get("baseline"))}</div></div>'
            f'<div><div style="{_LAB}">Billed</div><div style="font-size:15px;font-weight:700">'
            f'{esc(inr(f.get("amount_billed_inr") or 0))}</div></div></div>')


def evidence_card(finding: dict, t: dict) -> str:
    """HTML evidence card for one audit lead (a row of run_audit() as a dict).

    duplicate_bill          -> the two bills side by side, matching fields marked
    overbilled_vs_rate_card -> rate card vs upper end of normal vs billed, plus the borderline note
    dlp_paid_by_bmc         -> road, last resurfaced date, warranty status and the DLP scope
    Render with st.markdown(evidence_card(f, t), unsafe_allow_html=True); every value is escaped here."""
    f = dict(finding)
    body = {"duplicate_bill": _duplicate_body, "overbilled_vs_rate_card": _overbilled_body,
            "dlp_paid_by_bmc": _dlp_body}.get(f.get("rule_id"), _generic_body)(f, t) or _generic_body(f, t)
    return f'<div style="{_CARD}">{_header(f)}{body}{_footer(f)}</div>'


# ---------------------------------------------------------------- ward map
def ward_review_table(t: dict, findings: pd.DataFrame) -> pd.DataFrame:
    """Per ward: billed, budget and the de-duplicated rupees to review (same maths as the headline)."""
    wo, w = t["work_orders"], t["wards"]
    flags = findings[findings.severity == "review"] if "severity" in findings else findings
    by = {k: recovery_summary(g) for k, g in flags.groupby("ward_code")}
    out = w[["ward_code", "ward_name", "centroid_lat", "centroid_lon", "monsoon_repair_budget_inr_2025"]].copy()
    out = out.rename(columns={"monsoon_repair_budget_inr_2025": "budget_inr"})
    out["billed_inr"] = out.ward_code.map(wo.groupby("ward_code").cost_inr.sum()).fillna(0)
    out["jobs"] = out.ward_code.map(wo.groupby("ward_code").size()).fillna(0).astype(int)
    out["review_inr"] = [by[k]["total_at_risk_inr"] if k in by else 0 for k in out.ward_code]
    out["review_jobs"] = [by[k]["jobs"] if k in by else 0 for k in out.ward_code]
    out["review_share"] = (out.review_inr / out.billed_inr.where(out.billed_inr > 0)).fillna(0)
    return out


def ward_map(t: dict, findings: pd.DataFrame, selected_ward: str | None = None, height: int = 520) -> go.Figure:
    """Ward choropleth coloured by de-duplicated rupees to review, with the selected ward outlined.

    Use with st.plotly_chart(fig, on_select="rerun", selection_mode="points", key=...) and read the click with
    selected_ward_from_event(). ward_code is the customdata of every point on both traces."""
    d = ward_review_table(t, findings)
    hover = ("<b>Ward %{customdata[0]}</b> · %{customdata[1]}<br>To review: <b>%{customdata[2]}</b> "
             "(%{customdata[3]} of billed, %{customdata[4]} jobs)<br>Billed: %{customdata[5]} · Budget: %{customdata[6]}"
             "<extra></extra>")
    custom = [[r.ward_code, r.ward_name, inr(r.review_inr), f"{r.review_share:.0%}", r.review_jobs,
               inr(r.billed_inr), inr(r.budget_inr)] for r in d.itertuples()]
    fig = go.Figure(go.Choroplethmap(
        geojson=t["wards_geo"], locations=d.ward_code, featureidkey="properties.ward_code", z=d.review_inr / 1e5,
        colorscale=[[i / (len(REVIEW_SCALE) - 1), c] for i, c in enumerate(REVIEW_SCALE)], zmin=0,
        marker=dict(opacity=0.78, line=dict(color="#FFFFFF", width=1)), customdata=custom, hovertemplate=hover,
        colorbar=dict(title=dict(text="To review<br>(₹ lakh)", font=dict(size=12)), thickness=12, len=0.6, x=0.99, xanchor="right",
                      bgcolor="rgba(255,255,255,0.8)", tickfont=dict(size=11)),
        selected=dict(marker=dict(opacity=0.78)), unselected=dict(marker=dict(opacity=0.78)), name="Wards"))
    # Ward labels: also a reliable click target, carrying the same customdata.
    fig.add_scattermap(lat=d.centroid_lat, lon=d.centroid_lon, mode="markers+text", text=d.ward_code,
                       marker=dict(size=22, color="rgba(255,255,255,0.01)"),
                       textfont=dict(size=12, color=INK, weight=700), customdata=custom, hovertemplate=hover,
                       selected=dict(marker=dict(opacity=0.01)), unselected=dict(marker=dict(opacity=0.01)),
                       name="Ward labels", showlegend=False)
    if selected_ward is not None:
        for feat in t["wards_geo"]["features"]:
            if feat["properties"].get("ward_code") == selected_ward:
                ring = feat["geometry"]["coordinates"][0]
                fig.add_scattermap(lat=[p[1] for p in ring], lon=[p[0] for p in ring], mode="lines",
                                   line=dict(color=INK, width=4), hoverinfo="skip", name=f"Ward {selected_ward}",
                                   showlegend=False)
    fig.update_layout(map=dict(style="carto-positron", center=dict(lat=19.085, lon=72.875), zoom=9.7),
                      height=height, margin=dict(l=0, r=0, t=0, b=0), clickmode="event+select", dragmode="pan",
                      showlegend=False, font=dict(color=INK))
    return fig


def selected_ward_from_event(event) -> str | None:
    """ward_code from the value st.plotly_chart(..., on_select="rerun") returns, or None if nothing is selected."""
    try:
        points = event["selection"]["points"] if isinstance(event, dict) else event.selection.points
    except (KeyError, AttributeError, TypeError):
        return None
    for p in points or []:
        cd = p.get("customdata")
        if isinstance(cd, (list, tuple)) and cd:
            return str(cd[0])
        if isinstance(cd, str):
            return cd
        if p.get("location"):
            return str(p["location"])
    return None


# ---------------------------------------------------------------- SLA heatmap
def sla_heatmap(t: dict, height: int = 440) -> go.Figure:
    """On-time rate by contractor x SLA tier, single hue. The bottom row shows every tier is hard for everyone."""
    wo = t["work_orders"]
    on = (wo.sla_met == "Y").astype(float)
    m = on.groupby([wo.contractor_name.map(_clean), wo.sla_hours]).mean().unstack()
    n = on.groupby([wo.contractor_name.map(_clean), wo.sla_hours]).size().unstack()
    m = m.loc[on.groupby(wo.contractor_name.map(_clean)).mean().sort_values(ascending=False).index]
    n = n.loc[m.index]
    m.loc["All contractors"] = on.groupby(wo.sla_hours).mean()
    n.loc["All contractors"] = on.groupby(wo.sla_hours).size()
    cols = [f"{int(c)} h" for c in m.columns]
    fig = go.Figure(go.Heatmap(
        z=m.values, x=cols, y=list(m.index), colorscale="Blues", zmin=0, zmax=1, xgap=3, ygap=3,
        text=[[f"{v:.0%}" for v in row] for row in m.values], texttemplate="%{text}", textfont=dict(size=13),
        customdata=n.values, hovertemplate="%{y}<br>%{x} SLA: <b>%{z:.0%}</b> on time (%{customdata:.0f} jobs)<extra></extra>",
        colorbar=dict(title=dict(text="On time"), tickformat=".0%", thickness=12, len=0.7)))
    fig.update_layout(height=height, margin=dict(l=0, r=0, t=46, b=0), font=dict(color=INK),
                      title=dict(text="On time within each SLA tier: urgent jobs are late for everyone", font=dict(size=15)),
                      xaxis=dict(title="SLA tier (target hours from first complaint)", side="bottom", type="category"),
                      yaxis=dict(autorange="reversed", title=None), plot_bgcolor=PAPER)
    return fig


# ---------------------------------------------------------------- hero illustration
def hero_background_css(selector: str = ".hero") -> str:
    """A <style> block that puts docs/assets/hero.png on the right of the dark hero band (empty string if missing).
    The image is embedded as a data URI so the app needs no static file server."""
    if not HERO_IMAGE.exists():
        return ""
    b64 = base64.b64encode(HERO_IMAGE.read_bytes()).decode()
    return (f"<style>{selector}{{background-image:linear-gradient(90deg,#16181D 0%,#16181D 38%,rgba(22,24,29,0.55) 62%,"
            f"rgba(22,24,29,0.15) 100%),url(data:image/png;base64,{b64});background-size:cover;"
            f"background-position:right center;background-repeat:no-repeat}}</style>")
