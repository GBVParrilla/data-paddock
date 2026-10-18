# Data Paddock — Full Site Review

**Site:** https://gbvparrilla.github.io/data-paddock/
**Reviewed:** 17 Oct 2026, after round 17 (Singapore)
**Method:** Every page was opened in a real browser and fully reloaded each time. Covered: the home page, all race pages (Australia R1, Dutch R12 and Singapore R17 in depth), every session tab (FP1, FP2, FP3, Sprint quali, Sprint, Qualifying, Race), clicking a driver, two-driver comparison, the Tyre strategy, Sectors and Turn-by-turn tabs, driver and constructor standings, the season story, and a 375px mobile viewport. I also audited the published JSON for all 85 sessions with scripts, and spot-checked facts against real-world 2026 news.

---

## The short version

The bones of this project are genuinely good. Most F1 fan sites don't have the design language, the track-outline grid, the turn-by-turn corner analysis, or the depth of data you have. But the site breaks trust in three ways a fan will notice within five minutes:

1. **You can't navigate it.** Clicking anything that changes page shows a blank screen until you refresh.
2. **The stories get facts wrong**, and one shows raw machine output to the reader.
3. **Some numbers are simply wrong**: constructor standings, retirement counts, and corner deltas that don't add up.

A data-storytelling site lives and dies on credibility, so these come before any new feature.

---

## Severity-ranked bug list (evidence included)

### P0: breaks the product or its credibility

| # | Bug | Evidence |
|---|---|---|
| 1 | **Navigating within the app crashes to a blank page.** Every page change from inside the app fails. Only a full reload works. | Console: `Uncaught TypeError: l is not a function` in React's effect-cleanup routine (`Sl` → `l()` on the stored `destroy`). Root cause: a `useEffect` returns something that isn't a function, e.g. `useEffect(async () => …)`, or an arrow that implicitly returns `null` or a value. React calls it as a cleanup when the page unmounts. A fresh load never unmounts, which is why refreshing "fixes" it. |
| 2 | **Raw model output leaks into a published story.** | The Australia race story for Esteban Ocon, in the strategy section, ends with `…cannot isolate.}<br>BAD_FORMAT_FIXED_BELOW>{}` |
| 3 | **Driver stories state false facts.** | Gasly (Aus race): "qualified P14… one place behind teammate Franco Colapinto". The qualifying table shows Gasly P14 and Colapinto P16. Hadjar season story: "He sits 97 points behind the leader's 340". It's actually 243 behind; 97 is his total. Piastri (Aus): "his climb from P9 to P5 on lap 18 coincided with the first Virtual Safety Car", but the first VSC was on lap 12. Hadjar's list of finishing positions is out of order. |
| 4 | **Each driver is stored with one team for the whole season, so constructor standings are wrong.** | Lawson drove for Red Bull at rounds 12–14 while Hadjar was injured (confirmed by formula1.com). The site lists him as Racing Bulls on the Dutch GP page, which then shows three Racing Bulls cars (LAW, TSU, LIN). Red Bull's 318 points = VER 221 + HAD 97 exactly, so Lawson's Red Bull points went to Racing Bulls (114 = 75 + 38 + 1). *(This flaw came from my earlier backend spec: `drivers(…, team, …)`. Team has to be stored per driver per event.)* |
| 5 | **Strategy analysis gets basic race logic backwards.** | Gasly: "The stop came just *before* the lap 12 VSC, which *may have reduced* the time lost". Pitting before a VSC is the unlucky case; pitting during one is the cheap stop. Ocon: "the Hard field average was 1:25.457, which is 2.582s off Hamilton's compound best" means nothing. |

### P1: wrong or misleading data

