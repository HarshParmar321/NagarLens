"""Deterministic audit rules. Owner: audit engineer. Flags are review leads, never accusations.

Three flag rules (severity "review") feed the recovery headline:
    overbilled_vs_rate_card, duplicate_bill, dlp_paid_by_bmc
Two informational rules (severity "informational") feed the scorecards only and never the headline:
    reopened_fix, sla_missed
"""
import pandas as pd

# Frozen order. New columns are only ever appended at the end.
FINDING_COLS = ["finding_id", "rule_id", "severity", "work_order_id", "ward_code", "road_id", "contractor_id",
                "contractor", "amount_billed_inr", "amount_at_risk_inr", "observed", "baseline", "evidence_ids",
                "reason", "fair_context", "review_action", "dlp_scope"]

RULE_LABEL = {"dlp_paid_by_bmc": "Paid during warranty", "overbilled_vs_rate_card": "Above rate card",
              "duplicate_bill": "Possible duplicate bill", "reopened_fix": "Fix re-opened within 30 days",
              "sla_missed": "SLA missed"}
FLAG_RULES = ["overbilled_vs_rate_card", "duplicate_bill", "dlp_paid_by_bmc"]
INFO_RULES = ["reopened_fix", "sla_missed"]

OVERBILL_RATIO = 1.4        # normal jobs fall between 0.75x and 1.3x of the rate card
BORDERLINE_RATIO = 1.5      # flagged, but close to the edge of normal variation
TOLERANCE_RATIO = 1.3       # amount at risk = billed minus this multiple of the rate-card cost
DUP_WINDOW_DAYS = 7
DUP_COST_TOLERANCE = 0.10   # twin must be billed within 10% of the same amount (all planted twins are within 5%)

# A resurfacing warranty covers the road surface. Drainage and manhole work on a DLP road may fall outside it.
SURFACE_WORK = {"Pothole", "Road cave-in", "Broken paver blocks"}
DLP_SURFACE = "surface"
DLP_OTHER = "drainage/manhole - verify DLP scope"


