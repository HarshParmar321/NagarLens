# Aditya: strategy comparison (same budget, three ways)

Idea source: RaastaIQ. Read `AGENTS.md`, `CLAUDE.md` and `TASKS.md` first.

## Goal
Show that the NagarLens plan is better, instead of asserting it. Spend the same ward budget three ways (most complaints first, highest severity first, NagarLens risk plan) and compare what each one covers, using only measures that come from the dataset.

## Why it scores
Budget smarts (20%): the rubric checks the next-rupee ranking and whether methods are sensible. A side-by-side comparison under one budget cap is the proof.

## What already exists
- `src/budget.py` (the lead's file, read only):
  - `open_issues(t, ward) -> DataFrame`: open complaints merged into issues and matched to roads.
  - `road_risk(t, issues, weights) -> DataFrame`: one row per issue, sorted by `risk_score` (0 to 100, normalised city-wide). Columns include `issue_id, road_name, category_reported, complaints, upvotes, severity, flood, traffic, hospitals, schools, accidents, repeat, bus_route, nearest_hotspot, under_dlp, method, method_why, est_cost_inr, risk_score, why`.
  - `allocate(risk, budget_inr, crew_jobs=None) -> dict` with `selected, deferred, dlp_routed, excluded, total_inr, unallocated_inr`. It walks the rows in the order given, so re-sorting `risk` changes the strategy.
  - `default_budget(t, ward, findings) -> (int, str)`, `method_table(t)` (re-open rate per work type and method), `DEFAULT_WEIGHTS`, `PLAN_DAYS`.
- API: `GET /api/wards/{ward}/plan?budget_inr=...` in `backend/routers/plan.py` (see `build_plan` there for how budget, weights and crew cap are assembled).
- Page: `frontend/app/next-rupee/page.tsx`.

## Build this
1. `src/strategies.py`:
   ```python
   STRATEGIES = {"most_complaints": "Most complaints first",
                 "highest_severity": "Highest severity first",
                 "nagarlens_risk": "NagarLens risk plan"}
   def compare(t: dict, ward: str, budget_inr: int, findings, weights: dict | None = None) -> dict
   ```
   Compute `risk = road_risk(t, open_issues(t, ward), weights or DEFAULT_WEIGHTS)` once. For each strategy, sort a copy (`complaints` desc; `severity` desc then `complaints` desc; `risk_score` desc) and call `allocate(sorted, budget_inr, crew_jobs)` with the same crew cap `build_plan` uses. All three share the same issues, costs and methods; only the order differs.
2. For each strategy return, from the `selected` items only:
   `issues_funded`, `total_inr` (estimate), `risk_covered` (sum of `risk_score`), `risk_covered_share` (of all fundable issues), `hospital_road_issues`, `school_road_issues`, `flood_hotspot_issues` (`nearest_hotspot` not empty), `bus_route_issues`, `complaints_addressed`, `warranty_routed` (count of `dlp_routed`), and `funded_issue_ids`.
3. Also return `overlap` (issue ids funded by all three) and `only_in_nagarlens` (ids with their `why`), so the UI can show what the risk plan picks that the others miss.
4. `tests/test_strategies.py`: for 4 wards and 3 budgets, every strategy has `total_inr <= budget_inr`; the three use the same candidate issue set; `nagarlens_risk` has `risk_covered` at least as high as the other two when budgets bind (if a counter-example exists, report it in the PR instead of hiding it).
5. `backend/routers/strategies.py`: `GET /wards/{ward:path}/strategies?budget_inr=` -> `{ward_code, budget_inr, strategies: [{id, label, ...measures}], overlap, only_in_nagarlens, assumptions, data_layer}`. Default budget from `default_budget`. Register in `backend/main.py` before `wards`.
6. `frontend/components/strategy-compare.tsx`: three columns (one per strategy) with the measures, or a grouped bar chart with Recharts, plus a list "Only the risk plan funds these" with the `why` text. Mount it on `frontend/app/next-rupee/page.tsx` under the plan (one import and one line; tell the team chat first).

## Rules
- No invented benefit numbers. Do not estimate accidents prevented, lives saved or rupees saved. Report coverage counts and sums of the existing `risk_score` only.
- Costs are estimates (rate card x median historical area). Label `total_inr` as an estimate in the UI.
- If the three strategies fund the same issues because the budget does not bind, say so on screen and suggest a lower budget. Do not fake a difference.
- Use the same budget, crew cap and warranty routing for all three, or the comparison is not fair.

## Done when
- [ ] `pytest` passes including `tests/test_strategies.py`.
- [ ] `/next-rupee` for ward L at a binding budget (try Rs 5,00,000) shows three strategies with different picks and the "only the risk plan funds these" list.
- [ ] Every number on the panel traces to a column of `road_risk()`.
- [ ] Screenshot in the PR.

## Do not touch
`src/budget.py`, `backend/routers/plan.py`, `src/ai.py`. If you need a change there, ask the lead in chat.
