"""City-wide headline numbers."""
from fastapi import APIRouter

from ..deps import DATA_LAYER, review_total, state

router = APIRouter(tags=["overview"])


@router.get("/overview")
def overview():
    s = state()
    t, f = s["t"], s["findings"]
    wo, c, w = t["work_orders"], t["complaints"], t["wards"]
    status = c.status.value_counts()
    return {
        "data_layer": DATA_LAYER,
        "period": "Monsoon 2025 (Jun to early Oct)",
        "billed_inr": int(wo.cost_inr.sum()),
        "budget_inr": int(w.monsoon_repair_budget_inr_2025.sum()),
        "jobs": int(len(wo)),
        "wards": int(len(w)),
        "contractors": int(wo.contractor_id.nunique()),
        "failed_fix_spend_inr": int(wo[wo.reopened_within_30d == "Y"].cost_inr.sum()),
        "reopened_jobs": int((wo.reopened_within_30d == "Y").sum()),
        "on_time_rate": float((wo.sla_met == "Y").mean()),
        "review": review_total(f),
        "complaints": {
            "total": int(len(c)),
            "linked_to_work_order": int(c.work_order_id.notna().sum()),
            "open": int(status.get("Open", 0) + status.get("In Progress", 0)),
            "forwarded_or_rejected": int(sum(v for k, v in status.items() if k.startswith(("Forwarded", "Rejected")))),
            "languages": {k: int(v) for k, v in c.language.value_counts().items()},
        },
        "trail": [   # every join edge with its match class and measured coverage
            {"link": "Complaint → work order", "match_class": "exact", "coverage": float(c.work_order_id.notna().mean()),
             "note": "work_orders.linked_complaint_ids; every id matches a complaint"},
            {"link": "Work order → complaint", "match_class": "exact", "coverage": float((wo.n_linked_complaints > 0).mean()),
             "note": "45 work orders have no complaint behind them"},
            {"link": "Work order → road, rate card, ward", "match_class": "exact", "coverage": float(wo.road_name.notna().mean()),
             "note": "road_id, repair_method and ward_code all match 100%"},
        ],
    }
