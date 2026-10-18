# Data Paddock Review — Round 2

Oct 18, 2026 · @George

The site is now correct and stable, but its main promise is switched off: all 2,291 published stories are fact-sheet templates, and the page is still busier than it needs to be. It scores 65 out of 100 on the benchmark scorecard. It fails the ship gate on one cheap item: no "data through round 17" freshness stamp.

## Scorecard

Scored against the 42-row scorecard in BENCHMARKS.md (§7). Each row is 0, 1 or 2 points, and section A counts double. The ship gate is no zeros in section A. This is the first scored pass, so there is no earlier number to compare against.

| Section | Score | Max | Biggest gap |
| --- | --- | --- | --- |
| A. Trust and accuracy (×2) | 24 | 32 | No freshness stamp (0, fails the gate); footer claims Claude wrote stories that are templates |
| B. First five minutes | 10 | 14 | Chart titles name the metric, not the takeaway; home page is 7,600px tall on a phone |
| C. Depth for data fans | 6 | 16 | No Essential/Expert toggle, no lap drill-down, turn-by-turn withheld, no methods page |
| D. Storytelling | 9 | 12 | Template headlines state results, not verdicts; the Dutch GP summary misses how the race was won |
| E. Sharing and return visits | 6 | 12 | No spoiler-free mode; follow-a-team only on /races; season page has no title |
| F. Craft and engineering | 10 | 14 | No public changelog; no feedback route without GitHub |
| **Total** | **65** | **100** | Ship gate fails on A7 only |

Lighthouse figures come from PROGRESS.md and were not re-measured here.

## Round 1 issues

26 of the 30 are fully fixed. Four are fixed in code but waiting on a pipeline run, or fixed only partly. I re-checked each one myself on a production build of current `main`, with the published database: crawl, data checks and spot reads of the JSON.

| # | Issue | Status | What I saw |
| --- | --- | --- | --- |
| 1 | Blank page on in-app navigation | Fixed | Crawl with a promise-returning `scrollTo` passes; home → R17 → home → R1, no errors |
| 2 | Raw model output in a story | Fixed | No `BAD_FORMAT` or tag leaks anywhere |
| 3 | False facts in stories | Fixed (templates) | Hadjar arc says 243 behind, with rounds 12–14 missed; the AI rewrite is still to come |
| 4 | One team per driver; constructors wrong | Fixed | Red Bull 332, Racing Bulls 100; Lawson tagged "Stand-in" at Zandvoort |
| 5 | VSC logic backwards | Fixed | Gasly: stop just before the VSC called "unlucky timing" |
| 6 | DNS shown as DNF | Fixed | R1 shows 4 DNF and 2 DNS (PIA, HUL) |
| 7 | Qualifying missing drivers | Fixed | R1 qualifying lists 22, with three "No time" |
| 8 | Corner deltas don't add up | Partly | Fix is built, but no turn-by-turn data is exported yet, so the tab is empty |
| 9 | Key moments were routine stops | Fixed | R1 now lists PIA DNS, HAD retirement, VER P20→P6 and all 3 VSCs |
| 10 | "lap None" | Fixed | Forbidden-text check passes |
| 11 | Stationary time missing | Fixed as presentation | The feed doesn't publish it; stories say so once |
| 12 | Lap count off by one | Fixed | R1 chart runs to lap 58 |
| 13 | Classification sort | Fixed | Classified retirements keep their position |
| 14 | Third VSC missing | Fixed | Lap 34 VSC listed |
| 15 | Head-to-heads only for teammates | Fixed | Adjacent finishers and shared stewards' cases added |
| 16 | Two drivers' stories disagree | Fixed (templates) | Gasly and Ocon both cite the lap 23 Turn 3 case |
| 17 | Y-axis stopped at P20 | Fixed | Runs to P22 |
| 18 | Teammates share a line colour | Fixed | Second car dashed |
| 19 | Hover-only hint on phones | Fixed | "Tap a line" below md |
| 20 | Sector labels mixed references | Fixed | "14th of 20 who set a time · to the session best" |
| 21 | "16th of 20" with 22 cars | Fixed | Denominator explained |
| 22 | Unknown compound unlabelled | Fixed | Hatched swatch plus legend entry |
| 23 | One-option year dropdown | Fixed | Hidden |
| 24 | Titles, previews, hash URLs | Partly | Path routes and prerendered titles; /season/2026 still says only "Data Paddock" |
| 25 | Bundle size | Fixed | Home JS 87 KB gzipped; charts lazy-loaded |
| 26 | Repeated card text | Partly | Within a card, yes; across panels, no (see Still wrong) |
| 27 | Bare-adjective event names | Fixed | "Dutch Grand Prix" |
| 28 | No races index | Fixed | /races with sprint filter and follow-a-team |
| 29 | Error reports need GitHub | Waiting on you | The email option needs the `VITE_REPORT_EMAIL` variable |
| 30 | Tall highlight cards on phones | Fixed | Replaced by the 30-second summary |

