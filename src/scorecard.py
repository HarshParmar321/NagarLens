"""Like-for-like scorecards for contractors and wards. Owner: audit engineer.

Fairness rules, each checked against the data:
- Speed is compared within the same SLA tier AND the same flood-proneness band. 97% of 24-hour jobs miss the SLA
  whoever does them, and low-lying wards finish on time far less often (34% vs 58%), so raw on-time rates punish
  whoever got the urgent jobs or the flood-prone wards.
- Durability is compared within the same repair method (cold mix re-opens more than hot mix for everyone).
  Re-open rates do not vary with ward flood-proneness or with rain on the day, so no further adjustment is made.
- "Expected" is always what the PEERS (everyone else) achieve on the same mix of jobs, so an entity is never
  compared with itself.
- A chip only says "better than" or "below" peers when the gap is at least 3 percentage points and larger than
  twice its standard error. Small samples therefore stay "in line with peers".
- Warranty-period (DLP) billing is spread evenly across all contractors: it is reported separately as a BMC
  process gap and never counts against a contractor.

All figures are computed from the organizer's synthetic dataset. Nothing here is an accusation.
"""
import numpy as np
import pandas as pd

from .audit import OVERBILL_RATIO, recovery_summary

BETTER, INLINE, BELOW = "better than peers", "in line with peers", "below peers"
TIER = {BETTER: "Tier 1 - holds up best", INLINE: "Tier 2 - typical", BELOW: "Tier 3 - re-opens most often"}
MIN_GAP = 0.03            # a chip needs at least a 3-point gap ...
MIN_Z = 2.0               # ... that is also at least twice its standard error
MIN_PEER_N = 5            # below this many peer jobs in a stratum, fall back to the peers' overall rate
MIN_FOCUS_N = 10          # only name a method / SLA tier as the thing to improve if it has this many jobs
SMALL_SAMPLE = 30
HEAVY_RAIN_MM = 64.5      # IMD "heavy" rain threshold
LL_BINS, LL_LABELS = [0, 0.5, 0.65, 0.8, 1.0], ["low", "medium", "high", "very high"]

SPEED_STRATA = ["sla_hours", "ll_band"]
DURABILITY_STRATA = ["repair_method"]


def _inr(x) -> str:
    return f"₹{x / 1e7:.2f} Cr" if abs(x) >= 1e7 else f"₹{x / 1e5:.1f} L" if abs(x) >= 1e5 else f"₹{x:,.0f}"


def _prep(t: dict) -> pd.DataFrame:
    wo = t["work_orders"].copy()
    wo["on_time"] = (wo.sla_met == "Y").astype(float)
    wo["reopened"] = (wo.reopened_within_30d == "Y").astype(float)
    wo["over"] = (wo.cost_ratio > OVERBILL_RATIO).astype(float)
    wo["ll_band"] = pd.cut(wo.low_lying_index, LL_BINS, labels=LL_LABELS, include_lowest=True).astype(str)
    rain = t["rainfall_daily"].groupby("date").rainfall_mm.max()
    wo["heavy_rain"] = (wo.assigned_at.dt.normalize().map(rain) >= HEAVY_RAIN_MM).astype(float)
    wo["contractor"] = wo.contractor_name.str.replace(" (synthetic)", "", regex=False)
    return wo


def _like_for_like(wo: pd.DataFrame, group: str, strata: list, outcome: str):
    """Expected rate for each entity = what its peers achieve on the same mix of strata (leave-one-out).
    Returns (expected rate per entity, per-stratum detail)."""
    g = wo.groupby([group, *strata])[outcome].agg(hits="sum", n="size").reset_index()
    tot = g.groupby(strata)[["hits", "n"]].transform("sum")
    own = g.groupby(group)[["hits", "n"]].transform("sum")
    peer_n = tot.n - g.n
    overall = (wo[outcome].sum() - own.hits) / (len(wo) - own.n)
    g["peer_rate"] = ((tot.hits - g.hits) / peer_n.where(peer_n > 0)).where(peer_n >= MIN_PEER_N, overall)
    g["own_rate"] = g.hits / g.n
    g["expected_hits"] = g.peer_rate * g.n
    s = g.groupby(group)[["expected_hits", "n"]].sum()
    return s.expected_hits / s.n, g


def _chip(actual: float, expected: float, n: int, higher_is_better: bool):
    se = np.sqrt(max(expected * (1 - expected), 1e-9) / max(n, 1))
    gap = (actual - expected) * (1 if higher_is_better else -1)   # positive = better than peers
    bar = max(MIN_Z * se, MIN_GAP)
    return (BETTER if gap >= bar else BELOW if gap <= -bar else INLINE), gap / se


