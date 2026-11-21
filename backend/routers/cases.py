"""Follow one case: complaint(s) -> work order -> road -> bill vs rate card -> did it hold -> audit leads."""
import pandas as pd
from fastapi import APIRouter, HTTPException, Query

from ..deps import DATA_LAYER, RULE_LABEL, clean_contractor, record, records, state
from .audit import work_order

router = APIRouter(tags=["cases"])

PRESETS = [
    {"work_order_id": "WO25-02068", "label": "Paid during warranty", "place": "Kurla"},
    {"work_order_id": "WO25-00268", "label": "3 complaints, warranty road", "place": "Kurla"},
    {"work_order_id": "WO25-02472", "label": "Possible duplicate bill", "place": "Dharavi"},
    {"work_order_id": "WO25-01576", "label": "Billed 3.1× the rate card", "place": "Western Express Highway"},
    {"work_order_id": "WO25-00646", "label": "Fixed fast, failed in 30 days", "place": "Tilak Nagar"},
]
C_COLS = ["complaint_id", "received_at", "channel", "category_reported", "description", "language", "locality_text",
          "ward_code", "lat", "lon", "upvotes", "status", "resolved_at", "work_order_id"]


@router.get("/cases/presets")
def presets():
    return PRESETS


@router.get("/cases")
def cases(ward: str | None = None, q: str | None = None, limit: int = Query(100, le=500)):
    """Work orders to pick from, largest bill first."""
    s = state()
    wo = s["t"]["work_orders"]
    flagged = set(s["findings"].work_order_id)
    d = wo[wo.ward_code == ward] if ward else wo
    if q:
        d = d[d.work_order_id.str.contains(q, case=False, regex=False) | d.road_name.str.contains(q, case=False, regex=False)]
    d = d.sort_values("cost_inr", ascending=False).head(limit)
    out = d[["work_order_id", "ward_code", "road_name", "work_type", "cost_inr", "reopened_within_30d"]].copy()
    out["flagged"] = out.work_order_id.isin(flagged)
    return {"data_layer": DATA_LAYER, "rows": records(out)}


@router.get("/cases/{work_order_id}")
def case(work_order_id: str):
    s = state()
    t, f = s["t"], s["findings"]
    w = work_order(t, work_order_id)
    if w is None:
        raise HTTPException(404, f"Unknown work order {work_order_id}")
    wo, c, roads = t["work_orders"], t["complaints"], t["roads"]
    cc = c[c.work_order_id == work_order_id].sort_values("received_at")
    road = roads[roads.road_id == w["road_id"]].iloc[0]
    assigned, started, done = (pd.Timestamp(w[k]) for k in ["assigned_at", "work_started_at", "completed_at"])
    first = cc.received_at.min() if len(cc) else None
    clock_start = first if first is not None else assigned
    hist = wo[wo.road_id == w["road_id"]].sort_values("assigned_at")
    later = hist[(hist.assigned_at > done) & (hist.assigned_at <= done + pd.Timedelta(days=30)) & (hist.work_type == w["work_type"])]
    flagged = f[f.work_order_id.isin(hist.work_order_id)].groupby("work_order_id").rule_id.apply(
        lambda x: [RULE_LABEL[r] for r in x])
    h = hist[["work_order_id", "assigned_at", "completed_at", "work_type", "repair_method", "contractor_name", "cost_inr",
              "cost_ratio", "sla_met", "reopened_within_30d", "n_linked_complaints"]].copy()
    h["contractor"] = h.contractor_name.map(clean_contractor)
    h["flags"] = h.work_order_id.map(flagged).apply(lambda v: v if isinstance(v, list) else [])
    h["is_this_case"] = h.work_order_id == work_order_id
    fh = f[f.work_order_id == work_order_id]
    iso = lambda ts: None if ts is None or pd.isna(ts) else pd.Timestamp(ts).isoformat()
    return {
        "data_layer": DATA_LAYER,
        "work_order": w,
        "complaints": records(cc[C_COLS]),
        "road": record(road),
        "timeline": {
            "first_complaint_at": iso(first), "assigned_at": iso(assigned), "work_started_at": iso(started),
            "completed_at": iso(done), "sla_deadline": iso(clock_start + pd.Timedelta(hours=int(w["sla_hours"]))),
            "sla_clock_starts": "first complaint" if first is not None else "assignment (no complaint linked)",
            # 284 work orders were assigned up to a day before their first linked complaint was logged
            "assigned_before_first_complaint": bool(first is not None and assigned < first),
            "hours_first_complaint_to_done": None if first is None else round((done - first).total_seconds() / 3600, 1)},
        "bill": {"billed_inr": int(w["cost_inr"]), "expected_cost_inr": int(round(w["expected_cost_inr"])),
                 "upper_normal_inr": int(round(1.3 * w["expected_cost_inr"])), "cost_ratio": round(w["cost_ratio"], 2),
                 "flagged": bool(w["cost_ratio"] > 1.4),
                 "basis": (f"₹{w['standard_rate_inr']:,.0f} per sqm × {w['area_sqm']:g} sqm" if w["unit"] == "per sqm"
                           else f"₹{w['standard_rate_inr']:,.0f} per job")},
        "outcome": {"held_30_days": w["reopened_within_30d"] == "N", "repeat_jobs_within_30d": later.work_order_id.tolist()},
        "findings": records(fh.assign(rule=fh.rule_id.map(RULE_LABEL))),
        "road_history": records(h),
        "road_history_total": {"jobs": int(len(hist)), "billed_inr": int(hist.cost_inr.sum()),
                               "reopened": int((hist.reopened_within_30d == "Y").sum())},
    }


@router.get("/complaints/{complaint_id}")
def complaint(complaint_id: str):
    t = state()["t"]
    c = t["complaints"]
    hit = c[c.complaint_id == complaint_id]
    if hit.empty:
        raise HTTPException(404, f"Unknown complaint {complaint_id}")
    row = record(hit.iloc[0][C_COLS])
    return {"data_layer": DATA_LAYER, "complaint": row,
            "work_order": work_order(t, row["work_order_id"]) if row["work_order_id"] else None}
