# Data Paddock Review — Round 3

Oct 19, 2026 · @George

Round 2 worked. The site is calm, it passes the ship gate for the first time, and real Claude stories are live for rounds 1, 12 and 17. It scores 75 out of 100, up from 65. All four of your concerns are real: turn-by-turn colours are wrong in two separate ways, comparing is clunky, Expert changes almost nothing, and the look is the generic dark-card template.

## Scorecard

Scored on the 42-row scorecard in `docs/BENCHMARKS.md` §7: each row 0, 1 or 2, with section A counting double. Section A has no zeros now, so the ship gate passes.

| Section | Round 2 | Round 3 | Max | What still costs points |
| --- | --- | --- | --- | --- |
| A. Trust and accuracy (×2) | 24 | 26 | 32 | Corner colours contradict sector ranks; factual slips in pilot stories; 69 stories talk about missing data |
| B. First five minutes | 10 | 14 | 14 | Nothing; the declutter fixed this section |
| C. Depth for data fans | 6 | 7 | 16 | Expert adds almost nothing; no lap drill-down; no methods page; turn-by-turn untrustworthy |
| D. Storytelling | 9 | 10 | 12 | 63 stories share a headline shape with another driver in the same session |
| E. Sharing and return visits | 6 | 7 | 12 | No spoiler-free mode, no share card, follow-a-team only on /races |
| F. Craft and engineering | 10 | 11 | 14 | No changelog; no feedback route without GitHub |
| **Total** | **65** | **75** | **100** | Claude Code's own estimate was about 78 |

## Your four concerns

All four are real, and each has a specific cause.

### 1. Turn timings show purple everywhere

There are two separate bugs.

- **Broken alignment in 51 of 1,730 breakdowns (3%).** In Baku FP1, Norris's Turn 1 reads +98.9s and his other 19 corners each read 0.6–12.5s *faster* than the session-best lap. So the map is purple everywhere while his sector ranks say 4th, 9th and 20th. It hits 18 sessions: 7 FP1, 6 races, 1 sprint and 4 others. The invariant only checks that corners add up to the lap, and these still add up.
- **The wrong meaning for purple.** `turnTier` paints a corner purple whenever a driver beats the *reference lap* by 30ms there, but the legend says "Fastest of all". With a session-best reference that happens a lot: 25% of all corners on the site are purple. Purple has to mean fastest of anyone through that corner, ranked across every driver's best lap, the same way the sector colours already work.

### 2. Comparison is clunky

One tap does three different things. The first tap selects a driver, the second adds a comparison instead of switching, and the third throws both away. Someone trying to switch from Gasly to Ocon lands in a head-to-head, and the page grows from 3,300px to 4,770px with two full driver stories stacked. Your idea is better: a tap always selects one driver, and the teammate comparison is built into their panel.

### 3. Essential and Expert are nearly the same

Expert adds a fourth key number, one line of sector ranks, and opens the same story text that Essential hides behind "Read the full story". The prose is identical in both modes. It needs a different format, not just more of the same.

### 4. It looks generic

It hits four of the five traits the design guidance lists as tells of generated pages:

- a near-black background with bright accents
- the same rounded card on every panel
- all-caps eyebrow labels ("THE RACE IN 30 SECONDS", "DRIVERS' CHAMPIONSHIP")
- meta strings joined with middle dots, and → arrows on links

Nothing about it says F1 except the track outlines, which are the best visual asset on the site and are used as thumbnails.

## Pilot stories

The stories are a big step up from the templates. I agree with Claude Code's 3.67 out of 5, and I'd put my own read at about 3.6. The best are good: "Pitting just before the VSC was unlucky for Gasly" and "Russell won by taking the lead for good on lap 27" each explain a result in one line.

**Where I agree with Claude Code.** I confirmed these four in the published JSON: Verstappen's "fastest in both final sectors" (he was 1st in S1 and S3, 6th in S2), Hadjar's "softs over laps 2–62" despite a lap-33 stop, Gasly's "missed Q2" for a Q2 exit, and the weather temperatures.

**One correction.** Claude Code calls Lawson's "standing in for Red Bull" at Zandvoort invented. It isn't. Lawson drove Hadjar's Red Bull at rounds 12–14, and the site's own entries table marks him as a stand-in there. Banning the phrase would remove a true fact. The checker should verify stand-in claims against `entries` instead.

**What Claude Code's review missed** (counted across all 324 pilot stories and 202 arcs):

| Pattern | Count | Example |
| --- | --- | --- |
| Same headline shape as another driver in that session | 63 stories | 10 drivers in R12 FP1 get "X's long-run pace beat his single-lap place"; Gasly and Ocon both get "Pitting just before the VSC was unlucky for X" |
| "Indicative" boilerplate on practice pace | 104 stories | "the pace order is only indicative" |
| Talking about data that isn't published | 69 stories | "Stationary times are not published for this race, so the data gives no figure for them" |
| Rankings out of one | 3 stories, 6 arcs | "1st of 1 on medium", "ranked 1 of 1" |
| Points as decimals | 52 arcs | "for 1.0 points" |
| Headline verdict that misreads the outcome | spot-checked | Singapore: "Russell's climb from P19 was undone by a stop under the VSC", for a driver who went P19 to P9 |
| The biggest moment reduced to "no stated reason" | spot-checked | Zandvoort: "Verstappen's race ended on lap 1 with no stated reason"; race-control messages on laps 1–2 aren't linked to the retirement |

