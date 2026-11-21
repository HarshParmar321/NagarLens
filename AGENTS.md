# AGENTS.md

Instructions for any coding agent (Claude Code, Codex, Gemini, Cursor) working in this repo.

Read these two files before you write code:

1. `CLAUDE.md`: project rules, data rules, architecture and commands.
2. `TASKS.md`: who builds what, the timeline, and how to add a router, a page or a table. Your own task file is in `docs/tasks/`.

Run it (three terminals, from the repo root unless stated):

```
.venv/Scripts/python -m uvicorn backend.main:app --reload --port 8000   # API, docs at http://localhost:8000/docs
cd frontend && npm install && npm run dev                               # web app at http://localhost:3000
.venv/Scripts/python -m pytest                                          # tests, run before every push
```

First-time setup: `uv venv --python 3.12 .venv && uv pip install --python .venv -r requirements.txt`.
On macOS or Linux use `.venv/bin/python` instead of `.venv/Scripts/python`.

Five rules that cannot be broken:

1. Never invent numbers, columns, joins or findings. If the dataset cannot support a feature, say so in the UI.
2. Every figure comes from the deterministic code in `src/`, served through the API in `backend/`. The frontend only formats. Claude never computes or changes a number.
3. Audit flags are "needs review" leads with evidence, fair context and a next action. Never write fraud, scam, guilty or blame language, in code, UI text or prompts.
4. Never commit `.env`, an API key or `backend/nagarlens.db`. The key lives only in `.env` (template: `.env.example`).
5. Commits and PRs carry no `Co-Authored-By`, `Claude-Session` or other attribution trailers.

The dataset in `data/raw/` is synthetic and must stay unchanged. All contractors are fictional.
