# Data Paddock overhaul: progress log

The working memory for the overhaul in `LONG_RUN_PROMPT.md` against the audit in `REVIEW.md`.
Re-read this file whenever resuming.

## Current phase

Phases 0–4 are implemented on `claude/laughing-clarke-t71435`. Phase 5 (frontend for both audiences) is partly done. Waiting on the owner for:
1. Merging the PR, so the Site workflow upgrades the live database (entries, statuses, pit alignment, moments) and recomputes turn deltas.
2. A pilot story run (`stories-only`, story_rounds `1,12,17`) to produce the first fact-checked stories for the §5.2 review.

## How this run deviates from the prompt (and why)

| Prompt says | What this run does | Why |
|---|---|---|
| Work on a branch named `overhaul` | Works on `claude/laughing-clarke-t71435` | This session may only push to that branch. The owner merges PRs into `main`. |
| Merge to main at each phase gate, let CI deploy, roll back if the live crawl fails | Opens a PR at each gate; the owner merges; the crawler then runs against the live site | Merging deploys the public site, so the owner decides when that happens. |
| `NARRATIVE_MODEL = "claude-fable-5-1"` | One constant (`config.NARRATIVE_MODEL`), env-overridable, still defaulting to Haiku 5.5 at low effort | The owner ran out of credits on Fable 5.1 and chose Haiku for cost. See "Blocked: needs owner". |
| Key from `ANTHROPIC_API_KEY` | Supported, plus Workload Identity Federation in CI (already in place) | Production generation runs in GitHub Actions with no stored key. |
| Regenerate pilot stories and review them | The pipeline, fact-checker and fallback are built and unit-tested here; pilot regeneration runs in the owner's workflow (`stories-only`, pilot rounds) | This sandbox has no Claude credentials, and the federation rule only accepts runs from `main`. |

## Verification of REVIEW.md (done before any change)

Every claim was checked against the live site (relayed locally), the published JSON, Jolpica, and OpenF1.

| # | Verdict | Evidence |
|---|---|---|
| 1 | **Not reproduced yet** | Live site and local build: home → race → driver → home → standings → race with in-app clicks gave no console errors. The suggested cause (an effect returning a non-function) doesn't match the code: `setEvent` and `window.scrollTo` both return `undefined`. The full crawler (Phase 0) must settle it. |
| 2 | True | `sessions/5/drivers/11/narrative.json` strategy text ends `...cannot isolate.}<br>BAD_FORMAT_FIXED_BELOW>{}` |
| 3 | True | Gasly Q story and weekend arc: "one place behind his Alpine teammate Franco Colapinto" (Gasly P14, Colapinto P16). Hadjar season arc: "97 points behind the leader's 340". Piastri's R1 story ties a lap-18 move to "the first Virtual Safety Car" (first VSC was lap 12). |
| 4 | True | R12 race: Racing Bulls ×3, Red Bull ×1 on the site. Jolpica: LAW `red_bull` at R12 and R14, TSU `rb`. Official constructors after R17: Red Bull 332 and RB 100; ours: 318 and 114. |
| 5 | True | Gasly R1 analysis: "The stop came just before the lap 12 VSC, which may have reduced the time lost". |
| 6 | True | Jolpica R1: positionText `W` for PIA and HUL ("Did not start"), `R` for STR, ALO, BOT, HAD. The site shows DNF for all six; the tile counts 3 retirements; the true numbers are 4 DNF and 2 DNS. STR's raw status is "Lapped" although he isn't classified (positionText `R`). |
| 7 | True | R1 qualifying has 19 rows (Jolpica has only 19; VER, SAI and STR set no time). P9 +2.729 against P10 +1.703, because a Q3 time is compared with Q2 times. |
| 8 | True, and the cause is found | Gasly R1: corners sum to 3.461s and the stated total is 5.880s. The reference lap is the event's *qualifying* pole lap (session 4), not the race session's best. Corner windows are ±60 m around each apex, so the time on the straights is never attributed. |
| 9 | True | R1 moments are mostly pit stops and VSCs; HAD retiring from P3, PIA DNS from P5 and VER P20→P6 are missing. R17 shows "compound unknown" for every stop while all 47 stints have compounds: the stint-boundary join (`lap_end == in-lap`) misses. |
| 10 | True | 17 "Virtual Safety Car deployed on lap None" in practice sessions. |
| 11 | True, a feed limitation | OpenF1 `/pit` has `stop_duration: null` for every stop in R5, R6, R8, R9 and R11–R17. Lane time is always present. The fix is presentation. |
| 12 | True for 2 races | Max position lap vs race distance: R1 57/58 and R10 44/45; the other races match. |
| 13 | **Partly wrong** | The order is the official classification. R17 ALB has positionText `18` (classified retirement, 59 laps) ahead of BOT P19 (lapped, 59 laps). The real bug is displaying "DNF" in place of the classified P18. |
| 14 | To check in Phase 3 | |
| 15 | True by design | Head-to-heads exist only for teammates. |
| 16 | Plausible | Ocon's and Gasly's stories are written independently from different inputs; this is checked in Phase 4. |
| 17–30 | Mostly true | Checked as each one is fixed. "Bahrain in Malaysia" is correct (the review says so too). |

