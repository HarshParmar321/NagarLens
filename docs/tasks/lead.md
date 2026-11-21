# Lead (Kshitij, with the two Claude sessions): merge, key, video, submit

Read `TASKS.md` for the timeline. This file is the checklist from 13:15 to submission.

## Goal
Keep `main` runnable at all times, merge the four feature PRs by 14:15, record the 2-minute demo video by 14:30, review it by 14:45, and submit by 16:15.

## 1. Claude key and cache (do first, it runs while others build)
1. Put `ANTHROPIC_API_KEY=` in `.env` at the repo root (never commit it). `src/ai.py` loads it.
2. Restart the API. `GET /api/health` should report `ai_available: true`.
3. Pre-warm the cache so the video and a judge without a key both see Claude output: open each demo screen once (case verdicts for the five presets in `GET /api/cases/presets`, the ward L brief, scorecard text for 8 contractors, the Marathi question below), and run the complaint triage batch for the 896 open complaints.
4. Commit `data/cache/ai_cache.json`. It is the reason the app shows AI answers offline.
5. Check every AI panel shows the "Written by Claude" badge, and "Template" only when offline.

## 2. Merge order and what to check
Merge smallest and most independent first. After each merge: `pytest`, `npm run build`, open the page.

| Order | PR | Check before merging |
|---|---|---|
| 1 | Deven, road history | New router registered before `wards`. `/roads/RD0220` loads. Social matches labelled candidate. |
| 2 | Aditya, strategy comparison | All three strategies within budget. No invented benefit numbers. `src/budget.py` untouched. |
| 3 | Shariyan, rain context + letter | Chip logic in `src/scorecard.py` unchanged. Letter has no legal-notice wording. Works offline. |
| 4 | Harsh, verdict + hearing | Verdict is rule based. Hearing has a template fallback. Uses "billed", not "paid". |

Conflicts will be in `backend/main.py` (router tuple), `frontend/components/shell.tsx` (`NAV`) and `frontend/app/audit/page.tsx` (two teammates mount a component there). Resolve by keeping both lines.
Reject or defer anything that breaks a rule in `AGENTS.md`. A feature missing from the video is better than a wrong number in it.

## 3. Demo video (record 14:15 to 14:30, review to 14:45)
The plan, shot list and word-for-word voiceover are in `demo/DEMO_SCRIPT.md`. That file is the only script; do not keep a second copy here.

Before recording, and again after each merge:
1. `.venv/Scripts/python demo/check_demo.py` checks every number in the voiceover against the app. It must end with `ALL CLAIMS MATCH THE APP`.
2. `.venv/Scripts/python demo/walkthrough.py --fast` proves every click in the shot list works.
3. `.venv/Scripts/python demo/walkthrough.py` records a silent backup take to `demo/out/walkthrough.webm`.

If a merged PR makes either check fail, fix it or revert the PR before recording.

## 4. Fallback
If the new stack breaks close to recording: `.venv/Scripts/python -m streamlit run app.py`. It covers the same six steps in tabs. Record from it and say nothing about the stack.

## 5. Submission checklist
- [ ] Repo is public and `main` has everything.
- [ ] README: what it is, the two start commands (API and frontend), the fallback command, the synthetic-data notice, team names.
- [ ] `.env.example` committed with a blank `ANTHROPIC_API_KEY=`. `.env` is ignored.
- [ ] `git log -p | grep -i "sk-ant"` finds nothing. If a key was ever pushed, revoke it.
- [ ] `node_modules/`, `.next/`, `*.db`, `docs/TEAM_PLAN.md` and the hackathon spec are not tracked.
- [ ] `data/cache/ai_cache.json` is committed.
- [ ] Fresh clone test on a second laptop: setup, both servers start, `/` loads.
- [ ] `pytest` passes on `main`.
- [ ] Every page shows the "Synthetic (organizer)" badge and no fraud or blame wording.
- [ ] Video link and repo link submitted by 16:15.
