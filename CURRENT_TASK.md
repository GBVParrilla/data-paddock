# Current task: Data Paddock round 3 (handoff, 13 Nov)

## Project
F1 analysis site. FastAPI/SQLAlchemy/SQLite pipeline (`f1tracker/`) → static JSON export → GitHub Pages; React 19 + Vite + Tailwind 4 frontend (`frontend/`). Claude Haiku writes per-driver stories, checked against a fact sheet (`narratives/factcheck.py`); template fallback. DB snapshot is release asset `db-snapshot/f1.db.gz`. Memory: `PROGRESS.md` → "# Round 3" (checklist, decisions, owner actions, scorecard). Brief: `docs/LONG_RUN_PROMPT_ROUND3.md`.

## Done this session
- Prompt v5/v6 and pilots 2–3 (average 4.15, 4.09 vs 4.3 gate; gate missed, owner chose **Haiku for all stories**, decision H12). PRs #12, #13 merged.
- Full-season stories run: 2,271 of 2,291 stories by Claude (99.1%), 245 invariants pass.
- Live audit: crawl green, scorecard **85/100** (every A row 2), personas 7–8. Finding #62 (driver story under the sheet) merged as PR #14.
- **PR #15 (open, CI green, mergeable, branch `claude/laughing-clarke-t71435`, head `b9904fc`)**, four commits: (1) #63 duplicate midfield rows, #64 named margin notes, #65 head-to-head prompt and checks (own `COMPARISON_PROMPT_VERSION`), "The numbers" tables + CSV under charts; (2) lap drill-down (`?lap=N`, `LapCard`, lap-times export now has sectors); (3) spoiler-free mode, follow a driver (`state/prefs.tsx`), `/changes`; (4) #61 performance: gap chart and title fight as hand-drawn SVG, flat season grid. Mobile Lighthouse now 90–98 on every page type.

## Verified
Local production build: crawl 32/32 desktop+mobile; 78 unit tests; 245 invariants; lint clean. Live crawl (before PR #15) 24/24 via a localhost relay (sandbox Chromium distrusts the proxy CA). Lighthouse on a local gzipped server, 3 runs. **Not verified:** PR #15 on the live site; head-to-head rewrite output; scorecard rows A1–A2 against formula1.com.

## Open items
Scorecard gaps: no feedback channel without GitHub (F40), share card per driver (E32), season "Wrapped" (E34). Personas still below 9. Head-to-heads on the site still read times aloud until rewritten.

## Rules
Don't merge PRs; push only to `claude/laughing-clarke-t71435` (restart it from `main` after a merge). No model IDs in commits/PRs. Don't poll workflow runs; the owner reports. Never print keys. Model, effort, word limits, call cap are the owner's call. `MAX_NEW_STORIES` stays 0; pilots pass it explicitly. Record decisions in the PR and PROGRESS.md.

## Next steps
1. Owner merges PR #15, then runs Actions → Site → `stories-only`, story_rounds empty, max_new_stories `1000` (rewrites 715 head-to-heads only).
2. After the owner reports it finished: re-export, check pass rate and invariants, confirm no head-to-head reads times or non-events.
3. Crawl the live URL (`E2E_BASE_URL`, via the relay if TLS fails); re-score BENCHMARKS §7 and the five personas in light and dark; log in PROGRESS.md.
4. Fix the lowest-scoring item first, with a test; number new findings from #68.
5. Exit criteria still open: scorecard ≥ 85 (met), every persona ≥ 9 twice in a row, live crawl green.
