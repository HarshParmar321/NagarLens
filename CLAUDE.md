# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

NagarLens ("Follow the Rupee") is a one-day, 5-person hackathon build (Claude Impact Lab Mumbai, 21 Nov 2026): a Streamlit app that makes Mumbai BMC road-repair spending auditable — complaint → issue → work order → payment trail, evidence-backed audit leads, and a "next rupee" budget allocator.

**The working plan lives in the team's shared "NagarLens Team Plan" doc** (ask the lead for the link). It holds the verified data facts, the concept, 5-person file ownership, frozen interfaces (function signatures, finding columns, `allocate()` output) and the timeline (feature freeze 3:30 pm, submit 4:15 pm). Field names are frozen; don't rename them without the team agreeing. The lead may keep local reference copies in `docs/` (`TEAM_PLAN.md`, the hackathon spec). Those are gitignored and must never be committed.

Commits carry no `Co-Authored-By`, `Claude-Session` or other attribution trailers.

**Teammates: start with `TASKS.md`.** It has the ground rules, the API map and your own task file in `docs/tasks/<name>.md`. Read it before writing code.

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

## Architecture

Stack (final, agreed by the team): **Next.js + TypeScript frontend** (`frontend/`, Tailwind + shadcn/ui, Recharts, react-leaflet, TanStack Query, localhost:3000) and a **FastAPI backend** (`backend/`, localhost:8000) that is a thin JSON wrapper over the deterministic core in `src/`. `app.py` (Streamlit) is kept runnable as a fallback demo; no new Streamlit UI work.

- All numbers, join classes, finding status and budget math are deterministic pandas in `src/`. The API never recomputes a figure differently. Claude (`src/ai.py`) only reads messy text and writes explanations. It never overwrites a computed value, every call is cached in `data/cache/ai_cache.json`, and every call has a template fallback, so the app runs offline.
- Anthropic SDK calls happen only in the backend (`src/ai.py`), never in the frontend. The key comes from `.env`.
- API conventions: snake_case keys matching the DataFrame columns; rupees are integers with the type in the key name (`*_inr`); timestamps are ISO strings; NaN becomes null; every rupee response carries `"data_layer"`. Ward codes contain "/": declare routes with `{ward:path}`. Don't add a bare `/wards/{ward:path}` route that would swallow `/plan` or `/brief`.
- File ownership: `backend/routers/plan.py`, `backend/routers/ai.py`, `src/budget.py`, `src/ai.py` and `src/data.py` belong to the lead's session. The other routers, `backend/deps.py`, `backend/db.py` and `frontend/` belong to the teammate session. `src/audit.py`, `src/scorecard.py` and `tests/` belong to the audit owner. Coordinate before editing someone else's file. Teammates add features by PR.

## Commands

Use the Python 3.12 venv at `.venv` (created with uv). System Python 3.14 has no packages. 

```
uv venv --python 3.12 .venv && uv pip install --python .venv -r requirements.txt
.venv/Scripts/python -m uvicorn backend.main:app --reload --port 8000   # API (from the repo root)
cd frontend && npm install && npm run dev                               # web app on :3000
.venv/Scripts/python -m streamlit run app.py                            # fallback demo
.venv/Scripts/python -m pytest                                  # all tests
.venv/Scripts/python -m pytest tests/test_audit.py::test_name   # single test
```

On Windows, the console uses cp1252 and crashes on Devanagari output. Call `sys.stdout.reconfigure(encoding="utf-8")`, or set `PYTHONIOENCODING=utf-8`, when printing complaint text.

Claude API key goes in `.env` (template in `.env.example`); never commit `.env`. Don't commit `.idea/workspace.xml`.
