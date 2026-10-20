# Current task: Data Paddock round 3

## Project
Data Paddock is an F1 analysis site. The backend uses FastAPI and SQLAlchemy over SQLite (`f1tracker/`). A static JSON export is deployed to GitHub Pages. The frontend uses React 19, Vite and Tailwind 4 (`frontend/`). Claude (the Haiku model) writes the stories, and code checks each one against a fact sheet. The database snapshot is the GitHub release asset `db-snapshot/f1.db.gz`.

The round 3 brief is `docs/LONG_RUN_PROMPT_ROUND3.md` and the review is `docs/REVIEW_ROUND3.md` (findings #48–#60, decisions D6–D8). `PROGRESS.md` → "# Round 3" is the working memory: checklist, decisions, owner actions, scorecard log.

## Order of work
1. **PR 1, Workstream F (turn-by-turn, #48, #49): built and pushed on `claude/laughing-clarke-t71435`; waiting for the owner to merge.** It also carries the round 3 docs and the two round 2 docs commits.
2. PR 2, Workstream H pipeline: checker fixes, prompt v4, data fixes (stints that span a stop, lap 1–2 incidents linked to retirements, the DNS template, the home midfield line) and `debrief` in the fact-sheet pipeline. Then list the pilot under owner actions and stop story work until the owner reports it finished.
3. PR 3, Workstreams G and H UI: `selectDriver`, `vs=`, the vs strip, the Expert debrief view and a methods page. Build it while the pilot runs.
4. PR 4, Workstream E (Circuit atlas).
5. Small PRs: spoiler-free mode, follow a driver, a changelog.

## State
- This session may push only to `claude/laughing-clarke-t71435`. Each next workstream restarts that branch from `main` after the previous PR merges. Prepare later work locally meanwhile.
- The turn-delta version is now 3, so the next daily `full` run recomputes every breakdown within its 270-minute budget (no Claude calls). Until then, version 2 breakdowns show behind the plausibility gate.
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
1. Owner merges PR 1.
2. Restart the branch from `main` and build PR 2 (Workstream H pipeline).
