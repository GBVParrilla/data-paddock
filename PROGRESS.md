# Data Paddock overhaul: progress log

The working memory for the overhaul in `LONG_RUN_PROMPT.md` against the audit in `REVIEW.md`.
Re-read this file whenever resuming.

# Round 2

Prompt: `docs/LONG_RUN_PROMPT_ROUND2.md`. Review: `docs/REVIEW_ROUND2.md`. Started 2026-10-18 on `main` at 35cff79 (PR #5 merged).

## Round 2: current workstream

**A (declutter)**: built, PR open. **C** next.

## Round 2: deviations from the prompt

| Prompt says | What this run does | Why |
|---|---|---|
| One branch per workstream, each from the latest `main` | One workstream at a time on `claude/laughing-clarke-t71435`; the next one starts from `main` after the previous PR merges | This session may only push to that branch. Work for later workstreams is prepared locally meanwhile. |
| Score against `docs/BENCHMARKS.md` §7 | Uses the section totals and row findings quoted in `docs/REVIEW_ROUND2.md` until the file exists | BENCHMARKS.md was never committed and was not provided to this session (see Needs owner). |

## Round 2: verification of REVIEW_ROUND2.md

Checked on a production build of `main` (35cff79) with the live `db-snapshot` (upgraded, data version 2), before any change. Numbers come from `frontend/scripts/page-metrics.mjs` (new) unless noted.

| # | Claim | Verdict | Evidence |
|---|---|---|---|
| 36 | All 2,291 published stories are templates | Holds | Export log `stories by source: {'template': 2291}`; 1,851 stored narratives, none written after the fact-checker |
| 37 | Footer says Claude wrote stories that are templates | Holds | `Shell.tsx` footer "Stories written by Claude from that data" on every page |
| 38 | Same fact up to three times | Holds | R1: VER P20→P6 in the summary, Key moments and Beyond the podium; R12: ALO P18→P9 likewise |
| 39 | Summary and moments miss how the race was won | Holds, cause found | R12 leaders: NOR 1, ANT 5, HAM 22, ANT 26, NOR 41, HAM 48, NOR 54. The engine kept only the first 3 lead changes and deduped them per driver, so laps 26–54 vanished |
| 40 | Template prose reads like a log | Holds | "Stop 1 cost him 1 place", "(-0.06s per lap)" in R1 Gasly |
| 41 | Turn-by-turn tab empty | Holds | 1,814 cached breakdowns, all from the old method (no `version`); the export withholds them |
| 42 | No freshness stamp | Holds | Not on any page |
| 43 | /season/2026 title only "Data Paddock" | Holds, more precisely | A direct load gets the prerendered title, but after in-app navigation from home the page keeps "2026 season · Data Paddock" (no `useTitle`) |
| 44 | DNS car has a tyre bar | Holds | R1 `stints.json`: HUL (DNS) has a lap-1 hard stint |
| 45 | Pts cut off at 375px | Holds | Classification scrolls sideways inside its panel; Pts is off-screen |
| 46 | Pages run long | Holds | Home 7,596px at 375; race R1 3,007px at 1360 (4,896 at 375); 13–23 underlines per race page |
| 47 | Two lint warnings | Understated | Five: `useFetch` deps, two `CircuitPanel` exports, a `Glossary` export, `check-effects.mjs` |

Before (1360px / 375px): home 2,926 / 7,596 · races 2,309 / 6,305 · standings 1,520 / 1,990 · R1 3,007 / 4,896 · R12 3,118 / 4,901 · R17 3,107 / 5,033 · R1 Gasly 3,210 / 5,020. Panels before a driver is picked: 7 on every race page. Underlines: R1 19, R12 17, R17 13, R1 Gasly 23.

## Round 2: checklist

| # | Issue | Workstream | Status |
|---|---|---|---|
| 8 / 41 | Turn-by-turn empty | C | in progress (C: the tab hides unless the picked driver has a breakdown, from a per-session index; the recompute itself runs in the next full Site run, because cached breakdowns are versioned. Proof `test_turn_deltas_reconcile` un-skips then) |
| 24 / 43 | Season page title | A | fixed (evidence: `useTitle` on SeasonPage; crawl asserts "· Data Paddock" titles on every page and "standings" after in-app navigation) |
| 26 / 38 | Facts repeat across panels | A | fixed (evidence: `lib/mentions.ts`; crawl `calmRacePage` finds no fact in both the summary and key moments on any session of any race) |
| 29 | Error reports need GitHub | owner | open (needs `VITE_REPORT_EMAIL`) |
| 36 | No AI stories live | B | in progress (pipeline ready locally; needs the owner's pilot run on the new prompt) |
| 37 | False footer claim | A | fixed (evidence: footer line removed; one source line per page from the stories shown; crawl fails any page that says "by Claude" without a Claude-written story on it) |
| 39 | Summary/moments miss how the race was won | A (summary) + C (engine) | C: engine fixed locally (`test_the_lead_change_that_won_the_race_and_a_lap_one_exit_are_always_kept`; on the live data R12 now lists Verstappen's lap-1 exit and Norris's lap-54 lead change). A part fixed (summary priority: deciding lead change, front-runner DNF/DNS, a stoppage that reshuffled the top five, then the biggest climb; R1 now says "Russell took the lead for good from Hamilton through the pit stops on lap 27"). R12 needs the C engine fix to emit the lap-54 change |
| 40 | Template prose reads like a log | B | fixed locally (rewritten templates; all 1,860 non-DNS templates pass the full fact-check including the new verdict-headline and plain-Essential rules; 15-story review below scores 3.67 for new-fan readability, target 3.5) |
| 42 | No freshness stamp | A | fixed (evidence: `meta.json`/`/meta`; crawl asserts "Data through round N · updated D Mon" on home, every race and standings) |
| 44 | DNS car has a tyre bar | C | fixed locally (`session_detail` drops DNS stints; invariant `test_no_tyre_stint_for_a_car_that_never_started` failed on 4 sessions before, passes after) |
| 45 | Pts off-screen on phones | A | fixed (evidence: Grid and Stops hidden below 640px; mobile crawl asserts Pts in the viewport; a new check fails if the classification scrolls sideways at any width, which also caught a 16–40px overflow at 1024–1360px) |
| 46 | Pages run long | A | fixed for the targets (evidence: page-metrics below; home 375px 3,418 < 3,500; race 1360px 1,925 < 2,200) |
| 47 | Lint warnings | A | fixed (evidence: `npm run lint` 0 warnings, down from 5) |
| 48 | Optional per-session files 404 on the live site: `midfield-spotlight.json` when no story stood out, `turn-deltas.json` until the recompute | C | fixed locally (spotlight always written, `null` when none; a per-session turn-deltas index the client asks first; two invariants; crawl against a server with real 404s has no console errors) (found by crawling with a server that returns real 404s; `vite preview` answers them with HTML, which hid them in CI) |

## Round 2: scorecard log

| Date | Commit | Total | A | B | C | D | E | F | Gate |
|---|---|---|---|---|---|---|---|---|---|
| 2026-10-18 | 35cff79 | 65 | 24/32 | 10/14 | 6/16 | 9/12 | 6/12 | 10/14 | fails (A7) |

(Reviewer's scores. Row-level re-scoring needs `docs/BENCHMARKS.md`.)

## Round 2: needs owner

- **Before 06:17 UTC on 19 Oct: set the repository variable `MAX_NEW_STORIES` to `0`.** The daily scheduled run uses `full` mode, which writes stories for every round. The prompt version is part of each story's cache key, so it would rewrite up to 800 stories on the old prompt before the pilot gate. With 0, the scheduled run still updates data and turn deltas.
- **Pilot story run, after the Workstream B PR merges.** Actions → Site → Run workflow: mode `stories-only`, story_rounds `1,12,17`, max_new_stories `800` (about 550 stories: 330 session stories, about 150 head-to-heads, 66 weekend arcs, plus retries).
- **`docs/BENCHMARKS.md`.** Commit the round 1 benchmarks file. Its §7 scorecard is the bar, and this session doesn't have it.
- **Report address (#29).** Choose an address and set the repository variable `VITE_REPORT_EMAIL`.
- **Turn-by-turn recompute (#8/#41).** About 70 minutes of OpenF1 downloads in one Site run; Workstream C adds a switch for it.

## Round 2: after Workstream A (measured, same build setup as "before")

1360px / 375px: home 1,667 / 3,418 · races 2,309 / 6,288 · standings 1,544 / 1,976 · R1 1,925 / 3,088 · R12 1,925 / 2,955 · R17 1,925 / 3,070 · R1 Gasly 3,293 / 5,089 · R1 Gasly Expert 3,581 / 5,670. Panels before a driver is picked: 5 on every race page (was 7). Underlines: R1 4, R12 5, R17 4 (were 19, 17, 13). Crawl 18/18 (desktop and mobile), unit 44, invariants 206 + 1 skipped (turn deltas).

## Round 2: Workstream B (stories), built locally

What the model now gets and must return (`PROMPT_VERSION` 3):
- **Verdict candidates computed in code** (`facts.verdict_candidates`): up to three checked conclusions per driver-session, weighted by how telling they are. Covered: how a winner won (the deciding lead change, or led every lap), a retirement, stop timing against a neutralisation, a pit cycle that swung places, a first-lap gain kept over the race, a climb, a slide (and when it happened), a teammate comparison, pole, a cut-line margin, a weak sector, long-run pace beating single-lap pace. Each has a verdict sentence and a headline of at most 12 words. Examples on the live data: R1 Russell "Russell took the lead for good on lap 27", R12 Norris "…on lap 54", R17 Verstappen "led every lap from pole", R17 Hadjar "worked his way from P22 to P10".
- **Story shape**: headline (12), essential (90), expert (110), analysis (80), key_numbers, glossary_terms. The prompt asks for about 70% of each limit. Essential and Expert are saved in the columns the site already reads (`summary`, `narrative_text`), so the Essential/Expert switch from Workstream A shows them with no frontend change.
- **New checks**: a headline must be a verdict (at least two words beyond result vocabulary: "P10 from P14" fails); Essential may not contain lap times or notation like "(-0.06s per lap)".
- **Three worked examples** (`narratives/examples.py`: Russell, Gasly, Hadjar, R1), written by hand from the live fact sheets. Each passes the real fact-check against its full sheet, and `tests/test_prompts.py` checks them against their excerpts (that test caught two examples quoting numbers the excerpt didn't show).
- **Leaner sheets for the model** (`prompt_sheet`): no rival stop laps, car numbers, weather on dry days or bookkeeping. The checker still uses the full sheet.
- **Prompt caching** on the system prompt (rules + examples, about 2,000 tokens; Haiku 5.5 caches from 512). Cache reads and writes are now logged per call.
- **Plain-word verdicts**: "His only stop, on lap 10, came just before the Virtual Safety Car on lap 12: unlucky timing…", "…P10 before, P11 after", "his pace held steady … allowing for the fuel he burned". The old "Stop 1 (lap 10)" and "(-0.06s per lap)" forms are gone.
- **Weekend arcs**: the prompt asks for about 65 words. Verified: the arc limit in the code is 95 words (+15% slack), not 170; all 397 stored arcs exceed 109 words and 256 exceed 170, because they were written before the checker existed. The limit is unchanged.

Templates (#40), the fallback for every story: the headline is the lead verdict; Essential gives the cause when it adds to the headline, then the result and the next finding; the analysis states the verdicts Essential didn't use. Sweep over the live data: 1,860 templates, 0 fact-check violations; longest Essential 66 words.

Template review for new-fan readability (1–5), 15 stories across the pilot rounds:

| Story | Score | Note |
|---|---|---|
| R1 R Russell | 4 | Cause then result; "took the lead for good on lap 27, from Hamilton through the pit stops" |
| R12 R Norris | 4 | Same shape; analysis thin (a lap-40 pit battle) |
| R17 Q Verstappen | 3 | A pole-sitter's Essential mentions the Q2 margin, which is jargon here |
| R12 S Piastri | 3 | Correct but thin: result only |
| R17 R Leclerc | 3 | Thin: "started and finished P2" |
| R1 R Gasly | 4 | Result, then the unlucky VSC timing in plain words |
| R12 R Alonso | 3 | Headline is the first lap; Essential doesn't say how he got from P15 to P9 |
| R17 R Hadjar | 4 | Climb from P22, then the stop that cost 2 places |
| R1 Q Gasly | 4 | The 0.280s cut-line miss, named |
| R12 FP1 Lawson | 3 | Practice stories stay thin by nature |
| R1 R Hadjar | 4 | "retired on lap 11 while running P5" |
| R1 R Piastri (DNS) | 4 | Clear |
| R17 R Stroll | 4 | Clear |
| R12 Q Bottas | 4 | Clear |
| R17 S Pérez | 4 | Clear |

Average 3.67 (target 3.5), none below 3. Worst: R17 Q Verstappen — "Max Verstappen qualified on pole. In Q2 Max Verstappen got through by 1.145s over the first car knocked out (Nico Hülkenberg). Teammate Isack Hadjar was P22." The pilot run is what tests the AI stories against the 4.3 gate.

## Round 2: decisions made

| # | Decision | Alternatives | Why | Undo |
|---|---|---|---|---|
| A1 | Home's 4 cards are the 4 rounds *before* the featured latest race | The latest 4 including it | The featured panel already shows round 17; a card would say it twice | `earlier` in `pages/Home.tsx` |
| A2 | The "Data Paddock" wordmark hides below 640px (logo stays, labelled) | Smaller toggle labels; toggle in a menu | The header must fit logo, Races, Standings and "Essential · Expert" at 375px | `hidden sm:inline` in `Brand` (`Shell.tsx`) |
| A3 | Midfield items only fill spare key-moment rows, except to guarantee one driver from beyond the podium | Always add two | In R12 two midfield items pushed Verstappen's lap-1 retirement out | `planSession` in `lib/mentions.ts` |
| A4 | Classification is half the grid at 1024–1279px; "Retired, classified" note from 1280px; no full-name column at 1536px+ | Horizontal scroll | The table overflowed by 16–40px and clipped Pts on desktop | `RaceWeekend.tsx`, `Classification.tsx` |
| A5 | Standings subtitle "After N rounds" replaced by the freshness stamp | Both | Same fact twice | `SeasonPage.tsx` |
| A6 | "updated <date>" is the export time | Last ingestion time | The daily run checks the sources then exports; re-run transforms would otherwise move ingestion times | `site_meta` in `api/main.py` |
| A7 | AI authorship wording: "Stories on this page are written by Claude from the timing data and fact-checked against it" only when a Claude-written story is on the page; otherwise "computed from the timing data"; mixed pages give counts | Keep a global footer line | #37; flagged because it describes AI authorship | `components/PageSources.tsx` |
| A8 | "A red flag / the safety car reshuffled the top five" compares the lap before with the first lap after | Three laps after | My first version credited Antonelli's lap-5 pass in R12 to the lap-2 red flag; the top five were identical on laps 1–4 | `howItWasWon` in `lib/mentions.ts` |
| A9 | More detail's closed row names what's inside ("Tyres, sectors and race control") | Title only | A closed box with no hint hides the tyre chart people used to see | `RaceWeekend.tsx` |

## Round 2: next 3 actions

1. Owner: merge PR #6 (A). Then I push C (data fixes) and B (stories) as their own PRs.
2. Owner: once B is merged, run the pilot (above). I then read the snapshot, score 15 AI stories against the 4.3 gate, and iterate the prompt up to 3 times.
3. After the merges: live crawl, scorecard and persona pass (needs `docs/BENCHMARKS.md` for row-level scoring).

# Round 1 (closed)

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

| Run | Prompt | Stories attempted | Published as Claude | Template fallbacks | Claude calls (session stories) | Notes |
|---|---|---|---|---|---|---|
| Scheduled `full`, 2026-10-19 13:24 UTC (run 39259824231, `main` 35cff79) | v2 (round 1) | 800 cap: 532 session stories, 89 weekend arcs, 179 head-to-heads, rounds 1–5 | 528 of 532 session stories (99.2%), 88 of 89 arcs | 4 session stories, 1 arc | 613 attempts for 532 stories (465 first try, 53 second, 14 third) | `MAX_NEW_STORIES` wasn't set before this run. It also recomputed all 1,815 turn-by-turn breakdowns. Merging round 2 (prompt v3) puts these stories behind the new rules, so they show as templates until rewritten |


No calls from this sandbox. Each workflow run now writes "Claude calls" and "published as fact-sheet templates" to the job summary; they will be copied here.

## Next 3 actions

1. Owner merges the PR. The push-triggered publish-only run upgrades the live database, and the gates (invariants, crawl) must pass before it deploys. Then I run the crawler against the live URL.
2. Owner runs the Site workflow: mode `stories-only`, story_rounds `1,12,17`. Then I download the snapshot, review 15 pilot stories against the §5.2 rubric and iterate on the prompts and fact sheets.
3. The next full run recomputes all turn deltas with the reconciling method (about 70 min of OpenF1 downloads), then the first critic pass.
