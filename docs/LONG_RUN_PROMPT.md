# Data Paddock — Long-Running Improvement Prompt

> **How to use:** Put `REVIEW.md` in the repo root, then paste everything below the line into Claude Code at the repo root. It is written to run unattended for many hours and to keep improving until the exit criteria in §9 are met. There is no time limit.

---

You are the lead engineer on **Data Paddock** (https://gbvparrilla.github.io/data-paddock/). It's an F1 site that turns timing data into driver-by-driver race stories for every session of the 2026 season. It serves two audiences: **new fans** who want to understand a weekend without being overwhelmed, and **data-curious and diehard fans** who want depth the broadcast doesn't give. The mission is that every driver, including midfield and backmarkers, gets a story as good as the race winner's.

A full audit of the live site is in **`REVIEW.md`** at the repo root. It contains 30 numbered issues with evidence, plus five persona reviews. **Read it completely before doing anything else.** It is your backlog and your bar.

Your job is to fix everything in it, then keep raising quality through repeated self-critique until the product is excellent by the rubric in §8. You have no time limit. Work carefully, verify everything, and never declare something fixed without proof.

## 0. Operating rules (apply for the entire run)

1. **Progress file.** Create and maintain `PROGRESS.md` at the repo root. It is your memory across context compaction. It contains:
   - the current phase
   - a checklist of every REVIEW.md issue (#1–#30) with status `open / in progress / fixed (evidence: …)`
   - newly discovered issues, numbered #31 and up
   - rubric scores from every critic pass
   - "Next 3 actions"

   Re-read it whenever you resume or feel unsure what's next. Update it after every meaningful step.
2. **Commit often.** Make small, focused git commits after each working change, with clear messages. Never commit secrets. Never force-push. Work on a branch named `overhaul`, and merge to the default branch only when a phase's gate passes (§7).
3. **Secrets.** The Anthropic API key is read only from the `ANTHROPIC_API_KEY` environment variable (`.env` is local and gitignored). Never print it, log it, hardcode it, or write it into any file.
4. **Model.** Put all text generation behind one config constant, `NARRATIVE_MODEL = "claude-fable-5-1"`, so it can change in one place.
5. **Proof over claims.** An issue is "fixed" only when an automated test or a reproducible check demonstrates it, and that evidence is linked in PROGRESS.md: a test name, a command, or a screenshot path.
6. **Don't break what works.** Keep everything listed under "What's genuinely good" in REVIEW.md, and improve those features rather than replacing them. Keep the static-JSON + GitHub Pages architecture unless you write a short ADR in `docs/adr/` justifying a change.
7. **Scope discipline.** Fix correctness before features. Don't add new features until Phases 1–3 pass their gates. Any idea outside the plan goes into an `IDEAS.md` backlog. Don't build it unless a later phase or critic pass pulls it in.
8. **Cost discipline for LLM calls.** Iterate on narrative quality using the **pilot set** only:
   - R1 Australia (DNS/DNF, VSCs, quali gaps)
   - R12 Dutch (driver swap, sprint)
   - R17 Singapore (sprint, wet sprint, street circuit)

   Regenerate the full season only after the pilot passes the §5 quality gate. Cache by input hash, and log the call count and approximate tokens per run in PROGRESS.md.
9. **When blocked** by missing data from an API, a design decision that really is the owner's call, or a credential: write it in PROGRESS.md under "Blocked — needs owner", choose the most reasonable default, and keep going on everything else.

## 1. Phase 0: Understand and build the safety net

Before changing any behaviour:

1. **Map the repo.** Write `ARCHITECTURE.md`: backend modules, ingestion → transforms → narrative generation → static JSON export → frontend build → deploy. List every published JSON file and which component reads it.
2. **Make it runnable locally.** Write one documented command each for: ingest, transform, generate, export, dev server, production build, and preview the production build.
3. **End-to-end tests (Playwright, against the production build).** Write a crawler test that:
   - loads `#/`, clicks into **every** race via in-app links (no reloads), and visits every session tab
   - selects a driver, selects a second driver, and opens each tab (Tyre strategy / Sectors / Turn by turn)
   - visits the standings for drivers and constructors, and selects a driver's season story
   - at each step, asserts **zero console errors**, a non-empty `<main>`, and none of these strings in visible text: `None`, `null`, `undefined`, `NaN`, `[object`, `BAD_FORMAT`, `{}`, `<br>`
   - runs at a desktop viewport (1280×800) and a mobile one (375×812)

   This test must fail today, because of bug #1. That's the point.
4. **Data invariant suite** (pytest or equivalent, run against the exported JSON). Implement at least these checks, each pointing to the REVIEW issue it guards:
   - the sum of per-corner deltas equals the stated total, and the stated total equals best lap minus reference lap, within 0.05s (#8)
   - within each qualifying segment, gaps increase monotonically with position, and every entrant appears in the qualifying classification, including no-time and DSQ drivers (#7)
   - DNF/DNS/DSQ counts are identical in the headline summary, the cards and the table (#6)
   - `position_by_lap` max lap equals race distance for classified, non-lapped finishers (#12)
   - finishers are sorted by position, followed by non-classified drivers in a defined order (#13)
   - each driver has exactly one team per event, and constructor points from entries equal the official Jolpica constructor standings after every round (#4)
   - every race-control VSC/SC period appears in key moments (#14)
   - no user-facing string field contains the forbidden tokens above (#2, #10)
   - every stint that has a known compound is used whenever the pivotal-moment text references that stint (#9)
5. **Narrative fact-check harness** (stub it now, flesh it out in Phase 3; see §5).
6. Wire everything into `make check` (or an npm script) and a GitHub Actions workflow that runs on every push. A deploy must not happen if checks fail.

**Gate 0:** the tests and invariants exist, run in CI, and fail for the known bugs. Record the baseline failure list in PROGRESS.md.

## 2. Phase 1: Stop the bleeding (P0 frontend)

1. **Fix bug #1 at the root.** Find every `useEffect`/`useLayoutEffect` whose callback returns something that isn't a function. Usual culprits are `async` callbacks, implicit-return arrows (`() => x && y()`, `() => ref.current = …`), and returning `null` or a value. Rewrite them to return `undefined` or a real cleanup function. Add an ESLint rule (`react-hooks` plus a custom or `no-async-effect` style rule) so it can't come back.
2. **Add error boundaries** at the app root and around each major panel (classification, track map, charts, story). A crashed panel shows a short, friendly message and a "reload this section" button. The rest of the page keeps working.
3. **Add loading skeletons** for every data-driven panel, and a proper 404 / "race not found" route.
4. **Gate 1:** the Playwright crawler passes with zero console errors on in-app navigation across all 17 races, at desktop and mobile.

## 3. Phase 2: Fix the data model and the numbers (P0/P1 backend)

1. **Entries table.** Introduce `entries(event_id, driver_id, team_id, car_number, is_substitute)` from Jolpica's per-race results and OpenF1's per-session driver list. Every team lookup (colours, labels, constructor sums, story inputs) joins through `entries`, never `drivers.team`. Backfill all 17 rounds. Check against the real R12–R14 swap: Lawson drove for Red Bull and Tsunoda for Racing Bulls while Hadjar was out injured.
2. **Status as an enum.** Use `CLASSIFIED / LAPPED(n) / DNF(reason?) / DNS / DSQ / DNQ / NC`, derived from Jolpica status plus laps completed. Use it in the table, cards, standings grid (show "DNS"/"DNF" chips, not a fake position) and story inputs. The UI and the stories must read the same field.
3. **Gaps and "lapped".** Never show both "Lapped" and a time gap behind the winner. Show `+1 Lap` or the time, according to the status.
4. **Qualifying.**
   - Store per-segment best times (Q1/Q2/Q3 and SQ1/SQ2/SQ3).
   - The classification gap is measured against the pole time *in the segment where that driver was eliminated*, and the gap column shows which segment it comes from. Alternatively, offer a segment switcher.
   - Show every entrant, including no-time drivers and grid-penalty starters, with a reason column (e.g. "No time set", "Pit lane start", "Grid penalty +5").
   - Fix "Gap pole to P10" so it uses Q3 times only.
5. **Lap counts.** Fix the off-by-one in `position_by_lap` (include the final lap and lap 1 correctly). Clip or extend the chart axes to the true race distance and the full grid size (P22, not P20).
6. **Pit stops.** Use OpenF1's stationary duration where it exists. Where it's missing, show pit lane time only and display "—" (with a tooltip explaining the feed doesn't publish it) rather than repeating "stop time unknown" in every sentence. Separate practice garage visits from race pit stops in the data model.
7. **Compounds.** Fix the pivotal-moment compound join (#9). Where a compound is truly unknown, give it its own legend entry ("Unknown") and a hatched pattern, not an unlabeled grey bar.
8. **Turn-by-turn reconciliation (#8).** Define one reference lap per session (the session-best lap) and compute corner deltas from distance-aligned telemetry so they add up to the lap delta. If alignment drift remains, show the residual as an explicit "unattributed" bar rather than letting the totals disagree.
9. **Sector labels (#20).** Labels must describe the actual comparison: "+0.810s to session best · 14th of 20 timed". If you show a vs-average label, compute it against the real field average and say so.
10. **Remove every `None`/`null` leak** at the export layer. Export through a serializer that refuses forbidden tokens in user-facing strings.
11. **Gate 2:** every invariant in §1.4 passes for all 85 sessions, and the constructor standings match Jolpica exactly after every round.

## 4. Phase 3: Rebuild the pivotal-moment engine (#9, #14)

The current engine ranks raw position changes, which pit cycles dominate. Replace it with a scored-candidate system:

- **Candidate types:**
  - DNS/DNF of a driver who started in the top 10, or of a championship contender
  - grid penalties and pit lane starts
  - qualifying shocks, such as a top-team driver eliminated in Q1/Q2
  - SC/VSC/red flag periods, each with who gained or lost from the timing (who pitted under it and the net positions gained)
  - on-track overtakes: position changes not explained by a pit stop within ±1 lap
  - the net effect of each pit cycle, measured once everyone in the battle has stopped
  - undercut/overcut successes and failures between cars within 3s of each other
  - penalties with their reason
  - fastest lap, if it decided a point
- **Scoring:** `impact = championship weight × positions affected × visibility`, with a bonus for midfield stories so that every race surfaces at least one non-podium moment.
- **Output:** 5–8 moments per race and 3–5 per qualifying session, each with a one-line plain-language headline, an optional detail line, and the lap number.
- **Test against the pilot:** Australia must surface Hadjar retiring from P3, Piastri not starting from P5, and Verstappen's P20→P6 recovery, and must **not** list a P16→P19 pit stop as "key".

## 5. Phase 4: Rebuild the narrative pipeline (#2, #3, #5, #15, #16)

Stories are the product. Make them **true, readable, and specific**.

### 5.1 Pipeline

1. **Fact sheet first.** For each driver-session, build a JSON fact sheet in code. It contains every number the story may use, each with a stable key, plus pre-computed comparisons:
   - teammate delta
   - nearest rivals on track
   - position net of the pit cycle
   - undercut verdicts (out-lap + pit loss vs. rival's in-lap)
   - VSC/SC timing relative to each stop: during = cheap, just before = unlucky, just after = missed
   - stint degradation slope (s/lap) with fuel correction (≈0.03 s/lap per lap of fuel burned; make it a constant)
   - incidents and investigations from race control involving this driver, with the other car named
2. **Cross-driver consistency.** Store incidents once, as shared facts. Both drivers' fact sheets reference the same fact, so their stories can't disagree (#16).
3. **Structured output.** Ask the model for strict JSON with:
   - `headline` (≤12 words)
   - `summary` (≤60 words, plain language, no lap times; written for a new fan)
   - `story` (≤220 words, short paragraphs, specific, for the data-curious)
   - `analysis` (≤150 words)
   - `key_numbers` (3–5 keys from the fact sheet to show as stat chips)
   - `glossary_terms` (terms used that need a tooltip)

   Validate against a JSON Schema. Reject and retry on any parse or schema failure. Never publish raw or partial output.
4. **Fact-check, deterministically.**
   - Extract every number, position (P\d+), lap reference, driver name and team name from the generated text.
   - Every one must match a fact-sheet value (with formatting tolerance) or be derivable from one.
   - Recompute arithmetic claims such as points behind, places gained and gaps.
   - Check that every named driver exists in that session's entries, and that teams match `entries`.
   - Check that no claim contradicts status: no race narrative for a DNS car, no "climbed" for a car that lost places.
   - On failure, send the model the specific violations and regenerate, up to 3 times. If it still fails, publish a templated fallback built purely from the fact sheet and log the failure.
5. **Analysis that commits.** The analysis section must state a conclusion whenever the fact sheet contains a computed verdict ("The early stop cost him about 2s against Bortoleto, because the VSC two laps later handed the cheaper stop to the cars behind"). It may hedge only when the fact sheet marks something `insufficient_data`, and then in one sentence, not six. Ban the hedging boilerplate you see in REVIEW.md ("it is hard to say", "the evidence does not support a strong conclusion either way") unless it's paired with that flag.
6. **Session-type logic.** DNS/DNQ drivers get no strategy analysis section at all. They get a short note plus their weekend arc. Practice stories describe programmes (long runs, compound evaluation) and don't rank 5-lap samples as definitive. Label any long-run ranking with sample size and a confidence note.
7. **Head-to-heads for any pair** (#15), not just teammates. Generate lazily on first request at build time for the obvious pairs (teammates, drivers who finished adjacent, drivers with a shared incident). For other pairs, show a deterministic comparison with no LLM text.
8. **Weekend arc and season arc.** Build these from fact sheets, not from earlier generated prose, so errors don't compound. Season arcs must cover missed races and substitutions (Hadjar's injury, Lawson's promotion, Tsunoda's return).

### 5.2 Narrative quality gate (pilot set first)

For every pilot driver-session:
- the fact-check passes with 0 violations
- no forbidden tokens appear
- word limits are respected
- the summary has no lap times and no undefined jargon
- the analysis contains at least one concrete, fact-backed conclusion unless the fact sheet is flagged `insufficient_data`

Then **manually review** 15 stories across the pilot: 5 front-runners, 5 midfield, 5 back-of-grid or DNF/DNS. Score each 1–5 on *accuracy, readability for a new fan, insight for a diehard, and specificity*. The gate is an average of at least 4.3 with no story below 3. Record the scores and the worst story's text in PROGRESS.md, and iterate on the prompts and fact sheets until the gate passes. Only then regenerate the full season.

## 6. Phase 5: Frontend for both audiences (P2 issues and personas)

**New-fan layer (default view):**
- Each race page opens with a **"The race in 30 seconds"** block: 3 sentences plus 3 stat chips, built from the pivotal-moment engine and the summaries.
- **Glossary tooltips** for every jargon term (VSC, SC, DNS, DNF, stint, compound, undercut, long run, Q1/Q2/Q3, sprint quali, parc fermé, track limits), driven by `glossary_terms` plus a static glossary file. Tooltips work on tap as well as hover.
- **Colour legend everywhere colour carries meaning** (purple = session best, green = personal or near-best, etc.), defined once and reused.
- Driver story panel order: headline → summary → stat chips → "Read the full story" (expands the story) → "Analysis" (still visually distinct, with the Interpretation chip).
- Merge "The weekend in context" into the weekend strip as a short arc, so the race story isn't repeated.

**Depth layer (one click away, never forced):**
- Qualifying segment view: Q1/Q2/Q3 columns, cutoff line, margin of survival or elimination.
- Gap-to-car-ahead and gap-to-leader charts.
- Degradation chart per stint, fuel-corrected, with slope labels.
- An undercut/overcut table for every pit-stop battle.
- A race-control incident timeline.
- Every chart has a "Show data" table alternative (for accessibility and for data people).

**Chart fixes:**
- full grid on the y-axis
- teammates as solid vs dashed lines
- label collision avoidance
- dim everything except the selected drivers
- touch interactions (tap to select, a long-press tooltip, and "Tap a line" copy on touch devices)
- the race distance matches the data

**Navigation and polish:**
- Fix the classification sort (#13).
- Deduplicate card copy (#26): no sentence repeated within a card. The "Midfield Story" highlight and the first "Beyond the podium" card must feature different drivers, or merge the two.
- Use full event names ("Spanish Grand Prix").
- Make "Races" a real index (grid plus filters: sprint weekends, my team).
- Hide the year dropdown while only one season exists.
- Add a lightweight in-site "Report a problem" form option alongside the GitHub one (it can open a prefilled email or a form that creates the issue). Never collect personal data beyond what the user types.
- On mobile, collapse the four highlight cards into a horizontal swipe row so the classification appears above the fold.

**Shareability:**
- Per-route `<title>` and meta description.
- An Open Graph image per race and per driver-race, generated at build time (track outline + headline).
- Move to path routing with a GitHub Pages `404.html` SPA fallback, or prerender static HTML shells per route at build time so links preview and get indexed. Write an ADR for the choice.

**Performance:**
- Route-level code splitting.
- Split `detail.json` into per-view files (positions, stints, sectors, corners) loaded on demand.
- Inline track outlines into `events.json` (simplified paths).
- Ship only that session's entrants in `headline.json`.
- Target: home page JS ≤250 KB gzipped, largest race-page data request ≤200 KB, Lighthouse performance ≥90 and accessibility ≥95 on mobile.

**Accessibility:**
- keyboard navigation through classification and tabs
- visible focus styles
- WCAG AA contrast for all text
- colour never the only signal (add pattern, shape or text)
- charts have an `aria-label` summary and a data table

## 7. Phase gates and the deploy rule

Each phase ends only when its gate passes **and** the full suite (`make check`: unit + invariants + fact-check + Playwright crawl, desktop and mobile) is green. Then:

1. Merge `overhaul` into the default branch.
2. Let CI deploy.
3. Run the Playwright crawler **against the live URL**.
4. Record the result in PROGRESS.md.

If the live crawl fails, roll back the merge commit, then fix.

## 8. The self-improvement loop (runs after Phase 5, and keeps running)

Repeat until the exit criteria in §9 hold:

1. **Full crawl.** Run the Playwright crawler on the production build. Capture desktop and mobile screenshots of: home, standings, and for each pilot race the race tab, the qualifying tab, a driver selected, and two drivers compared.
2. **Critic pass.** For each of the five personas in REVIEW.md (new fan, data-curious fan, diehard, website critic, data engineer), look at the actual screenshots and read 5 randomly sampled stories, *including at least 2 from outside the top 10*. Score 1–10 against these criteria:
   - **New fan:** understands the race in under 60 seconds; no undefined jargon; zero dead ends; mobile usable one-handed.
   - **Data-curious fan:** every number reconciles; every chart explains how to read it; analysis teaches something.
   - **Diehard:** facts correct, including driver swaps, penalties and incidents; key moments match what actually mattered; depth views exist for quali, strategy, degradation and incidents.
   - **Website critic:** no crashes, no layout jank, good loading states, share previews work, Lighthouse targets met, accessibility targets met.
   - **Data engineer:** invariants cover every user-visible number; pipeline idempotent and resumable; no unvalidated LLM text published; payload budgets met; CI blocks bad deploys.
3. **Write the findings.** Add every new issue to PROGRESS.md (#31+) with evidence and a severity (P0/P1/P2).
4. **Fix** the highest-severity, lowest-scoring items first. For each fix, add a test or invariant that would have caught it.
5. **Re-score** and log the scores with the date and commit hash.
6. **Raise the bar.** When a persona scores 9+ twice in a row, add one stricter criterion for that persona (e.g. "every key moment links to the lap on the chart"), and record the new criterion in PROGRESS.md. This keeps the loop from stopping at "good enough".
7. **Guardrails against drift:**
   - Never weaken or delete a test to make it pass.
   - Never remove a working feature to raise a score.
   - Refactors need a measurable reason (performance, correctness, a test gap).
   - Feature ideas go to IDEAS.md and are only built when a critic pass names them as the blocker to a higher score.

## 9. Exit criteria (all must hold at the same time)

- Every REVIEW.md issue #1–#30 is marked fixed with linked evidence, or "won't fix" with a written reason the owner can review.
- `make check` is green, and the Playwright crawl is green **against the live site**, at desktop and mobile, across all completed rounds.
- All §1.4 invariants pass for every session of every completed round.
- The narrative fact-check reports 0 published violations across the full season, and fewer than 2% of stories fall back to templates.
- The pilot narrative review averages at least 4.5 (§5.2 rubric) and a fresh random sample of 15 season-wide stories also averages at least 4.5.
- Every persona scores at least 9 on **two consecutive** critic passes, with the raised criteria from §8.6 included.
- Lighthouse mobile: performance ≥90, accessibility ≥95, best practices ≥95, SEO ≥90 on home and on one race page.
- PROGRESS.md ends with a final report: what changed, before/after scores, remaining known limits of the data feeds, and recommended next steps (e.g. live-session mode, which the architecture must still support via `sessions.status`).

When all of that holds, do one final full crawl of the live site, write the final report, and stop.

## 10. First actions, in order

1. Read `REVIEW.md` fully.
2. Create the `overhaul` branch and `PROGRESS.md` with the issue checklist.
3. Write `ARCHITECTURE.md`.
4. Build the Playwright crawler and watch it fail on bug #1.
5. Fix bug #1 at the root, add the lint rule, and confirm the crawler passes navigation.
6. Continue with Phase 0's invariant suite, and keep going phase by phase.
