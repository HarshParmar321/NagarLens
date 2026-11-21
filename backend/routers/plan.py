"""Next Rupee planner endpoint. Owner: nagarlens-81.

GET /api/wards/{ward}/plan wraps src/budget.py unchanged: open complaints -> issues on road segments ->
citywide-normalised risk -> budget- and crew-capped allocation. Ward codes may contain "/" (e.g. "F/N").
"""
import math

from fastapi import APIRouter, HTTPException, Query

from src.budget import (DEFAULT_WEIGHTS, PLAN_DAYS, allocate, default_budget, excluded_complaints, open_issues,
                        road_risk)

from ..deps import DATA_LAYER, records, state

router = APIRouter(tags=["plan"])

ISSUE_FIELDS = ["issue_id", "road_id", "road_ids", "road_name", "category_reported", "complaints", "upvotes",
                "complaint_ids", "locality_text", "match_class", "lat", "lon", "first_reported", "under_dlp",
                "bus_route", "nearest_hotspot", "hospitals", "schools", "accidents", "repeat", "flood", "traffic",
                "social", "severity", "risk_score", "method", "method_why", "est_cost_inr", "why", "reason"]
STATUS = {"selected": "funded", "deferred": "deferred", "dlp_routed": "warranty", "excluded": "excluded"}


def _clean(v):
    if isinstance(v, float) and math.isnan(v):
        return None
    if hasattr(v, "isoformat"):
        return v.isoformat()
    if hasattr(v, "item"):
        return v.item()
    return v


def _issue(row: dict, status: str) -> dict:
    out = {k: _clean(row.get(k)) for k in ISSUE_FIELDS if k in row}
    if out.get("est_cost_inr") is not None:
        out["est_cost_inr"] = int(out["est_cost_inr"])
    out["road_ids"] = list(row.get("road_ids") or [])
    out["status"] = status
    return out


def build_plan(ward: str, budget_inr: int | None = None, weights: dict | None = None) -> dict:
    s = state()
    t, findings = s["t"], s["findings"]
    wards = t["wards"].set_index("ward_code")
    if ward not in wards.index:
        raise HTTPException(404, f"Unknown ward {ward!r}")
    weights = {**DEFAULT_WEIGHTS, **(weights or {})}
    default_inr, default_reason = default_budget(t, ward, findings)
    budget = default_inr if budget_inr is None else int(budget_inr)
    crew_jobs = int(wards.engineering_crews[ward]) * PLAN_DAYS
    risk = road_risk(t, open_issues(t, ward), weights)
    exc_c = excluded_complaints(t, ward)
    base = {"ward_code": ward, "default_budget_inr": int(default_inr), "default_budget_reason": default_reason,
            "weights": weights, "crew_jobs": crew_jobs, "plan_days": PLAN_DAYS, "data_layer": DATA_LAYER,
            "excluded_complaints": records(exc_c[["complaint_id", "category", "locality", "description", "reason"]])
            if len(exc_c) else []}
    if risk.empty:
        return {**base, "budget_inr": budget, "selected": [], "deferred": [], "dlp_routed": [], "excluded": [],
                "total_inr": 0, "unallocated_inr": budget, "baseline_overlap": 0, "assumptions": [],
                "backlog_inr": 0, "top10_differ_from_complaint_ranking": 0}
    plan = allocate(risk, budget, crew_jobs)
    costed = risk[risk.est_cost_inr.notna()].reset_index(drop=True)
    top_risk = set(costed.head(10).issue_id)
    top_count = set(costed.sort_values(["complaints", "upvotes"], ascending=False).head(10).issue_id)
    out = {**base, **{k: plan[k] for k in ["budget_inr", "total_inr", "unallocated_inr", "baseline_overlap", "assumptions"]}}
    for key, status in STATUS.items():
        out[key] = [_issue(r, status) for r in plan[key]]
    out["backlog_inr"] = int(risk[risk.under_dlp != "Y"].est_cost_inr.sum())
    out["top10_differ_from_complaint_ranking"] = len(top_risk - top_count)
    return out


@router.get("/wards/{ward:path}/plan")
def ward_plan(ward: str,
              budget_inr: int | None = Query(None, ge=0, description="Defaults to the remaining ward budget, or the "
                                             "recoverable amount for an overspent ward"),
              severity: int | None = Query(None, ge=0, le=10), flood: int | None = Query(None, ge=0, le=10),
              traffic: int | None = Query(None, ge=0, le=10), facilities: int | None = Query(None, ge=0, le=10),
              accidents: int | None = Query(None, ge=0, le=10), repeat: int | None = Query(None, ge=0, le=10),
              complaints: int | None = Query(None, ge=0, le=10), social: int | None = Query(None, ge=0, le=10)):
    given = dict(severity=severity, flood=flood, traffic=traffic, facilities=facilities, accidents=accidents,
                 repeat=repeat, complaints=complaints, social=social)
    return build_plan(ward, budget_inr, {k: v for k, v in given.items() if v is not None})
