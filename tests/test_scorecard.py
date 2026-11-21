"""Scorecards: one row per contractor / ward, like-for-like, plain language, no accusations."""
import pytest

from src.scorecard import BELOW, BETTER, INLINE, contractor_scorecard, scorecard_text, ward_scorecard

CHIPS = {BETTER, INLINE, BELOW}


@pytest.fixture(scope="module")
def cs(t, findings):
    return contractor_scorecard(t, findings)


@pytest.fixture(scope="module")
def ws(t, findings):
    return ward_scorecard(t, findings)


def test_one_row_each(t, cs, ws):
    assert len(cs) == 8 and cs.contractor_id.is_unique
    assert len(ws) == 24 and ws.ward_code.is_unique
    assert cs.jobs.sum() == ws.jobs.sum() == len(t["work_orders"])
    assert cs.billed_inr.sum() == ws.billed_inr.sum() == t["work_orders"].cost_inr.sum()


def test_chips_and_rates_are_valid(cs, ws):
    for sc in (cs, ws):
        for c in ["speed_chip", "durability_chip", "cost_chip"]:
            assert set(sc[c]) <= CHIPS
        for c in ["on_time_rate", "expected_on_time_rate", "reopen_rate", "expected_reopen_rate", "over_rate_card_share"]:
            assert sc[c].between(0, 1).all()
        assert sc.durability_tier.str.startswith("Tier").all()


def test_same_result_with_or_without_informational_findings(t, findings_all, cs, ws):
    assert contractor_scorecard(t, findings_all).billing_review_inr.tolist() == cs.billing_review_inr.tolist()
    assert ward_scorecard(t, findings_all).total_review_inr.tolist() == ws.total_review_inr.tolist()


def test_ward_review_totals_add_up_to_the_headline(ws):
    # every flagged job belongs to exactly one ward, so ward totals add up to the citywide headline
    assert ws.total_review_inr.sum() == 32_224_600 and ws.total_review_jobs.sum() == 622


def test_durability_tiers_match_the_data(cs):
    chip = cs.set_index("contractor").durability_chip
    for name in ["Deccan Paving Solutions", "Mithi Infra Projects", "Sahyadri Infra Works"]:
        assert chip[name] == BETTER
    for name in ["Arabian Sea Engineering", "Mahalaxmi Civil Contractors", "Western Coast Asphalt Co"]:
        assert chip[name] == BELOW
    for name in ["Konkan Roadcon Pvt Ltd", "Shivneri Construction"]:
        assert chip[name] == INLINE


def test_dlp_never_counts_against_a_contractor(cs, findings):
    billing = findings[findings.rule_id != "dlp_paid_by_bmc"]
    assert cs.billing_review_jobs.sum() == billing.work_order_id.nunique()
    assert cs.dlp_jobs.sum() == 493                       # reported separately as a process gap


def test_text_is_short_complete_and_neutral(cs, ws):
    for sc in (cs, ws):
        for _, row in sc.iterrows():
            text = scorecard_text(row)
            assert len(text.split()) < 120, text
            for part in ["Speed:", "Durability:", "Cost:", "One thing to improve:"]:
                assert part in text
            low = text.lower()
            for word in ["fraud", "scam", "corrupt", "theft", "guilty", "cheat", "overcharg", "blame"]:
                assert word not in low
    assert scorecard_text(cs.iloc[0].to_dict()) == scorecard_text(cs.iloc[0])     # dict rows work too
