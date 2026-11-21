"""AI endpoints. Owner: nagarlens-81.

Every call goes through src/ai.py: cached on disk, with a deterministic template fallback, and Claude never
changes a number. `source` says who wrote the text: claude | ollama | cache | template | rules.
"""
import re

import pandas as pd
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src import ai
from src.budget import DEFAULT_WEIGHTS, map_open_complaints, open_issues, road_risk

from ..deps import DATA_LAYER, record, state
from .plan import build_plan

router = APIRouter(tags=["ai"])

STATUS_NOTE = {
    "Forwarded to MMRDA/PWD": "This road is maintained by MMRDA/PWD, not BMC, so BMC forwarded the complaint to them.",
    "Forwarded to SWM dept": "This was a solid-waste issue, so it went to BMC's SWM department, not the roads department.",
    "Rejected - Not BMC road": "BMC rejected this complaint because the road is not a BMC road.",
    "Rejected - Not road issue": "BMC rejected this complaint as not a road issue.",
}
WO_FIELDS = ["work_order_id", "contractor_name", "repair_method", "cost_inr", "expected_cost_inr", "sla_hours", "sla_met",
             "completed_at", "reopened_within_30d", "road_name", "road_id", "n_linked_complaints"]


class AskIn(BaseModel):
    question: str


def _open_map(t):
    if "_open_map" not in t:
        t["_open_map"] = map_open_complaints(t)
    return t["_open_map"]


@router.post("/ask")
def ask(body: AskIn):
    t = state()["t"]
    m = re.search(r"BMC25-\d{6}", body.question.upper())
    if not m:
        raise HTTPException(422, "Include a complaint number, e.g. BMC25-001690.")
    c = t["complaints"][t["complaints"].complaint_id == m.group(0)]
    if c.empty:
        raise HTTPException(404, f"No complaint {m.group(0)}")
    c = c.iloc[0]
    wo = t["work_orders"]
    w = wo[wo.work_order_id == c.work_order_id] if pd.notna(c.work_order_id) else wo.iloc[0:0]
    complaint = record(c[["complaint_id", "received_at", "channel", "category_reported", "description", "language",
                          "ward_code", "status", "resolved_at"]])
    work_order = record(w.iloc[0][WO_FIELDS]) if len(w) else None
    open_issue, status_note = None, STATUS_NOTE.get(c.status)
    if c.status in ("Open", "In Progress"):
        placed, excluded = _open_map(t)
        p = placed[placed.complaint_id == c.complaint_id]
        if len(p):
            pw = p.iloc[0]
            rk = road_risk(t, open_issues(t, pw.ward_code), DEFAULT_WEIGHTS).reset_index(drop=True)
            hit = rk[(rk.road_id == pw.road_id) & (rk.category_reported == pw.category)]
            open_issue = {"ward_code": pw.ward_code, "road_id": pw.road_id, "match_note": pw.match_note,
                          "road_name": hit.road_name.iloc[0] if len(hit) else None,
                          "rank": int(hit.index[0]) + 1 if len(hit) else None, "of": len(rk),
                          "risk_score": float(hit.risk_score.iloc[0]) if len(hit) else None,
                          "why": hit.why.iloc[0] if len(hit) else None}
        else:
            e = excluded[excluded.complaint_id == c.complaint_id]
            status_note = "Not yet in a repair plan: " + (e.reason.iloc[0] if len(e) else "not matched to a road") + "."
    elif c.status == "Closed - Duplicate" and work_order:
        status_note = (f"Merged with {int(work_order['n_linked_complaints']) - 1} other complaint(s) about the same "
                       f"problem into work order {work_order['work_order_id']}.")
    recs = {"complaint": complaint, "work_order": work_order, "open_issue": open_issue, "status_note": status_note}
    answer, source = ai.answer_citizen(body.question, recs)
    return {"answer": answer, "source": source, "language": ai.detect_lang(body.question), "status": c.status,
            "status_note": status_note, "complaint": complaint, "work_order": work_order, "open_issue": open_issue,
            "data_layer": DATA_LAYER}


@router.get("/cases/{work_order_id}/verdict")
def case_verdict(work_order_id: str):
    s = state()
    t, findings = s["t"], s["findings"]
    wo = t["work_orders"].set_index("work_order_id")
    if work_order_id not in wo.index:
        raise HTTPException(404, f"No work order {work_order_id}")
    r = wo.loc[work_order_id]
    cids = r.linked_complaint_ids.split("|") if isinstance(r.linked_complaint_ids, str) else []
    cc = t["complaints"][t["complaints"].complaint_id.isin(cids)]
    hist = t["work_orders"][t["work_orders"].road_id == r.road_id]
    later = hist[(hist.assigned_at > r.completed_at) & (hist.assigned_at <= r.completed_at + pd.Timedelta(days=30))
                 & (hist.work_type == r.work_type)]
    case = {"work_order": {k: (str(v) if isinstance(v, pd.Timestamp) else v) for k, v in r.to_dict().items()}
            | {"work_order_id": work_order_id},
            "n_complaints": len(cc), "complaints": cc[["complaint_id", "channel", "description", "status"]].to_dict("records"),
            "findings": findings[findings.work_order_id == work_order_id].to_dict("records"),
            "repeat_jobs_within_30d": later.work_order_id.tolist()}
    text, source = ai.explain_case(case)
    return {"work_order_id": work_order_id, "text": text, "source": source}


@router.post("/wards/{ward:path}/brief")
def ward_brief(ward: str):
    s = state()
    f = s["findings"][s["findings"].ward_code == ward]
    if ward not in set(s["t"]["wards"].ward_code):
        raise HTTPException(404, f"Unknown ward {ward!r}")
    from src.audit import recovery_summary
    plan = build_plan(ward)
    payload = {"ward": ward, "leads": f.sort_values("amount_at_risk_inr", ascending=False).head(3).to_dict("records"),
               "recoverable_inr": recovery_summary(f)["total_at_risk_inr"] if len(f) else 0, "n_leads": len(f),
               "plan": [{k: x[k] for k in ["road_name", "category_reported", "risk_score", "est_cost_inr"]}
                        for x in plan["selected"]]}
    md, source = ai.officer_brief(payload)
    return {"ward_code": ward, "markdown": md, "source": source, "data_layer": DATA_LAYER}


@router.get("/scorecards/{kind}/{entity_id:path}/text")
def scorecard_text(kind: str, entity_id: str):
    s = state()
    if kind == "contractors":
        df, key = s["contractors"], "contractor_id"
    elif kind == "wards":
        df, key = s["wards"], "ward_code"
    else:
        raise HTTPException(404, "kind must be contractors or wards")
    row = df[df[key] == entity_id]
    if row.empty:
        raise HTTPException(404, f"No {kind[:-1]} {entity_id!r}")
    row = row.iloc[0]
    text, source = ai.scorecard_narrative(row.to_dict(), row["text"])
    return {"kind": kind, "id": entity_id, "text": text, "source": source}
