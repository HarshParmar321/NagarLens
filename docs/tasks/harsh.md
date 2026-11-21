# Harsh: recommended verdict, fair hearing, repair receipt

Idea source: RupeeProof. Read `AGENTS.md`, `CLAUDE.md` and `TASKS.md` first.

## Goal
Turn every audit lead into a decision an officer can take. For each flagged bill the app recommends one of three verdicts (Release payment, Hold for evidence, Return under warranty) with the reason, shows a short hearing in which both sides are argued, and lets the officer confirm. The officer decides; the app only recommends.

## Why it scores
Audit accuracy (25%) and Usable demo (20%): a lead becomes an action. Fair accountability (20%): the hearing shows fairness happening on screen.

## What already exists
- Leads: `run_audit()` in `src/audit.py`. Columns include `finding_id, rule_id, work_order_id, amount_billed_inr, amount_at_risk_inr, observed, reason, fair_context, review_action, dlp_scope`. `rule_id` is `duplicate_bill`, `overbilled_vs_rate_card` or `dlp_paid_by_bmc`. `dlp_scope` is `"surface"` or `"drainage/manhole - verify DLP scope"`. Borderline over-billing has `"(borderline)"` in `observed`.
- Storage: `LeadReview` and `DECISIONS = ["release_payment", "hold_for_evidence", "return_under_warranty"]` in `backend/db.py`.
- API: `GET /api/findings/{finding_id}` returns `{finding, evidence, review, decisions}`. `PUT /api/findings/{finding_id}/review` with `{decision, note}` saves the officer's choice. `GET /api/reviews` lists saved choices.
- UI: three decision buttons at the bottom of the `Evidence` component in `frontend/app/audit/page.tsx`. Labels are in `DECISION_LABEL` in `frontend/lib/api.ts`.

## Build this
1. `src/verdict.py`: `recommend(finding: dict) -> dict` returning `{"decision", "rule", "reason", "documents": [...]}`. Deterministic rules, each written down in the module docstring:
   - `duplicate_bill` -> `hold_for_evidence`. Documents: site records for two visits, geotagged photos, measurement book.
   - `dlp_paid_by_bmc` with `dlp_scope == "surface"` -> `return_under_warranty`. Documents: DLP register entry.
   - `dlp_paid_by_bmc` with drainage or manhole scope -> `hold_for_evidence`. Documents: the DLP contract scope.
   - `overbilled_vs_rate_card` -> `hold_for_evidence` for the amount above 1.3x. If borderline, say so and ask for the measurement book first.
   - A work order with no lead -> `release_payment`.
   Also `summary(findings) -> list[dict]` with `{decision, jobs, amount_at_risk_inr}`, counting each work order once (same de-duplication as `recovery_summary` in `src/audit.py`).
2. `tests/test_verdict.py`: every finding gets a decision in `DECISIONS`; the three rule mappings above; summary rupees add up to 32,224,600.
3. `backend/routers/verdicts.py`: `GET /findings/{finding_id}/verdict` -> `{finding_id, recommended: {...}, review, data_layer}` and `GET /verdicts/summary?ward=` -> `{rows: [...], data_layer}`. Register in `backend/main.py` before `wards`.
4. `src/hearing.py`: `hearing(finding: dict, evidence: dict) -> tuple[dict, str]`. Call `src.ai._call("hearing", payload, system, user, schema, max_tokens=900)` with a JSON schema requiring `auditor`, `fairness_advocate`, `neutral_summary`, `evidence_to_request`. If it returns `(None, None)`, build the same keys from `reason`, `fair_context` and `review_action`, and return source `"template"`. The prompt must forbid fraud, guilt and intent, and forbid changing any number.
5. Endpoint `GET /findings/{finding_id}/hearing` -> `{auditor, fairness_advocate, neutral_summary, evidence_to_request, source}`.
6. `frontend/components/verdict-panel.tsx`: recommended verdict with its reason and documents, the two-column hearing (Auditor, Fairness advocate), the neutral summary, and `SourceBadge`. Mount it in `frontend/app/audit/page.tsx` above the officer buttons (one import and one line; tell the team chat first).
7. Stretch: `frontend/app/receipt/[id]/page.tsx` from `GET /api/cases/{work_order_id}`: complaint, contractor, billed amount, completion date, warranty status, and "Did this repair survive?" Yes/No stored in a new `RepairFeedback` SQLModel table. A "No" on a road with `under_dlp == "Y"` is recorded as a warranty case at Rs 0 to BMC.

## Rules
- The verdict is rule based. Claude never chooses it; the hearing only explains.
- Citizen answers on the receipt are new data: badge them "Synthetic (NagarLens)" and never add them to organizer totals.
- Use "billed", never "paid". The dataset has no payment records, so "Release payment" is a recommendation label, not a fact about payments.
- Neutral wording throughout.

## Done when
- [ ] `pytest` passes including `tests/test_verdict.py`.
- [ ] On `/audit`, lead `AUD-0112` (a duplicate, work order `WO25-02485`) shows "Hold for evidence" with its reason, the hearing, and a saved officer decision.
- [ ] The hearing works with no API key (template badge).
- [ ] Screenshot of the panel in the PR.

## Do not touch
`src/audit.py`, `src/ai.py`, `src/budget.py`, `backend/routers/audit.py` (ask in chat if you need a field added).