def _focus(detail: pd.DataFrame, group: str, entity, strata_col: str, higher_is_better: bool) -> str:
    """The stratum (SLA tier or repair method) where the entity loses most against its peers, as a phrase.
    Empty string when no stratum with enough jobs is behind its peers."""
    d = detail[(detail[group] == entity) & (detail.n >= MIN_FOCUS_N)]
    if d.empty:
        return ""
    d = d.groupby(strata_col)[["hits", "expected_hits", "n"]].sum()
    short = (d.expected_hits - d.hits) if higher_is_better else (d.hits - d.expected_hits)
    k = short.idxmax()
    if short[k] <= 0:
        return ""
    own, peers = d.hits[k] / d.n[k], d.expected_hits[k] / d.n[k]
    if strata_col == "sla_hours":
        return f"{int(k)}-hour jobs ({own:.0%} on time against {peers:.0%} for peers)"
    return f"{str(k).lower()} jobs ({own:.0%} re-opened against {peers:.0%} for peers)"


def _core(wo: pd.DataFrame, group: str, findings: pd.DataFrame) -> pd.DataFrame:
    """Columns shared by the contractor and ward scorecards, indexed by the group key."""
    sc = wo.groupby(group).agg(
        jobs=("work_order_id", "size"), billed_inr=("cost_inr", "sum"),
        on_time_rate=("on_time", "mean"), reopen_rate=("reopened", "mean"),
        over_rate_card_jobs=("over", "sum"), over_rate_card_share=("over", "mean"),
        median_cost_ratio=("cost_ratio", "median"), heavy_rain_job_share=("heavy_rain", "mean"),
        dlp_jobs=("under_dlp", lambda x: int((x == "Y").sum())))
    sc["over_rate_card_jobs"] = sc.over_rate_card_jobs.astype(int)
    sc["failed_fix_spend_inr"] = wo[wo.reopened == 1].groupby(group).cost_inr.sum().reindex(sc.index, fill_value=0)
    sc["dlp_billed_inr"] = wo[wo.under_dlp == "Y"].groupby(group).cost_inr.sum().reindex(sc.index, fill_value=0)

    exp_speed, d_speed = _like_for_like(wo, group, SPEED_STRATA, "on_time")
    exp_dur, d_dur = _like_for_like(wo, group, DURABILITY_STRATA, "reopened")
    sc["expected_on_time_rate"] = exp_speed
    sc["on_time_gap"] = sc.on_time_rate - sc.expected_on_time_rate
    sc["expected_reopen_rate"] = exp_dur
    sc["reopen_gap"] = sc.reopen_rate - sc.expected_reopen_rate
    # Cost benchmark is the typical peer (median), so two outliers do not make everyone else look "better".
    sc["peer_over_rate_card_share"] = [sc.over_rate_card_share.drop(k).median() for k in sc.index]

    # Rupees to review from the audit: billing rules only (above rate card + possible duplicate), de-duplicated.
    flags = findings[findings.severity == "review"] if "severity" in findings else findings
    key = {"contractor_id": "contractor_id", "ward_code": "ward_code"}[group]
    billing = flags[flags.rule_id != "dlp_paid_by_bmc"]
    billing = billing.sort_values("amount_at_risk_inr", ascending=False).drop_duplicates("work_order_id")
    sc["billing_review_jobs"] = billing.groupby(key).size().reindex(sc.index, fill_value=0)
    sc["billing_review_inr"] = billing.groupby(key).amount_at_risk_inr.sum().reindex(sc.index, fill_value=0)

    chips = []
    for k, r in sc.iterrows():
        speed, z_s = _chip(r.on_time_rate, r.expected_on_time_rate, r.jobs, True)
        dur, z_d = _chip(r.reopen_rate, r.expected_reopen_rate, r.jobs, False)
        cost, z_c = _chip(r.over_rate_card_share, r.peer_over_rate_card_share, r.jobs, False)
        chips.append(dict(speed_chip=speed, durability_chip=dur, cost_chip=cost, speed_z=z_s, durability_z=z_d,
                          cost_z=z_c, durability_tier=TIER[dur],
                          speed_focus=_focus(d_speed, group, k, "sla_hours", True),
                          durability_focus=_focus(d_dur, group, k, "repair_method", False)))
    sc = sc.join(pd.DataFrame(chips, index=sc.index))
    sc["small_sample"] = sc.jobs < SMALL_SAMPLE
    return sc


def _improve(r, warranty_first: bool = False) -> str:
    """One concrete thing to improve: the measure furthest below peers, phrased without blame."""
    z = {"speed": r.speed_z, "durability": r.durability_z, "cost": r.cost_z}
    chip = {"speed": r.speed_chip, "durability": r.durability_chip, "cost": r.cost_chip}
    below = [k for k in z if chip[k] == BELOW]
    if not below and warranty_first and r.dlp_billed_inr > 0:
        return (f"claim the {_inr(r.dlp_billed_inr)} billed on roads still under warranty "
                f"from the original resurfacing contractors")
    weakest = min(below or z, key=z.get)
    if weakest == "durability":
        return "make repairs last longer" + (f", starting with {r.durability_focus}" if r.durability_focus else "")
    if weakest == "speed":
        return "finish more jobs inside the SLA" + (f", starting with {r.speed_focus}" if r.speed_focus else "")
    return (f"have the {int(r.over_rate_card_jobs)} bills above {OVERBILL_RATIO}x the rate card checked against "
            f"the measurement book")


