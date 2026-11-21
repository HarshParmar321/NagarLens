# TASKS.md: who builds what

NagarLens won the team vote. The base is built on the agreed stack (Next.js frontend, FastAPI backend, pandas core). Each teammate now adds one borrowed feature by pull request. Read `AGENTS.md` and `CLAUDE.md` first, then your file in `docs/tasks/`.

## 1. Status at handover (13:15, 21 Nov 2026)

What already works:

**API** (`backend/`, thin JSON wrapper over `src/`, all under `/api`, live docs at `http://localhost:8000/docs`)

| Router file | Endpoints |
|---|---|
| `backend/main.py` | `GET /health` |
| `routers/overview.py` | `GET /overview` (city totals, review total by rule, complaint counts, trail coverage) |
| `routers/wards.py` | `GET /wards`, `GET /wards/geojson`, `GET /wards/{ward}` (ward scorecard row, money flow, weekly rain vs billed, contractors, roads) |
| `routers/audit.py` | `GET /findings?ward=&rule=&contractor_id=&include_informational=&limit=&offset=`, `GET /findings/cost-ratio-histogram`, `GET /findings/{finding_id}` (finding + evidence + saved review), `PUT /findings/{finding_id}/review`, `GET /reviews` |
| `routers/scorecards.py` | `GET /scorecards/contractors`, `GET /scorecards/wards`, `GET /scorecards/sla-tiers` |
| `routers/cases.py` | `GET /cases/presets`, `GET /cases?ward=&q=&limit=`, `GET /cases/{work_order_id}` (work order, complaints, road, timeline, bill, outcome, findings, road history), `GET /complaints/{complaint_id}` |
| `routers/plan.py` | `GET /wards/{ward}/plan?budget_inr=&severity=&flood=&traffic=&facilities=&accidents=&repeat=&complaints=&social=` |
| `routers/ai.py` | `POST /ask`, `GET /cases/{work_order_id}/verdict`, `POST /wards/{ward}/brief`, `GET /scorecards/{kind}/{entity_id}/text` |

