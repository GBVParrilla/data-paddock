# Current task: Data Paddock round 3

## Project
Data Paddock is an F1 analysis site. The backend uses FastAPI and SQLAlchemy over SQLite (`f1tracker/`). A static JSON export is deployed to GitHub Pages. The frontend uses React 19, Vite and Tailwind 4 (`frontend/`). Claude (the Haiku model) writes the stories, and code checks each one against a fact sheet. The database snapshot is the GitHub release asset `db-snapshot/f1.db.gz`.

The round 3 brief is `docs/LONG_RUN_PROMPT_ROUND3.md` and the review is `docs/REVIEW_ROUND3.md` (findings #48–#60, decisions D6–D8). `PROGRESS.md` → "# Round 3" is the working memory: checklist, decisions, owner actions, scorecard log.

## Order of work
1. PR 1, Workstream F (turn-by-turn, #48, #49): merged (PR #7, 20 Oct).
2. PR 2, Workstream H pipeline: merged (PR #8, 20 Oct). **The owner runs the pilot** (stories-only, rounds 1,12,17, max_new_stories 800). Then score the same 15 stories (list in PROGRESS.md round 2 "Pilot") against the gate: average ≥ 4.3, none below 3, ≤ 10% of a session's headlines sharing a shape, no missing-data sentences. Don't change stories until the owner reports the pilot finished.
3. PR 3, Workstreams G and H UI: merged (PR #9). Pilot v4 scored 3.86 (gate 4.3; PROGRESS.md "Pilot (prompt v4)"). **Pilot-fixes PR open** (prompt v5); the owner then decides effort medium and runs a second pilot.
4. PR 4, Workstream E (Circuit atlas): merged (PR #11). Finding #61 (driver-page performance) open.
4b. Pilot 2 (v5): average 4.15. Prompt v6 merged (PR #12). Pilot 3 (v6): 98.8% Claude, 0 violations, filler gone, average **4.09** (gate 4.3). All three prompt iterations are spent. **Pilot 3 review PR open** (adds `check_half`). The owner chose Haiku for every story (H12).
5. Small PRs: spoiler-free mode, follow a driver, a changelog.

## State
- This session may push only to `claude/laughing-clarke-t71435`. Each next workstream restarts that branch from `main` after the previous PR merges. Prepare later work locally meanwhile.
- The turn-delta version is now 3, so the next daily `full` run recomputes every breakdown within its 270-minute budget (no Claude calls). Until then, version 2 breakdowns show behind the plausibility gate.
- `PROMPT_VERSION` is 6: Claude writes headline + Essential only; `debrief` (code) is in every `narrative.json`. Style rules apply at generation only (`style=False` at export).
- Local dev DB: `data/f1.db` is the latest snapshot after `run_pipeline.py --no-ingest --no-stories`. `scratchpad/measure.py`-style checks are now invariants (`tests/invariants/test_stories_round3.py`).
- `MAX_NEW_STORIES` stays 0. A pilot must pass `max_new_stories` explicitly.

## Rules
- Don't merge PRs. Push only to the branch above.
- Never put model IDs in commits or PRs.
- Don't poll or watch workflow runs. The owner reports when they finish.
- Never print the API key.
- Batch prompt changes into as few pilots as possible.
- The model, effort, word limits and call cap are the owner's call: recommend, don't change.
- Never ask questions. Record each call under "Decisions made" in the PR and in PROGRESS.md.

## Next steps
1. Full-season run done (99.1% Claude). Live crawl green; scorecard 85/100 (every A row at 2); personas 7–8. #62 PR open (driver story under the sheet). Next: #63, #64, then the small PRs (spoiler-free, follow a driver, changelog) and #61.
2. Meanwhile: re-score the BENCHMARKS §7 scorecard and the five personas (light and dark), then the small PRs (spoiler-free mode, follow a driver, changelog).
