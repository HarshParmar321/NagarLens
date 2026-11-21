"""Next Rupee: the plan must never exceed the budget, whatever the ward or the amount."""
import pytest

from src.budget import DEFAULT_WEIGHTS, allocate, open_issues, road_risk

WARDS = ["L", "E", "F/N", "K/W", "A", "C", "R/C", "T"]
BUDGETS = [0, 10_000, 50_000, 250_000, 1_000_000, 5_000_000]


@pytest.fixture(scope="module")
def risk_by_ward(t):
    return {w: road_risk(t, open_issues(t, w), DEFAULT_WEIGHTS) for w in WARDS}


@pytest.mark.parametrize("ward", WARDS)
@pytest.mark.parametrize("budget", BUDGETS)
def test_plan_never_exceeds_budget(risk_by_ward, ward, budget):
    risk = risk_by_ward[ward]
    if risk.empty:
        pytest.skip(f"no open issues in ward {ward}")
    plan = allocate(risk, budget)
    assert plan["total_inr"] <= budget
    assert plan["total_inr"] == pytest.approx(sum(s["est_cost_inr"] for s in plan["selected"]))
    assert plan["unallocated_inr"] == pytest.approx(budget - plan["total_inr"])
    assert plan["unallocated_inr"] >= 0


@pytest.mark.parametrize("ward", WARDS)
def test_every_issue_is_accounted_for(risk_by_ward, ward):
    risk = risk_by_ward[ward]
    if risk.empty:
        pytest.skip(f"no open issues in ward {ward}")
    plan = allocate(risk, 1_000_000)
    buckets = [plan["selected"], plan["deferred"], plan["dlp_routed"], plan["excluded"]]
    ids = [s["issue_id"] for b in buckets for s in b]
    assert sorted(ids) == sorted(risk.issue_id)                  # nothing dropped, nothing counted twice
    for b in buckets[1:]:
        assert all(s.get("reason") for s in b)                   # every non-funded item says why
    assert all(s["est_cost_inr"] > 0 for s in plan["selected"])


def test_zero_budget_funds_nothing(risk_by_ward):
    plan = allocate(risk_by_ward["L"], 0)
    assert plan["selected"] == [] and plan["total_inr"] == 0
