"""Like-for-like scorecards for contractors and wards (computed in src/scorecard.py)."""
from fastapi import APIRouter

from ..deps import DATA_LAYER, clean_contractor, records, state

router = APIRouter(tags=["scorecards"])

METHOD = [
    "Speed is compared within the same SLA tier and the same flood-proneness band: urgent jobs are late for "
    "everyone, and low-lying wards finish on time far less often.",
    "Durability is compared within the same repair method. Re-open rates do not vary with flood-proneness or "
    "rain on the day, so no further adjustment is made.",
    "Expected = what everyone else achieves on the same mix of jobs. Nobody is compared with themselves.",
    "A chip only says better or below when the gap is at least 3 points and more than twice its standard error.",
    "Warranty-period billing is spread across all contractors: it is a process gap and never counts against a contractor.",
]


@router.get("/scorecards/contractors")
def contractors():
    return {"data_layer": DATA_LAYER, "method": METHOD, "rows": records(state()["contractors"])}


@router.get("/scorecards/wards")
def wards():
    return {"data_layer": DATA_LAYER, "method": METHOD, "rows": records(state()["wards"])}


@router.get("/scorecards/sla-tiers")
def sla_tiers():
    """On-time rate by contractor and SLA tier, plus the all-contractor row that shows the tier effect."""
    wo = state()["t"]["work_orders"]
    on = (wo.sla_met == "Y").astype(float)
    name = wo.contractor_name.map(clean_contractor)
    rate, n = on.groupby([name, wo.sla_hours]).mean().unstack(), on.groupby([name, wo.sla_hours]).size().unstack()
    order = on.groupby(name).mean().sort_values(ascending=False).index
    tiers = [int(c) for c in rate.columns]
    rows = [{"contractor": c, "cells": [{"sla_hours": h, "on_time_rate": float(rate.loc[c, h]), "jobs": int(n.loc[c, h])}
                                        for h in tiers]} for c in order]
    all_rate, all_n = on.groupby(wo.sla_hours).mean(), on.groupby(wo.sla_hours).size()
    rows.append({"contractor": "All contractors", "cells": [
        {"sla_hours": h, "on_time_rate": float(all_rate[h]), "jobs": int(all_n[h])} for h in tiers]})
    return {"data_layer": DATA_LAYER, "tiers": tiers, "rows": rows}
