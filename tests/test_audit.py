"""Audit rules must reproduce the planted signals exactly and never flag normal variation."""
from src.audit import DLP_OTHER, DLP_SURFACE, FINDING_COLS, FLAG_RULES, INFO_RULES, RULE_LABEL, recovery_summary

FROZEN = ["finding_id", "rule_id", "severity", "work_order_id", "ward_code", "road_id", "contractor_id",
          "contractor", "amount_billed_inr", "amount_at_risk_inr", "observed", "baseline", "evidence_ids",
          "reason", "fair_context", "review_action"]
HEADLINE_INR, HEADLINE_JOBS = 32_224_600, 622


def test_flag_counts(findings):
    n = findings.groupby("rule_id").work_order_id.nunique().to_dict()
    assert n == {"dlp_paid_by_bmc": 493, "overbilled_vs_rate_card": 111, "duplicate_bill": 45}
    assert set(findings.severity) == {"review"}
    assert findings.finding_id.is_unique


def test_frozen_columns_keep_their_order(findings):
    assert list(findings.columns) == FINDING_COLS
    assert FINDING_COLS[:len(FROZEN)] == FROZEN          # new columns are appended, never inserted


def test_headline_is_deduplicated(findings):
    rs = recovery_summary(findings)
    assert rs["total_at_risk_inr"] == HEADLINE_INR and rs["jobs"] == HEADLINE_JOBS
    assert rs["total_at_risk_inr"] < findings.amount_at_risk_inr.sum()     # overlapping jobs counted once
    assert set(rs["by_rule"].index) == set(FLAG_RULES)


def test_informational_rules_never_reach_the_headline(findings, findings_all):
    info = findings_all[findings_all.severity == "informational"]
    assert set(info.rule_id) == set(INFO_RULES)
    assert info.groupby("rule_id").size().to_dict() == {"reopened_fix": 611, "sla_missed": 1259}
    assert (info.amount_at_risk_inr == 0).all()
    assert info.finding_id.str.startswith("INF-").all()
    rs = recovery_summary(findings_all)
    assert rs["total_at_risk_inr"] == HEADLINE_INR and rs["jobs"] == HEADLINE_JOBS
    assert set(rs["by_rule"].index) == set(FLAG_RULES)
    # the flag rows are identical with or without the informational rows
    flags = findings_all[findings_all.severity == "review"].reset_index(drop=True)
    assert flags.equals(findings.reset_index(drop=True))


def test_normal_variation_is_never_flagged(t, findings):
    wo = t["work_orders"].set_index("work_order_id")
    over = findings[findings.rule_id == "overbilled_vs_rate_card"]
    assert (wo.cost_ratio[over.work_order_id] > 1.4).all()
    assert (over.amount_at_risk_inr > 0).all()
    normal = wo[(wo.cost_ratio <= 1.3) & (wo.under_dlp == "N") & wo.linked_complaint_ids.notna()]
    assert not set(normal.index) & set(findings.work_order_id)


def test_borderline_overbilling_is_marked_but_still_flagged(findings):
    over = findings[findings.rule_id == "overbilled_vs_rate_card"]
    b = over[over.observed.str.contains("borderline")]
    assert sorted(b.work_order_id) == ["WO25-00018", "WO25-00045"]
    assert b.reason.str.contains("Borderline").all()


def test_duplicates_have_no_complaint_and_a_close_cost_twin(t, findings):
    wo = t["work_orders"].set_index("work_order_id")
    dup = findings[findings.rule_id == "duplicate_bill"]
    assert len(dup) == 45
    assert wo.linked_complaint_ids[dup.work_order_id].isna().all()
    for f in dup.itertuples():
        ids = f.evidence_ids.split("|")
        me, twin = wo.loc[ids[0]], wo.loc[ids[1]]
        assert ids[0] == f.work_order_id and twin.name in f.reason and twin.name in f.baseline
        assert twin.road_id == me.road_id and twin.work_type == me.work_type
        assert abs(me.cost_inr / twin.cost_inr - 1) <= 0.05 and "cost within 5%" in f.reason
        assert abs((twin.assigned_at - me.assigned_at).total_seconds()) <= 7 * 86400
        assert isinstance(twin.linked_complaint_ids, str)          # the twin is the job a citizen asked for


def test_dlp_scope_split(findings):
    dlp = findings[findings.rule_id == "dlp_paid_by_bmc"]
    assert dlp.dlp_scope.value_counts().to_dict() == {DLP_SURFACE: 274, DLP_OTHER: 219}
    assert (findings[findings.rule_id != "dlp_paid_by_bmc"].dlp_scope == "").all()


def test_wording_is_neutral(findings_all):
    text = " ".join(findings_all.reason + " " + findings_all.fair_context + " " + findings_all.review_action).lower()
    for word in ["fraud", "scam", "corrupt", "theft", "stole", "guilty", "cheat"]:
        assert word not in text
    assert set(findings_all.rule_id) <= set(RULE_LABEL)
    assert (findings_all.fair_context.str.len() > 0).all() and (findings_all.review_action.str.len() > 0).all()