| # | Bug | Evidence |
|---|---|---|
| 6 | **Drivers who never started (DNS) are labeled DNF.** | Australia: Piastri's story correctly says he did not start, but the table shows "DNF". The Fastest Lap card says "3 did not finish" while the table lists 5 DNFs. Standings show him "21" for R1 instead of DNS. Hülkenberg (0 laps) looks the same. |
| 7 | **Qualifying classification is missing drivers and mixes times from different segments.** | Australia Q shows 19 of 22 drivers. Verstappen (started P20), Sainz and Stroll are absent. Verstappen starting P20 is one of the race's biggest stories and nothing explains it. Gaps aren't in order: P9 Lindblad +2.729 but P10 Bortoleto +1.703. Q3 and Q2 times are compared as if they were the same. The "Gap pole to P10" card inherits the same problem. |
| 8 | **The corner breakdown doesn't add up.** | Gasly's Turn-by-turn says "Total +5.880s". The 14 corner bars sum to +3.462s. His best lap (1:24.486) minus the session best (1:22.091) is +2.395s. Three figures that should agree give three different answers. |
| 9 | **"Key moments" are mostly routine pit stops, not pivotal moments.** | Australia lists a P15→P19 pit stop and a P16→P19 slow stop. It never mentions Hadjar retiring from P3, Piastri not starting from P5, or Verstappen's recovery from P20. Singapore's key moments are 5 pit stops in a row, all "compound unknown", even though the stint data for that race has a compound for every stint. The generator's join is broken. |
| 10 | **Python `None` shows on the page.** | Australia FP1: "Virtual Safety Car deployed on lap None". |
| 11 | **Pit stop stationary time is missing for most of the season.** | Data audit: in 11 of 17 Grands Prix (R5, R6, R8, R9, R11–R17), 100% of pit stops have no stationary time. The UI repeats "stop time unknown" and the stories hedge around it. |
| 12 | **The race lap count is off by one.** | Australia position data ends at lap 57, but the tyre chart and race distance say 58. |
| 13 | **The classification sort puts a DNF between finishers.** | Singapore: 17 PER, then DNF ALB, then 19 BOT. |
| 14 | **The third VSC is missing from key moments.** | Piastri's story mentions VSCs on laps 12–14, 18–20 and 34. Key moments shows only two. |
| 15 | **Teammate comparisons are skipped for non-teammates.** | Comparing Gasly and Ocon, who ran together all race and had a stewards' investigation together, shows "Written head-to-heads cover teammates." The most interesting battles get no story. |
| 16 | **The two drivers' stories disagree with each other.** | Ocon's story describes a Turn 3 incident with Gasly that the stewards investigated. Gasly's story doesn't mention it. Ocon's says he ran next to Gasly "for 54 laps". Gasly's says his notable neighbour was Bortoleto for six. |

### P2: UX, presentation, polish

| # | Issue |
|---|---|
| 17 | The position chart y-axis stops at P20 with 22 cars, so lines run below the axis. |
| 18 | Teammates share an identical line colour on the race position chart. The standings chart already solves this with dashed lines, but the race chart doesn't use it. |
| 19 | "Hover a line, click to select" is the only instruction on mobile, where there's no hover. |
| 20 | Sector labels mix up their reference point. "+0.810s · Around average" and "+0.267s · Faster than average" are gaps to the session *best*, labeled against the *average*. Rank 11/20 is called "faster than average". |
| 21 | Texts say "ranked 16th of 20" when 22 cars raced, with no explanation of who's excluded. |
| 22 | Unknown tyre compounds show as an unlabeled dark grey bar with "?" and no legend entry. The race winner's opening stint in Australia is "unknown". |
| 23 | The year dropdown has a single option (2026). |
| 24 | Every page has the title "Data Paddock" and no social preview image. Hash URLs (`#/race/1`) aren't indexed, and shared links preview as nothing. |
| 25 | One 669 KB JavaScript bundle with no code-splitting. The home page fetches 17 track-outline files and every race page fetches roughly 700 KB of detail JSON. |
| 26 | Card text repeats itself: "Was P12 on single-lap pace but 3rd on soft long-run pace… Was P12 on single-lap pace but 1st on hard long-run pace." |
| 27 | Event names read as bare adjectives ("Spanish", "Italian", "Dutch"). |
| 28 | "Races" and the logo both go to the same page, so there's no separate races index. |
| 29 | "Report an error" opens a GitHub issue form, which a casual fan without a GitHub account can't use. |
| 30 | On mobile, four stacked highlight cards push the actual data about 1,000px down the page. |

**Corrections to what I told you earlier:** "Bahrain in Malaysia" is **correct**. The 2026 Bahrain GP really was held at Sepang. The home page **does** have the 4-per-row track-outline grid. My earlier text-only read missed it.

---

## Perspective 1: A brand-new F1 fan

*"My friend got me into Drive to Survive, I want to understand what happened in Singapore."*

The home page is the best part of the site. Track shapes, the winner's team colour, a podium per race and a clean dark look make it feel premium, and I understand it immediately.

Then I click Singapore and get a black screen. I'd assume the site is broken and leave. Most new fans will never press refresh. **This one bug means a large share of first-time visitors never see a race page.**

If I do get in, I'm hit with "Sprint quali", "SQ", "Stops", "+/−", "VSC", "Lapped", "stint", "compound", "long-run pace", "undercut". None of it is explained. There's no glossary, no tooltip, no "what is a VSC?". The colour coding (purple, green, yellow) is never explained for someone who doesn't know F1's timing colours.

The stories are the feature I came for, and they're the hardest part to read. Gasly's race story is one ~280-word paragraph containing 25+ numbers: "averaged 1:26.435 early and 1:25.691 late… starting at 1:34.068 on the early laps". That's a data log written in sentences. I wanted "Gasly had a quiet, solid race: one early stop, a long run on hard tyres, and he picked up the last point." Then show me numbers if I ask.

