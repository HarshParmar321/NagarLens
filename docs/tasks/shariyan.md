# Shariyan: rain and flood context on scorecards, evidence-request letter

Idea source: MargDarshak. Read `AGENTS.md`, `CLAUDE.md` and `TASKS.md` first.

## Goal
Make the scorecards visibly fair to a contractor or ward that worked through heavy rain in a flood-prone area, and give the officer a one-click letter that asks a contractor for evidence or raises a warranty claim. The letter is a request, never a legal notice.

## Why it scores
Fair accountability (20%): context is shown before any judgement. Usable demo (20%): the officer leaves with a document to send.

## What already exists (do not redo)
- `src/scorecard.py` already compares speed within the same SLA tier and flood-proneness band (`SPEED_STRATA = ["sla_hours", "ll_band"]`), compares durability within the same repair method, and uses leave-one-out peers. Each row has `heavy_rain_job_share` and `low_lying_exposure`.
- Measured on the dataset: on-time falls from 58% to 34% in the most low-lying wards. Re-open rate does not vary with low-lying index or with rain on the day. So speed needs the flood adjustment and durability does not.
- API: `GET /api/scorecards/contractors`, `GET /api/scorecards/wards`. Page: `frontend/app/scorecards/page.tsx`.
- Leads and evidence: `GET /api/findings/{finding_id}` returns `{finding, evidence}`; evidence has `work_order`, and by rule `twin` + `match`, `rate_card`, or `road`.
- Rainfall: `t["rainfall_daily"]` (`date, station, rainfall_mm, imd_category`). Heavy rain threshold used in the code: 64.5 mm (`HEAVY_RAIN_MM`).

## Build this
Part A, rain context (new file, no change to chip logic):
1. `src/context.py`: `rain_context(t: dict, group: str) -> pd.DataFrame` with `group` = `"contractor_id"` or `"ward_code"`. Columns: `heavy_rain_jobs`, `heavy_rain_job_share`, `on_time_heavy_rain`, `peer_on_time_heavy_rain` (other entities, same heavy-rain days), `on_time_dry`, `peer_on_time_dry`. A job is "heavy rain" when the maximum of the two stations on its `assigned_at` date is at least 64.5 mm.
2. `tests/test_context.py`: one row per contractor (8) and per ward (24); shares between 0 and 1; heavy-rain jobs sum to the dataset count.
3. `backend/routers/context.py`: `GET /scorecards/{kind}/context` with `kind` = `contractors` or `wards` -> `{rows, data_layer}`. Register before `scorecards` in `backend/main.py` (the lead's `ai.py` has `/scorecards/{kind}/{entity_id:path}/text`, so your fixed path must be matched first: put your router first in the tuple).
4. In `frontend/app/scorecards/page.tsx`, add a "Context" line under the three numbers on each card: "N jobs in heavy-rain weeks: X% on time, peers in the same weeks Y%". One small component in `frontend/components/rain-context.tsx`.
5. If you believe the chip itself should change, open a PR against `src/scorecard.py` with the measurement that justifies it and a test in `tests/test_scorecard.py`. Do not rewrite it directly.

Part B, letter:
6. `src/letters.py`: `draft_letter(finding: dict, evidence: dict) -> str` (markdown). One deterministic template per rule:
   - `duplicate_bill`: request for evidence of two separate visits. Cite both work orders, dates, amounts, road. Ask for site records, geotagged photos, measurement book entries.
   - `overbilled_vs_rate_card`: request for the measurement book and site photos. Cite billed amount, rate-card cost, the 1.3x upper end of normal.
   - `dlp_paid_by_bmc`, scope `surface`: warranty claim addressed to the original resurfacing contractor (not named in the dataset: write "the original resurfacing contractor"), copy to the DLP register holder. Other scope: request to confirm whether the DLP contract covers this work.
   Each letter ends with the evidence ids, a reply-by line, and "This is a request for information, not a finding of wrongdoing."
7. Optional polish: `src.ai._call("letter", ...)` to improve the wording, with the template as fallback. The numbers in the result must match the template.
8. `backend/routers/letters.py`: `GET /findings/{finding_id}/letter` -> `{markdown, source, data_layer}`.
9. `frontend/components/letter-button.tsx`: "Draft letter" button that fetches, shows the letter, and offers a `.md` download. Mount it in the `Evidence` component in `frontend/app/audit/page.tsx` (one import and one line; tell the team chat first).
10. `tests/test_letters.py`: a letter exists for every flag finding; it contains the work order id and the amount; none contain the words legal notice, fraud, penalty or blacklist.

## Rules
- A letter is a request for evidence or a warranty claim. Never a legal notice, never a threat.
- All contractors are fictional and marked "(synthetic)". Keep that marker in the letter header.
- Use "billed", never "paid". Every amount in the letter is copied from the finding or evidence.

## Done when
- [ ] `pytest` passes including the two new test files.
- [ ] `/scorecards` shows the context line for Mahalaxmi Civil Contractors and for ward L.
- [ ] `/audit`: lead `AUD-0112` produces a downloadable letter with no API key.
- [ ] Screenshots of both in the PR.

## Do not touch
`src/scorecard.py` chip logic, `src/audit.py`, `src/ai.py`, `backend/routers/scorecards.py`, `backend/routers/ai.py`.
