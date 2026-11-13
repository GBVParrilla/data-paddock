# Data Paddock audit, 13 November 2026

Audit only: no code, data, tests or workflows were changed, no stories were generated and no workflow was triggered. The only additions are this file and `docs/audit-screenshots/`.

**What was audited.** Two things, and they differ:

- **The live site** (`gbvparrilla.github.io/data-paddock`) is `main` at `ad9a96a` (PR #14) with data through round 19, generated 2 Nov.
- **The local build** is this branch (`claude/laughing-clarke-t71435`, head `6baeca0`, which is `main` plus the still-open PR #15) on the latest `db-snapshot`, which holds data through round 20. Every screenshot and number below comes from this build unless it says "live".

## 1. Summary

The engineering is solid and the site is calm and readable, but it has stopped publishing and its newest rounds are its weakest. The Site workflow has failed every day since 3 Nov because the official Mexico City result changed after ingest and the pipeline never re-fetches a finished session; the live site is frozen at 2 Nov, Brazil is not published, and in the local build Brazil's qualifying page shows "No time" for all 22 drivers. Rounds 18 to 20 (three of the four rounds the home page shows large) have no Claude stories at all, only two-sentence templates. The Circuit atlas tokens are in place (paper, ink, Archivo, hairlines, the sheet), but the atlas idea itself, a circuit with the story drawn onto it, is not: the sheet is a large outline with numbered dots and a half-empty margin, and everything below it is a standard table-and-line-chart dashboard in 12 to 13px grey.

### The five changes that would matter most

1. **Re-fetch results and qualifying for recent rounds, and repair rounds 19 and 20.** This unblocks publishing and fixes 11 wrong race positions, 7 wrong championship totals and a qualifying page with no times (issues 1 to 3).
2. **Write the stories for rounds 18 to 20 and make new rounds get stories automatically.** 327 session stories, 84 weekend arcs and all 34 season arcs are templates today (issue 4).
3. **Make one number mean one thing.** The Expert finding and the table beside it rank the same long run on two different rules in 177 of 193 cases; a caption calls "3rd of 3" stronger; a driver who qualified P4 is described as having set no time (issues 5 to 8).
4. **Build the signature the atlas promised: plan and section.** The circuit as the plan, a lap ruler under it as the section, and every key moment written on one or the other as a callout. Give the sheet its own paper, and fix the type scale (section 4).
5. **Give the home page a story.** It currently has one sentence of prose. Lead with the latest race's verdict as a headline and three driver headlines to read (section 4).

### Scorecard (BENCHMARKS.md section 7): 62 / 100

The last self-score was 85. The drop is almost all section A, and almost all of that is stale data: fix issues 1 to 3 and A returns to about 26.

| Section | Score | Max | Rows (0, 1 or 2) and why |
| --- | --- | --- | --- |
| A. Trust and accuracy (×2) | 16 | 32 | A1 **0** round 19 classification wrong for 11 drivers. A2 **0** 7 constructors' totals differ from official. A3 **1** long-run ranks contradict in 177 debriefs. A4 **1** stand-in and DNS explained; Brazil grid drops (Leclerc qualified P4, started P14) are not. A5 **1** nothing rendered, but `n/as ahead of George Russell` is in the exported summary and "Midfield q3" is on a page. A6 **1** 5 factual slips in 28 stories read. A7 **2**. A8 **2** |
| B. First five minutes | 10 | 14 | B9 2, B10 2 (crawl 32/32), B11 2, B12 **1** ("overcut", "undercut" in story text are not glossary terms), B13 **1** (Hard tyre legend and bars invisible), B14 **1** (chart title stays "Russell led from lap 27" with Gasly selected), B15 **1** (on a phone a driver's story starts about 1,250px down) |
| C. Depth | 10 | 16 | C16 **1** (27% of race debriefs have no stint table), C17 1 (no table under Title fight or tyre strategy), C18 1, C19 1, C20 1, C21 2, C22 1 (ranks sound; reference lap suspect in 10 sessions), C23 2 |
| D. Storytelling | 6 | 12 | All six rows 1: headlines that misread a gain (9), stock phrases, false causes, rounds 18 to 20 templates, head-to-heads still read times aloud, routine pit stops among key moments |
| E. Sharing and return | 10 | 12 | E30 2, E31 2, E32 1 (preview image per driver, no share action), E33 2, E34 1 (all season arcs are templates), E35 2 |
| F. Craft | 10 | 14 | F36 **1, not re-measured this run**, F37 1, F38 2, F39 2, F40 0, F41 2, F42 2 |

Ship gate (no zero in A): **fails** on A1 and A2. That matches reality: the deploy gate has been refusing to publish for ten days.

### Checks run

| Check | Result |
| --- | --- |
| Unit tests (`make test`) | 78 passed |
| Lint and types (`make lint`) | clean (oxlint, check-effects 49 files, check-design 50 files, `tsc -b`) |
| Build, export, prerender | ok; 464 page shells, 460 preview images |
| Data invariants | **273 passed, 2 failed**: `test_constructor_points_match_official_standings`, `test_driver_points_match_official_standings` |
| Playwright crawl, desktop and mobile | 32 passed |
| Live URL | reachable; `data/meta.json` says `last_round: 19`, `generated_at: 2026-11-02` |
| Site workflow (read only) | runs 41 to 50 (3 to 12 Nov) all failed at the "Data invariants" step; last success run 40 on 2 Nov |

Local build notes: the sandbox Python is 3.13 (CI uses 3.12) and Chromium came from `PW_CHROMIUM_PATH`; neither changed a result.

### Earlier findings, re-checked

| # | Finding | Status now | Evidence from this run |
| --- | --- | --- | --- |
| 36 | No AI stories live | **Regressed for new rounds** | Rounds 1 to 17: 1,840 Claude, 20 template. Rounds 18, 19, 20: 0 Claude, 327 template |
| 48, 49 | Corner alignment; meaning of purple | Fixed | 1,522 corner groups: rank order follows delta order in all but 18 (ties); exactly one purple per corner (invariant passes) |
| 50 | Ambiguous driver selection | Fixed | Crawl "one driver per tap" passes; vs strip seen in `r01-compare-1360-light.jpg` |
| 51 | Expert same as Essential | Fixed in form, **hollow in places** | 154 of 572 race and sprint debriefs have no stint rows; 281 debriefs have one finding, 32 have none (`r12-driver-expert-1360-dark.jpg`) |
| 52 | Factual slips | Named slips fixed, new ones found | Verstappen R17 Q now says "middle sector ranked 6th". New slips in section 3 |
| 53 | Repeated headline shapes | Fixed for Claude stories, **not for templates** | Most common Claude shape appears 7 times in 1,840. Round 18 qualifying: 12 of 22 are "X missed the QN cut by Ns" |
| 54 | Missing-data talk | Fixed | 0 matches across 2,187 summaries |
| 55 | "1st of 1", decimal points | **Partly** | Gone from stories. "stronger on long runs: 1st of 1" is still in 45 midfield spotlights; `Points: 25.0` is in 52 `key_numbers` (not rendered) |
| 56 | Lap-1 retirement, no reason | Fixed | Verstappen R12: "The race was then red-flagged on lap 2" |
| 57, 58 | Home repeats name; DNS repeats itself | Fixed | `home-1360-light.jpg`; Piastri R1 DNS has no long text |
| 59 | Generic look | **Partly** | Tokens done; composition not. Section 4 |
| 60 | "Standing in" banned | Fixed | Lawson R12 FP1: "standing in for Red Bull Racing" |
| 61 | Driver page performance | Not re-measured | |
| 62 | Driver link opens below the fold | Fixed on desktop, **still far on phone** | Story heading at about 1,250px at 375px (`r01-driver-essential-375-light.jpg`) |
| 63, 64 | Duplicate midfield rows; cryptic margin notes | Fixed on this branch only | PR #15 is still open, so not live |
| 65 | Head-to-heads read times aloud | **Open** | All 715 are the old text: "ranking 7 of 20 in sector 1 at 29.042, 1 of 20 in sector 2 at 17.380…" |

## 2. Issues to fix

P0 breaks trust or the product, P1 is wrong or misleading, P2 is polish. Screenshot paths are under `docs/audit-screenshots/`.

| # | Sev | What is wrong | Where | Evidence | Fix | Proof |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | P0 | **The site has not published since 2 Nov.** A finished session is never re-fetched, so when the official Mexico City result changed the standings invariants began failing and every deploy has been refused. Brazil (8 Nov) is not live | `f1tracker/ingest/season.py:93` ("already ingested - skipping"); Site workflow step "Data invariants" | Runs 41 to 50 failed at that step. Live `meta.json`: `last_round 19`, `2026-11-02` | Re-fetch Jolpica results, sprint and qualifying for every session of the last 3 completed rounds on each run; compare a hash; when it changes, update rows, rerun transforms and mark that round's stories stale. Also send a failure notice (the workflow fails silently today) | Unit test: change a stored result, run ingest, row is corrected and stories flagged. Existing standings invariants pass |
| 2 | P0 | **Round 19 race classification is out of date for 11 drivers**, so 7 drivers' and 7 constructors' championship totals are wrong, and their stories describe results that no longer stand | Session 95; `/race/19`, `/season/2026` | Ours vs official: Piastri P7, 6 pts vs P13, 0. Colapinto P8 vs P15. Gasly P10 vs P17. Lawson P9 vs P7. Bortoleto P11 vs P8. Hadjar P12 vs P9. Hirakawa P13 vs P10, 1 pt. Piastri's story: "started P12 and finished P7, scoring 6 points" | Falls out of #1. Then rewrite round 19 race stories and arcs (owner decision 3) | New invariant: every race and sprint classification equals Jolpica's (position, points, status) for all rounds, not only the standings totals |
| 3 | P0 | **Brazil qualifying has no times.** All 22 rows read "No time", the title block says "Set no time 22", and the race's key moments say Verstappen, Hamilton and Leclerc "set no time in qualifying". Official times exist (Norris 1:27.470) | Session 99; `f1tracker/analysis/pivotal.py:177`; exported summary in `sessions/99/headline.json` | `r20-qualifying-1360-light.jpg`. Summary string: "Lando Norris took pole for qualifying at the Brazilian Grand Prix, n/as ahead of George Russell." 16 rows have a position and `status_code: NO_TIME` | Falls out of #1. Also: never export a qualifying session where the pole-sitter has no time; say "times not yet published" instead; `pivotal.py` must use "set no time" only when the driver has no position-earning lap, not when times are missing | Invariant: in a completed qualifying session P1 has a Q3 (or SQ3) time; no exported string contains `n/a` |
| 4 | P0 | **The newest three rounds have no Claude stories.** Race stories are two sentences; weekend arcs and all 34 season arcs are templates. These are the rounds the home page leads with | Rounds 18, 19, 20; `seasons/2026/arc/*` | Camara R20: "Rafael Camara started P11 and finished P20, 2 laps down, scoring no points. Teammate Oliver Bearman finished P17." Season arcs: 34 of 34 `source: template`, 32 at `through_round: 17` | Owner runs stories for rounds 18 to 20 (after #1 to #3 and #9). Then let the daily run write stories for newly ingested rounds with a small cap | Invariant: for every round older than 3 days, at least 90% of session stories have `source: claude` |
| 5 | P1 | **Two ranks for the same long run, six lines apart.** The finding (and the story) ranks among drivers with 8 or more laps; the table ranks among 5 or more | `f1tracker/narratives/facts.py:46, 448` vs `f1tracker/narratives/debrief.py:33, 179`; practice Expert panel | 177 of 193 findings disagree with their table. Hülkenberg R1 FP2: finding "Medium long run 1st of 3", table "3rd of 7", headline "Medium long-run pace stood out" | One constant, one function, used by facts, debrief, midfield and arcs. Recommend 5 laps and a field of at least 5 | Invariant: every "long run Nth of M" finding equals the table row for that tyre |
| 6 | P1 | **Last place described as "stronger".** The practice caption picks a driver who was last of the long-run field | `f1tracker/analysis/midfield.py:136`; practice sheet caption and key moments | Singapore FP1 caption: "Franco Colapinto was P19 on a single lap but stronger on long runs: 3rd of 3 on hard". 45 spotlights say "1st of 1" | Only emit when the long-run rank, as a share of its field, beats the single-lap rank, and the field is at least 5 | Invariant on `midfield-spotlight.json`: no "N of M" with M under 5; long-run percentile better than single-lap percentile |
| 7 | P1 | **One driver stored as two.** Rafael Câmara's timing data is on driver 39 (`rafael_c_mara`), his results on driver 40 (`rafael_camara`, no code). His race page shows 0 stops, no sectors, no practice, a blank code in the qualifying table. A placeholder "Driver #236" owns 2 pit stops | `f1tracker/ingest/drivers.py:107` (`slugify` drops the accented letter); `drivers.json` | `r20-driver-essential-1360-light.jpg`: "Stops 0 vs 3", "Sector 1: No time", FP1 to FP3 "–". DB: laps 166 rows on id 39, 0 on id 40 | Transliterate before slugifying (NFKD, strip marks); match OpenF1 to Jolpica by car number within the event first; merge 39 into 40; resolve or drop #236 | Invariant: no driver without a code; no two drivers share a car number in one event; no `driver_` refs exported |
| 8 | P1 | **Hard tyres are invisible in the light theme.** White on near-white paper | `frontend/src/index.css:42` (`--hard: #FFFFFF` on `--paper: #EEF2F3`, contrast 1.13:1) | `r01-driver-essential-1360-light.jpg`, tyre strategy: hard stints look like empty rows; the "Hard" legend dot cannot be seen | Draw Hard as paper fill with a 1.5px ink outline (legend dot the same). Put the compound letter on every bar, not only the selected driver's | `check-design.mjs`: every data colour has at least 3:1 against paper in both themes |
| 9 | P1 | **Expert is nearly empty for whole races.** When the feed's tyre and pit records disagree, the stint table is dropped for that car, and in 7 races that is every car | `f1tracker/narratives/debrief.py` (stint reconciliation); rounds 2, 6, 12, 13, 16, 17, 19 | 154 of 572 race and sprint debriefs. Alonso R12 (P18 to P9): one finding, "Lap 1: P18 to P15", an empty stints table and dashes (`r12-driver-expert-1360-dark.jpg`) | Rebuild stints from pit-stop laps when the tyre records disagree (laps and pace are still known; show the compound as unknown). Never render a table with headers and no rows. Add findings that need no tyre data: places made on track vs in the pits, pace vs teammate over the same laps | Invariant: every classified finisher has at least one stint row with a pace, and at least 2 findings |
| 10 | P1 | **Headlines that misread a good result.** A stop that cost one place becomes the headline for a driver who gained places and scored | Claude race stories; `narratives/variety.py`, `factcheck.py` | 9 found. "Unlucky stop timing on lap 10 took Gasly a place" (P14 to P10, 1 point). "A lap-46 stop just before the Safety Car was unlucky" (Pérez, +6 places) | Compute the outcome frame in code (gained, lost, held; points or not) and pass it as the required angle. Checker: if net places are +3 or better, or points came from outside the top-10 grid slots, the headline's main verb cannot be a loss verb unless the outcome is also in it | Unit tests with these 9; invariant over the export |
| 11 | P1 | **Routine pit stops and wrong labels among key moments.** Brazil lists two pit-cycle losses and a slow stop; qualifying files Verstappen under "Midfield"; a raw type name reaches the page | `f1tracker/analysis/pivotal.py`; `frontend/src/lib/sheet.ts:33`; `/race/12?session=59` | 19 `pit_cycle` and 18 `slow_stop` moments site-wide. "Midfield q3 (Lindblad)" in `r12-qualifying-1360-light.jpg`. "Midfield: Max Verstappen qualified P7" | Keep a pit moment only if it changed the podium or the lead. Midfield excludes the top 4 teams in the standings at that round. Map every `moment_type` to a reader's label, with a test that no label contains an underscore or a lowercase "q3" | Unit test on the label map; invariant: no midfield moment for a top-4 team driver |
| 12 | P1 | **"He made 17 places on track" for an 11-place climb.** The recovery note adds places lost in the pits back without saying so | `f1tracker/analysis/pivotal.py` (recovery) | Brazil: "Lewis Hamilton climbed from P20 to P9 … He made 17 places on track, away from the pit stops." Leclerc: P14 to P8, "14 places on track" | Say both halves: "passed 17 cars on track and lost 6 places in the pits", or drop the second sentence | Invariant: on-track places minus pit-cycle places equals net places in the same sentence |
| 13 | P1 | **On a phone the driver's story is a long scroll down.** The full sheet, legend, sectors and title block come first | `frontend/src/pages/RaceWeekend.tsx` (story slot), `RaceSheet.tsx` | Headline at about 1,250px at 375px wide (`r01-driver-essential-375-light.jpg`) | Under 640px with a driver selected, collapse the sheet to a 148px strip (thumbnail, race name, one-line result) with "Show the sheet" | Crawl: at 375px a driver link has the story headline within the first 700px |
| 14 | P2 | The positions chart keeps the race's title when a driver is picked | `frontend/src/lib/takeaways.ts:31` | "Russell led from lap 27" above a chart highlighting Gasly | With a driver selected: "Gasly: P14 on the grid, P9 after lap 1, P10 at the flag" | Crawl assertion |
| 15 | P2 | Corner deltas look odd against the reference in 10 sessions: the median driver is 400ms or more off in one corner and the opposite way in the next. Ranks are unaffected | `f1tracker/analysis/turns.py` (`_reference`); sessions 8, 15, 16, 20, 42, 43, 45, 60, 71, 95 | Alonso R12 race: T4 +0.353s yet 5th of 20; T5 −0.077s yet 16th of 20 | Show each delta against the field median, or reject a reference whose corner times sit outside the field's range in adjacent corners | Invariant: field median delta per corner within ±250ms |
| 16 | P2 | Hungary has two corners numbered 1 and two numbered 12 | `track-outline.json`, event 11 | Corner list `1, 1, 2 … 12, 12, 13, 14` | Keep MultiViewer's letter suffix (1A, 1B) or number by distance | Invariant: corner labels unique per circuit |
| 17 | P2 | Two key-number labels for one thing, and bare numbers | Claude `key_numbers` | "Stops" vs "Pit stops"; "Piastri's finish: 6"; `Points: 25.0` in JSON | Compute key numbers in code from the fact sheet; the model no longer writes them | Invariant: labels come from a fixed list |
| 18 | P2 | "Neutralised: never" on a wet race with inter-to-slick changes; "Set no time: 0" as a title-block row | `RaceSheet.tsx` title block | `r20-driver-essential-1360-light.jpg`, `r12-qualifying-1360-light.jpg` | Drop rows whose value is zero or never; add "Conditions: wet start" when intermediates were used on lap 1 | Crawl assertion |
| 19 | P2 | Twenty or more controls under 32px tall on a race page at 375px | Session tabs, "The numbers", lap select, classification rows | Counted 20 to 27 per race page | 44px minimum hit area on phones | Crawl: no interactive element under 40px tall at 375px |
| 20 | P2 | No feedback route without GitHub (scorecard F40) | Footer | Not present | A mailto link or a form link in the footer | Crawl assertion |

## 3. Stories

**Sample.** 28 stories read in full against their exported data: 7 front-runners, 13 midfield, 8 back of grid, DNF or DNS, across 15 race, 3 sprint, 6 qualifying or sprint qualifying and 4 practice stories, from rounds 1, 6, 9, 10, 12, 14, 17, 19 and 20. Pattern counts are over all 2,187 exported session stories.

**What is good.** No missing-data talk, no leftover text, no decimals, no em dashes; median 63 words; stand-in claims are right; the lap-1 retirement reads properly. The best stories explain a result in one line: "Ocon held off Alonso's undercut and climbed to P9", "Slowest in sectors 1 and 3 ended Alonso's session in SQ1" (true: 22nd, 21st, 22nd).

**Factual slips (5 in 28).**

| Story | Slip |
| --- | --- |
| R1 FP2 Hülkenberg | "His medium long run was the real standout, ranking first": first of 3 on one rule, third of 7 on the other (issue 5) |
| R10 FP3 Bortoleto | "ran five practice sessions on soft tyres": it was 5 runs in one session. Also "He was also one deletion for track limits" (broken sentence) and "His best sector was the middle one, where he ranked 10th" when sector 3 was also 10th |
| R9 sprint Leclerc | Headline "One medium stint left Leclerc a place down at P5": every car runs one stint in a sprint; he lost three places on lap 1 and recovered two |
| R19 race Piastri | "finished P7, scoring 6 points": officially P13, no points (issue 2) |
| R1 race Bottas | Headline "Bottas retired on lap 16 after a slow pit stop": the stop was on lap 11; nothing in the data links the two |

**Headlines that misread the result.** 9 race or sprint headlines lead with a loss for a driver who gained 3 or more places (issue 10). Gasly at Australia is the clearest: P14 to P10 and a point, headlined as an unlucky stop that "took Gasly a place".

**The biggest moment missed.**

- Hadjar R1: retired on lap 11 from P5; a Virtual Safety Car ran on laps 12 to 14. The story says "the Virtual Safety Cars came only after he had left it" and never asks whether his car caused it.
- Lawson R12 FP1: the table has his hard long run 1st of 8. The headline is "Stand-in Lawson's best lap came on the soft tyres", which is true of nearly every driver in every practice session.
- Alonso R12: the key moment credits him with 12 places made on track; the story spends its one detail on a stop that cost a place.

**Repetition.**

| Phrase | Stories (of 1,840 by Claude) |
| --- | --- |
| "…cost him a place once the cars around him had stopped too" | 124 |
| "on the lead lap" | 121 |
| "held steady" / "faded" (pace) | 97 / 97 |
| "cheap" (stop) | 189 |
| "never pitted" for an early retirement | 27 |
| "made no pit stops" in a sprint | 23 |
| Qualifying openings: "was knocked out" 88, "got through Q1" 54, "reached Q3 and" 45 | 187 of 369 |

Qualifying is the flattest genre: nearly every story is cut margin, last car through, teammate. Nothing says where on the lap the time went.

**Filler and tautology.** "He retired on lap 16, so his race ended before the flag." "…his race ended on lap 11, so he did not finish." "He scored no points." "…and the winner was Lando Norris." "Sainz's Q2 time was not enough to reach the final round." (after saying he went out in Q2). "All his running was on soft tyres, in separate runs." "Its ranking came from laps on medium tyres, not from his single fastest lap."

**Sentences about missing data.** None in Essential. In Expert the notes are worded once and clearly; the problem there is volume (issue 9).

**Rounds 18 to 20.** Templates are accurate and empty. Shared shapes are back: 12 of 22 in round 18 qualifying, 11 of 22 in round 20 qualifying ("X out-qualified teammate Y").

### Changes to make

**Fact sheets** (`narratives/facts.py`, `inputs.py`)

1. **Outcome frame, computed.** `frame: {net_places, points, from_outside_top10, result_class}` and a one-line `angle` the headline must agree with (issue 10).
2. **Lead fact chosen in code.** Rank candidates by how much of the result they explain: places made on track, lap-1 change, pit-cycle net, safety-car timing, pace vs teammate. Pass the top one as `lead` and at most two as `support`. A stop that moved one place can never be `lead` when net places are ±3 or more.
3. **Cause links, only when the data supports them.** A retirement followed within two laps by a VSC, Safety Car or red flag gets `followed_by`; if a race-control message names the car, `caused: true`. A candidate carries `cause_supported: true|false`; unsupported ones may be stated as sequence ("then"), never as cause ("after", "left", "pushed").
4. **Drop non-events before the prompt.** No "no stops" or "one stint" fact in a sprint. No pit or VSC facts for a car that retired before its first stop. No "best lap on softs" in practice unless the driver's best came on a harder tyre than the session's fastest.
5. **Qualifying: where the time went.** Sector deltas to the last car through, the run-to-run improvement, whether the final run improved, and the teammate gap by segment. That gives "Bearman lost 0.2s of his 0.274s in the final sector" instead of the 88th "was knocked out".
6. **One long-run rule** (issue 5), field of at least 5.
7. **Places sentence that adds up** (issue 12).
8. **Key numbers computed in code** (issue 17).

**Prompt** (`narratives/prompts.py`)

1. The headline must restate or sharpen `angle`; give two right and two wrong examples from the list above (Gasly, Leclerc sprint).
2. Three or four sentences, each carrying a fact not already in the headline. A sentence that restates the result class ("so he did not finish") is an error.
3. Give the pit-cycle fact as numbers (P10 before, P11 after) with three phrasings to choose from, and tell the model not to reuse the sheet's wording.
4. "Runs" are within a session; "sessions" are FP1, FP2, FP3. Say it explicitly.

**Checker** (`narratives/factcheck.py`)

1. Loss-verb headline against a positive frame (issue 10).
2. Causal connectives ("after", "left", "pushed", "ended", "cost") between two facts with `cause_supported: false`.
3. Tautology list: "so he did not finish", "so his race ended", "scored no points" after a DNF, "the winner was", "was not enough to reach".
4. A number next to "sessions" must equal the count of sessions, next to "runs" the count of runs.
5. Copy check: reject 8 or more consecutive words taken from a fact-sheet candidate.
6. Session-level phrase budget: the same 6-word phrase in more than 3 stories of a session is a retry for the later ones.
7. Keep style rules write-time only (decision H8); 1 to 4 are fact rules and should also run at export.

**A note on the model, once.** The remaining weakness is judgement about which fact is the story. Changes 1 to 3 to the fact sheet move that judgement into code, which is the right response under the Haiku decision. If headlines still misread results after that, the model is the limit.

## 4. Front end and look

### Where it stands against the Circuit atlas

The tokens landed and they are good: `#EEF2F3` paper, `#17222C` ink, Archivo at three widths, zero radius, hairlines, sentence case, no near-black, a clean dark slate. `check-design.mjs` passes. Standings is the best page on the site (`standings-1360-light.jpg`).

The idea did not land. The plan said "the circuit drawn large, the story annotated onto it". What a visitor sees on `r01-race-1360-light.jpg`:

1. **The sheet is a big outline, not a drawing.** One uniform 6px line, fourteen numbered circles, a start tick. No sector boundaries, no corner names, no direction of travel, no lap length, no scale. It is the thumbnail enlarged.
2. **Nothing is written on it.** Moments 4 and 5 are black dots on the track with no words. The rest are a list of 12px grey fragments in the left column: "Lap 12, VSC", "Recovery (Verstappen)". The reader has to match numbers across to a second list 400px lower to learn what any of them mean.
3. **Half the sheet is empty.** Below the five margin lines there is about 300px of dot grid on the left and a gap between the caption and the title block. On qualifying and practice (`r12-qualifying-1360-light.jpg`, `r17-practice-1360-light.jpg`) the sheet holds two or three lines of text and 700px of height.
4. **Sheet, page and panels are the same colour.** `--bg`, `--panel` and `--paper` are all `#EEF2F3`. The sheet is marked only by a hairline and four corner brackets, so it does not read as an object.
5. **Below the sheet it is a generic dashboard.** A table beside a list, a default line chart with 22 pastel lines and a beige band, a native `<select>`, a `<details>` called "The numbers", tabs. This is the part that reads as generated.
6. **The type has no scale.** Measured on a driver page: eleven sizes between 12 and 17px (12, 12.5, 13, 13.5, 14, 14.5, 15, 15.5, 16, 17), almost all weight 400 in graphite. After the race name there is no second level. The story a reader came for is 15.5px; its headline is 24px; the weekend arc above it is 12.5px grey.
7. **A driver's map is mustard.** "Middle half" is `#C99A06`, and most sectors of most drivers are middle half, so the selected-driver view is a dark yellow track (`r01-driver-essential-1360-light.jpg`). It reads as a warning, and it is the largest area of colour on the page while meaning "nothing notable".
8. **Home has no story.** One 440px outline in the winner's team colour, three driver codes, one midfield sentence. A site whose pitch is "a story for every driver" opens with no headline about the race (`home-1360-light.jpg`).
9. **Team colour is used as decoration.** Circuit outlines on home and `/races` are stroked in the winner's team colour. Twenty orange and teal squiggles on grey cards is the most template-like view on the site, and it spends the one saturated colour on something that is not a driver's line.

### The signature: plan and section

An engineer's sheet shows the same object twice: from above (plan) and along its length (section). A race has both. The circuit is the plan. The race distance, lap 1 to lap 58, is the section. Every key moment belongs on one of them: on the plan when the data says where (a corner named by race control), on the section when it only says when (a lap).

Put a **lap ruler** along the bottom of every race sheet: a 56px band, one tick per lap, labelled every 10, with Safety Car and VSC periods as hatched blocks, the leader's team colour as a 4px strip along the top edge (so lead changes are visible as colour changes), and each key moment as a numbered flag standing on its lap with its sentence written beside it. That one element replaces the left-column list, the "Neutralised" row, and most of the Key moments panel, and nobody else in this space draws a race that way. Shrunk to 640 by 80 it is also the share card and the home page's summary of a race.

```
┌ sheet (lighter paper on a darker desk) ─────────────────────────────────────────┐
│ Australian Grand Prix                                        S2 ┼ T8             │
│ Albert Park, 8 March, 58 laps                       T6 ╭───────╮                │
│                                                       ╱         ╲    T9–10      │
│ Russell won from pole after                          │           ╰──╮  ╭──── T11│
│ taking the lead back on lap 27.                  T3 ─╯  ②●          ╰──╯      │ │
│                                                   ╰─ T1 ──── ▸ ──┼S/F── T14 ───╯ │
│ ② Lap 11. Hadjar stops at T3 from P5.             S1 ┼                  S3 ┼    │
│   (leader line to the dot)                        5.278 km  ─────── 500 m       │
│                                                                                  │
│ ▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂  leader (team colour) │
│ ①        ②③▨▨▨  ④ ⑤▨▨▨        ⑥              ⑦▨                                │
│ ┬─────────┬─────────┬─────────┬─────────┬─────────┬────────┬                    │
│ 1         10        20        30        40        50       58                   │
│ ① DNS Piastri  ③ VSC, 4 cars pit  ⑥ Russell takes the lead through the stops   │
│                                                    ┌ Round 1 │ 8 Mar │ 58 laps ┐ │
│                                                    └ Winner Russell │ 4 DNF ───┘ │
└──────────────────────────────────────────────────────────────────────────────────┘
```

On qualifying the section is the three segments (Q1, Q2, Q3 with the cut lines and who fell at each); on practice it is the session clock with red flags. The sheet is then never half empty.

### Tokens: exact values

**Paper.** Two tones, so the sheet is an object.

| Token | Light | Dark | Use |
| --- | --- | --- | --- |
| `--desk` (page) | `#E4EAEC` | `#141B21` | Page background |
| `--paper` (sheet, panels with content) | `#F6F8F8` | `#1C262E` | The sheet, the driver panel |
| `--ink` | `#17222C` | `#E4EAEE` | Text, track |
| `--graphite` | `#56636E` | `#93A1AC` | Secondary text, leader lines |
| `--rule` | `#C5CFD5` | `#33414C` | Hairlines |
| `--rule-strong` | `#17222C` | `#E4EAEE` | Sheet border, 1.5px |

**Timing.** Keep purple `#8344E0` and green `#1F9D55`. Change the other two tiers so colour means news:

- Middle half: ink at full weight (the plain track line). No yellow on the map.
- Bottom quarter: graphite, drawn at half the stroke width and dashed `2 5`.
- Keep `#C99A06` only for flags and VSC marks on the lap ruler.

This needs your OK because the round 3 palette named yellow as a timing tier (decision 5 below).

**Tyres.** Soft `#DA291C` solid, Medium `#E8B004` solid, Hard paper fill with a 1.5px ink outline, Intermediate `#2F9E44`, Wet `#2066C8`, Unknown a 45° graphite hatch. A letter on every bar.

**Type.** One family (Archivo), six sizes, nothing in between.

| Role | Size / line | Weight | Width | Notes |
| --- | --- | --- | --- | --- |
| Display (race name, leader) | 56/56 desktop, 34/36 phone | 800 | 125 | letter-spacing −0.01em |
| Headline (story verdict, sheet caption) | 28/32 desktop, 22/26 phone | 700 | 112 | max 24ch per line |
| Section heading | 20/26 | 700 | 100 | |
| Story body | 17/27 | 400 | 100 | max 62ch, ink not graphite |
| UI and table text | 14/20 | 500 | 100 | names in ink, 600 |
| Figures and notes | 13/18 | 500 | 75 | tabular; the smallest size on the site |

Graphite is for labels and notes only. Any sentence a reader is meant to read is ink.

**Spacing.** 8px base. Between sections 64px desktop, 40px phone. Sheet inner margin 32px desktop, 16px phone. Table rows 40px (44px on phones).

**Lines.** Sheet border 1.5px ink with the registration marks outside it; hairlines 1px rule; leader lines 1px graphite ending in a 3px dot. Track 5px ink, round joins. Sector boundary ticks 14px, labelled S1, S2, S3 in 13px width 75. A direction arrow on the main straight. A scale bar and the lap length under the plan.

### Page by page

**Race page**

- Build the plan and section sheet above. Remove the left-column moment list, the legend when no corner data is shown, and the "Data through round N" line inside the sheet (it is in the header of every page already; if it stays, it goes in the title block).
- Key moments below the sheet shrinks to the two or three that need a second sentence; the rest live on the ruler.
- Classification: surnames instead of codes from 768px up; the team bar 4px; the points column in ink 600; a 2px rule under P10 (the points line). Keep it a hairline table.
- Positions chart: every line 1px `#AEBAC1`, no dashes; the podium in team colour at 2px with end labels; the selected driver 3px and their teammate 2px dashed. Hatch the neutralised laps instead of a beige fill. Drop the dotted horizontal gridlines; keep P1, P5, P10, P15, P20 ticks. Title follows the selection (issue 14).
- "The numbers" and the lap picker become one quiet row of text links under the chart: "Table", "CSV", "Lap by lap".

**Driver panel**

```
┌ driver sheet ───────────────────────────────────────────────────────────────┐
│ 10   Pierre Gasly                     FP1  FP2  FP3   Q    R                │
│      Alpine                           P18  P16  P15  P14  P10  ← a 5-point  │
│                                        ·────·────·────·────●     trace       │
│ Gasly climbed from P14 to a point, made on lap 1                            │
│                                                                              │
│ Story body, 17px ink, 62ch…                     │ Grid      P14             │
│                                                 │ Finish    P10  +4         │
│                                                 │ Points      1             │
│                                                 │ vs Colapinto  P10 v P14   │
└──────────────────────────────────────────────────────────────────────────────┘
```

- The car number at 96px, weight 800, width 125, in the team colour: the one large saturated mark on the page, and it is the driver's.
- Key numbers as a title-block table on the right, not a row of label-over-value pairs.
- The weekend arc becomes the caption under the five-session trace, in ink at 14px, not a 12.5px grey paragraph above the headline.
- The vs strip: the gap chart's axis runs from 0 to the maximum, not ±67s with half the plot empty. Hide the written head-to-head until the rewrite lands; the three facts and the chart say more than "ranking 7 of 20 in sector 1 at 29.042".
- Expert: findings as numbered callouts in the left margin with their tables beside them; never a table with no rows.

**Home**

```
┌──────────────────────────────────────────────┬─────────────────────────┐
│ Round 20, Brazilian Grand Prix, 8 Nov        │ Drivers' championship   │
│                                              │ 1 Antonelli   390       │
│ Norris won in the wet from pole.             │ 2 Verstappen  −111 ▬▬   │
│ Verstappen went from P21 to P2.   (44px)     │ …                       │
│                                              │                         │
│ [plan, 320px, ink]   [lap ruler, full width] │                         │
│                                              │                         │
│ Read  Norris: took the lead for good, lap 54 │                         │
│       Verstappen: 19 places from P21         │                         │
│       Lindblad: P18 to P11, best of the rest │                         │
├──────────────┬──────────────┬────────────────┤                         │
│ R19 Mexico   │ R18 USA      │ R17 Singapore  │                         │
│ one-line     │ one-line     │ one-line       │                         │
│ verdict      │ verdict      │ verdict        │                         │
└──────────────┴──────────────┴────────────────┴─────────────────────────┘
Next: Las Vegas, 22 Nov.   All 20 races
```

- The verdict sentence is the hero, not the outline. Three story links under it: winner, biggest mover, best midfield.
- Circuits in ink everywhere. Team colour appears only in the podium ticks and the ladder.
- "Still to come" becomes one line.
- Each of the three smaller cards gets its one-line verdict; today they carry a name and three codes.

**Standings.** Keep it. Three changes: the leader panel's empty middle (about 130px) closes up or takes the last-five-races form; add "Table / CSV" under Title fight; a 2px rule after the last points scorer.

**/races.** Circuits in ink at 1.5px; each card gains its one-line verdict; the winner's surname in ink with a team tick. Twenty cards of outline plus codes is a gallery, not an index of stories.

**Mobile**

- Driver selected: collapse the sheet to a 148px strip and start the story within the first screen (issue 13).
- On the sheet at 375px the plan sits above the ruler; ruler flags stack as a numbered list directly under it, each with its sentence.
- A sticky bottom bar on race pages: the selected driver's name (opens the picker) and the Essential / Expert switch. The header switch is out of reach one-handed.
- 44px rows and controls (issue 19).

### What to remove

- Team-coloured circuit outlines.
- The yellow "middle half" on maps.
- The left-column moment fragments on the sheet.
- Title-block rows with zero or "never".
- The native select styling for "Compare with" and "Lap" (keep the element, style it as an underlined text control with a caret).
- Graphite on anything that is a full sentence.
- The half-sizes (12.5, 13.5, 14.5, 15.5px).

### If only one day

Do the race sheet, in this order: two-tone paper (an hour), the six-size type scale applied to the race page (two hours), then the lap ruler with the moments written on it (the rest of the day). It changes the first screen of every one of the 100 session pages, it is the element that would make a screenshot recognisable, and it needs no new data: `pivotal-moments.json`, `race-control.json` and the lap count are already exported.

## 5. Ideas worth considering

Separate from the fixes; none is needed to reach a good score.

| Idea | The fan's question |
| --- | --- |
| **"The result changed" note.** When a re-fetch alters a classification, show a dated line on the race page: who moved and by how much | "I watched Piastri finish seventh. Why does it say thirteenth?" |
| **Where the gap came from.** One bar per driver splitting the gap to the car ahead into pace, pit lane, and laps under yellow, computed from data already in the debrief | "Was he slow, or was it the strategy?" |
| **Garage ledger.** A season page per team: qualifying and race head-to-head by round, as a two-row strip | "Who is actually winning at Alpine this year?" |
| **Friday form.** After practice, one ranked list combining each driver's best long run across FP1 to FP3 with sample sizes | "Who looks quick for Sunday?" |
| **The lap ruler as the share card.** A 1200 by 630 image per driver: ruler, their position trace, their headline | "How do I show a friend what happened to my driver?" |

## 6. What could not be checked, and doubts

- **formula1.com directly.** Classifications were compared with Jolpica for all 20 races and all sprints (position, points, status, grid), not with formula1.com. Qualifying was compared only for round 20.
- **Lighthouse** was not run; F36 is carried at 1, not verified.
- **Head-to-head rewrite** (#65) cannot be judged until the owner's run; the 715 on the site are the old text.
- **Why rounds 18 to 20 have no stories.** The daily run's story cap comes from a repository variable that cannot be read from here; the result (0 Claude stories in three rounds) is certain, the cause is inferred.
- **Why the grid differs from qualifying in Brazil** (Leclerc P4 to P14, Hamilton P11 to P20, Verstappen P16 to P21). The grid matches Jolpica; the reason is not in the exported data, and the site does not explain it.
- **Corner reference laps** (issue 15) are flagged on a statistical sign, not by re-fetching telemetry.
- **Stories about two drivers agreeing with each other** (D28) was not checked systematically.
- **Screen readers.** Keyboard focus was checked (visible outline on every stop, no skip link); no screen-reader pass was made.
- **Dark theme** was looked at on five pages at both widths; it holds up, and nothing in it changes a finding.
- **Scores in D** are judgement from 28 stories; a different sample could move them a point either way.

## 7. Prompts for the follow-up work

Each prompt stands alone and is meant for a fresh session on a branch from the latest `main` (after PR #15 is merged). Run them in order; 1 to 3 are data, 4 and 5 are stories, 6 to 8 are the look.

Common rules, to paste at the top of each:

```
Rules for this session:
- Read docs/FABLE_AUDIT.md first; the issue numbers below refer to its section 2.
- Do not trigger any GitHub Actions workflow and make no Claude API calls from the pipeline.
  Never pass a non-zero MAX_NEW_STORIES. Story generation is the owner's action.
- Build as CI does: restore data/f1.db from the db-snapshot release, then
  `python scripts/run_pipeline.py --year 2026 --no-ingest --no-stories`, `make build`,
  `make invariants`, `make e2e`. All of `make check` must pass before you push.
- Every fix ships with the test or invariant named in the audit's "Proof" column.
- Don't merge PRs. No model names in commits or PR text. Record decisions in PROGRESS.md.
```

### Prompt 1: publish again (issues 1, 2, 3)

```
Goal: the site publishes again and can never freeze like this silently.

1. In f1tracker/ingest/season.py (the "already ingested - skipping" branch near line 93), add a
   refresh pass: for every session of the last 3 completed rounds, re-fetch Jolpica results,
   sprint results and qualifying, compare with the stored rows, and when anything differs update
   the rows, rerun the transforms for that session and for the standings, and mark that round's
   stories, weekend arcs and the season arcs as stale (data changed) without regenerating them.
   Log one line per changed driver. This pass is allowed to use the network; it makes no Claude calls.
2. Run it locally against the snapshot and confirm round 19's race now matches Jolpica
   (Lawson P7, Bortoleto P8, Hadjar P9, Hirakawa P10, Piastri P13, Colapinto P15, Gasly P17) and
   round 20 qualifying has times (Norris 1:27.470 in Q3).
3. Stale stories must not publish a superseded result: at export, a story whose data hash is
   stale falls back to the template until it is rewritten.
4. Qualifying export: if P1 has no time in a completed session, export the order with the note
   "Times not yet published" and no "No time" labels, no "Set no time N" row and no
   "set no time" key moments. Fix f1tracker/analysis/pivotal.py:177 so "He set no time in
   qualifying" is used only when the driver truly set none. Remove the "n/as" string from the
   qualifying summary in f1tracker/transforms/headline.py.
5. Invariants: (a) every race and sprint classification equals Jolpica's position, points and
   status for every round; (b) a completed qualifying session's P1 has a time; (c) no exported
   string contains "n/a".
6. .github/workflows/site.yml: when the build job fails, open or update one GitHub issue titled
   "Site publish failing" with the failing step. Do not change what gates a deploy.
Report: the list of rows changed by the refresh, and the invariant results before and after.
```

### Prompt 2: one driver, one record (issue 7)

```
Goal: Rafael Câmara is one driver, and it cannot happen again.

1. f1tracker/ingest/drivers.py: slugify must transliterate (NFKD, strip combining marks) so
   "Câmara" becomes "camara". When resolving an OpenF1 driver, match by car number within the
   same event's Jolpica entry list before falling back to the name.
2. Write a one-off, idempotent repair in the pipeline's upgrade path that merges driver 39
   (rafael_c_mara) into driver 40 (rafael_camara) using the existing _merge_into, sets the code
   CAM, and resolves "Driver #236" (2 pit stops) to its real driver by car number and session or
   deletes the orphan rows. Rerun transforms for the affected sessions.
3. Invariants: no exported driver without a three-letter code; no driver_ref starting with
   "driver_"; no two driver ids sharing a car number within one event.
4. Check /race/20?session=100&drivers=<Câmara>: stops, stints, sectors and FP positions present.
```

### Prompt 3: one number, one meaning (issues 5, 6, 11, 12, 15, 16, 17)

```
Goal: no two places on a page disagree, and no label misleads.

1. Long runs: one shared constant and one ranking function used by narratives/facts.py,
   narratives/debrief.py, analysis/midfield.py and narratives/weekend_arc.py. Minimum 5 laps,
   ranked only in a field of 5 or more. Rename the fact-sheet key that says "8_plus_laps".
   Invariant: each "long run Nth of M" finding equals its table row.
2. analysis/midfield.py:136: emit "stronger on long runs" only when the long-run rank as a share
   of its field beats the single-lap rank as a share of its field. Invariant on
   midfield-spotlight.json.
3. analysis/pivotal.py: a pit_cycle or slow_stop moment survives only if it changed the lead or
   the podium. "Midfield" moments exclude drivers of the top 4 teams in the constructors'
   standings going into that round. The recovery note must add up: on-track places minus pit
   places equals net places, stated in one sentence, or the second sentence is dropped.
4. frontend/src/lib/sheet.ts: a complete moment_type to label map; unit test that no label
   contains "_" or a lowercase segment name.
5. Corner deltas: show each delta against the field median for that corner (keep ranks as they
   are). Invariant: field median delta per corner within ±250ms. Corner labels unique per
   circuit (Hungary has two 1s and two 12s): keep MultiViewer's letter suffix.
6. Key numbers: computed in code from the fact sheet with labels from a fixed list; the model
   no longer writes them. Points as whole numbers.
```

### Prompt 4: story inputs and checker (section 3; issue 10)

```
Goal: the next stories run produces headlines that read the result correctly, with less
repetition. This session changes code only; it writes no stories.

Implement section 3 "Changes to make" of docs/FABLE_AUDIT.md:
- Fact sheets: outcome frame and angle; lead and support facts chosen in code; cause links with
  cause_supported; non-events dropped; qualifying "where the time went" facts.
- Prompt: the four prompt changes. Bump PROMPT_VERSION once.
- Checker: the six rules, each with a unit test built from the audit's quoted examples
  (Gasly R1, Pérez R9, Leclerc R9 sprint, Bottas R1, Bortoleto R10 FP3, Hadjar R1).
  Fact rules 1 to 4 also run at export; style rules stay write-time only.
- Run the new checker over the current export without rewriting anything and report how many
  published stories each rule would reject, by round. Do not let that change what is published
  in this PR beyond the fact rules.
Then stop and give the owner: the count of stories a full rewrite would touch, and the
recommended run order (rounds 18 to 20 first).
```

### Prompt 5: an Expert view that is never empty (issue 9)

```
Goal: every classified finisher's Expert panel has stints, pace and at least two findings.

1. narratives/debrief.py: when the tyre records disagree with the pit-stop records, build the
   stints from the pit-stop laps (laps, fuel-corrected pace and fade are still computable) and
   show the compound as unknown with one note. Rounds 2, 6, 12, 13, 16, 17 and 19 are the test set.
2. Findings that need no tyre data: places made on track vs in the pits; average pace vs the
   teammate over the laps both ran in clear air; gap to the car ahead at the flag and where it
   opened. Order findings by how much of the result they explain; "ahead of teammate" is last.
3. frontend/src/components/Debrief.tsx: never render a table with headers and no rows.
4. Invariant: every classified finisher has at least one stint row with a pace and at least 2
   findings. Crawl: Alonso at /race/12 in Expert shows a stints row.
```

### Prompt 6: the race sheet, plan and section (section 4)

```
Goal: build the signature element described in docs/FABLE_AUDIT.md section 4,
"The signature: plan and section", on race, sprint, qualifying and practice sheets.

1. Tokens in frontend/src/index.css: add --desk (#E4EAEC light, #141B21 dark) as the page
   background and set --paper to #F6F8F8 light, #1C262E dark for the sheet and content panels.
   Sheet border 1.5px ink.
2. Type: the six-size scale in the audit's table, as CSS custom properties and utility classes.
   Replace every 12.5, 13.5, 14.5 and 15.5px. Story body 17/27 in ink, max 62ch. Extend
   scripts/check-design.mjs to fail on a font size outside the scale and on graphite used for
   a paragraph.
3. Plan (components/race/RaceSheet.tsx, lib/circuitOverlay.tsx): sector boundary ticks labelled
   S1, S2, S3; a direction arrow on the main straight; lap length and a scale bar; moments that
   have a location get a leader line and their sentence beside the track. No fragments list.
4. Section: a new LapRuler component under the plan. One tick per lap, labels every 10; Safety
   Car and VSC as hatched blocks; a 4px strip along the top in the leader's team colour per lap;
   each key moment as a numbered flag on its lap with its sentence. Qualifying: Q1, Q2, Q3 with
   cut lines and who fell at each. Practice: the session clock with red flags and VSC.
   Data comes from pivotal-moments.json, race-control.json and position-by-lap already exported.
5. Title block: drop rows whose value is zero or "never" (issue 18).
6. Key moments below the sheet keeps only moments with a second sentence.
7. Reduced motion: unchanged (finished drawing). Phone: plan above ruler; flags as a list.
8. Crawl: the ruler exists on every session page of rounds 1, 12 and 17; each flag's number
   matches a moment; no horizontal scroll at 375px. Screenshots before and after at 1360 and
   375, light and dark, into docs/screenshots/round4/.
Do not change the classification, the charts or the driver panel in this PR.
```

### Prompt 7: home, driver panel, mobile (section 4; issues 13, 19)

```
Goal: the home page leads with a story, the driver panel reads as the driver's own sheet,
and a phone reader reaches the story on the first screen.

Home (pages/Home.tsx), per the wireframe in the audit:
- Hero is the latest race's verdict sentence at the headline size, the plan in ink at 320px,
  the lap ruler, and three "Read" links (winner, biggest mover, best midfield) using each
  story's headline. The three smaller cards each carry a one-line verdict.
- Circuits are drawn in ink on home and /races. Team colour only in podium ticks and the ladder.
- "Still to come" becomes one line: the next race and its date.

Driver panel (components/DriverStory.tsx, CompareView.tsx), per the wireframe:
- Car number at 96px, weight 800, width 125, in the team colour. Key numbers as a title-block
  table. The weekend as a five-point position trace with the arc as its caption in ink.
- Gap chart axis from 0 to the maximum. Hide a head-to-head text that contains three or more
  sector times until it has been rewritten.

Mobile:
- Under 640px with a driver selected, the sheet collapses to a 148px strip with "Show the sheet".
- A sticky bottom bar on race pages: driver picker and Essential / Expert.
- 44px minimum rows and controls.
Crawl: at 375px a driver link shows the story headline within the first 700px; no interactive
element under 40px tall; home contains a sentence with the winner's name and a verb.
```

### Prompt 8: charts, tyres and small things (issues 8, 14, 20; section 4)

```
Goal: the charts stop looking like library defaults.

1. Tyres: Hard is paper fill with a 1.5px ink outline in both themes; a compound letter on every
   bar; Unknown is a 45° graphite hatch. check-design.mjs: every data colour at least 3:1
   against the paper it sits on, in both themes.
2. Timing tiers on maps: middle half is the plain ink line; bottom quarter is graphite at half
   width, dashed 2 5; purple and green unchanged. Update the legend. (Owner decision 5 must be
   yes before this step.)
3. Positions chart: all cars 1px #AEBAC1; podium in team colour at 2px with end labels;
   selected driver 3px, teammate 2px dashed; hatched neutralised laps; no dotted gridlines.
   The title follows the selection ("Gasly: P14 on the grid, P9 after lap 1, P10 at the flag").
4. Classification: surnames from 768px up; 4px team bar; a 2px rule under P10.
5. "The numbers", CSV and the lap picker become one row of text links. Add the same under
   Title fight and the tyre strategy chart.
6. Standings: close the empty space in the leader panel; a rule after the last points scorer.
7. Glossary: "undercut", "overcut", "pit cycle" and "lead lap" become tappable terms inside
   story text. A feedback link in the footer that needs no GitHub account.
```

## Owner decisions needed

1. **Merge PR #15.** It is still open; findings #63, #64, the lap drill-down, spoiler-free mode, follow and the changelog are not live until it is.
2. **Stories for rounds 18 to 20, and from now on.** About 327 session stories, 84 weekend arcs and 34 season arcs. Decide whether the daily run may write stories for newly ingested rounds with a small cap (for example 150), so a new round is never template-only for more than a day.
3. **When an official result changes after stories are written.** Rewrite that round's race stories and arcs automatically (about 22 stories and 22 arcs for Mexico City), or show templates until you approve a run. The audit's prompt 1 assumes the second.
4. **Should one failing invariant block the whole deploy?** Today it does, and it cost ten days. The alternative is to publish with the affected round marked "result under review". Prompt 1 keeps the gate and adds a failure notice; say if you want the other.
5. **Timing colours.** Dropping yellow for "middle half" on maps (ink instead) changes the round 3 palette. Yes or no.
6. **Two-tone paper** (`#E4EAEC` desk, `#F6F8F8` sheet). A small departure from the single paper colour in the round 3 plan.
