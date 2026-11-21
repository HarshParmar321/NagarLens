"""Deterministic audit rules. Owner: audit engineer. Flags are review leads, never accusations."""
import pandas as pd

FINDING_COLS = ["finding_id", "rule_id", "severity", "work_order_id", "ward_code", "road_id", "contractor_id",
                "contractor", "amount_billed_inr", "amount_at_risk_inr", "observed", "baseline", "evidence_ids",
                "reason", "fair_context", "review_action"]

RULE_LABEL = {"dlp_paid_by_bmc": "Paid during warranty", "overbilled_vs_rate_card": "Above rate card",
              "duplicate_bill": "Possible duplicate bill"}


def run_audit(t: dict) -> pd.DataFrame:
    wo = t["work_orders"]
    rows = []

    def add(r, rule, at_risk, observed, baseline, evidence, reason, context, action):
        rows.append(dict(rule_id=rule, severity="review", work_order_id=r.work_order_id, ward_code=r.ward_code,
                         road_id=r.road_id, contractor_id=r.contractor_id, contractor=r.contractor_name,
                         amount_billed_inr=int(r.cost_inr), amount_at_risk_inr=int(round(at_risk)),
                         observed=observed, baseline=baseline, evidence_ids=evidence, reason=reason,
                         fair_context=context, review_action=action))

    for r in wo[wo.cost_ratio > 1.4].itertuples():
        add(r, "overbilled_vs_rate_card", r.cost_inr - 1.3 * r.expected_cost_inr, f"{r.cost_ratio:.2f}x rate card",
            "normal jobs 0.75-1.3x", r.work_order_id,
            f"Billed ₹{r.cost_inr:,.0f} against an expected ₹{r.expected_cost_inr:,.0f} ({r.repair_method}).",
            "Could be legitimate if the job had extra scope the record does not show.",
            "Request the measurement book and site photos.")

    s = wo.sort_values("assigned_at")
    for r in s[s.linked_complaint_ids.isna()].itertuples():
        twins = s[(s.road_id == r.road_id) & (s.work_type == r.work_type) & (s.work_order_id != r.work_order_id)
                  & ((r.assigned_at - s.assigned_at).abs() <= pd.Timedelta(days=7))]
        if len(twins):
            tw = twins.iloc[0]
            add(r, "duplicate_bill", r.cost_inr, "no linked complaint", f"twin {tw.work_order_id} (₹{tw.cost_inr:,.0f})",
                "|".join([r.work_order_id, *twins.work_order_id]),
                f"Same road, same work type as {', '.join(twins.work_order_id)} within 7 days, with no complaint behind it.",
                "Could be a genuine second visit after heavy rain.",
                "Check site records for two separate visits before releasing payment.")

    for r in wo[wo.under_dlp == "Y"].itertuples():
        add(r, "dlp_paid_by_bmc", r.cost_inr, "billed to BMC", "₹0 under Defect Liability Period", r.work_order_id,
            f"{r.road_name} is still under its Defect Liability Period, so the original contractor should repair it free.",
            "Spread across all contractors: a BMC process gap, not this contractor's fault.",
            "Check the DLP register and claim from the original resurfacing contractor.")

    f = pd.DataFrame(rows)
    f.insert(0, "finding_id", [f"AUD-{i:04d}" for i in range(1, len(f) + 1)])
    return f[FINDING_COLS]


def recovery_summary(findings: pd.DataFrame) -> dict:
    dedup = findings.sort_values("amount_at_risk_inr", ascending=False).drop_duplicates("work_order_id")
    by_rule = findings.groupby("rule_id").agg(jobs=("work_order_id", "nunique"), at_risk_inr=("amount_at_risk_inr", "sum"))
    return {"total_at_risk_inr": int(dedup.amount_at_risk_inr.sum()), "jobs": int(len(dedup)), "by_rule": by_rule}
