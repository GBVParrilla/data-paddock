# Data Paddock Long-Run Prompt — Round 2

Oct 18, 2026 · @George

This is the prompt for Claude Code's next long run. It combines Claude Code's own declutter plan, my round 2 review, the round 1 review and the benchmarks, plus every decision you made. It runs for as long as it takes without stopping to ask questions: it makes the calls itself and lists them in each PR, so you can review or overrule them.

## How to use this page

Add two files to the repo, then paste everything from "Mission and decisions" down into Claude Code at the repo root.

1. Export **Data Paddock Review — Round 2** as Markdown and commit it as `docs/REVIEW_ROUND2.md`.
2. Commit BENCHMARKS.md (from the earlier round) as `docs/BENCHMARKS.md`. The scorecard in its §7 is the bar.
3. Keep `REVIEW.md` and `PROGRESS.md` where they are.
4. In parallel, trigger the Site workflow in GitHub Actions: mode `stories-only`, story rounds `1,12,17`. That produces the pilot stories Workstream B reviews.
5. Pre-approve the commands Claude Code needs (git, npm, npx, python, pytest, playwright) so an unattended run doesn't stall on a permission prompt.
6. Edit anything on this page before pasting. It's yours.

## Mission and decisions

You are the lead engineer on **Data Paddock** (https://gbvparrilla.github.io/data-paddock/). It turns F1 timing data into a story for every driver in every session of the 2026 season. It serves two audiences: new fans who want to understand a weekend without being overwhelmed, and data-curious and diehard fans who want depth the broadcast doesn't give. The mission is that a midfield or backmarker driver gets a story as good as the winner's.

Round 1 (PR #5, merged) made the site correct and stable. Round 2 makes it **calm, and actually tell stories**. Read these before doing anything: `docs/REVIEW_ROUND2.md` (current state, findings #36–#47, the verdict on the declutter plan), `docs/BENCHMARKS.md` (the §7 scorecard is the bar), `REVIEW.md` and `PROGRESS.md`.

The owner made these decisions. They are requirements: don't reopen them, and don't work around them.

| # | Decision | Requirement |
| --- | --- | --- |
| D1 | Story model: **Haiku 5.5** | Keep `config.NARRATIVE_MODEL` at Haiku 5.5. Make Haiku succeed (Workstream B). If it can't hit the quality gate, keep Haiku and write a model recommendation in the PR rather than switching on your own |
| D2 | Race page: **story first** | Before a driver is picked: 30-second summary → classification beside key moments → positions by lap → a closed "More detail". Beyond the podium is merged into Key moments |
| D3 | Home: **4 big cards + link** | The latest 4 rounds as big cards, then "All N races →" to `/races`. No compact list on home |
| D4 | Order: **in parallel** | Ship the declutter PR without waiting for stories; the owner runs the pilot story workflow meanwhile |
| D5 | Story voice: **verdict first, Expert adds data** | A site-wide Essential/Expert toggle. Essential: a verdict headline, cause → effect, 2–3 numbers. Expert: the same story plus key numbers, sector ranks and stint pace inline, with More detail open by default |

## Operating rules

These apply for the whole run.

1. **One PR per workstream**, each branched from the latest `main`. Workstream A (declutter) comes first and stays layout-only, with no pipeline changes. The owner merges; never push to `main`.
2. **PROGRESS.md is your memory.** Add a "Round 2" section: the current workstream, a checklist of #8, #24, #26, #29 and #36–#47 with `open / in progress / fixed (evidence: …)`, a scorecard log, "Needs owner" and "Next 3 actions". Re-read it whenever you resume.
3. **Proof over claims.** "Fixed" means a test, invariant, crawl step or screenshot proves it, linked in PROGRESS.md. Never weaken or delete a test to make it pass.
4. **Keep what works.** Everything listed as fixed in round 1 stays fixed, and `make check` stays green after every commit.
5. **Secrets.** Never print, log or commit a key. Story generation runs in GitHub Actions through Workload Identity Federation, as now.
6. **Cost.** Iterate on stories with the pilot rounds (1, 12, 17) only. Log Claude calls and fact-check pass rates per run in PROGRESS.md.

### Big calls: decide, then flag

Don't stop the run to ask questions, and don't use multiple-choice or interactive question prompts. Make the call yourself, then flag it for the owner to review when it would:

- change what a visitor sees **by default** on home, race or driver pages beyond this spec
- remove or hide a feature that works today, other than what Workstream A lists
- add anything to the site that claims or describes AI authorship
- start a Workstream D feature

How to flag: choose the option that best serves the mission. Record it under **"Decisions made"** in the PR description and in PROGRESS.md: what you chose, the alternatives, why, and how to undo it. The owner can overrule it in PR review.

A few things aren't yours to change, so don't wait on them either. **Never change the story model or effort, raise word limits or the per-run Claude call cap, or publish anything personal (such as a report email address).** Write a recommendation for those, and list anything only the owner can do (run a workflow, set a repository variable) under **"Owner actions"** in the PR. Then carry on with everything that doesn't depend on it.

Everything else (implementation details, test design, naming, refactors with a measurable reason) is your call. Record the reasoning in the PR description.

## Workstream A: the declutter PR

Goal: a race page that reads top to bottom in under a minute, with every fact said once. This is a separate PR from the latest `main` (PR #5 is already merged). The frontend is in `frontend/src` (React 19, Vite, Tailwind 4). Today Australia shows 7 panels before a driver is picked, 19 glossary underlines and Verstappen's P20→P6 three times; the target is 4 panels and every fact once.

**Race page** (`pages/RaceWeekend.tsx`, `components/race/*`)

1. **Order (D2).** Summary → classification (left) beside key moments (right, with the compact sector strip on top) → positions by lap → a closed "More detail" disclosure holding the deep dive (tyres, sectors, turn by turn, pace, race control). More detail opens on its own when a driver is picked, and stays open in Expert mode. Its open state goes in the URL (`?detail=1`) so shared links keep it.
2. **Merge Beyond the podium into Key moments.** Stop rendering `BeyondPodium.tsx`. `KeyMoments.tsx` takes the midfield spotlight and adds up to 2 items tagged "Midfield" for drivers not already mentioned. Every race and sprint must show at least one non-podium driver, so the mission stays visible. Cap the list at 8 rows.
3. **One fact, one place.** Add `lib/mentions.ts`: a page-scoped register keyed by driver id and fact kind (climb, retirement, DNS, lead change, penalty…). The summary claims first, key moments skip what it claimed, and midfield items skip both. The summary's second sentence follows this priority: the race-deciding lead change, then a DNF or DNS of a top-6 starter, then a red flag or SC that reshuffled the top 5, then the biggest climb (#39).
4. **Compact circuit panel.** With no driver picked, `CircuitPanel.tsx` is one row: a small outline thumbnail (about 96px) and the three session-best sector times with their drivers. The full map with sector colours and corners appears only once a driver is picked. Move the non-component exports out of the file (fixes the lint warning, #47).
5. **Chart titles say the takeaway.** "Positions by lap" becomes a computed line, such as "Russell led from lap 27" or "Norris won from pole after losing the lead twice". The sector strip title names the fastest in each sector. Use the generic title when the data doesn't support a clear line.

**Less noise everywhere**

6. **Glossary underlines** (`components/Glossary.tsx`). Allow-list only: VSC, SC, red flag, DNF, DNS, DSQ, NC, lapped, undercut, overcut, stint, compound, long run, Q1/Q2/Q3, sprint quali, stand-in, interpretation. Underline only the first use per page, via a page-scoped context that resets on route change. Drop the Colours, Sector and Retirement/Did-not-start label underlines.
7. **Helper labels.** Keep exactly one: "Pick up to two drivers" on the classification. Remove "What decided the race, in lap order", "Pick a driver to follow their weekend", "Hover a line, click / Tap a line to follow a driver" and "Circles mark pit stops" (pit circles get a legend entry instead).
8. **Driver story** (`DriverStory.tsx`, `StoryMeta.tsx`). Remove the "Terms:" row. Replace the per-story source line with one source line per page, worded from the stories actually rendered ("Stories written by Claude from the timing data and fact-checked", or "Stories computed from the timing data", or both with counts). A story shows its own badge only when it differs from that line (edited by the editor, or a template on an otherwise AI page). Keep "Report an error" on each story: it carries the story id.
9. **Footer** (`Shell.tsx`, #37). Remove "Stories written by Claude from that data" from the global footer. The page-level line in item 8 replaces it.

**Home** (`pages/Home.tsx`, `components/RaceCard.tsx`)

10. **4 cards + link (D3).** Show only the latest 4 rounds as big cards, then "All 17 races →" to `/races`. `/races` keeps the full grid and its filters.
11. **Freshness stamp (#42).** Under the season heading, and on race and standings pages: "Data through round 17 · updated 18 Oct". `export_static.py` writes `meta.json` (last completed round, generated time); this is the one pipeline touch allowed in this PR.

**Phones**

12. **Classification** (`Classification.tsx`). Below `sm`, hide Stops and Grid and keep Pts. This deliberately differs from the original plan: points are the result fans look for, and +/− already shows the grid move. Pts must be visible without sideways scroll at 375px (#45).

**Essential/Expert (D5)**

13. A two-state toggle in the header ("Essential · Expert"). Persist it in `localStorage` (wrapped in try/catch) and accept `?mode=expert` in URLs. Expert opens More detail by default, expands each driver story, and shows key numbers and sector ranks inline. Until Workstream B ships expert fields, Expert shows the full story text and the existing key numbers.

**Small fixes in the same PR:** the `/season/2026` page title (#43), and the `useFetch` effect lint warning (#47).

### Done when

- `npm run lint`, `npx tsc -b` and `npx playwright test` (in `frontend`) pass, and the Checks workflow is green.
- The crawler is updated for removed panels. It walks every race via `/races` (home now shows 4), opens More detail before counting deep-dive tabs (at least 4 on pilot rounds), and adds four checks:
  - with no driver picked, a race page has at most 5 top-level panels
  - no driver's fact appears in both the summary and key moments
  - each glossary key is underlined at most once per page
  - only one helper label is present
- Before/after screenshots at 1360px and 375px of home, `/race/1` and `/race/1/driver/gasly`, plus `/race/1/driver/gasly?mode=expert` at 375px, are in the PR.
- PROGRESS.md is updated, and the PR description has "Decisions made" and "Owner actions" sections.

## Workstream B: real stories, written by Haiku

Goal: the stories that set Data Paddock apart are live, and they read like a sharp race engineer explaining a weekend, not a log. Today none are live: all 2,291 published stories are templates (#36). 1,851 were written before the fact-checker existed and are withheld; 431 weekend arcs failed the 170-word limit.

1. **Read the pilot run.** Once the owner's `stories-only` run for rounds 1, 12 and 17 finishes, download the `db-snapshot`, export, and record in PROGRESS.md: stories attempted, published as Claude, fallen back to template (by reason), and Claude calls.
2. **Story shape (D5).** Extend the structured output, keeping the old fields working:
   - `headline`: a verdict, at most 12 words. It says what the result meant or why it happened ("Alpine's early stop cost Gasly a place he won back"), not only the result ("P10 from P14")
   - `essential`: at most 90 words, cause → effect, plain words, 2–3 numbers, no lap times unless they are the point
   - `expert`: at most 110 words that add data: sector ranks, fuel-corrected stint pace, pit-lane time, gaps to the cars around him
   - `analysis`: at most 80 words; it states the computed verdict and hedges once, only when the fact sheet marks `insufficient_data`
   - `key_numbers`: 3–5 keys from the fact sheet
3. **Make Haiku succeed.** Do the reasoning in code so the model only phrases it:
   - Compute 1–3 **verdict candidates** per driver-session in the fact sheet (stop timing vs VSC, net places from the pit cycle, the decisive overtake, a teammate gap) and ask the model to pick and phrase one.
   - Trim fact sheets to what the story may use.
   - Prompt for about 70% of each word limit, so near-misses don't fail.
   - Add three worked examples to the prompt (a winner, a midfield driver, a DNF), hand-checked against the data.
   - Keep the fact-check, up to 3 retries with the specific violations, then the template fallback.
4. **Weekend arcs.** Build them from fact sheets, with a 110-word prompt target under the existing 170-word limit. Don't raise the limit; if arcs still fail, write a recommendation in the PR.
5. **Better templates (#40).** The template is the fallback, so it must read well. Rewrite its sentences in plain words: "His only stop, on lap 10, came two laps before the VSC, and that cost him a place once the cars around him had stopped", not "Stop 1 cost him 1 place". No raw expressions like "(-0.06s per lap)" in Essential mode.
6. **Pilot quality gate.** All of these must hold on rounds 1, 12 and 17:
   - at least 90% of stories publish as Claude-written
   - 0 published fact-check violations
   - 15 stories reviewed (5 front-runners, 5 midfield, 5 back-of-grid, DNF or DNS), scored 1–5 on accuracy, readability for a new fan, insight for a diehard, and specificity: an average of at least 4.3, none below 3
   - every headline passes the verdict test in item 2

   Record the scores and the worst story's text in PROGRESS.md.
7. **If the gate fails after 3 prompt iterations**, don't stop: keep the best prompt you have, with templates as the fallback, and write a recommendation in the PR from these options, recommended first:
   - A: raise Haiku's effort from low to medium
   - B: use Sonnet 5.5 for race and sprint stories only, and Haiku for practice and qualifying
   - C: ship improved templates only for now
   - D: keep iterating on prompts

   Include each option's estimated Claude calls and the pass rate you saw.
8. **Full season.** Once the gate passes, list under "Owner actions" a request to run `stories-only` for all rounds (with the per-run cap), then repeat the counts from item 1 season-wide.

## Workstream C: every remaining issue

These close out round 1 and the round 2 findings. Put pipeline and data items in their own PR, separate from Workstream A.

| # | Issue | Fix | Proof |
| --- | --- | --- | --- |
| 8 / 41 | Turn-by-turn tab is empty: no breakdowns exported | List the full recompute (about 70 min of OpenF1 downloads) under "Owner actions"; until it runs, hide the tab instead of showing an empty one | Invariant `test_turn_deltas_reconcile` runs (not skipped) on all race sessions |
| 24 / 43 | /season/2026 has no page title | `useTitle` on SeasonPage, plus a prerendered title | Crawl asserts a page-specific title on every route |
| 26 / 38 | Facts repeat across panels | Workstream A item 3 | Crawl duplicate-fact check |
| 29 | Error reports need GitHub | List under "Owner actions": the owner chooses a report address (it's personal data) and sets `VITE_REPORT_EMAIL` | The "Report an error" link opens a prefilled email |
| 36 | No AI stories live | Workstream B | Export log shows at least 90% Claude-written on the pilot rounds |
| 37 | Footer claims Claude wrote template stories | Workstream A item 9 | Crawl: no AI-authorship claim on a page whose stories are all templates |
| 39 | Summary and moments miss how the race was won | Pivotal engine: always emit the final lead change that decided the win, and a front-runner DNF on lap 1–3, as `must_include`; summary priority in A item 3 | New `test_pivotal.py` cases for R12 (Norris regaining the lead; Verstappen's lap-1 DNF) |
| 40 | Template prose reads like a log | Workstream B item 5 | 15-story review on templates scores at least 3.5 for new-fan readability |
| 42 | No freshness stamp | Workstream A item 11 | Crawl asserts the stamp on home, race and standings |
| 44 | A DNS car has a tyre bar | Drop stints for status DNS at export | Invariant: no stints for DNS drivers |
| 45 | Pts off-screen on phones | Workstream A item 12 | Mobile crawl: Pts column visible in the viewport |
| 46 | Pages run long | Workstreams A and D | Recorded page heights: home at 375px under 3,500px; race page at 1360px with no driver picked under 2,200px |
| 47 | Lint warnings | Workstream A | `npm run lint` with 0 warnings |

## Workstream D: benchmark gaps, owner-picked

Don't start any of these until A to C are merged. Then build them in the order below, one small PR each, so the owner can merge or drop each one. Each one must fit the calm layout from Workstream A: it lives behind Expert mode or More detail unless the owner says otherwise.

| Option | Scorecard row | Size | Benchmark |
| --- | --- | --- | --- |
| Spoiler-free mode (results hidden until tapped) | E35 | S | MultiViewer |
| Follow a driver or team, so home leads with them | E33 | S | FotMob, TracingInsights favourites |
| Methods page for every derived number | C23 | S | Opta explainers, Our World in Data |
| Public changelog page | F39 | S | Baseball Savant |
| "Show data" table beside every chart | C17 | S | TracingInsights Chart/Data/Docs |
| Share card per driver-race (from the existing OG images) | E32 | S–M | Spotify Wrapped, Strava |
| Lap drill-down: click a lap to see its sectors | C21 | M | F1 Tempo |
| Season percentile bars per driver (quali pace, race pace, tyre management, starts) | new | M | Baseball Savant |
| Battle graphic: gap between two cars lap by lap, with who gained | new | M | FotMob momentum |
| End-of-season "Wrapped" per driver and team (after Abu Dhabi, 6 Dec) | E34 | M | Spotify Wrapped |

Build these first: spoiler-free mode, follow a driver, the methods page and the changelog. They're small, and they lift scorecard sections C, E and F the most for the least added clutter.

## Self-improvement loop and exit

After each workstream's PR is merged and deployed, run this loop, and keep running it until the exit criteria hold.

1. **Crawl the live site** with `E2E_BASE_URL=https://gbvparrilla.github.io/data-paddock/ npx playwright test`, plus screenshots at 1360px and 375px of home, `/races`, standings, and for each pilot round: the race, qualifying, one driver picked, two drivers picked and Expert mode.
2. **Score the scorecard** in `docs/BENCHMARKS.md` §7. Each row is 0, 1 or 2, with evidence, and section A counts double. Log the total and section scores in PROGRESS.md with the date and commit. Round 2 started at **65/100** and fails the gate on A7.
3. **Critic pass.** Score each of the five personas from 1 to 10: new fan, data-curious fan, diehard, website critic, data engineer. Use the screenshots and 5 random stories, at least 2 from outside the top 10. Persona checks:
   - **New fan:** understands the race in 60 seconds; no more than 4 panels before picking a driver; no undefined jargon
   - **Data-curious fan:** every number reconciles; Expert mode teaches something
   - **Diehard:** facts right, including stand-ins and penalties; key moments match what decided the race
   - **Website critic:** calm, no repetition, fast, shareable
   - **Data engineer:** every visible number covered by an invariant; no unchecked AI text published
4. **Fix** the lowest-scoring, highest-severity item first, adding the test that would have caught it. Number new findings #48 and up.
5. **Raise the bar.** When a persona scores 9 or more twice in a row, add one stricter check for it and record it.
6. **Guard against drift.**
   - Clutter is a regression: a change that adds a default-visible panel, label or underline needs a reason, or an owner yes.
   - Never remove a working feature to raise a score.
   - Ideas go to `IDEAS.md` until the owner picks them.

### Exit criteria (all at once)

- Every issue in this prompt is fixed with linked evidence, or marked "won't fix" with a reason the owner accepted.
- The scorecard is at least **85/100**, every section A row scores 2, and the ship gate passes.
- The pilot story gate (Workstream B item 6) passes, and season-wide at least 90% of stories are Claude-written, with 0 published violations.
- Every persona scores at least 9 on two passes in a row.
- `make check` is green, and the crawl is green against the live URL on desktop and mobile.
- PROGRESS.md ends with a Round 2 report: before/after scores, before/after page heights and panel counts, Claude calls and pass rates, owner decisions taken, and what's next (for example, live sessions, which `sessions.status` still supports).

Then run one last live crawl, write the report, and stop.

## First actions

1. Read `docs/REVIEW_ROUND2.md`, `docs/BENCHMARKS.md`, `REVIEW.md` and `PROGRESS.md`. Add the Round 2 section and checklist to PROGRESS.md.
2. Branch from the latest `main` for Workstream A. Take the "before" screenshots first (1360px and 375px: home, `/race/1`, `/race/1/driver/gasly`, plus Expert at 375px once it exists).
3. Update the crawler's new checks (panel count, duplicate facts, single underline, one helper label) and watch them fail on today's build.
4. Build Workstream A items 1–13 until those checks pass, then the "after" screenshots, then open the PR with its "Decisions made" and "Owner actions" sections.
5. Meanwhile, check PROGRESS.md for the owner's pilot story run. When its snapshot exists, start Workstream B item 1.
6. Open the Workstream C PR (pipeline and data items), then run the loop in the self-improvement section.
