# Current task: Data Paddock round 2, story quality (Workstream B)

## Project
Data Paddock is an F1 analysis site. The backend uses FastAPI and SQLAlchemy over SQLite (`f1tracker/`). A static JSON export is deployed to GitHub Pages. The frontend uses React 19, Vite and Tailwind 4 (`frontend/`). Driver-session stories, weekend arcs and head-to-heads are written by Claude (the Haiku model). Code checks every story against a fact sheet (`f1tracker/narratives/factcheck.py`). If a story fails, a template is used instead. The database snapshot is the GitHub release asset `db-snapshot/f1.db.gz`. The site workflow modes are full, stories-only and publish-only.

## Done
- Round 2 Workstreams A (declutter), C (data fixes) and B (stories, prompt v3) were merged in PR #6 (merge commit 3ab9aa4).
- The owner ran the pilot: a stories-only run for rounds 1, 12 and 17 (run 39277498505).
- I reviewed the pilot. Results are recorded in `PROGRESS.md` under "Pilot (prompt v3)" and in the LLM usage log.
  - **Pass rate:** 317 of 324 driver stories (97.8%) were written by Claude, against a 90% gate. All 66 arcs and all 139 head-to-heads were written by Claude.
  - **Quality gate failed:** the 15 sampled stories averaged 3.67 against the 4.3 target. The worst was R12 Qualifying, Bottas, at 2.5.

## State (confirmed)
- **Branch:** `claude/laughing-clarke-t71435` is pushed and 2 commits ahead of `main`:
  - `5480cc8` adds `docs/BENCHMARKS.md`.
  - `f15697e` records the pilot review in PROGRESS.md.
- No PR is open for these commits yet.
- The repository variable `MAX_NEW_STORIES` is set to 0, so the daily run writes no stories. A pilot has to pass `max_new_stories` explicitly.
- The pilot's deploy job showed "waiting" when last checked, so the pilot stories may not be live. This is unverified since then.

## Files changed this session (after the merge)
- `PROGRESS.md`: the pilot scores, worst-story text, proposed fixes and a usage-log row.
- `docs/BENCHMARKS.md`: the owner's scorecard knowledge base.

## Verification
- **Pilot snapshot queries:**
  - pass rates and attempts (212 first try, 101 second, 11 third)
  - rejection reasons
  - a regex sweep of all 317 stories: 1 wrong ordinal, 104 sentences about missing data, 10 filler phrases, 7 weather temperatures, 3 invented "standing in"
- The scored sample was hand-read.
- No code has changed since the merge, so no tests were run.

## Decisions and constraints
- The model, effort, word limits and call cap stay unchanged; I only recommend changes to them.
- Don't merge PRs. Push only to the branch above.
- No model IDs in commits or PRs.
- **The owner is credit-conscious:** don't poll or watch runs. The owner reports when runs finish.
- Never print the API key. Don't commit the insights report.
- Each prompt iteration needs a pilot run by the owner, up to 3 iterations.

## Next steps
1. **Wait for the owner's go-ahead**, then build prompt v4 (PROMPT_VERSION "4"):
   - **Checker fixes:**
     - Accept numbers like "35.9C".
     - Check ordinal suffixes.
     - Check sector claims ("final sectors", "weakest") against the sector ranks.
     - Check Q1/Q2/Q3 naming against the segment the driver was knocked out in.
   - **Prompt fixes:**
     - Leave weather out of `prompt_sheet` unless rain mattered.
     - Add a rule: don't mention data that isn't published.
     - Add a rule: no guessed motives or invented roles ("standing in").
   - **Data fix:** flag stints that span a pit stop (example: R17 Hadjar has a soft stint for laps 2–62 but pitted on lap 33).
   - Add tests in `tests/test_factcheck.py` and `tests/test_prompts.py`.
2. Owner reruns the pilot. Then re-score the same 15 stories (the list is in PROGRESS.md) against these gates:
   - average of at least 4.3
   - no story below 3
   - every headline a verdict
3. If the gate passes, add an owner action for a full-season stories-only run.
4. Later:
   - a PR for the branch commits
   - BENCHMARKS.md scorecard scoring (draft estimate about 78/100)
   - Workstream D: spoiler-free mode, follow a driver, a methods page, a changelog