The "Weekend in context" section repeats most of the race story I just read.

**Verdict: 4/10.** Gorgeous front door, then a crash, then a wall of jargon.

---

## Perspective 2: A fan who wants to get into the data

*"I watch every race. I want to understand why things happened, and learn to read the numbers myself."*

This is the audience the site serves best right now. The Turn-by-turn tab, showing time gained or lost at each corner against the reference lap, is genuinely something I can't get anywhere else for free. The weekend strip (FP1 P18 → FP2 P16 → FP3 P15 → Q P14 → R P10) is a great idea. Comparison mode with a lap-by-lap gap chart is exactly what I wanted.

But I'm using the numbers to learn, and the numbers contradict each other. The turn-by-turn total, the bar sum and the lap delta are three different values. Qualifying gaps don't decrease down the order. The fastest-lap card says 3 DNFs, the table shows 5. Once I spot one of these I stop trusting all of it, and this site's entire value is that I can trust it.

The site never teaches me how to read a chart. There's no "how to read this" for the tyre strategy, no explanation of what a long run is or why 5 laps is enough to count, and no explanation of what "reference lap" means. The "Interpretation" label on strategy analysis is a good instinct. But that section hedges every sentence ("may have", "it is hard to say", "the evidence does not support a strong conclusion either way") until it says nothing. Gasly's ends with "an undercut-style earlier stop may have been worth testing, but the evidence does not support a strong conclusion either way." That's 180 words to say "we don't know."

**Verdict: 6/10.** The best raw material on the web for this audience, undermined by internal contradictions and analysis that won't commit.

---

## Perspective 3: The diehard

*"I've watched since 2005. I know what a delta is, I read the FIA documents, I want the stuff Sky won't show me."*

You got the Lawson/Red Bull swap wrong, and that's disqualifying. Hadjar's injury and the rounds 12–14 driver shuffle was a major storyline of 2026. Your site shows three Racing Bulls cars at Zandvoort and credits Lawson's Red Bull points to the wrong team. Hadjar's season story doesn't mention he missed three races. A diehard closes the tab at that point.

The "Key moments" are not key moments. The biggest stories of Australia were a Red Bull qualifying P3 and retiring, a McLaren starting P5 and not taking the start, and Verstappen coming from P20 to P6. Your list instead shows Colapinto losing four places in a pit stop. "Largest swings" based on position changes through pit cycles is the wrong metric. Every routine stop looks like a swing.

The strategy analysis has the VSC logic backwards: it says pitting just before a VSC reduced the time lost. Anyone who has watched one season knows that's the unlucky case. If the analysis can't get VSC timing right, I don't believe its undercut opinions either.

Missing stationary times for 11 of 17 races means there's no real pit-stop analysis. The long-run "pace rankings" use 5–6 lap samples with no fuel correction and no traffic filter. You call Bottas "2nd on soft long-run pace" in FP1 off five laps, which is noise presented as a stat. Sprint weekends are handled structurally (SQ/S tabs exist) but the quali gaps mix segments.

What I'd actually love: a quali segment view (Q1/Q2/Q3 with the cutoff line and who survived by how much), gap-to-car-ahead charts, undercut/overcut verdicts computed from real in-lap/out-lap deltas, tyre degradation slopes per compound per team, and incident timelines from race control. The data for most of this is already in your JSON.

**Verdict: 3/10 today.** It could reach 9/10, because the infrastructure is there, but right now it fails the basic accuracy test this audience applies first.

---

## Perspective 4: Website critic

**Visual design: 8/10.** Restrained dark palette, confident type, strong hierarchy on the race page header, good card system. The track grid on the home page is distinctive and on-brand. The standings heatmap of finishing positions is lovely. This looks like a real product.

**Engineering quality as experienced: 2/10.** The SPA crashes on in-app navigation, the single most common action. There's no error boundary, so one throwing component blanks the whole page with no message, no retry and no way home. There are no loading skeletons. The bug ships to production because there's evidently no test that clicks a link.

**Content design: 4/10.** Stories are walls of text with no subheadings, no pull-out facts and no progressive disclosure. The "Interpretation" chip is good, but there's no length tier for new versus deep readers. Highlight cards repeat each other (Midfield Story = first "Beyond the podium" card on both pages I checked).

**Mobile: 6/10.** No horizontal overflow, which is good. Stacked cards are tall. Hover-only chart interactions. The 22-line position chart is unreadable at 375px.

**Accessibility: 5/10.** Tested lightly. Most SVGs have labels, buttons have names and `lang` is set, but the charts have no data-table alternative, meaning relies on colour alone in places (sector colours, compound colours, team colours), and several grey-on-dark labels look low-contrast.

