"""Pre-flight check for the demo video: every figure the voiceover says must match the app.

Run from the repo root before recording, and again after merging any PR:

    .venv/Scripts/python demo/check_demo.py

It calls the API in-process (no server needed) and exits non-zero if a line of demo/DEMO_SCRIPT.md has
gone stale. Fix the script or the code before recording; never narrate a number this check rejects.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from fastapi.testclient import TestClient  # noqa: E402

from backend.main import app  # noqa: E402

FAILED = []


def check(beat: str, claim: str, ok: bool, got=None):
    print(f"{'PASS' if ok else 'FAIL'}  [{beat}] {claim}" + ("" if ok else f"   <- app says: {got}"))
    if not ok:
        FAILED.append(claim)


def lakh(x):
    return round(x / 1e5, 1)


def crore(x):
    return round(x / 1e7, 2)


with TestClient(app) as c:
    get = lambda p: c.get("/api" + p).json()  # noqa: E731

    o = get("/overview")
    check("hero", "₹13.43 Cr billed", crore(o["billed_inr"]) == 13.43, crore(o["billed_inr"]))
    check("hero", "₹3.22 Cr needs a second look", crore(o["review"]["total_at_risk_inr"]) == 3.22, crore(o["review"]["total_at_risk_inr"]))
    rules = {r["rule_id"]: r for r in o["review"]["by_rule"]}
    check("audit", "493 / 111 / 45 jobs by rule",
          [rules[k]["jobs"] for k in ["dlp_paid_by_bmc", "overbilled_vs_rate_card", "duplicate_bill"]] == [493, 111, 45],
          {k: v["jobs"] for k, v in rules.items()})

    w = get("/wards/L")
    check("ward", "Kurla billed 110% of its budget", round(w["ward"]["billed_vs_budget"] * 100) == 110, w["ward"]["billed_vs_budget"])
    flow = {r["outcome"]: r["billed_inr"] for r in w["money_flow"]["by_outcome"]}
    check("ward", "₹39.6 L billed on roads still under warranty", lakh(flow.get("Paid during warranty", 0)) == 39.6, flow)
    check("ward", "most of it held (Held is the largest outcome)", max(flow, key=flow.get) == "Held 30 days", flow)
    check("ward", "₹44.4 L to review in ward L", lakh(w["review"]["total_at_risk_inr"]) == 44.4, w["review"]["total_at_risk_inr"])

    dups = get("/findings?ward=L&rule=duplicate_bill")["rows"]
    check("audit", "first duplicate lead in ward L is AUD-0133 (WO25-02486)",
          bool(dups) and dups[0]["finding_id"] == "AUD-0133" and dups[0]["work_order_id"] == "WO25-02486", dups[:1])
    f = get("/findings/AUD-0133")
    e, m = f["evidence"], f["evidence"]["match"]
    check("audit", "two bills on LBS Marg, same contractor, method and area",
          e["work_order"]["road_name"] == "LBS Marg" and all(m["same"].values()), m["same"])
    check("audit", "three days apart, about half a percent different",
          m["days_apart"] == 3.0 and 0.004 <= m["cost_difference"] <= 0.006, m)
    check("audit", "one bill has three complaints, the other has none",
          e["twin"]["n_linked_complaints"] == 3 and e["work_order"]["n_linked_complaints"] == 0,
          (e["twin"]["n_linked_complaints"], e["work_order"]["n_linked_complaints"]))
    check("audit", "decision buttons offer 'hold for evidence'", "hold_for_evidence" in f["decisions"], f["decisions"])

    case = get("/cases/WO25-02068")
    check("case", "first preset is WO25-02068", get("/cases/presets")[0]["work_order_id"] == "WO25-02068")
    check("case", "four complaints, at least one written in Marathi",
          len(case["complaints"]) == 4 and any(x["language"] == "mr" for x in case["complaints"]), len(case["complaints"]))
    check("case", "road cave-in, late against a 24-hour SLA",
          case["work_order"]["work_type"] == "Road cave-in" and case["work_order"]["sla_hours"] == 24 and case["work_order"]["sla_met"] == "N",
          (case["work_order"]["work_type"], case["work_order"]["sla_hours"], case["work_order"]["sla_met"]))
    check("case", "failed within 30 days, road still under warranty",
          case["outcome"]["held_30_days"] is False and case["road"]["under_dlp"] == "Y", (case["outcome"], case["road"]["under_dlp"]))

    cs = {r["contractor"]: r for r in get("/scorecards/contractors")["rows"]}
    mah = cs["Mahalaxmi Civil Contractors"]
    check("scorecards", "Mahalaxmi: 38% re-opened where peers on the same methods see 23%",
          round(mah["reopen_rate"] * 100) == 38 and round(mah["expected_reopen_rate"] * 100) == 23,
          (mah["reopen_rate"], mah["expected_reopen_rate"]))
    check("scorecards", "Mahalaxmi's durability chip reads 'below peers'", mah["durability_chip"] == "below peers", mah["durability_chip"])
    tiers = get("/scorecards/sla-tiers")["rows"][-1]
    all24 = next(x for x in tiers["cells"] if x["sla_hours"] == 24)
    check("scorecards", "24-hour deadlines are missed by almost everyone (under 5% on time)",
          tiers["contractor"] == "All contractors" and all24["on_time_rate"] < 0.05, all24)
    wl = next(r for r in get("/scorecards/wards")["rows"] if r["ward_code"] == "L")
    check("scorecards (extended cut)", "Kurla: 32% on time, similar wards 34%, chip 'in line with peers'",
          round(wl["on_time_rate"] * 100) == 32 and round(wl["expected_on_time_rate"] * 100) == 34 and wl["speed_chip"] == "in line with peers",
          (wl["on_time_rate"], wl["expected_on_time_rate"], wl["speed_chip"]))

    p = get("/wards/L/plan")
    check("next rupee", "default plan: Kurla overspent, budget comes from recoverable money",
          "overspent" in p["default_budget_reason"] and "recoverable" in p["default_budget_reason"], p["default_budget_reason"])
    check("next rupee", "five issues go back to the warranty contractor", len(p["dlp_routed"]) == 5, len(p["dlp_routed"]))
    check("next rupee (extended cut)", "seven of the top ten differ from counting complaints",
          p["top10_differ_from_complaint_ranking"] == 7, p["top10_differ_from_complaint_ranking"])
    p5 = get("/wards/L/plan?budget_inr=500000")
    check("next rupee", "at ₹5 lakh: nine funded, sixteen deferred, never over budget",
          len(p5["selected"]) == 9 and len(p5["deferred"]) == 16 and p5["total_inr"] <= 500000,
          (len(p5["selected"]), len(p5["deferred"]), p5["total_inr"]))
    why = " ".join(s["why"] for s in p5["selected"][:4])
    check("next rupee", "top cards show hospital road, bus route and flood hotspot chips",
          all(k in why for k in ["hospital", "bus route", "flood hotspot"]), why)

    a = c.post("/api/ask", json={"question": "माझी तक्रार BMC25-001690 चं काय झालं?"}).json()
    check("ask", "the Marathi question gets a Marathi answer", a["language"] == "mr" and "तक्रार" in a["answer"], a["answer"][:80])
    check("ask", "answer cites work order WO25-00646 and that the fix failed within 30 days",
          "WO25-00646" in a["answer"] and a["work_order"]["reopened_within_30d"] == "Y", a["answer"])
    health = get("/health")
    print(f"\nAI: {'Claude is live' if health['ai_available'] else 'OFFLINE: panels will show the Template badge'}"
          f" (ask answer source: {a['source']}). Only say 'Claude wrote this' when the badge on screen says so.")

print(f"\n{'ALL CLAIMS MATCH THE APP' if not FAILED else str(len(FAILED)) + ' CLAIM(S) ARE STALE: fix before recording'}")
sys.exit(1 if FAILED else 0)
