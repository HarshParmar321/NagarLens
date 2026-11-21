"""Audit leads ("needs review", never accusations), their evidence, and the officer's decision on each."""
from datetime import datetime, timezone

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import Session, select

from ..db import DECISIONS, LeadReview, get_session
from ..deps import DATA_LAYER, RULE_LABEL, clean_contractor, record, records, review_total, state

router = APIRouter(tags=["audit"])
TOLERANCE_RATIO = 1.3
WO_COLS = ["work_order_id", "ward_code", "road_id", "road_name", "work_type", "repair_method", "contractor_id",
           "contractor_name", "assigned_at", "work_started_at", "completed_at", "area_sqm", "cost_inr", "unit",
           "standard_rate_inr", "expected_cost_inr", "cost_ratio", "sla_hours", "sla_met", "reopened_within_30d",
           "n_linked_complaints", "under_dlp", "last_resurfaced", "engineer_remark", "hours_to_complete"]


def work_order(t: dict, work_order_id: str) -> dict | None:
    wo = t["work_orders"]
    hit = wo[wo.work_order_id == work_order_id]
    if hit.empty:
        return None
    d = record(hit.iloc[0][WO_COLS])
    d["contractor"] = clean_contractor(d["contractor_name"])
    return d


def _rows(f: pd.DataFrame) -> list[dict]:
    out = f.assign(rule=f.rule_id.map(RULE_LABEL), contractor=f.contractor.map(clean_contractor),
                   borderline=f.observed.str.contains("borderline", na=False))
    return records(out)


@router.get("/findings")
def findings(ward: str | None = None, rule: str | None = None, contractor_id: str | None = None,
             include_informational: bool = False, limit: int = Query(200, le=3000), offset: int = 0):
    s = state()
    f = s["informational"] if include_informational else s["findings"]
    if ward:
        f = f[f.ward_code == ward]
    if rule:
        f = f[f.rule_id.isin(rule.split(","))]
    if contractor_id:
        f = f[f.contractor_id == contractor_id]
    f = f.sort_values("amount_at_risk_inr", ascending=False)
    return {"data_layer": DATA_LAYER, "total": int(len(f)), "review": review_total(f[f.severity == "review"]),
            "rules": [{"rule_id": k, "label": v} for k, v in RULE_LABEL.items()],
            "rows": _rows(f.iloc[offset:offset + limit])}


@router.get("/findings/cost-ratio-histogram")
def cost_ratio_histogram(bin_width: float = 0.05):
    """Bill / rate card for every job: shows the gap between normal variation and the flagged outliers."""
    wo = state()["t"]["work_orders"]
    b = (wo.cost_ratio // bin_width * bin_width).round(2)
    h = b.value_counts().sort_index()
    return {"data_layer": DATA_LAYER, "threshold": 1.4, "normal_range": [0.75, 1.3],
            "bins": [{"ratio": float(k), "jobs": int(v), "flagged": bool(k >= 1.4)} for k, v in h.items()]}


@router.get("/findings/{finding_id}")
def finding(finding_id: str, session: Session = Depends(get_session)):
    s = state()
    t, f = s["t"], s["informational"]
    hit = f[f.finding_id == finding_id]
    if hit.empty:
        raise HTTPException(404, f"Unknown finding {finding_id}")
    row = _rows(hit)[0]
    me = work_order(t, row["work_order_id"])
    evidence: dict = {"work_order": me}
    if row["rule_id"] == "duplicate_bill":
        ids = row["evidence_ids"].split("|")
        twin = work_order(t, ids[1]) if len(ids) > 1 else None
        evidence["twin"] = twin
        if twin:
            a, b = pd.Timestamp(me["assigned_at"]), pd.Timestamp(twin["assigned_at"])
            evidence["match"] = {
                "same": {k: me[k] == twin[k] for k in ["road_id", "work_type", "repair_method", "contractor_id", "area_sqm"]},
                "days_apart": round(abs((a - b).total_seconds()) / 86400, 1),
                "cost_difference": round(abs(me["cost_inr"] / twin["cost_inr"] - 1), 4)}
    if row["rule_id"] == "overbilled_vs_rate_card":
        exp = me["expected_cost_inr"]
        evidence["rate_card"] = {
            "expected_cost_inr": int(round(exp)), "tolerance_inr": int(round(TOLERANCE_RATIO * exp)),
            "billed_inr": int(me["cost_inr"]), "cost_ratio": round(me["cost_ratio"], 2), "tolerance_ratio": TOLERANCE_RATIO,
            "basis": (f"{me['repair_method']}: ₹{me['standard_rate_inr']:,.0f} per sqm × {me['area_sqm']:g} sqm"
                      if me["unit"] == "per sqm" else f"{me['repair_method']}: ₹{me['standard_rate_inr']:,.0f} per job")}
    roads, wo = t["roads"], t["work_orders"]
    road = roads[roads.road_id == row["road_id"]]
    if len(road):
        on_road = wo[wo.road_id == row["road_id"]]
        evidence["road"] = record(road.iloc[0]) | {"jobs_this_monsoon": int(len(on_road)),
                                                   "billed_this_monsoon_inr": int(on_road.cost_inr.sum())}
    review = session.get(LeadReview, finding_id)
    return {"data_layer": DATA_LAYER, "finding": row, "evidence": evidence,
            "review": review.model_dump(mode="json") if review else None, "decisions": DECISIONS}


class ReviewIn(BaseModel):
    decision: str
    note: str = ""


@router.put("/findings/{finding_id}/review")
def set_review(finding_id: str, body: ReviewIn, session: Session = Depends(get_session)):
    """Record the officer's decision on a lead. A human decides; the audit only raises the lead."""
    f = state()["informational"]
    hit = f[f.finding_id == finding_id]
    if hit.empty:
        raise HTTPException(404, f"Unknown finding {finding_id}")
    if body.decision not in DECISIONS:
        raise HTTPException(422, f"decision must be one of {DECISIONS}")
    review = session.get(LeadReview, finding_id) or LeadReview(finding_id=finding_id, work_order_id=hit.iloc[0].work_order_id,
                                                              decision=body.decision)
    review.decision, review.note, review.decided_at = body.decision, body.note[:2000], datetime.now(timezone.utc)
    session.add(review)
    session.commit()
    session.refresh(review)
    return review.model_dump(mode="json")


@router.delete("/findings/{finding_id}/review")
def clear_review(finding_id: str, session: Session = Depends(get_session)):
    """Undo the officer's decision on a lead (also used to reset the demo before recording)."""
    review = session.get(LeadReview, finding_id)
    if review:
        session.delete(review)
        session.commit()
    return {"finding_id": finding_id, "cleared": bool(review)}


@router.get("/reviews")
def reviews(session: Session = Depends(get_session)):
    return [r.model_dump(mode="json") for r in session.exec(select(LeadReview)).all()]