## Issue checklist

Status: `open` / `in progress` / `fixed (evidence: ...)` / `won't fix (reason)`. Tests named here live in `tests/` (pytest), `tests/invariants/` (run on the export) and `frontend/e2e/crawl.spec.ts` (Playwright).

| # | Issue | Status |
|---|---|---|
| 1 | In-app navigation crash | fixed (evidence: reproduced with a wrapped `window.scrollTo` in `crawl.spec.ts`; the crawl now passes navigation; `npm run lint` runs `scripts/check-effects.mjs`, which rejects expression-bodied effects; commit d0ea969) |
| 2 | Raw model output in a story | fixed for publication (evidence: `test_factcheck.py::test_leaked_model_output_is_caught`; publish-time re-check replaces failing stories with the computed template; invariant `test_no_machine_text_in_user_facing_strings` passes; 64 leaked strings in the old export, 0 now). Regeneration pending (owner run). |
| 3 | False facts in stories | fixed in the pipeline (evidence: `test_factcheck.py` teammate, numbers, points-arithmetic and unentered-driver tests; season facts give Hadjar "243 behind" with his missed rounds 12–14). Published stories are templates until the pilot regeneration. |
| 4 | Team per event, constructor standings | fixed (evidence: `entries` table; `test_entries.py`; invariants `test_constructor_points_match_official_standings`, `test_driver_points_match_official_standings`, `test_one_team_per_driver_per_event`, `test_team_cars_per_race` pass; Red Bull 332 and RB 100, matching Jolpica) |
| 5 | VSC logic backwards | fixed (evidence: `strategy.neutralisation_relation` + `test_stop_timing_relative_to_a_vsc`; checker `test_vsc_logic_inversion_is_caught`; Gasly R1 verdict: "just before the VSC: unlucky timing") |
| 6 | DNS shown as DNF; counts disagree | fixed (evidence: `test_race_status_codes`, `test_headline_race_order_and_counts`; invariant `test_race_status_is_an_enum_and_counts_agree` for all 23 race/sprint sessions) |
| 7 | Qualifying missing drivers, mixed segments | fixed (evidence: invariants `test_qualifying_lists_every_entrant`, `test_qualifying_gaps_are_per_segment_and_ordered`, `test_gap_pole_to_p10_uses_final_segment`; R1 shows all 22, with VER, SAI and STR as "No time") |
| 8 | Corner deltas don't add up | fixed (evidence: invariant `test_turn_deltas_reconcile` passes for all 317 recomputed pilot breakdowns; corners + "Other" = lap − session-best lap; old breakdowns are withheld until the pipeline recomputes them) |
| 9 | Key moments are routine stops; compound join | fixed (evidence: new engine `analysis/pivotal.py`; `test_race_moments_surface_what_mattered`; invariants `test_key_moments_are_not_routine_stops`, `test_pit_moments_use_known_compounds`; R1 now lists PIA DNS from P5, HAD retired from P5 (started P3), VER P20→P6, all three VSCs) |
| 10 | "lap None" | fixed (evidence: invariant `test_no_machine_text_in_user_facing_strings`; practice neutralisations no longer carry a lap) |
| 11 | Stationary time missing | fixed as presentation (feed limitation: OpenF1 `/pit` has `stop_duration: null` for R5, R6, R8, R9, R11–R17). Stories get "not published by the timing feed" once, in `insufficient_data`; pit-lane time is used instead; glossary entry "Stationary time". |
| 12 | Lap count off by one | fixed (evidence: invariant `test_position_chart_covers_race_distance`; final laps come from the classification; `test_position_by_lap_takes_the_final_lap_from_the_classification`) |
| 13 | Classification sort | fixed. The order was the official classification; the label was the bug. Evidence: invariant `test_classification_order`; R17 shows ALB as P18 "Retired, classified". |
| 14 | Third VSC missing | fixed (evidence: every neutralisation is `must_include`; invariant `test_every_neutralisation_is_a_key_moment`) |
| 15 | Head-to-heads only for teammates | fixed (evidence: `compare.comparison_pairs` adds adjacent finishers and shared stewards' cases; other pairs get the computed comparison in `CompareView`) |
| 16 | Two drivers' stories disagree | fixed in the pipeline: shared stewards' cases (`race_control.cases`, `test_classifier_types_and_shared_cases`) feed both drivers' fact sheets and the pair facts. To be confirmed in the pilot review. |
| 17 | Y-axis stops at P20 | fixed (domain = grid size; R1 axis runs to P22) |
| 18 | Teammates share a line colour | fixed (second car of each team dashed) |
| 19 | Hover-only instruction on mobile | fixed ("Tap a line to follow a driver" below md; glossary tooltips work on tap) |
| 20 | Sector labels mix references | fixed (rank-based tiers with a legend; labels "14th of 20 · to the session best") |
| 21 | "16th of 20" when 22 raced | fixed (labels read "14th of 20 who set a time"; fact sheets carry `of_means`) |
| 22 | Unknown compound unlabelled | fixed (hatched swatch plus "Unknown (not in the feed)" legend entry) |
| 23 | Year dropdown with one season | fixed (hidden while only one season exists) |
| 24 | Titles, previews, hash URLs | fixed (path routing plus 393 prerendered shells with titles, descriptions, canonical URLs and 391 Open Graph images; sitemap.xml and robots.txt; old `#/` links redirect; ADR `docs/adr/0001-path-routing-and-prerendered-shells.md`; crawl tests for legacy links and driver pages) |
| 25 | Bundle and payload size | fixed (home JS 87 KB gzipped against a 250 KB target; the chart library (102 KB) loads only when a chart scrolls into view; detail.json split per view, largest race-page file 46 KB against a 200 KB target; export total 37.5 MB → 8.3 MB; outline previews inlined in events.json; headline has this session's entrants only) |
| 26 | Card text repeats | fixed (midfield reasons merged per driver with no repeated sentences; the midfield tile is gone; the summary avoids repeating a driver) |
| 27 | Bare-adjective event names | fixed (full event names on every card) |
| 28 | No separate races index | fixed (`/races`: grid with an all/sprint-weekends filter and "Follow a team", which puts that team's results on every card) |
| 29 | Report needs GitHub | fixed in code; needs owner: an email "Report an error" link appears when the repository variable `VITE_REPORT_EMAIL` is set (an address isn't published without the owner choosing one) |
| 30 | Mobile highlight cards | fixed (four cards replaced by the 30-second summary block; numbers scroll sideways on phones) |

## New issues found (#31+)

| # | Sev | Issue | Status |
|---|---|---|---|
| 31 | P1 | FP1 rookies stored as "Driver #34", and a rookie who changed number was stored twice | fixed (names and codes from OpenF1; duplicates merged; resolve by name before number) |
| 32 | P0 | OpenF1's pit `lap_number` is the out-lap at some events and the in-lap at others, so stops were a lap early in most races, corrupting compounds, VSC timing and pit dots | fixed (`align_pit_laps` anchors on the out-lap flag; `test_pit_in_lap_follows_the_out_lap_flag_whatever_openf1_numbers_the_stop`; existing sessions repaired once) |
| 33 | P1 | Red-flag pit-lane queues (R12) were counted as pit stops, so every car had an extra stop and slow-stop moments read "1559.6s longer" | fixed (`strategy.real_stops`, a 120s lane cut-off; "SESSION ABORTED" treated as a red flag) |
| 34 | P1 | 64 published strings carried model self-talk (`</strategy_analysis_text>}`, "Note to reviewer", "Wait, invalid trailing character"), not only Ocon's | fixed for publication (publish-time check) |
| 35 | P2 | OpenF1 stints and pit records disagree for some cars (soft for lap 1, then mediums for laps 2–36, but a stop on lap 26) | handled (fact sheets drop the stint list and say the tyre data is inconsistent) |

## Blocked: needs owner

- **Story model.** The prompt asks for Fable 5.1; the owner chose Haiku 5.5 (low effort) after running out of credits. The new pipeline works with either model. To switch, set the repository variable `F1_NARRATIVE_MODEL`.
- **Pilot regeneration.** Stories can only be generated by the GitHub workflow on `main` (federation rule). After the Phase 4 PR is merged, run the Site workflow with mode `stories-only` and pilot rounds `1,12,17`.

## Measurements

Lighthouse, mobile, production build served compressed (2026-10-18):

| Page | Performance | Accessibility | Best practices | SEO |
|---|---|---|---|---|
| Home | 98 | 100 | 96 | 100 |
| Race (Australia) | 96 | 100 | 96 | 100 |

Best practices loses its points to Google Fonts failing TLS in this sandbox's proxy only.

Local suite on the production snapshot (upgraded) + pilot turn deltas: unit 44 passed · invariants 207 passed · Playwright crawl 16/16 (desktop 1280×800 and mobile 375×812, every race and session tab via in-app links, pilot driver/compare/deep-dive flows, standings, 404, legacy links, driver pages, no horizontal scroll on mobile).

## Critic scores

(first pass after the pilot stories exist; the narrative persona scores depend on them)

**Pass 0 (layout and template text only, before the pilot stories; not scored).** Desktop and 375px screenshots of home, races, standings, a race, a qualifying session, a driver page, a head-to-head and the R12 red-flag race. Found and fixed:
- Templates said "In qualifying he was missed out by 0.280s". Cut-line margins are now verb phrases ("he got through by", "he missed out by").
- Head to head said "Gasly made 1 stop, Ocon 1." It now says "Both stopped once."
- The race summary listed one label per neutralisation ("VSC · VSC · VSC"). It now counts them by kind ("1 Red · 2 VSC").
- The empty "Positions by lap" panel in full-page screenshots is the lazy chart not yet scrolled into view; scrolled, it renders all 22 lines with the red flag and VSC bands.
- CI: the crawler's preview server bound to IPv6 on the runner. It is now pinned to 127.0.0.1.

## LLM usage log

No calls from this sandbox. Each workflow run now writes "Claude calls" and "published as fact-sheet templates" to the job summary; they will be copied here.

## Next 3 actions

1. Owner merges the PR. The push-triggered publish-only run upgrades the live database, and the gates (invariants, crawl) must pass before it deploys. Then I run the crawler against the live URL.
2. Owner runs the Site workflow: mode `stories-only`, story_rounds `1,12,17`. Then I download the snapshot, review 15 pilot stories against the §5.2 rubric and iterate on the prompts and fact sheets.
3. The next full run recomputes all turn deltas with the reconciling method (about 70 min of OpenF1 downloads), then the first critic pass.