def run_audit(t: dict, include_informational: bool = False) -> pd.DataFrame:
    """Return review leads. With include_informational=True, also append the reopened_fix and sla_missed rows
    (severity "informational", amount_at_risk_inr 0), which recovery_summary ignores."""
    wo = t["work_orders"]
    rows = []

    def add(r, rule, at_risk, observed, baseline, evidence, reason, context, action, severity="review", dlp_scope=""):
        rows.append(dict(rule_id=rule, severity=severity, work_order_id=r.work_order_id, ward_code=r.ward_code,
                         road_id=r.road_id, contractor_id=r.contractor_id, contractor=r.contractor_name,
                         amount_billed_inr=int(r.cost_inr), amount_at_risk_inr=int(round(at_risk)),
                         observed=observed, baseline=baseline, evidence_ids=evidence, reason=reason,
                         fair_context=context, review_action=action, dlp_scope=dlp_scope))

    # ---- 1. billed above the rate card ----
    for r in wo[wo.cost_ratio > OVERBILL_RATIO].itertuples():
        borderline = r.cost_ratio <= BORDERLINE_RATIO
        add(r, "overbilled_vs_rate_card", r.cost_inr - TOLERANCE_RATIO * r.expected_cost_inr,
            f"{r.cost_ratio:.2f}x rate card" + (" (borderline)" if borderline else ""),
            "normal jobs 0.75-1.3x", r.work_order_id,
            f"Billed ₹{r.cost_inr:,.0f} against an expected ₹{r.expected_cost_inr:,.0f} ({r.repair_method})."
            + (" Borderline: just above the 1.4x line and below the main group of outliers, so check this one first"
               " before treating it as an overcharge." if borderline else ""),
            "Could be legitimate if the job had extra scope the record does not show.",
            "Request the measurement book and site photos.")

    # ---- 2. possible duplicate bill ----
    s = wo.sort_values("assigned_at")
    for r in s[s.linked_complaint_ids.isna()].itertuples():
        twins = s[(s.road_id == r.road_id) & (s.work_type == r.work_type) & (s.work_order_id != r.work_order_id)
                  & ((r.assigned_at - s.assigned_at).abs() <= pd.Timedelta(days=DUP_WINDOW_DAYS))
                  & ((r.cost_inr / s.cost_inr - 1).abs() <= DUP_COST_TOLERANCE)]
        if twins.empty:
            continue
        # The twin is the job billed for almost the same amount, not simply the earliest one on that road.
        twins = twins.assign(cost_diff=(r.cost_inr / twins.cost_inr - 1).abs()).sort_values("cost_diff")
        tw = twins.iloc[0]
        same = ["same road", "same work type"]
        if tw.repair_method == r.repair_method:
            same.append("same method")
        if tw.contractor_id == r.contractor_id:
            same.append("same contractor")
        if tw.area_sqm == r.area_sqm:
            same.append("same area")
        days = abs((r.assigned_at - tw.assigned_at).total_seconds()) / 86400
        pct = "5%" if tw.cost_diff <= 0.05 else "10%"
        add(r, "duplicate_bill", r.cost_inr, "no linked complaint",
            f"twin {tw.work_order_id} (₹{tw.cost_inr:,.0f})",
            "|".join([r.work_order_id, *twins.work_order_id]),
            f"Matches {tw.work_order_id} ({', '.join(same)}, cost within {pct}: ₹{r.cost_inr:,.0f} vs "
            f"₹{tw.cost_inr:,.0f}), assigned {days:.0f} day(s) apart, with no complaint behind this one.",
            "Could be a genuine second visit after heavy rain.",
            "Check site records for two separate visits before releasing payment.")

    # ---- 3. billed to BMC while the road is under its Defect Liability Period ----
    for r in wo[wo.under_dlp == "Y"].itertuples():
        surface = r.work_type in SURFACE_WORK
        add(r, "dlp_paid_by_bmc", r.cost_inr, "billed to BMC", "₹0 under Defect Liability Period", r.work_order_id,
            f"{r.road_name} is still under its Defect Liability Period, so the original contractor should repair it free."
            if surface else
            f"{r.road_name} is still under its Defect Liability Period. This was {r.work_type.lower()} work, "
            f"which a surfacing warranty may not cover.",
            "Spread across all contractors: a BMC process gap, not this contractor's fault."
            + ("" if surface else " Drainage and manhole work may be outside the warranty scope."),
            "Check the DLP register and claim from the original resurfacing contractor." if surface else
            "Check whether the DLP contract covers drainage and manhole work before raising a claim.",
            dlp_scope=DLP_SURFACE if surface else DLP_OTHER)

    n_flags = len(rows)

    # ---- informational: context for scorecards, never part of the recovery headline ----
    if include_informational:
        tier_miss = (wo.sla_met == "N").groupby(wo.sla_hours).mean()
        for r in wo[wo.reopened_within_30d == "Y"].itertuples():
            add(r, "reopened_fix", 0, "re-opened within 30 days", "fix holds for 30 days", r.work_order_id,
                f"The {r.repair_method.lower()} repair on {r.road_name} failed within 30 days "
                f"(₹{r.cost_inr:,.0f} billed).",
                "Heavy rain, traffic load or a utility trench can undo a sound repair.",
                "Compare the contractor's re-open rate with peers using the same method before drawing conclusions.",
                severity="informational")
        for r in wo[wo.sla_met == "N"].itertuples():
            add(r, "sla_missed", 0, f"completed in {r.hours_to_complete:.0f} h after assignment",
                f"{r.sla_hours} h SLA from first complaint", r.work_order_id,
                f"Missed the {r.sla_hours}-hour SLA.",
                f"{tier_miss[r.sla_hours]:.0%} of all {r.sla_hours}-hour jobs miss the SLA, whoever does them.",
                "Compare within the same SLA tier; review whether the tier's target is achievable.",
                severity="informational")

    f = pd.DataFrame(rows)
    ids = [f"AUD-{i:04d}" for i in range(1, n_flags + 1)] + [f"INF-{i:04d}" for i in range(1, len(f) - n_flags + 1)]
    f.insert(0, "finding_id", ids)
    return f[FINDING_COLS]


def recovery_summary(findings: pd.DataFrame) -> dict:
    """De-duplicated rupees to review. Only severity "review" counts; informational rows are ignored."""
    flags = findings[findings.severity == "review"] if "severity" in findings else findings
    dedup = flags.sort_values("amount_at_risk_inr", ascending=False).drop_duplicates("work_order_id")
    by_rule = flags.groupby("rule_id").agg(jobs=("work_order_id", "nunique"), at_risk_inr=("amount_at_risk_inr", "sum"))
    return {"total_at_risk_inr": int(dedup.amount_at_risk_inr.sum()), "jobs": int(len(dedup)), "by_rule": by_rule}
