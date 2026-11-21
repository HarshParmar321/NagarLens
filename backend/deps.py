"""Shared state for the API: the organizer dataset, audit findings and scorecards, loaded once.

The API is a thin wrapper. Every number comes from the deterministic modules in src/ (pandas); nothing is
recomputed differently here, and Claude never touches a figure.
"""
import json
import sys
from functools import lru_cache
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.audit import RULE_LABEL, recovery_summary, run_audit  # noqa: E402
from src.data import load_all  # noqa: E402
from src.scorecard import contractor_scorecard, scorecard_text, ward_scorecard  # noqa: E402

DATA_LAYER = "synthetic_organizer"   # every rupee in this API comes from the organizer's synthetic dataset


@lru_cache(maxsize=1)
def state() -> dict:
    t = load_all()
    findings = run_audit(t)
    cs, ws = contractor_scorecard(t, findings), ward_scorecard(t, findings)
    cs["text"] = [scorecard_text(r) for _, r in cs.iterrows()]
    ws["text"] = [scorecard_text(r) for _, r in ws.iterrows()]
    return {"t": t, "findings": findings, "informational": run_audit(t, include_informational=True),
            "contractors": cs, "wards": ws}


def records(df: pd.DataFrame) -> list[dict]:
    """DataFrame -> JSON-safe rows: NaN -> null, timestamps -> ISO strings, numpy -> plain numbers."""
    return json.loads(df.to_json(orient="records", date_format="iso", date_unit="s"))


def record(s: pd.Series) -> dict:
    return json.loads(s.to_json(date_format="iso", date_unit="s"))


def clean_contractor(name) -> str:
    return str(name).replace(" (synthetic)", "")


def rule_rows(findings: pd.DataFrame) -> list[dict]:
    if findings.empty:
        return []
    by = recovery_summary(findings)["by_rule"]
    return [{"rule_id": k, "label": RULE_LABEL[k], "jobs": int(r.jobs), "at_risk_inr": int(r.at_risk_inr)}
            for k, r in by.sort_values("at_risk_inr", ascending=False).iterrows()]


def review_total(findings: pd.DataFrame) -> dict:
    if findings.empty:
        return {"total_at_risk_inr": 0, "jobs": 0, "by_rule": []}
    rs = recovery_summary(findings)
    return {"total_at_risk_inr": rs["total_at_risk_inr"], "jobs": rs["jobs"], "by_rule": rule_rows(findings)}
