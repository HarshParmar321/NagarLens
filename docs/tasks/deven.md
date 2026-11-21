# Deven: road history (one page per road)

Idea source: SadakScore. Read `AGENTS.md`, `CLAUDE.md` and `TASKS.md` first.

## Goal
Answer "did the fix last?" at road level. One page per road shows every repair this monsoon, what each cost, who did it, whether it held, the warranty status, the complaints behind the work, and the audit leads on that road, with a small chart of spend and failures over time.

## Why it scores
Connects the trail (15%): complaint to work order to road, on one page. Fair accountability (20%): repeat failures are shown with their context (traffic, flood, warranty).

## What already exists
- `GET /api/cases/{work_order_id}` (`backend/routers/cases.py`) already returns `road`, `road_history` (every work order on that road with `flags` and `is_this_case`) and `road_history_total`. Reuse the same column list.
- `GET /api/wards/{ward}` returns `roads`: top roads in the ward with `road_id, road_name, jobs, billed_inr, reopened, under_dlp, review_inr`. The overview page (`frontend/app/page.tsx`) shows them in "Roads that took the most money".
- Data frames in `state()["t"]`: `roads` (`road_id, road_name, ward_code, road_type, surface, lanes, length_m, last_resurfaced, under_dlp, bus_route`), `traffic` (by `road_id`), `accidents` (by `road_id`), `facilities` (`ambulance_entry_road` is a `road_id`), `work_orders`, `complaints` (has `work_order_id`), `flood_hotspots`.
- Leads: `state()["findings"]` has `road_id` on every row.

## Build this
1. `backend/routers/roads.py`:
   - `GET /roads?ward=&limit=` -> `{rows: [{road_id, road_name, ward_code, road_type, surface, under_dlp, bus_route, jobs, billed_inr, reopened, reopen_rate, review_inr, review_jobs}], data_layer}`, sorted by `billed_inr` descending. `review_inr` counts each work order once (sort findings by `amount_at_risk_inr` descending, `drop_duplicates("work_order_id")`, then sum by road).
   - `GET /roads/{road_id}` -> `{road, traffic, facilities, accidents: {total, by_cause, by_severity}, totals: {jobs, billed_inr, reopened, review_inr}, work_orders: [...], complaints: [...], findings: [...], monthly: [{month, billed_inr, jobs, reopened}], data_layer}`. 404 for an unknown id.
   - Register in `backend/main.py` before `wards`.
2. `tests/test_roads.py` with `fastapi.testclient.TestClient`: `/api/roads` returns 291 roads city-wide; billed totals over all roads equal `work_orders.cost_inr.sum()`; `/api/roads/RD0220` has 35 jobs; unknown id gives 404.
3. `frontend/app/roads/page.tsx`: road list for the selected ward (`useWard()`), each row linking to the road page.
4. `frontend/app/roads/[id]/page.tsx`: header (road name, id, ward, type, surface, last resurfaced, warranty pill, bus route), KPI row (jobs, billed, failed fixes, to review), a Recharts chart of monthly billed with failed jobs marked, a timeline table of every repair (date, work type, method, contractor, billed, on time, held or failed, flags) where each work order id links to `/case`, the complaints, and the leads. In Next.js 16 read the route param with the hook `useParams()` in a client component.
5. Link to the road page from the road table in `frontend/app/page.tsx` and from the road name on `frontend/app/case/page.tsx` (one line each; tell the team chat first). Add "Roads" to `NAV` only if the lead agrees; a link from the overview table is enough.

## Rules and honest limits
- Location-verified voting cannot be shown. The dataset has only an `upvotes` count per complaint, with no voter location. If you mention the idea, label it "not in this dataset".
- Social posts have no road id. Match them only by a road name or locality name found in the post text, label each match "candidate", and show how many posts could not be matched. Never present a text match as an exact link.
- Complaint to work order links are exact. Open complaints are not linked to a road by an id; if you show them, use the match class from the planner (`gps` or `road named`) and label them candidate.
- Amounts are billed amounts. Use the `inr()` helper and the data badge.
- Repeat failures are context, not blame: show the contractor, the method and whether the road is a bus route or near a flood hotspot next to each failure.

## Done when
- [ ] `pytest` passes including `tests/test_roads.py`.
- [ ] `/roads/RD0220` (Kurla Andheri Road, ward L, under warranty) shows 35 repairs, its failed fixes and its leads.
- [ ] Clicking a work order opens the case page.
- [ ] Screenshot in the PR.

## Do not touch
`backend/routers/cases.py`, `backend/routers/wards.py`, `src/` modules. Add new files; ask in chat if an existing endpoint needs a field.