**The structural problem.** One prose story is trying to serve both audiences, so it carries sector ranks a new fan doesn't want and hedges an expert doesn't need. Splitting Essential (story) from Expert (debrief) fixes most of the patterns above at the source.

## Round 2 fixes

10 of the 12 findings from round 2 are fixed. Two are partly done.

| # | Finding | Status | Evidence |
| --- | --- | --- | --- |
| 36 | No AI stories live | Partly | 425 Claude-written stories for rounds 1, 12 and 17; 1,866 others still templates until the full-season run |
| 37 | Footer claimed Claude wrote template stories | Fixed | Footer is neutral; one accurate source line per page |
| 38 | Facts repeated across panels | Fixed | Australia: Verstappen's climb appears once, in Key moments |
| 39 | Summary missed how the race was won | Fixed | Zandvoort: "Norris took the lead for good from Hamilton on lap 54" |
| 40 | Template prose read like a log | Fixed | "His only stop, on lap 10, came just before a Virtual Safety Car" |
| 41 | Turn-by-turn empty | Partly | 1,730 breakdowns exported, but see #48 and #49 |
| 42 | No freshness stamp | Fixed | "Data through round 17 · updated 19 Oct" |
| 43 | Season page title | Fixed | "2026 standings · Data Paddock" |
| 44 | DNS car had a tyre bar | Fixed | Hülkenberg row gone from Australia's strategy chart |
| 45 | Pts cut off on phones | Fixed | Pts visible at 375px; Stops and Grid hidden |
| 46 | Pages too long | Fixed | Australia 2,986 → 1,925px; phone home 7,596 → 3,418px; underlines 19 → 4 |
| 47 | Lint warnings | Fixed | 0 warnings |

All 49 unit tests, all 232 data invariants (2 skipped offline) and all 18 crawl tests pass.

## New findings

Numbering continues from round 2.

| # | Sev | Finding | Evidence |
| --- | --- | --- | --- |
| 48 | P0 | Turn-by-turn alignment broken in 51 breakdowns | Baku FP1 Norris: T1 +98.9s, the other 19 corners 0.6–12.5s faster than the session best; 18 sessions affected; the reconciliation invariant still passes |
| 49 | P1 | Purple means "beat the reference by 30ms", not "fastest of all" | 25% of all corners are purple; the legend says "Fastest of all" |
| 50 | P1 | Selecting drivers is ambiguous | The second tap compares, the third resets; the compare page reaches 4,770px |
| 51 | P1 | Expert barely differs from Essential | Same prose; adds one number and a sector line |
| 52 | P1 | Factual slips in pilot stories | Verstappen's sectors (R17 Q), Hadjar's stint (R17 R), Q2 vs Q3 (R1 Q Gasly), Colapinto's headline (R12 R), Russell's "undone" (R17 R) |
| 53 | P1 | Repetitive headlines within a session | 63 stories share a headline shape with another driver |
| 54 | P2 | Talking about missing data | 69 stories; "indicative" boilerplate in 104 |
| 55 | P2 | Rankings out of one, decimal points | "1st of 1" in 3 stories and 6 arcs; "1.0 points" in 52 arcs |
| 56 | P2 | A lap-1 retirement with "no stated reason" | Zandvoort Verstappen; incident messages on laps 1–2 aren't linked to retirements |
| 57 | P2 | Home repeats the driver's name | "Isack Hadjar. Isack Hadjar climbed from P22 to P10" |
| 58 | P2 | A template repeats its own summary | Piastri DNS (R1): the full story equals the summary, word for word |
| 59 | P1 | The look is the generic dark-card template | Near-black, identical rounded panels, all-caps eyebrows, middle dots, → arrows |
| 60 | P2 | The checker would ban a true fact | The "standing in" rule proposed for prompt v4; Lawson was Red Bull's stand-in at R12 |

## The new look: Circuit atlas

Every race page becomes a sheet from an engineer's circuit atlas: the track is drawn large, the story is annotated onto it, and team colour is the only bright colour. The site's best asset, the circuit outline, moves from thumbnail to centrepiece.

**Palette.** Light is the default. Dark follows the system setting.

| Token | Light | Dark | Use |
| --- | --- | --- | --- |
| Paper | #EEF2F3 | #1A232B | Page background: cool drafting paper, not cream; dark slate, not black |
| Ink | #17222C | #E4EAEE | Text and the track line |
| Graphite | #56636E | #93A1AC | Secondary text, leader lines |
| Rule | #C5CFD5 | #33414C | Hairlines, the dot grid |
| Team colour | per team | per team | The only saturated colour: driver lines, selected traces |
| Timing | purple #8344E0 · green #1F9D55 · yellow #C99A06 | same | Data only: fastest of all, top quarter, middle half; bottom quarter in graphite |

