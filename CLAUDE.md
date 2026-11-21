# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

NagarLens ("Follow the Rupee") is a one-day, 5-person hackathon build (Claude Impact Lab Mumbai, 21 Nov 2026): a Streamlit app that makes Mumbai BMC road-repair spending auditable — complaint → issue → work order → payment trail, evidence-backed audit leads, and a "next rupee" budget allocator.

**`docs/TEAM_PLAN.md` is the working plan**: verified data facts, the concept, 5-person file ownership, frozen interfaces (function signatures, finding columns, `allocate()` output) and the timeline (feature freeze 3:30 pm, submit 4:15 pm). Field names in it are frozen; don't rename them without the team agreeing. `docs/FOLLOW_THE_RUPEE_HACKATHON_SPEC.md` is the earlier generic spec, written before the data was seen; where the two disagree, TEAM_PLAN wins.

## The dataset (verified)

- Organizer repo cloned to `data/raw/` (commit `81d2280`); CSVs are in `data/raw/data/`, columns are in `data/raw/DATA_DICTIONARY.md`. **Everything is synthetic**, including the fictional contractors. Judges score audit flags and next-rupee rankings against a hidden answer key, so precision on planted anomalies matters most.
- Joins are exact (spec path A): `work_orders.linked_complaint_ids` (pipe-separated) → `complaints.complaint_id` matches 100%. `road_id` → roads, `repair_method` → rate_card and `ward_code` → wards also match 100%.
- Expected cost = `area_sqm × standard_rate_inr` for `per sqm` methods, or `standard_rate_inr` for `per job` methods. Normal jobs fall between 0.75× and 1.3× of it.
- Complaints with status `Open`/`In Progress` (896) are not linked to any work order. These are the next-rupee candidates, and they have no `road_id`; mapping them to roads is part of the work.

## Data layers

- `data/raw/` is the organizer dataset. It is the scoring core: all audit flags and next-rupee rankings come from it alone.
- `data/live/` holds real BMC public records. Use them only as context; they never join to raw records.
- `data/synthetic/` holds our own seeded generators, each with a README.

Every UI number carries a badge for its layer: Synthetic (organizer), Live BMC, or Synthetic (NagarLens).

## Non-negotiable data rules

- **Never invent** columns, row counts, joins, amounts, or findings. Only activate an audit rule when the columns it needs actually exist. Report what is verified vs. inferred vs. unavailable.
- The organizer's headline figures (24 wards, 2,499 jobs, ₹13 crore) are unverified claims — reconcile against data, don't force agreement.
- Every join edge has a `match_class`: `exact` (validated shared ID, cardinality checked), `candidate` (spatial-temporal, needs review), `aggregate_context` (same ward/GL/budget head — never an individual link), or unlinked. Never present aggregate/candidate as exact.
- Keep monetary types separate: `allocated`, `sanctioned`, `contract_value`, `invoiced`, `paid`, `estimated_cost`. Never sum across types into one "spend". Don't label anything "paid" without payment data. Every displayed amount shows type, unit, date context and source.
- Every normalized record keeps raw IDs plus `source_file` and `source_row` (`record_id` = `source:<file>:row:<n>`).
- `data/raw/` is preserved unchanged; `data/normalized/` is generated; `data/fixtures/` is **clearly synthetic** and must never be mixed with or shown as real data.
- Audit findings are "needs review" leads with baseline, evidence refs, alternative explanations, limitations and a review action — never fraud/blame language.
- Budget allocation must never exceed the user's budget; don't invent repair costs (use source costs or explicitly user-entered/labeled assumptions); show excluded items and why.

## Architecture (planned, spec §7, §13–14)

Single-process Streamlit app; no REST API, DB server, queues or microservices.

```
data/raw → src/ingest.py (profile_sources, normalize_sources)
         → src/joins.py  (build_trail → trail edges + coverage)
         → src/audit.py  (run_audit)        → src/budget.py (allocate_budget)
         → src/ai.py     (explain_findings — Claude)
         → app.py / src/ui.py (tabs: Overview, Money Trail, Audit Leads, Next Rupee, optional Data Quality)
```

- All numbers, join classes, finding status and budget math are deterministic pandas/Python. Claude (`src/ai.py`) only does extraction from genuinely unstructured inputs and explanations; its output is Pydantic/JSON-schema validated, cached, and must never overwrite computed values. Every Claude call needs a deterministic templated fallback — the app must run offline from cached normalized data.
- Map (Folium/Plotly) only if real coordinates/geometry exist.
- File ownership is split across 5 teammates (spec §12) — avoid editing another workstream's files without coordination; keep function interfaces from spec §14 stable.

## Commands

Use the Python 3.12 venv at `.venv` (created with uv). System Python 3.14 has no packages. Once the scaffolding exists (`requirements.txt`, `app.py`, `tests/`):

```
uv venv --python 3.12 .venv && uv pip install --python .venv -r requirements.txt
.venv/Scripts/python -m streamlit run app.py
.venv/Scripts/python -m pytest                                  # all tests
.venv/Scripts/python -m pytest tests/test_audit.py::test_name   # single test
```

On Windows, the console uses cp1252 and crashes on Devanagari output. Call `sys.stdout.reconfigure(encoding="utf-8")`, or set `PYTHONIOENCODING=utf-8`, when printing complaint text.

Claude API key goes in `.env` (template in `.env.example`); never commit `.env`. Don't commit `.idea/workspace.xml`.