## Still wrong

The biggest problem is no longer a bug but an absence: the AI stories that set Data Paddock apart aren't on the site. Numbering continues from PROGRESS.md (#31–#35).

| # | Sev | Finding | Evidence |
| --- | --- | --- | --- |
| 36 | P0 | No AI stories are published: all 2,291 are fact-sheet templates | Export log `stories by source: template 2291`; 1,851 were written before the fact-checker existed, and 431 weekend arcs failed the 170-word limit |
| 37 | P1 | The footer says "Stories written by Claude" while every story says "no AI text" | Shell.tsx footer vs StoryMeta on the same page |
| 38 | P1 | The same fact appears up to three times on one page | R1: Verstappen P20→P6 in the summary, Key moments and Beyond the podium; R12: Alonso P18→P9 in all three |
| 39 | P1 | The summary and key moments miss how the race was won | R12 summary leads with Alonso's and Hülkenberg's climbs, not Verstappen's lap-1 retirement or the red flag; key moments show Hamilton leading from lap 22 but never how Norris got the lead back |
| 40 | P1 | Template prose reads like a log | "Stop 1 cost him 1 place", "(-0.06s per lap)", "He ran a compound the feed didn't record for laps 1-10" |
| 41 | P2 | Turn-by-turn tab and corner dots are empty | No breakdowns in the export (the reconciling recompute hasn't run on the live data) |
| 42 | P2 | No "data through round 17, updated \<date>" stamp | Not on any page; fails scorecard row A7 |
| 43 | P2 | /season/2026 page title is only "Data Paddock" | No `useTitle` in SeasonPage.tsx |
| 44 | P2 | Hülkenberg (DNS) has a tyre bar in the R1 strategy chart | Lap-1 stint drawn for a car that never started |
| 45 | P2 | Points column is cut off on a 375px phone | Classification scrolls sideways; Pts lands off-screen |
| 46 | P2 | Pages run long | Home 7,600px on a phone; race page about 3,000px on desktop; 13–23 glossary underlines per race page |
| 47 | P3 | Two lint warnings | `useFetch` effect with no dependency list; CircuitPanel.tsx exports non-components |

## Claude Code's declutter plan

Claude Code's diagnosis is right: Australia shows 7 panels before you pick a driver, and a lot of that is repetition. I keep five items as written, change four, and add three it missed.

| # | Claude Code proposed | Verdict | Do this |
| --- | --- | --- | --- |
| 1 | Fold the tyre chart and deep dive until a driver is picked, or behind "More detail" | Agree | One "More detail" toggle. It opens on its own when a driver is picked, and Expert mode keeps it open |
| 2 | Cut Beyond the podium to 2 cards, or merge it into Key moments | Change | Merge it into Key moments (your call), tagging midfield items "Midfield". At least one non-podium driver must appear, so the mission stays visible |
| 3 | Dedupe facts across the summary, key moments and cards | Agree, extend | One fact, one place: the summary wins, and key moments skip anything it already said. Also fix #39: the summary must say how the race was won (decisive lead change, front-runner DNF, red flag) before it says who climbed |
| 4 | Compact circuit panel until a driver is picked | Agree | An S1 · S2 · S3 strip with a small outline thumbnail; the full map appears once a driver is picked. The outline is the brand, so keep it, just smaller |
| 5 | Glossary underlines for real jargon only, first use per page | Agree | Allow-list: VSC, SC, red flag, DNF, DNS, DSQ, NC, lapped, undercut, overcut, stint, compound, long run, Q1/Q2/Q3, sprint quali, stand-in. Drop Colours, Sector, Retirement, Did not start |
| 6 | Drop most helper labels; keep "Pick up to two drivers" | Agree | Also drop "Tap a line" on phones: picking from the table is the main path |
| 7 | Remove "Terms:" and the per-story source line; show the source once | Change | Remove "Terms:". Show the source once per page, worded from the stories actually on it, and fix the false footer (#37). Keep a per-story badge only when that story differs (edited, or template on an AI page), and keep "Report an error": it carries the story id |
| 8 | Big cards for the latest 3–4 races; older rounds compact | Change | 4 big cards, then "All 17 races →" to /races, which already has the full grid (your call). No second list on home |
| 9 | Hide Stops and Pts below `sm` | Change | Hide Stops and Grid instead and keep Pts. Points are the result fans look for; +/− already shows the grid move |
| — | (missing) | Add | An Essential/Expert toggle (your call): Essential = verdict-first story; Expert = extra data detail, More detail open |
| — | (missing) | Add | A "Data through round 17 · updated 18 Oct" stamp on home, race and standings pages |
| — | (missing) | Add | Chart titles that state the takeaway ("Russell led from lap 27", not "Positions by lap") |

The "Done when" list holds, with one addition: the before/after screenshots must include a 375px race page with a driver picked, because that's where the toggle and the hidden columns meet.

## Your decisions

These five calls are yours. The long-run prompt treats them as fixed requirements.

| Decision | You chose | Other options | What it means for the build |
| --- | --- | --- | --- |
| Story model | Haiku 5.5 | Sonnet 5.5 (my pick), Fable 5.1, templates only | Cheapest. The prompt makes Haiku succeed with tighter fact sheets, a target 30% under each word limit, and a report if the pass rate is low |
| Race page before a driver is picked | Story first | Claude Code's plan, keep as is | Summary + classification + key moments + positions; everything else behind More detail; Beyond the podium merged into Key moments |
| Home page older results | 4 cards + link to /races | 4 cards + compact list, smaller cards | Home loses 13 cards; /races stays the full grid |
| Order of work | Both in parallel | Declutter first, stories first | Declutter PR now; you trigger the pilot story run (`stories-only`, rounds 1,12,17) in Actions meanwhile |
| Story voice | Verdict first, a bit more data, maybe behind an Expert toggle | Broadcaster recap, bullet briefing | Essential: verdict headline, cause → effect, 2–3 numbers. Expert: the same story plus key numbers, sector ranks and stint pace inline |

## Five perspectives

The site went from broken to trustworthy. It isn't yet a place you'd go to be told a story.

| Perspective | Round 1 | Now | Verdict |
| --- | --- | --- | --- |
| New fan | 4 | 6 | Nothing crashes, and the 30-second summary is the best thing on the site. Then come seven panels and 19 dotted underlines, and the story reads like a spreadsheet said aloud |
| Data-curious fan | 6 | 7 | The numbers finally agree with each other. Turn-by-turn, the feature that taught you most, is empty, and there's no way to drill from a lap into its sectors |
| Diehard | 3 | 6 | Stand-ins, DNS, classified retirements and VSC timing are right, and that earns trust. But Zandvoort's summary talks about Alonso's climb, not Verstappen's lap-1 exit or how Norris won it back |
| Website critic | 5 | 7 | Path URLs, page titles, error boundaries and an 87 KB home bundle are pro work. It loses points for density, repetition, a footer that contradicts the stories, and a 7,600px phone home page |
| Data engineer | 3 | 8 | 204 invariants, a fact-checker, an entries table and a DB snapshot are what this needed. Remaining risk: stories depend on a CI-only federation rule, and nothing measures story quality once Haiku writes them |

Round 1 scores come from the first review. For the web critic and data engineer, they are the averages of that review's sub-scores.

## Method and sources

The browser on your computer was offline, and this workspace can't reach github.io. So I rebuilt the site the way the Checks workflow does: cloned `main` at 35cff79 (PR #5 merged), restored the published `db-snapshot` database, upgraded it with no ingest and no Claude calls, then built, exported and prerendered.

- Unit tests: 44 passed. Data invariants: 204 passed, 3 skipped (two need Jolpica, which was unreachable; one because no turn breakdowns are exported).
- Playwright crawl (`e2e/crawl.spec.ts`): 16 of 16 passed, desktop and 375px.
- My own pass: screenshots at 1360px and 375px of home, /race/1, /race/1/driver/gasly, R12, R17, standings and /races; panel, underline and helper-label counts; an in-app navigation run with a promise-returning `scrollTo`; spot reads of the exported story, moment and standings JSON.
- Live-site behaviour should match, because CI builds from the same snapshot. Recheck on the live URL once your browser is back.

Sources: [Data Paddock repo](https://github.com/GBVParrilla/data-paddock) · [live site](https://gbvparrilla.github.io/data-paddock/) · REVIEW.md and BENCHMARKS.md (round 1) · PROGRESS.md on `main`.