**Type.** One family, Archivo, using its variable width axis:

- race names and verdict headlines at width 125, weight 800
- body text at width 100, weight 400
- tables and timings at width 75 with tabular figures

Sentence case everywhere: no tracked all-caps labels.

**Layout.** The race page reads like a drawing sheet.

```
┌ sheet ───────────────────────────────────────────────────────┐
│ Australian Grand Prix                                            │
│                     T6 ─╮  ① L11 Hadjar retires                    │
│   Russell won from    ╱   ╰───╮           T8                     │
│   pole and led for   │  ·  ·  · ╲──────────╮                     │
│   good from lap 27.   ╲  ② L12 VSC          ╲ T11              │
│                        ╰── T1 ───── T14 ────╯                  │
│                                     ┌ title block ─────────────┐ │
│                                     │ Round 1  8 Mar  58 laps  │ │
│                                     │ Winner Russell │ thru R17 │ │
│                                     └────────────────────────────┘ │
└────────────────────────────────────────────────────────┘
  Classification (hairline rows)    │  Key moments ① ② ③ … (same numbers as on the drawing)
  Positions by lap — "Russell led from lap 27"
```

- **The signature.** Key moments are numbered annotations pinned to the corner where they happened when the data says where (race-control messages often name a turn). The rest sit in the margin, in lap order. The 30-second summary is written beside the drawing as its caption.
- **The title block.** It's the drawing sheet's own device. It replaces middle-dot meta strings and the stat chips: round, date, laps, winner, DNF and DNS, "data through round 17".
- **Picking a driver** recolours the drawing to that driver's sectors and corners, and their panel opens below as the next sheet.
- **Home** draws the 4 latest circuits large, with the championship as a gap ladder beside them.
- **Motion.** One moment only. On a race page's first load the track draws itself in ink (about 1.2s), then the winner's colour traces one lap. Nothing moves on scroll or hover, and reduced-motion users get the finished drawing.

**Rules that keep it from looking generated:**

- no rounded cards (radius 0 on sections, 3px only on buttons and inputs)
- no all-caps eyebrows, middle-dot meta strings or → on links
- no near-black
- colour only for teams and timing
- whitespace separates sections; the sheet border and its corner registration marks appear only around the drawing

**Checked against the defaults.** Hairlines and zero radius alone would read as the broadsheet template. What makes this specific to F1 is the drafting devices: dot grid, leader lines, corner callouts, title block and registration marks, plus annotation pinned to the track. There are no newspaper columns.

## Your decisions

These are new this round. Round 2's decisions D1–D5 still stand.

| # | Decision | You chose | Alternatives | What it means |
| --- | --- | --- | --- | --- |
| D6 | Visual direction | Circuit atlas | Pit wall timing screen, race programme, polish the current look | A full visual redesign (Workstream E), built on the plan above |
| D7 | Expert mode | Engineer's debrief | A longer story with more data, story pinned to the chart | Essential stays a short verdict-first story. Expert swaps it for a structured debrief computed in code: stint table, pace vs teammate and rivals, and 3 numbered findings, each with its number |
| D8 | Picking drivers | One driver, teammate built in | Keep two picks and fix the toggling | A tap always selects one driver. Their panel shows a vs-teammate strip, with "Compare with…" for the car ahead, the car behind, or anyone else |

The debrief is computed in code, not written by Claude. That cuts Claude calls and removes most of the places stories can go wrong. Claude only writes the Essential story and the weekend arc.

## Method and sources

This workspace can't reach github.io, so I rebuilt the site exactly as the Checks workflow does. I used `main` at 3ab9aa4 (PR #6 merged) with the latest `db-snapshot` (the pilot run), upgraded with no ingest and no Claude calls, then built, exported and prerendered.

- Tests: 49 unit, 232 invariants (2 skipped offline), 18 crawl tests, all passing.
- My pass: screenshots at 1360px and 375px of home, standings, /races, Australia (no driver, Gasly in Essential and Expert, Gasly vs Ocon), Zandvoort (race; Bottas in qualifying), Singapore (race; Hadjar), and Baku FP1 with Norris's broken corners.
- Story sweep: all 324 Claude-written pilot stories and 202 arcs scanned for the patterns above; 10 stories read in full against the data.
- Claude Code's pilot report and handoff (`PROGRESS.md`, `CURRENT_TASK.md` on `claude/laughing-clarke-t71435`).
- Design: the frontend-design guidance's list of generated-page tells, and BENCHMARKS.md.

Sources: [Data Paddock repo](https://github.com/GBVParrilla/data-paddock) · [live site](https://gbvparrilla.github.io/data-paddock/) · [Red Bull confirm Hadjar to miss Dutch GP as Lawson steps up — Formula1.com](https://www.formula1.com/en/latest/article/red-bull-confirm-hadjar-to-miss-dutch-grand-prix-as-lawson-steps-up-and-yuki-tsunoda-returns.3D3k7oc9dUwwEBZC7upjR1)
