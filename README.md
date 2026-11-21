![NagarLens](docs/assets/banner.png)

# NagarLens

**Team 11 · Claude Impact Lab Mumbai · 21 Nov 2026**

**Follow every rupee from a citizen's complaint to a fix that held.**

> **₹13.43 Cr billed for Mumbai's 2025 monsoon road repairs; ₹3.22 Cr needs a second look.**
> De-duplicated across 622 work orders (a job caught by two rules counts once). These are review leads, not findings of wrongdoing.

Built in one day for the challenge *"Follow the Rupee: where did Mumbai's road repair money go?"*. All data is synthetic; see [Data and fairness](#data-and-fairness).

---

## The problem

Every monsoon, Mumbai pays to fix the same roads again. Citizens complain, repairs get logged and the potholes come back. Nobody can easily answer three questions:

1. **Where did the money go?**
2. **Did the fix last?**
3. **Who is responsible?**

Our pitch is **"Recover, then reinvest."** About ₹3 Cr went on repairs to roads still under warranty, duplicate bills, and charges above the rate card. NagarLens shows how to get that money back and where each ward should spend next.

| Judging criterion | How NagarLens addresses it |
|---|---|
| **Connects the trail** | Exact complaint → work order → road → rate card → ward joins (100% match), plus a ward money-trail Sankey |
| **Audit accuracy** | Three precision-tuned rules, each flag carrying evidence ids, a reason, fair context and a review action |
| **Fair accountability** | Contractors compared within the same SLA tier and method, with "system problem vs contractor problem" called out |
| **Budget smarts** | Risk-ranked Next Rupee plan, capped at the budget, choosing methods by lifetime cost and sending warranty roads to the original contractor at ₹0 to BMC |
| **Usable** | Citizens ask "what happened to my complaint?" in Marathi, Hindi, Hinglish or English and get an answer in the same language |

### What the audit finds (computed, organizer dataset)

| Rule | Logic | Jobs | ₹ at risk |
|---|---|---:|---:|
| Paid during warranty (DLP) | Road still under its Defect Liability Period, so the original contractor should repair it free | 493 | ₹2.62 Cr |
| Above rate card | Bill > 1.4× the rate-card cost (normal jobs fall between 0.75× and 1.3×) | 111 | ₹44.7 L above the 1.3× tolerance |
| Possible duplicate bill | No linked complaint, same road, same work type within 7 days of another job | 45 | ₹25.9 L |
| **Total, de-duplicated** | | **622** | **₹3.22 Cr** |

---

## What it does

A single Streamlit app with a ward picker in the sidebar:

| Tab | What you see |
|---|---|
| **① Follow a case** | One work order end to end: complaints → assignment → repair → bill vs rate card → did it hold? → verdict, with a map, SLA timeline and a downloadable case file |
| **② Ward overview** | Budget vs billed, money spent on fixes that failed, a contractor → method → outcome Sankey, a citywide ward choropleth with flood hotspots, and rainfall vs spend |
| **③ AI inbox** | Messy open complaints and social posts go through Claude triage and come out as merged, road-matched, risk-scored actions |
| **④ Recovery ledger** | The headline total, money at risk by rule and contractor, the cost-ratio distribution, a CSV export and a Claude-written ward officer brief |
| **⑤ Scorecards** | Durability vs billing per contractor, plus on-time rates *within each SLA tier* (the fair comparison) |
| **⑥ Next rupee** | Recover first, then a budget-capped plan: risk-ranked issues, adjustable risk-weight sliders, a map, and deferred, warranty-routed and excluded items with reasons |
| **⑦ Ask NagarLens** | "What happened to my complaint?" answered in the citizen's own language from the linked records |
| **Data quality** | How complete each link in the trail is, and whether each one is an exact or a candidate match |

### The AI workflow

```
complaints + social posts (en / hi / mr / Hinglish)
  → Claude triage   (category, locality, road, landmark, severity, noise)
  → merge duplicates (same place + same problem)
  → match to a road (nearest segment within 800 m = candidate match)
  → risk score      (severity, flood + rain/tide, traffic, hospitals/schools, accidents, repeat failures, complaints, social posts)
  → action          (fund, defer, route to warranty contractor, or exclude with a reason)
```

Claude also writes **case verdicts** in plain language, the **ward officer brief**, and **citizen answers in Marathi or Hindi**.

**Guardrails**

- Every number is deterministic pandas. Claude never computes totals and never overwrites a computed value.
- Every Claude call is cached on disk (`data/cache/ai_cache.json`) and has a template fallback, so the app runs offline and the demo never breaks. Each output is badged as Claude or Template.
- Claude prompts forbid fraud, guilt or blame language.

---

## Quick start

Requires [uv](https://docs.astral.sh/uv/) and Python 3.12.

```bash
uv venv --python 3.12 .venv && uv pip install --python .venv -r requirements.txt
.venv/Scripts/python -m streamlit run app.py      # Windows
# .venv/bin/python -m streamlit run app.py        # macOS / Linux
```

**Optional, for live Claude:** set `ANTHROPIC_API_KEY` in the environment before launching. Without it the sidebar shows "offline", and the AI steps use cached answers or the deterministic templates. Never commit a key.

On Windows, set `PYTHONIOENCODING=utf-8` if you print Devanagari complaint text to the console.

---

## Architecture

Single-process Streamlit app. No API server, database or queue.

```
app.py              Streamlit UI: the 7 tabs + Data quality; scorecards are computed here
src/
  data.py           load_all(): load CSVs, parse dates, derived columns
                    (expected_cost_inr, cost_ratio, under_dlp, hours_to_complete, ...)
  audit.py          run_audit() -> review leads; recovery_summary() -> de-duplicated ₹ by rule
  budget.py         open_issues(), road_risk(), allocate() (never exceeds the budget)
  ai.py             Claude layer: triage, explain_case, answer_citizen, officer_brief
                    (disk cache + template fallback)
data/
  raw/              Organizer dataset (synthetic). Scoring core: all flags and rankings come from it
  cache/            Cached Claude responses
  live/             (planned) Real BMC public records, context only, never joined to raw records
  synthetic/        (planned) NagarLens' own seeded extensions, each with a README
docs/
  TEAM_PLAN.md      Verified data facts, concept, roles, frozen interfaces, timeline
```

Every number in the UI is tagged with its data layer: **Synthetic (organizer)**, **Live BMC** or **Synthetic (NagarLens)**.

---

## Team 11

| # | Role | Owns | Builds | Name |
|---|---|---|---|---|
| 1 | Tech lead / Claude | `app.py`, `src/ai.py`, `src/data.py` scaffold | Repo skeleton, Claude layer (parser, explanations, scorecard text, ward one-pager, citizen Q&A) with cache and fallbacks, integration | TBD |
| 2 | Trail engineer | `src/data.py`, `src/trail.py` | Derived columns, complaint → work order → road trail, dedupe and road-match open complaints, coverage stats | TBD |
| 3 | Audit engineer | `src/audit.py`, `src/scorecard.py` | Three flag rules plus two informational ones, recovery summary, like-for-like scorecards, precision checks | TBD |
| 4 | Budget engineer | `src/budget.py` | Road risk score, cost estimates, method choice by lifetime cost, budget-capped allocation, DLP routing, adjustable weights | TBD |
| 5 | UI / story lead | UI pages, `demo/`, README | Streamlit pages, maps, pitch slide, demo script, backup recording | TBD |

---

## Data and fairness

- **Everything is synthetic.** The dataset looks like Mumbai civic data, but it is **not BMC data**. All contractors are fictional, and every amount, date, coordinate and record is made up. Ward codes, localities, roads, flood spots and hospitals are real names, used only for realism. Don't use NagarLens output to judge any real person, contractor or department.
- **Flags are review leads, not accusations.** Each one cites its evidence ids, a baseline, a fair alternative explanation and a concrete review action. Normal variation (0.75–1.3× the rate card) is never flagged.
- **System problems are named as such.** 24-hour SLAs are missed on almost every job by every contractor, and warranty-period payments are spread across all eight contractors. These are process gaps, not one contractor's fault.
- **Every ₹ figure says what it is** (billed, budget or estimate). Next Rupee costs are estimates: rate card × the median historical repair area.

**Dataset credit:** *Follow the Rupee: Mumbai Monsoon Roads*, by Sumeet Doshi for Claude Impact Lab Mumbai: <https://github.com/SumeetGDoshi/Claude-Impact-Labs-data-2>, released under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