def contractor_scorecard(t: dict, findings: pd.DataFrame) -> pd.DataFrame:
    """One row per contractor, compared like-for-like with the other contractors."""
    wo = _prep(t)
    sc = _core(wo, "contractor_id", findings)
    names = wo.groupby("contractor_id").agg(contractor_name=("contractor_name", "first"), contractor=("contractor", "first"),
                                            low_lying_exposure=("low_lying_index", "mean"), wards_served=("ward_code", "nunique"))
    sc = names.join(sc)
    sc["peer_low_lying_exposure"] = [wo[wo.contractor_id != k].low_lying_index.mean() for k in sc.index]
    sc["improve"] = [_improve(r) for r in sc.itertuples()]
    sc.insert(0, "entity_type", "contractor")
    return sc.reset_index().sort_values("contractor").reset_index(drop=True)


def ward_scorecard(t: dict, findings: pd.DataFrame) -> pd.DataFrame:
    """One row per ward, compared like-for-like with the other wards."""
    wo = _prep(t)
    sc = _core(wo, "ward_code", findings)
    w = t["wards"].set_index("ward_code")
    info = w[["ward_name", "zone", "low_lying_index", "engineering_crews"]].rename(columns={"low_lying_index": "low_lying_exposure"})
    sc = info.join(sc, how="right")
    sc["budget_inr"] = w.monsoon_repair_budget_inr_2025.reindex(sc.index)
    sc["billed_vs_budget"] = sc.billed_inr / sc.budget_inr
    sc["budget_status"] = np.where(sc.billed_vs_budget > 1, "over budget", "within budget")
    # Durability given WHO did the work: separates "this ward's roads fail" from "this ward got the contractors
    # whose repairs re-open more often everywhere".
    exp_c, _ = _like_for_like(wo, "ward_code", ["repair_method", "contractor_id"], "reopened")
    sc["expected_reopen_given_contractors"] = exp_c
    flags = findings[findings.severity == "review"] if "severity" in findings else findings
    by_ward = {k: recovery_summary(g) for k, g in flags.groupby("ward_code")}
    sc["total_review_inr"] = [by_ward[k]["total_at_risk_inr"] if k in by_ward else 0 for k in sc.index]
    sc["total_review_jobs"] = [by_ward[k]["jobs"] if k in by_ward else 0 for k in sc.index]
    c = t["complaints"]
    sc["open_complaints"] = c[c.status.isin(["Open", "In Progress"])].groupby("ward_code").size().reindex(sc.index, fill_value=0)
    sc["improve"] = [_improve(r, warranty_first=True) for r in sc.itertuples()]
    sc.insert(0, "entity_type", "ward")
    return sc.reset_index().sort_values("ward_code").reset_index(drop=True)


def scorecard_text(row) -> str:
    """Plain-language scorecard (template; Claude may rewrite it but must keep every number).
    Covers speed, durability, cost vs the rate card and one thing to improve, in under 120 words, no accusations."""
    r = row if isinstance(row, pd.Series) else pd.Series(dict(row))
    is_ward = r.get("entity_type") == "ward" or "ward_name" in r.index
    if is_ward:
        head = (f"Ward {r.ward_code} ({r.ward_name}): {int(r.jobs)} repairs, {_inr(r.billed_inr)} billed against a "
                f"{_inr(r.budget_inr)} budget ({r.billed_vs_budget:.0%}).")
        speed_peers, dur_peers, cost_peers = "similar wards", "other wards", "the typical ward"
    else:
        head = f"{r.contractor}: {int(r.jobs)} repairs, {_inr(r.billed_inr)} billed."
        speed_peers, dur_peers, cost_peers = "peers", "peers", "the typical contractor"
    speed = (f"Speed: {r.on_time_rate:.0%} on time; {speed_peers} with the same deadlines and flood risk manage "
             f"{r.expected_on_time_rate:.0%} ({r.speed_chip}).")
    dur = (f"Durability: {r.reopen_rate:.0%} of fixes re-opened within 30 days; {dur_peers} using the same methods "
           f"see {r.expected_reopen_rate:.0%} ({r.durability_chip}).")
    cost = (f"Cost: {int(r.over_rate_card_jobs)} bills ({r.over_rate_card_share:.0%}) were above {OVERBILL_RATIO}x "
            f"the rate card; {cost_peers} has {r.peer_over_rate_card_share:.0%} ({r.cost_chip}).")
    note = " Small sample: read with care." if r.get("small_sample") else ""
    return f"{head} {speed} {dur} {cost} One thing to improve: {r.improve}.{note}"
