# Data Paddock Long-Run Prompt — Round 3

Oct 19, 2026 · @George

This is Claude Code's next long run, built from **Data Paddock Review — Round 3** and your decisions D6–D8. It fixes the turn-by-turn colours, makes picking a driver one tap with the teammate built in, gives Expert its own debrief, tightens the stories, and redesigns the site as a circuit atlas. It never stops to ask questions. It records what it decided in each PR, and lists anything only you can do.

## How to use this page

1. Export **Data Paddock Review — Round 3** as Markdown and commit it as `docs/REVIEW_ROUND3.md`.
2. Merge (or let Claude Code open a PR for) the two docs-only commits on `claude/laughing-clarke-t71435`: `docs/BENCHMARKS.md` and the pilot review in PROGRESS.md.
3. Paste everything from "Mission, decisions and rules" down into Claude Code at the repo root.
4. When it asks under "Owner actions", run the pilot story workflow (`stories-only`, rounds `1,12,17`, an explicit `max_new_stories`). `MAX_NEW_STORIES` stays at 0 for the daily run.
5. Edit anything here first. It's yours.

## Mission, decisions and rules

You are the lead engineer on **Data Paddock** (https://gbvparrilla.github.io/data-paddock/). It turns F1 timing data into a story for every driver in every session of the 2026 season, for new fans and for data-curious and diehard fans alike. A midfield driver's story should be as good as the winner's.

Round 2 (PR #6) made the site calm and put real Claude stories live for the pilot rounds; it scores 75/100. Round 3 makes the numbers trustworthy everywhere, makes Expert genuinely different, and gives the site a look of its own.

Read these first:

- `docs/REVIEW_ROUND3.md`: findings #48–#60, the design plan, decisions D6–D8
- `docs/BENCHMARKS.md`: the §7 scorecard is the bar
- `PROGRESS.md`, `CURRENT_TASK.md` and `docs/REVIEW_ROUND2.md`

### The owner's decisions (requirements, not suggestions)

| # | Decision |
| --- | --- |
| D1 | Stories are written by Haiku 5.5. Don't change the model, effort, word limits or call cap; recommend instead |
| D2 | Race page is story-first (summary → classification and key moments → positions → More detail) |
| D3 | Home shows the latest 4 rounds big, then a link to /races |
| D4 | Layout and story work run in parallel |
| D5 | Essential/Expert toggle, verdict-first stories |
| D6 | **Visual direction: Circuit atlas** (Workstream E) |
| D7 | **Expert = engineer's debrief computed in code**; Essential = the short verdict-first story (Workstream H) |
| D8 | **One driver per tap, teammate comparison built in, "Compare with…" for anyone else** (Workstream G) |

### Operating rules

1. **One PR per workstream**, each from the latest `main`. Push only to your working branch; the owner merges.
2. **Never stop to ask questions**, and don't use multiple-choice or interactive prompts. Make the call and record it under **"Decisions made"** in the PR description and PROGRESS.md (what you chose, the alternatives, why, how to undo it). List anything only the owner can do under **"Owner actions"**.
3. **Never decide these yourself**; recommend instead: the story model, effort, word limits, the per-run Claude call cap, and anything personal (a report address).
4. **The owner is credit-conscious.** Don't poll or watch workflow runs; the owner tells you when a run finishes. Every story iteration needs an owner-run pilot, so batch prompt changes into as few pilots as possible.
5. **PROGRESS.md is your memory.** Add a "Round 3" section: a checklist of #48–#60, decisions made, owner actions, scorecard log, "Next 3 actions". Keep `CURRENT_TASK.md` current at every stopping point.
6. **Proof over claims.** "Fixed" means a test, invariant, crawl step or screenshot proves it. Never weaken or delete a test to pass it. `make check` stays green after every commit.
7. **Keep what works.** The declutter, the dedupe, the freshness stamp, the fact-checker and every round 1 and 2 fix stay fixed.

## Workstream F: turn-by-turn that tells the truth

Goal: every corner colour on the site is correct, and a broken breakdown is never shown. This goes first, in its own PR, because it's the one P0.

1. **Find the alignment fault (#48).** 51 of 1,730 breakdowns have a corner off by more than 3s. In Baku FP1, Norris's T1 is +98.9s and the other 19 corners are 0.6–12.5s faster than the session best, so it looks like a lap-start distance offset. Find the root cause in the distance alignment. Likely suspects: telemetry distance not reset at the line, or an out-lap or in-lap sample bleeding in. Anchor each lap on the start/finish line position, or cross-correlate its speed trace with the reference, then recompute the 51.
2. **Plausibility gate.** At export, withhold any breakdown where a corner's delta exceeds max(1.5s, 20% of that corner's time), or where the absolute deltas sum to more than |lap delta| + 3s. Show "Corner times aren't reliable for this lap" instead of a coloured map. Never colour a map from a withheld breakdown.
3. **Purple means fastest of all (#49).** Compute each driver's time through each corner window on their best lap, then rank every driver per corner within the session, as the sector colours already do:
   - purple: fastest of anyone
   - green: top quarter
   - yellow: middle half
   - red: bottom quarter

   Export `corner_ms` and `rank` per corner. The Turn-by-turn tab keeps the delta-to-reference bars, but colour always comes from rank. Remove the absolute-millisecond tiers in `turnTier`.
4. **Invariants**, each naming #48 or #49:
   - no exported corner delta above the plausibility bound
   - exactly one driver is purple at each corner of each session
   - a driver ranked 15th or worse in a sector can't be purple at every corner in that sector
   - the share of purple corners site-wide is below 10%
5. **Crawl check.** Screenshot Baku FP1 with Norris selected (`/race/15?session=71&drivers=19&detail=1`) before and after; the after shot must agree with his sector ranks.
6. **Owner action**, only if the fix needs fresh telemetry: one Site run with the turn-by-turn recompute switch, about 70 minutes of OpenF1 downloads and no Claude calls.

## Workstream G: one driver, teammate built in

Goal: a tap always means "show me this driver", and the most meaningful comparison in F1, the teammate, is already there (D8, #50).

1. **Selection.** Replace `toggleDriver` with `selectDriver(id)`. A tap selects that one driver, replacing any other; tapping the selected driver again clears the selection. The URL carries `drivers=<id>` and an optional `vs=<id>`. Old `drivers=a,b` links open driver a with `vs=b`.
2. **The driver panel**, in order:
   - header and weekend strip
   - the story: Essential, or the Expert debrief from Workstream H
   - the **vs strip**

   The vs strip holds: the two drivers' lines highlighted on the positions chart (selected solid in team colour, the comparison dashed), a small gap-over-time chart, three computed facts (finish, qualifying gap, stops), and the written head-to-head when one exists. There is never a second full driver story stacked below. A link ("Read Ocon's story") switches the selection instead.
3. **Who to compare with.** The default is the teammate *for that weekend*, from `entries` (Lawson's teammate at R12 is Verstappen). If the teammate didn't start or set no time, default to the car that finished next to them. **"Compare with…"** offers, in order: teammate, the car ahead at the flag, the car behind, anyone they shared a stewards' case with, then the full list.
4. **Classification hint.** "Pick up to two drivers" becomes "Pick a driver".
5. **Crawl checks:**
   - tapping a second driver switches the selection and shows no comparison
   - the vs strip appears for every selected driver who started
   - a page with `vs=` set is at most 900px taller than the same page without it
   - `vs=` links restore exactly
   - old two-driver links redirect
6. **Phones.** "Compare with…" opens a plain list. Nothing is hover-only.

## Workstream H: stories v4 and the Expert debrief

Goal: Essential is a short story a new fan enjoys, and Expert is a debrief an engineer would trust. Neither carries the other's baggage (D7, #51–#58, #60). The pilot averaged 3.67 against a 4.3 gate; this round gets it over the line in **one** owner-run pilot.

### The Expert debrief (computed in code, no Claude calls)

Build `debrief` in the fact-sheet pipeline and export it with each driver-session.

- **Race and sprint**
  - stint table: tyre, laps, fuel-corrected average pace, degradation in s/lap, and same-compound pace vs teammate
  - pit stops: lap, pit-lane time, stationary time where published, net places once the cycle settled, and timing relative to any SC or VSC
  - sector ranks
- **Qualifying**
  - segment table: Q1/Q2/Q3 best, margin to the cut line, gap to teammate
  - sector ranks and where the lap lost time
  - tyre runs
- **Practice**
  - run plan: compound, laps, average per stint
  - long-run pace rank, only when at least 3 drivers ran 5+ laps on that compound, with the sample size shown
  - single-lap rank
- **Three numbered findings**, the top-ranked verdict candidates, each one sentence with one number (for example, "Stop on lap 10, two laps before the VSC: lost 1 place").
- **Missing data** shows as — with one tooltip per table. Never as a sentence.

In Expert mode the debrief replaces the prose story. The verdict headline stays on top.

### Essential (written by Claude)

Claude writes the headline (a verdict, at most 12 words), the Essential story (60–90 words: cause → effect, at most 3 numbers, no sector ranks, no pit-lane times) and the weekend arc. Drop the long `narrative_text` and the separate analysis paragraph: the debrief's findings replace them. That also cuts calls and tokens. Keep each field within its existing word limit (D1).

### Prompt v4 and checker fixes

**Checker:**

- accept "35.9C" and other unit suffixes
- check ordinal suffixes ("20nd")
- check sector claims ("final sectors", "weakest") against sector ranks
- check Q1/Q2/Q3 wording against the segment the driver went out in
- check stand-in claims against `entries` instead of banning them; Lawson really was Red Bull's stand-in at R12 (#60)
- reject headlines whose verdict contradicts the net result, such as "undone" or "cost him" for a driver who gained places overall (#52: Russell P19→P9)
- reject any ranking out of fewer than 3 ("1st of 1") (#55)
- write points as integers in arcs ("1 point", not "1.0 points") (#55)
- allow no sentences about missing or unpublished data, and no "indicative", in Essential or arcs (#54). The practice caveat appears once per page in the UI.

**Prompt:**

- weather only when rain changed the order
- no motives or roles that aren't in the fact sheet
- **headline variety (#53):** pass in the headlines already written for that session and require a different construction, and lead with the fact most distinctive to this driver, not the situation the whole field shared

**Data:**

- flag stints that span a pit stop as a data gap (Hadjar R17)
- link race-control incidents on laps 1–2 to any retirement on those laps, so "no stated reason" only appears when there truly is none (#56: Verstappen R12)
- the DNS template must not repeat its own summary (#58)
- the home midfield line must not repeat the driver's name (#57)

### The pilot gate

One owner-run pilot (`stories-only`, rounds 1, 12 and 17) covers all of the above. It passes when all of these hold:

- at least 90% of stories are Claude-written, with 0 published violations
- the same 15 stories scored in round 2 average at least 4.3, with none below 3
- no more than 10% of a session's headlines share a shape
- no missing-data sentences in Essential

If it fails, keep the best version live. Then write a recommendation in the PR (raise Haiku's effort to medium, or Sonnet 5.5 for race and sprint stories only) with the pass rates you measured, and list a second pilot under "Owner actions".

## Workstream E: the Circuit atlas redesign

Goal: nobody mistakes Data Paddock for a generated dashboard. Every race page reads like a sheet from an engineer's circuit atlas: the track drawn large, the story annotated onto it, team colour as the only bright colour (D6, #59). The full plan, palette and wireframe are in `docs/REVIEW_ROUND3.md` under "The new look". Build it after Workstreams G and H, on their new structure.

1. **Tokens** (`index.css`), light by default and dark from the system setting:

   | Token | Light | Dark |
   | --- | --- | --- |
   | Paper | #EEF2F3 | #1A232B |
   | Ink | #17222C | #E4EAEE |
   | Graphite | #56636E | #93A1AC |
   | Rule | #C5CFD5 | #33414C |
   | Timing | purple #8344E0, green #1F9D55, yellow #C99A06 | same |

   Team colours are the only other saturated colour. Check every text pair for WCAG AA in both themes, and adjust a team colour's text use (not its line use) where it fails on paper.
2. **Type.** Self-host Archivo (variable width and weight) as subsetted woff2 in `public/fonts`, and drop Google Fonts:
   - race names and verdict headlines at width 125, weight 800
   - body text at width 100, weight 400
   - tables and timings at width 75 with tabular figures

   Sentence case throughout.
3. **The race sheet** (race page hero):
   - the circuit drawn large on a faint dot grid, with registration marks at the sheet corners
   - corner numbers as callouts with leader lines
   - the 30-second summary set beside the drawing as its caption
   - a **title block** in the drawing's corner (round, date, laps, winner, DNF and DNS, "data through round N") replacing the stat chips and any middle-dot meta
4. **Pinned key moments, the signature.** Each key moment gets a number. When the data names a place (race-control messages such as "turn 3", or a pit stop at the pit lane), its number is pinned to that spot on the drawing. The rest sit in the margin in lap order. The key moments list uses the same numbers.
5. **Picking a driver** recolours the drawing with that driver's sector and corner ranks (Workstream F), and their panel (Workstream G) opens below as the next sheet.
6. **Home.** The 4 latest circuits drawn large with the winner's colour, and the championship as a gap ladder (bars measuring each driver's gap to the leader). `/races` and standings use the same tokens.
7. **Charts.** Ink axes, graphite gridlines, team-coloured lines, teammates dashed. No chart-library default styling left.
8. **One motion moment.** On a race page's first view, the track draws itself in ink (about 1.2s), then the winner's colour traces one lap. Nothing else animates on load, scroll or hover. `prefers-reduced-motion` gets the finished drawing.
9. **Remove the generic tells:**
   - rounded panels (radius 0 on sections, 3px only on buttons and inputs)
   - all-caps or tracked eyebrow labels
   - meta strings joined with middle dots
   - → in link and button text
   - near-black backgrounds
   - identical cards used as the default container

   Whitespace separates sections. The sheet border appears only around drawings.
10. **Design lint** (`scripts/check-design.mjs`, run by `npm run lint`). It fails on `uppercase` or `tracking-` classes on labels, → in link text, `' · '`-joined meta in components, and border radius over 3px outside controls.
11. **Open Graph images** regenerate in the new style: track drawing plus verdict headline.
12. **Done when.** Before/after screenshots at 1360px and 375px of home, `/race/1`, `/race/1/driver/gasly` and the same in Expert, in light and dark, are in the PR. Lighthouse holds performance at 90 or above and accessibility at 95 or above on mobile.

## Order, loop and exit

### Order of work

1. **PR 1: Workstream F** (turn-by-turn). The only P0, and small.
2. **PR 2: Workstream H pipeline.** Checker, prompt v4, data fixes and the `debrief` data. Then list the pilot under "Owner actions" and stop working on stories until the owner reports it finished.
3. **PR 3: Workstreams G and H UI.** One-driver selection, the vs strip, the Expert debrief view, and a methods page explaining every computed number in the debrief (fuel-corrected pace, degradation, net places, sector and corner ranks). Build this while the pilot runs.
4. **PR 4: Workstream E** (Circuit atlas), on top of PR 3's structure.
5. **After that**, one small PR each: spoiler-free mode, follow a driver on home, a public changelog. Record each under "Decisions made" so the owner can drop any of them.

### The loop (after each PR is merged)

1. Crawl the local production build, then the live site once the owner says it's deployed (`E2E_BASE_URL=https://gbvparrilla.github.io/data-paddock/`).
2. Score the BENCHMARKS §7 scorecard with evidence and log it in PROGRESS.md. Round 3 started at **75/100**.
3. Score the five personas from 1 to 10: new fan, data-curious fan, diehard, website critic, data engineer. Use screenshots in light and dark, plus 5 random stories, at least 2 from outside the top 10.
4. Fix the lowest-scoring, highest-severity item first, with a test that would have caught it. Number new findings from #61.
5. Raise the bar when a persona scores 9 or more twice in a row.
6. **Drift guards:**
   - a new default-visible panel, label, underline or colour needs a written reason
   - design lint stays clean
   - never remove a working feature to raise a score

### Exit criteria (all at once)

- \#48–#60 fixed with linked evidence, or "won't fix" with a reason.
- Scorecard at least **85/100**, with every section A row at 2.
- Every turn-by-turn invariant passes, and fewer than 10% of corners are purple site-wide.
- The pilot gate passes. Then the owner's full-season run (listed under "Owner actions") gives at least 90% Claude-written stories with 0 published violations.
- Every persona scores at least 9 on two passes in a row, in both themes.
- `make check` is green, and the crawl is green against the live URL on desktop and mobile.
- PROGRESS.md ends with a Round 3 report: before/after scores and screenshots, Claude calls and pass rates, decisions made, owner actions done, and what's next (live sessions, which `sessions.status` still supports).

### First actions

1. Read the files listed under "Mission, decisions and rules", and add the Round 3 section to PROGRESS.md.
2. Reproduce #48 on Baku FP1 Norris and #49's 25% purple share in a failing invariant.
3. Fix and open PR 1, then start PR 2.