**Frontend** (`frontend/`, pages follow the brief's questions; the list is the `NAV` array in `frontend/components/shell.tsx`)

| Route | Page |
|---|---|
| `/` | Where did the money go? Ward KPIs, money flow, ward map, rain vs spend, top roads |
| `/case` | Follow one case from complaint to verdict |
| `/audit` | What doesn't add up? Leads, evidence card, officer decision buttons |
| `/scorecards` | Who is responsible? Like-for-like contractor and ward report cards |
| `/next-rupee` | Where should the next rupee go? Budget-capped risk plan |
| `/ask` | Ask about my complaint, in English, Hindi, Marathi or Hinglish |

**Core and tests**: `src/audit.py` (3 flag rules: 493 warranty, 111 above rate card, 45 possible duplicates; Rs 3.22 Cr counted once), `src/scorecard.py`, `src/budget.py`, `src/ai.py` (cache + template fallback), 73 tests in `tests/`.
**Fallback**: the Streamlit app (`app.py`) still runs and is the backup demo. No new Streamlit work.

## 2. Timeline (today)

| Time | What |
|---|---|
| 13:15 | Base handed over. Start your feature. |
| 14:00 | Pull request open, even if rough. |
| 14:15 | Merged into `main`. **Anything not merged by 14:15 is not in the video.** |
| 14:15 to 14:30 | Demo video recorded by the lead. |
| until 14:45 | Internal review of the video. |
| 15:30 | Feature freeze. Bug fixes only. |
| 16:15 | Submit. |

Build the smallest version that works end to end first, open the PR, then improve it.

## 3. How to work

- Branch `feat/<name>-<feature>` off `main`. One PR per feature. Small PRs merge faster.
- Create new files where you can. Your task file lists the files you own.
- Shared files that need a heads-up in the team chat before you edit them: `frontend/components/shell.tsx` (the `NAV` array), `backend/main.py` (the router tuple), `frontend/lib/api.ts`. Keep edits to one or two lines.
- Owned files: `src/budget.py`, `src/ai.py`, `src/data.py`, `backend/routers/plan.py`, `backend/routers/ai.py`, README and CLAUDE.md belong to the lead. `src/audit.py`, `src/scorecard.py` and `tests/` belong to the audit owner. Change them only through a PR that says why.

**Add a backend router**
1. New file `backend/routers/<name>.py` with `router = APIRouter(tags=["<name>"])`. Declare paths without the `/api` prefix.
2. Import it in `backend/main.py` and add it to the tuple in the `for r in (...)` loop **before `wards`**. The wards router ends with a catch-all `/wards/{ward:path}`.
3. Get data from `backend/deps.py`: `state()` returns `{"t", "findings", "informational", "contractors", "wards"}`. Convert with `records(df)` or `record(series)`. Return `"data_layer": DATA_LAYER` with every rupee response.
4. Ward codes contain a slash (`F/N`). Declare them as `{ward:path}`.
5. Keys are snake_case, rupees are integers named `*_inr`, timestamps are ISO strings.

**Add a page**
1. `frontend/app/<route>/page.tsx`, starting with `"use client";`.
2. Fetch with `useQuery` and `api()` from `frontend/lib/api.ts`. Selected ward: `useWard()` from `frontend/app/providers.tsx`.
3. Use the shared pieces in `frontend/components/bits.tsx`: `Kpi`, `Section`, `PageTitle`, `Pill`, `PeerChip`, `DataBadge`, `SourceBadge`, `Loading`, `ErrorBox`. Format with `inr()`, `pct()`, `when()` from `frontend/lib/format.ts`.
4. Add `{ href, label }` to `NAV` in `frontend/components/shell.tsx` if the page needs a tab.
5. Colours: green held, amber failed, orange needs review, purple warranty, blue neutral.

**Add a table**: a `SQLModel` class with `table=True` in `backend/db.py` (see `LeadReview`). `init_db()` creates it at start-up. The `.db` file is ignored by git.

**Use Claude**: only on the backend, only through `src.ai._call(task, payload, system, user, schema=None, max_tokens=...)`, which returns `(result, source)` and `(None, None)` when offline. Always write a deterministic template fallback and return `source` so the UI can badge it. Claude explains; it never decides a verdict or changes a number.

**Before you push**: `.venv/Scripts/python -m pytest` passes, and `cd frontend && npm run build` succeeds.

**PR checklist**
- [ ] Runs locally on both servers.
- [ ] No invented numbers. New figures come from `src/` and have a test.
- [ ] Every amount says what it is (billed, budget, estimate) and carries the data badge.
- [ ] Wording is neutral: "needs review", never fraud or blame.
- [ ] New deterministic logic has a test in `tests/`.
- [ ] No `.env`, key, `.db`, `node_modules/` or trailers in the commit.

## 4. Assignments

| Teammate | Feature | Criterion it strengthens | Files to create | Task file |
|---|---|---|---|---|
| Harsh | Recommended three-way verdict, fair hearing, repair receipt (stretch) | Audit accuracy, Fair accountability, Usable demo | `src/verdict.py`, `src/hearing.py`, `backend/routers/verdicts.py`, `frontend/components/verdict-panel.tsx`, `tests/test_verdict.py` | [docs/tasks/harsh.md](docs/tasks/harsh.md) |
| Shariyan | Rain and flood context on scorecards, evidence-request letter | Fair accountability, Usable demo | `src/context.py`, `src/letters.py`, `backend/routers/letters.py`, `frontend/components/letter-button.tsx`, `tests/test_letters.py` | [docs/tasks/shariyan.md](docs/tasks/shariyan.md) |
| Aditya | Strategy comparison: same budget spent three ways | Budget smarts | `src/strategies.py`, `backend/routers/strategies.py`, `frontend/components/strategy-compare.tsx`, `tests/test_strategies.py` | [docs/tasks/aditya.md](docs/tasks/aditya.md) |
| Deven | Road history: one page per road | Connects the trail, Fair accountability | `backend/routers/roads.py`, `frontend/app/roads/page.tsx`, `frontend/app/roads/[id]/page.tsx`, `tests/test_roads.py` | [docs/tasks/deven.md](docs/tasks/deven.md) |
| Kshitij (lead) | Merge PRs, Claude key and cache, demo video, submission | All | none | [docs/tasks/lead.md](docs/tasks/lead.md) |

## 5. Done for the video

- Both servers start from the README commands on a clean clone.
- All six base pages load for ward L with no error box.
- Each merged feature has one screen that works on a named example (your task file gives the example).
- No screen shows the word fraud, an untyped rupee amount, or a number that is not from the dataset.
- The "Synthetic (organizer)" badge is visible on every page.