**Discoverability and sharing: 2/10.** Hash routing, an identical title on every page and no Open Graph image. When someone shares "look at Hadjar's Singapore race" in a group chat, the preview is blank.

**Trust signals: 7/10.** The footer attributes OpenF1, Jolpica and MultiViewer, says "Not affiliated with Formula 1", and labels stories "Written by Claude from timing data". The prefilled "Report an error" link is a thoughtful touch, just the wrong channel for casual users.

---

## Perspective 5: Professional data engineer / computer scientist

**Architecture: smart choice, inconsistently executed.** Pre-rendering everything to static JSON on GitHub Pages is the right call. It's cheap, fast, and needs no server or API key at runtime. But the payloads aren't shaped for the views: around 700 KB of `detail.json` per race, every `headline.json` shipping all 34 drivers in the database, and the home page fetching 17 outline files to draw thumbnails that could be inlined into `events.json`.

**Data model: has a real flaw.** `drivers.team` is a single value per driver. Teams belong to a driver *per event* (an entry list). That one design error corrupts constructor standings, race-page colours, team labels and stories wherever a driver switches seats. The fix is an `entries(event_id, driver_id, team_id, car_number)` table, and every team lookup joins through it.

**Status is a string, but should be an enum.** DNS, DNF, DSQ, Lapped and Classified are different things with different display and scoring rules. Today DNS is folded into DNF in the UI while the stories say "did not start". The UI and the stories read different fields, which is how they end up disagreeing.

**No invariants, so contradictions ship.** Every bug in the P1 list would be caught by a 20-line assertion:
- the sum of corner deltas equals the lap delta (within a tolerance)
- qualifying gaps are in order *within* a segment
- the DNF count in the summary equals the DNF rows in the table
- the max lap in `position_by_lap` equals race distance for classified finishers
- constructor points equal the sum over entries, and match Jolpica's official constructor standings
- the number of qualifying classification rows equals the entry list
- no `None`, `null`, `undefined` or `NaN` appears in any user-facing string

None of these exist. The pipeline needs a validation stage that fails the build.

**The LLM layer has no guardrails after generation.** The model is told not to invent facts, but nothing checks that it didn't. Every number in a story can be matched against the fact sheet automatically. Arithmetic claims ("97 points behind") can be recomputed. Leaked formatting (`BAD_FORMAT_FIXED_BELOW`) can be caught by a schema check on structured output. Right now prompt instructions are the only safeguard. It should be: generate structured JSON, validate it, fact-check it, retry on failure, and only then publish.

**The analytics are statistically naive.** "Long-run pace" over 5 laps with no fuel or traffic correction isn't a ranking. Pivotal moments ranked by raw position change are dominated by pit cycles. That's a known pitfall; you need position change *net of the pit cycle* (position N laps after everyone has stopped) or on-track passes only. Hedging in the strategy text is a symptom: the model hedges because the pipeline never computes the counterfactual. Compute it deterministically (e.g. undercut: rival's out-lap + pit loss versus your in-lap at the same lap), hand the model the result, and let it narrate a conclusion it can defend.

**Frontend: the crash shows there are no end-to-end tests.** One Playwright test that loads the home page, clicks a race, clicks a driver and asserts no console errors would have caught it. There are also no error boundaries, and no route-level code-splitting in a 669 KB bundle.

**Scorecard:** data model 4/10 · pipeline robustness 3/10 · analytics rigor 4/10 · LLM safety 3/10 · frontend engineering 3/10 · infrastructure choice 8/10.

---

## What's genuinely good (keep these)

- The track-outline grid on the home page, and the outline-as-hero on race pages with numbered corners
- Turn-by-turn corner deltas: novel and valuable once the numbers reconcile
- The weekend strip (FP1 → R positions) on every driver
- Comparison mode with a lap-by-lap gap chart
- The standings heatmap and title-fight chart (dashed lines for teammates)
- The "Interpretation" chip separating analysis from facts
- The "Beyond the podium" section: the midfield mission is visible in the UI
- Prefilled error reports that carry the exact story ID and page
- Static JSON on GitHub Pages: cheap, fast, no runtime secrets
- Honest attribution and a non-affiliation note

## Sources used for fact-checks

- [Malaysia to host the 2026 Bahrain Grand Prix — GrandPrix.com](https://www.grandprix.com/news/malaysia-to-host-2026-bahrain-grand-prix.html)
- [Red Bull confirm Hadjar to miss Dutch Grand Prix as Lawson steps up and Tsunoda returns — Formula1.com](https://www.formula1.com/en/latest/article/red-bull-confirm-hadjar-to-miss-dutch-grand-prix-as-lawson-steps-up-and-yuki-tsunoda-returns.3D3k7oc9dUwwEBZC7upjR1)
