"""Wards: the map table, boundaries, and one ward's money trail."""
import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException

from ..deps import DATA_LAYER, RULE_LABEL, clean_contractor, record, records, review_total, state

router = APIRouter(tags=["wards"])

OUTCOME_HELD, OUTCOME_FAILED = "Held 30 days", "Failed within 30 days"


@router.get("/wards")
def wards():
    """One row per ward for the map and the ward picker (scorecard columns included)."""
    s = state()
    w = s["t"]["wards"].set_index("ward_code")
    sc = s["wards"].copy()
    sc["centroid_lat"] = sc.ward_code.map(w.centroid_lat)
    sc["centroid_lon"] = sc.ward_code.map(w.centroid_lon)
    sc["review_share"] = (sc.total_review_inr / sc.billed_inr.where(sc.billed_inr > 0)).fillna(0)
    sc["remaining_inr"] = sc.budget_inr - sc.billed_inr
    return {"data_layer": DATA_LAYER, "rows": records(sc)}


@router.get("/wards/geojson")
def wards_geojson():
    """Approximate (Voronoi) ward boundaries from the organizer dataset, not official boundaries."""
    return state()["t"]["wards_geo"]


def _money_flow(W: pd.DataFrame, fw: pd.DataFrame) -> dict:
    """Billed -> work type -> outcome. A flagged job goes to its rule (the one with most at risk), once."""
    top_rule = (fw.sort_values("amount_at_risk_inr", ascending=False).drop_duplicates("work_order_id")
                .set_index("work_order_id").rule_id.map(RULE_LABEL))
    outcome = W.work_order_id.map(top_rule)
    outcome = outcome.fillna(pd.Series(np.where(W.reopened_within_30d == "Y", OUTCOME_FAILED, OUTCOME_HELD), index=W.index))
    d = W.assign(outcome=outcome)
    types = list(d.groupby("work_type").cost_inr.sum().sort_values(ascending=False).index)
    order = [OUTCOME_HELD, OUTCOME_FAILED, *RULE_LABEL.values()]
    outcomes = [o for o in order if o in set(d.outcome)]
    nodes = ["Billed"] + types + outcomes
    ix = {n: i for i, n in enumerate(nodes)}
    kind = ["source"] + ["work_type"] * len(types) + [
        "held" if o == OUTCOME_HELD else "failed" if o == OUTCOME_FAILED else "review" for o in outcomes]
    links = [{"source": 0, "target": ix[k], "value": int(v)} for k, v in d.groupby("work_type").cost_inr.sum().items()]
    links += [{"source": ix[a], "target": ix[b], "value": int(v)}
              for (a, b), v in d.groupby(["work_type", "outcome"]).cost_inr.sum().items()]
    return {"nodes": [{"name": n, "kind": k} for n, k in zip(nodes, kind)], "links": links,
            "by_outcome": [{"outcome": o, "billed_inr": int(d[d.outcome == o].cost_inr.sum()),
                            "jobs": int((d.outcome == o).sum())} for o in outcomes]}


@router.get("/wards/{ward:path}")
def ward_detail(ward: str):
    s = state()
    t, f = s["t"], s["findings"]
    sc = s["wards"]
    if ward not in set(sc.ward_code):
        raise HTTPException(404, f"Unknown ward {ward}")
    wo = t["work_orders"]
    W, fw = wo[wo.ward_code == ward], f[f.ward_code == ward]

    rain = t["rainfall_daily"].groupby("date").rainfall_mm.max()
    weekly = pd.DataFrame({"rainfall_mm": rain.resample("W-MON", label="left", closed="left").sum()})
    weekly["billed_inr"] = W.set_index("assigned_at").cost_inr.resample("W-MON", label="left", closed="left").sum()
    weekly["jobs"] = W.set_index("assigned_at").cost_inr.resample("W-MON", label="left", closed="left").size()
    weekly = weekly.fillna(0).loc["2025-06-01":"2025-10-15"].reset_index().rename(columns={"date": "week"})
    weekly["week"] = weekly.week.dt.strftime("%Y-%m-%d")

    by_c = W.groupby("contractor_name").agg(
        jobs=("work_order_id", "size"), billed_inr=("cost_inr", "sum"),
        reopen_rate=("reopened_within_30d", lambda x: float((x == "Y").mean())),
        on_time_rate=("sla_met", lambda x: float((x == "Y").mean()))).reset_index()
    by_c["contractor"] = by_c.contractor_name.map(clean_contractor)

    by_road = W.groupby(["road_id", "road_name"]).agg(
        jobs=("work_order_id", "size"), billed_inr=("cost_inr", "sum"),
        reopened=("reopened_within_30d", lambda x: int((x == "Y").sum())),
        under_dlp=("under_dlp", "first")).reset_index().sort_values("billed_inr", ascending=False)
    by_road["review_inr"] = by_road.road_id.map(
        fw.sort_values("amount_at_risk_inr", ascending=False).drop_duplicates("work_order_id")
        .groupby("road_id").amount_at_risk_inr.sum()).fillna(0).astype(int)

    c = t["complaints"]
    cw = c[c.ward_code == ward]
    return {
        "data_layer": DATA_LAYER,
        "ward": record(sc[sc.ward_code == ward].iloc[0]),
        "review": review_total(fw),
        "money_flow": _money_flow(W, fw),
        "weekly": records(weekly),
        "contractors": records(by_c.sort_values("billed_inr", ascending=False)),
        "roads": records(by_road.head(12)),
        "complaints": {"total": int(len(cw)), "linked_to_work_order": int(cw.work_order_id.notna().sum()),
                       "open": int(cw.status.isin(["Open", "In Progress"]).sum())},
    }
