# Data Paddock — Benchmark Knowledge Base

**Compiled:** 18 Oct 2026 (after round 17 of the 2026 season)
**Purpose:** A reference for judging each new version of Data Paddock. It covers what popular F1 and data sites do well, what weaker sites keep getting wrong, and the scorecard in §7 for grading new builds.

**How this was gathered:** About 30 sites in three groups: F1 analytics and timing, other sports' stats sites, and data/storytelling products outside sports. Each note is tagged with how deeply it was checked:
- **[Used]**: opened in a real browser and actually used (clicked through, loaded charts).
- **[Fetched]**: the page was fetched and read, but not interacted with. JavaScript-heavy sites may show less than a real visit would.
- **[Described]**: based on the site's own description, a changelog, or third-party coverage.

Treat [Fetched] negatives ("no glossary found") as *unconfirmed*. Pages that build themselves with JavaScript often hide features from a plain fetch.

---

## 1. The landscape, and where Data Paddock fits

| Category | Who's there | What they're for | What none of them do |
|---|---|---|---|
| **Official** | formula1.com results, F1 TV | The source of record, basic tables | No analysis, no explanation, almost no visuals |
| **Live timing** | MultiViewer, f1-dash (sunset) → Nitrous, F1 Cosmos, Formula Live Pulse, Formula-Timer | Watching a session as it happens | Very little after the session, no story |
| **Telemetry explorers** | TracingInsights, GP Tempo (formerly F1 Tempo), F1 The Data, F1 DataStop, F1pace, BoardF1 | Pick drivers and laps, compare charts | You must already know what to look for. No conclusions |
| **Historical stats databases** | StatsF1, Pitwall.app, 4mula1stats, BigDataF1, Formula1Points | Records, careers, "on this day" | Static tables, ads, dated design |
| **Ratings and modelling blogs** | f1metrics, f1-analysis.com | Driver ratings, models | Hard to browse, charts as images |
| **Fantasy tools** | F1 Fantasy Tools, f1pitwall.dev | Turning data into a decision | Narrow purpose |
| **Expert journalism** | Mark Hughes (The Race / Motor Sport), Edd Straw | Explaining *why* | Not per-driver, not for every car, not data-first |
| **Reference** | Wikipedia race articles | One page per weekend with footnotes | Nothing visual, little analysis |

**Data Paddock's gap:** No site gives every driver in every session a data-backed story. Explorers give data without conclusions. Journalists give conclusions about the front of the grid. Wikipedia gives a neutral record. Data Paddock aims to be "Mark Hughes-style explanation, written from the data, for all 22 cars."

**Watch out:** TracingInsights now advertises "AI explanations of the session" in a separate app and has an "Ultra" subscription. The biggest telemetry site is moving into your space. Your edge has to be accuracy, coverage of the whole grid, and readability, not simply "has AI text."

---

## 2. F1 sites, one by one

### TracingInsights: tracinginsights.com [Used]
The most complete free F1 chart site.
- **Great at:**
  - An **Essential / Expert mode toggle** offered on the first visit ("Start with core charts, or switch on Expert for stints, sectors, tyre strategy"). This is progressive disclosure done explicitly.
  - Analyst-grade options: **fuel correction**, **hide outliers (107%)**, **show track status** (SC/VSC shading), **favourite drivers** saved and auto-selected.
  - **Chart / Data / Docs tabs** on every chart: a data-table alternative and documentation next to the visual.
  - **Free downloads** of every chart ("Download, edit, and share the charts freely — no credits needed").
  - The **whole selection lives in the URL** (`?y=2026&e=Singapore&s=P1&d=VER,BEA&l=…`), so any view can be shared as a link.
  - A deep back catalogue (2018 onward), a downloadable data hub, and a Substack where charts are turned into short articles.
- **Weak at:**
  - **Empty until you fill in a form.** You pick year → event → session → drivers (four steps) before seeing a single chart. A newcomer sees a form, not an insight.
  - **Stale banner:** a "NEW" banner advertised the *2025* Hungarian GP late in the 2026 season.
  - **Smoothed lap chart on by default:** curved lines invent values between laps, which misleads.
  - Lap times shown as decimal seconds (94–99) rather than m:ss.
  - The driver typeahead selected a different driver than the one typed when I pressed Return. That may be a keyboard quirk, but it shows how fragile search inputs can be.
  - Busy navigation: Analysis, Blog, Schedule, Dash, Socials, Contact, Data, settings, language and Support all in one bar.
- **Steal:** the mode toggle, the outlier/fuel/track-status switches, the Chart|Data|Docs tabs, URL state, and free chart export.

### GP Tempo (successor to F1 Tempo): gp-tempo.com [Used]
The best-looking telemetry tool.
- **Great at:**
  - A **"Jump Right In" carousel** of curated, pre-built comparisons ("Monaco pole position battle"). One click from the home page to an insight, with no form.
  - A **track-domination map**: the circuit outline coloured by which driver was fastest in each mini-sector. You read it at a glance.
  - **Lap cards** showing compound icon, time and delta to the fastest (+0.209s), plus a **lap replay** with play/pause and 0.5×–4× speed.
  - Speed trace with **sector lines and corner numbers**, and **click-and-drag zoom**.
  - All state in the URL. A **"Share" button**, a **"Feedback" button** on every page, and a clear non-affiliation notice.
  - F1 Tempo's old trick: **click a dot on the lap chart to add that lap to the telemetry view**. It links the overview to the detail.
- **Weak at:**
  - The curated examples were **all from 2025** while the 2026 season was 17 rounds in. Curated content goes stale unless it's refreshed automatically.
  - Watermark logos inside the charts add visual clutter (but make shared screenshots self-branding).
  - No explanation of what a domination map or a speed trace means. You're assumed to be an expert.
  - Moving domains (F1 Tempo → GP Tempo) split the audience. The old site now shows a modal asking people to move.
- **Steal:** curated one-click entry points (auto-generated from your key moments), the domination map, lap replay, and chart-to-detail linking.

### MultiViewer: multiviewer.app [Described]
The power user's live tool (desktop app, needs F1 TV).
- **Great at:** synced multi-stream video plus timing, mini sectors, a **track map with marshal-sector status**, race-control messages, **AI radio transcriptions**, a **Race Trace** chart of time gained and lost, saved layouts, and **spoiler-free** catalogue browsing (text only, no result thumbnails).
- **Weak at:** a desktop install, a paywalled data source, and an expert-only audience.
- **Steal:** **spoiler protection**. Many fans watch races delayed, so a "hide results" mode on race pages is a real feature for them. Also borrow the Race Trace idea for gap visualisation.

### f1-dash → Nitrous [Fetched]
- f1-dash was a popular open-source live dashboard (about 2,000 GitHub stars). It has **been sunset**. The page cites data "becoming locked behind subscriptions" and "increasing IP restrictions", and points to a desktop successor.
- **Lesson:** F1 data access is fragile. Projects die or migrate. Data Paddock's static, pre-built approach is more resilient than live scraping, but you should **cache raw data yourself** and never depend on a single upstream source.

### formula1.com results [Fetched]
- **Good:** authoritative, every season back to 1950, flags, team logos and driver photos, consistent navigation.
- **Bad for analytics fans:** the season page shows only the winner, laps and time, with no gaps, grid, stops or status. There's no visible export or sorting, and the page is surrounded by F1 TV, store and ticket promotion.
- **Lesson:** the official site sets the *minimum*. Anything you show must agree with it exactly, especially classification, status and points.

### Wikipedia race articles [Fetched]
The most-used F1 reference in practice.
- **Great at:**
  - A **fixed structure** every weekend: infobox → background → practice → qualifying → race → classification → standings.
  - **Footnotes that explain odd results:** a pit lane start because the car was modified under parc fermé, a DNS after a formation-lap crash, a tiebreak decided on count-back.
  - Everything cited to sources.
- **Lesson:** this is exactly where Data Paddock fails today (REVIEW #6 and #7). **Every unusual result needs a footnote-style explanation:** DNS, pit lane start, grid penalty, no time set, substitute driver, tiebreak.

### Pitwall.app [Fetched]
- **Good:** historical depth, a countdown to the next session, compact standings and results.
- **Bad (the version fetched):**
  - a stray "No results found" heading
  - two countdowns that disagreed (5 days vs 3 days)
  - sidebar articles from 2024
  - display ads competing with the data
  - times only in CET
  - repetitive filler text written for search engines
- **Lesson:** conflicting numbers on one screen and stale content beside fresh data both destroy trust quickly.

### F1 Cosmos, F1 The Data, F1 DataStop, BoardF1, 4mula1stats, f1-analysis.com [Fetched]
These smaller sites share the same failures (§5 lists them as anti-patterns):
- **Marketing before data.** F1 Cosmos's home page is a SaaS-style landing page ("Enter the Cosmos") with a promo video, a testimonial and an unfinished feature card. It shows no actual data. Its metadata targets "better than f1-dash".
- **The main content doesn't load for a plain fetch.** F1 The Data's schedule showed "Loading season" twice with no races. F1 DataStop returned only metadata. BoardF1 blocked automated access.
- **Visible leftovers and mistakes.** 4mula1stats had a stray `int(0)` debug output, empty "Percentage" columns, empty chart sections and typos. Several sites showed a literal `&amp;` in titles. f1-analysis.com had links pointing to the wrong articles, links into a staging site, and misspelled driver names.
- **No "last updated" date anywhere**, so you can't tell whether the data is current.
- **Ad and cookie clutter** before any data appears (4mula1stats, Pitwall).
- **Still useful:** f1-analysis.com's *teammate-adjusted driver rating* is a genuinely interesting metric, held back by charts saved as images. 4mula1stats's "on this day" and driver-vs-driver comparisons add replay value.

### F1 Fantasy Tools [Fetched]
- **Great at:** turning data into a **decision** (Team Calculator, Budget Builder, "Hindsight" optimal teams), a clear catalogue of tools with a one-line purpose each, a free tier leading into paid, testimonials from named users, and keeping data after the season ends.
- **Weak at:** testimonials repeated many times on one page, placeholder links, and plan contents not listed.
- **Lesson:** each tool answers one question in one line ("What should I change this week?"). Data Paddock's equivalent: every panel should answer one fan question in its title.

### Expert writing: Mark Hughes and TracingInsights' Substack [Fetched]
- **Hughes:** reasons as a **causal chain** (track surface → tyre behaviour → team choices → likely outcome). He uses **few numbers, each made concrete** ("more than a pit stop's worth"), adds historical precedent, and hedges **only where things are genuinely uncertain**, briefly ("it's early days yet"). He sounds confident without being dogmatic.
- **TracingInsights Substack:** the **subtitle states the conclusion** before any chart. The chart directly supports one claim, the article admits the confounders (fuel, traffic, setup) and checks colour-blind accessibility. *Weak:* jargon left undefined ("offset strategy", "delta", "scrubbed"), and a modelling choice never explained.
- **Lesson for Data Paddock's stories:** lead with the conclusion, give a cause for every claim, use few numbers that each do work, and hedge in a single sentence only when the data really is ambiguous. That fixes REVIEW #5 and the over-hedging problem.

---

## 3. Other sports: what the best stats sites do

### Baseball Savant (MLB Statcast) [Fetched + Described]
The gold standard for "deep data that casual fans can read."
- **Percentile bars** on every player page: one 0–100 slider per metric, colour-coded from blue (poor) to red (elite), grouped by skill (batting, running, fielding). MLB's own write-up calls the page "the back of a Statcast baseball card." Instant to read for a casual fan, with full numbers underneath for experts.
- **A snapshot at the top, depth below.** Season pills (2026 … 2018, All), tabs for each skill, **Save Image** on charts, and **↑↓ arrows** on year-over-year changes (direction shown without relying on colour).
- **A dated public changelog** with screenshots, and "New/Updated" labels in the menus. The 2026 comparison tool compares up to 9 players on percentile bars, with a "highlight the winner" option and a downloadable, titled image.
- **Weak:** very long pages, many near-duplicate tables, abbreviation-heavy, wide tables on mobile.
- **Steal:** **percentile bars for drivers** (qualifying pace, race pace, tyre management, starts, consistency, overtakes) ranked within the season. A new fan reads a shape; a diehard reads the number. Also borrow the public changelog.

### FBref (football) [Fetched]
- **Great at:** the same layout for every competition, advanced metrics (xG, npxG, xAG, PSxG±) next to the basics, and fast switching between stat categories. Learn it once and every page reads the same way.
- **Weak:** abbreviations everywhere, heavy self-promotion, tables of zeros or old seasons mixed in with current ones (which hurts trust).
- **Lesson:** consistency is a feature. Every Data Paddock race page should have identical structure, so a fan who learns Australia can read Singapore instantly.

### FotMob (football) [Described]
The most-loved live football app.
- **Great at:**
  - **Match momentum** (a single wave showing who was on top, minute by minute)
  - **one rating per player** (one number summarising a whole performance)
  - shot maps and xG
  - **following your team** for personalisation
  - fast, targeted push alerts
  - a clean interface
- **Weak:** ad load, repeated news (per user reviews).
- **Steal:** a **momentum-style race graphic** (who was gaining time each lap: leader vs chaser, or any battle), a **single "weekend rating"** per driver with its breakdown shown, and **"follow my team/driver"** so the home page leads with the fan's driver.

### StatMuse [Fetched]
- **A plain-English question box** ("most poles at Monaco since 2014") that answers with a sentence plus a table plus an image. It's the lowest-friction way into stats.
- **Lesson:** a search box that understands fan questions ("How did Gasly do in Singapore?") is the natural next step for an AI-powered stats site. Only build it once the answers are guaranteed to come from checked data.

### Opta Analyst [Fetched]
- **Editorial patterns:** headlines that state the claim after a colon, headlines that test conventional wisdom ("Do teams really need to run more to win?"), branded recurring series that build a habit, model projections as a recurring feature, and a "Metric Explainers" section.
- **Weak:** a huge mega-menu, repeated blocks, placeholder elements in the header.
- **Steal:** **recurring formats** ("Midfield Report", "Strategy Verdicts", "Rookie Watch") and a **metric explainer** page for every derived number you show.

### MoneyPuck (NHL), NFL Next Gen Stats [Fetched, mostly metadata]
- MoneyPuck: live win probability, playoff odds, a glossary link. NGS: tracking-data stats (speed, acceleration).
- **Lesson:** any probability or model output needs a "how this works" page. NGS's viewport also blocks pinch-to-zoom (`user-scalable=no`), an accessibility anti-pattern to avoid.

---

## 4. Outside sports: data products that get storytelling right

### Our World in Data [Fetched]
The best "chart as a trustworthy document" design on the web.
- Every chart has:
  - a **plain-language definition** directly under the title
  - **key takeaways** with show more/less
  - a **metadata block** (source, unit, date range, **last updated**, **next expected update**, the researcher responsible)
  - **caveats that explain odd data points** (why one country's data shows a sudden one-year dip)
  - a per-source **methodology** section
  - **full vs displayed-data downloads**, an API with code snippets, and a ready-made citation with a CC BY licence
- **Steal for Data Paddock:**
  - a "**Last updated / data through round N / next update after the US GP**" stamp on every page
  - a caveat line wherever the feed has gaps ("Stationary pit times aren't published for this race")
  - a methods page per metric
  - downloadable data per view

### The Pudding [Fetched]
- Visual essays built on **one human question plus a big dataset**, with teasers that work as hooks ("Are you more likely to die on your birthday? Yes."). The question is the headline and the answer arrives fast.
- **Steal:** frame each story's headline as the question a fan would actually ask ("Did Russell's Singapore qualifying cost him the title?"), then answer it.

### Spotify Wrapped and Strava Year in Sport [Described]
Principles behind the most-shared data stories (Juice Analytics' synthesis):
1. **A recurring ritual** (an expected moment)
2. **The person is the protagonist**
3. **Designed to be shared** (story-format cards)
4. **Do the interpretation for them** (a conclusion, not a dashboard)
5. **Identity rather than a scorecard**
6. **Accumulated history makes the payoff bigger every year**
7. **Accuracy protects trust**: generic or machine-sounding text feels impersonal

- **Steal:**
  - a **post-race "Your driver's weekend" share card** (track outline, headline, 3 stats) for each driver
  - an **end-of-season "Wrapped"** for each driver and team
  - a **"Season so far" ritual** after every round

### Flighty (flight tracking) [Described]
Turns aviation data into calm, plain-language status.
- **Short status cards:** icon, bold headline, one detail line ("Delayed 45m", "6:32am (22m early)").
- **Predictions with stated odds** ("Probability of extension is 30–60%").
- **"What's happening, why, and when it may clear"** summaries of airport conditions.
- A **lifetime "Passport"** of personal stats, with shareable graphics.
- **Steal:** the three-part status line (*what happened · why · what it means*) for every key moment, and **odds instead of hedging words** whenever you make a prediction or counterfactual ("an earlier stop gains P1 in roughly 6 of 10 simulations" beats "may have been worth testing").

### Datawrapper / data-journalism practice [general knowledge; the article fetch failed]
- Standard newsroom practice: **chart titles that state the takeaway** ("Verstappen lost all his time in sector 2", not "Sector deltas"), annotations directly on the chart rather than in the legend, and a source note on every chart.

---

## 5. Patterns of popular sites vs anti-patterns of unpopular ones

### What the popular sites have in common
1. **Insight within one click of landing.** GP Tempo's curated examples, FotMob's match momentum, Savant's percentile bars. Never an empty form first.
2. **Layered depth.** TracingInsights' Essential/Expert toggle, Savant's snapshot then detail. One page serves both audiences, with the default set for the casual reader.
3. **Everything shareable.** State in the URL (TracingInsights, GP Tempo), downloadable charts (Savant, TracingInsights), share-card formats (Wrapped, Strava, Flighty).
4. **Consistent page templates.** FBref, Wikipedia, Savant: learn one page, read them all.
5. **Visible trust markers.** Sources, last-updated dates and methodology (OWID), changelogs (Savant), non-affiliation notices (GP Tempo, MultiViewer).
6. **Data tables beside charts.** Chart|Data|Docs (TracingInsights), OWID's table view. Good for accessibility and good for experts.
7. **Opinionated, concrete conclusions.** Hughes, the TracingInsights Substack, Opta headlines. They say what happened and why.
8. **Personalisation.** Favourite drivers (TracingInsights), follow-a-team (FotMob), the user as protagonist (Wrapped).
9. **Visible feedback channels.** GP Tempo's Feedback button, the TracingInsights Substack comments, Savant's changelog.
10. **Speed.** FotMob's reputation rests on it, and MultiViewer syncs streams in real time.

### What the unpopular sites keep getting wrong
1. **Marketing page instead of data** (F1 Cosmos).
2. **Content that depends on JavaScript to appear**, so search engines, link previews and slow phones see "Loading…" (F1 The Data, F1 DataStop).
3. **Leftovers and placeholders shipped:** `int(0)`, `&amp;`, empty columns, "Your browser does not support the video tag", "No results found" headings (4mula1stats, F1 Cosmos, Pitwall). *Data Paddock has its own versions: `lap None`, `BAD_FORMAT_FIXED_BELOW`.*
4. **Numbers that contradict each other on one page** (Pitwall's two countdowns). *Data Paddock: "3 did not finish" next to 5 DNF rows.*
5. **Stale content next to fresh data** (2024 articles beside 2026 results; GP Tempo's 2025 examples; TracingInsights' 2025 banner).
6. **No last-updated date**, so freshness can't be verified.
7. **Ads and cookie banners before data.**
8. **Jargon with no definitions**, which nearly everyone does, popular sites included. This is a chance to stand out.
9. **Charts saved as images**, so the numbers can't be reused or read by screen readers (f1-analysis.com).
10. **Broken internal links and inconsistent naming** (f1-analysis.com, 4mula1stats URLs).
11. **Unclear rules about what is official.** Points, status and classification that differ from the official result.
12. **The project dies or moves** (f1-dash sunset; F1 Tempo → GP Tempo). The audience leaves with it.

---

## 6. What this means for Data Paddock (mapped to REVIEW.md)

| Benchmark lesson | Where Data Paddock stands | REVIEW issues |
|---|---|---|
| Insight within one click (GP Tempo, FotMob) | Good: the home grid takes you to a race in one click. Bad: that click crashes. | #1 |
| Footnotes for odd results (Wikipedia) | Missing: DNS shown as DNF, Verstappen's P20 start never explained | #6, #7 |
| Agree exactly with the official result (formula1.com) | Constructor standings are wrong after the driver swap | #4 |
| Lead with the conclusion, one-sentence hedges (Hughes, TI Substack) | Stories are number logs, and the analysis over-hedges | #3, #5 |
| Odds instead of hedging words (Flighty) | No counterfactual is computed | #5 |
| Percentile bars (Savant) | Not present. A big opportunity for new fans | new |
| Momentum graphic (FotMob) | Not present. Would make the gap chart readable at a glance | new |
| Mode toggle, Essential/Expert (TracingInsights) | Partly: the depth sits below the fold, with no explicit toggle | P2 |
| Chart / Data / Docs tabs (TracingInsights, OWID) | Only the sector table has a data view | P2 |
| URL state, share cards (GP Tempo, Wrapped) | Hash URLs, a fixed page title, no social preview image | #24 |
| Last updated, caveats, methods (OWID) | Missing | new |
| Public changelog (Savant) | Missing | new |
| Spoiler-free mode (MultiViewer) | Missing. Fans who watch delayed would value it | new |
| Follow my driver (FotMob, TracingInsights favourites) | Missing | new |
| Curated, *auto-refreshed* entry points (GP Tempo, minus the staleness) | "Beyond the podium" is close. Make it automatic each round | — |
| Consistent template (FBref, Wikipedia) | Good: race pages share one structure | keep |
| Track outline as hero (GP Tempo's domination map) | Good, and it could become a domination map | extend |
| Owning the raw data (f1-dash sunset lesson) | Good: static JSON. Also keep the raw source data | keep |

---

## 7. Iteration scorecard

Use this to grade every new version. Score each line **0 (missing / broken), 1 (partial), 2 (done well)**. Note the evidence (URL plus what you saw). The total is out of 100. Compare totals between versions, and compare against the benchmark site named on each line.

### A. Trust and accuracy (weight ×2: a zero in any row here is a blocker)
1. Classification, status (DNS/DNF/DSQ) and points match formula1.com exactly for 3 random races. *(benchmark: formula1.com)*
2. Constructor standings match the official ones after every round, including driver swaps.
3. No numbers on a page contradict each other (summary vs cards vs table vs chart).
4. Odd results carry a footnote-style explanation (DNS, pit lane start, grid penalty, no time, substitute). *(Wikipedia)*
5. No leftover text anywhere (`None`, `null`, `NaN`, `undefined`, `&amp;`, debug output, raw model output).
6. Five random driver stories checked line by line: zero factual errors.
7. A "data through round N, last updated <date>" stamp is visible. *(OWID)*
8. Caveats appear wherever the feed has gaps, worded once and clearly, not repeated in every sentence. *(OWID)*

### B. First five minutes for a new fan
9. The home page shows real data and a path to a story within one click, with no empty form. *(GP Tempo, FotMob)*
10. Navigating between pages never crashes or shows a blank screen.
11. Each race page opens with a plain-language "what happened" in three sentences or fewer.
12. Every jargon term has a tap-or-hover definition. *(no benchmark does this well, so it's a chance to stand out)*
13. Colours are explained by a visible legend wherever they carry meaning.
14. Chart titles state the takeaway, not just the metric. *(Datawrapper practice)*
15. Readable one-handed on a phone. Key content sits above the fold, and nothing depends on hover.

### C. Depth for data fans and diehards
16. A clear Essential/Expert split, or progressive disclosure, on every page. *(TracingInsights)*
17. A data table or download beside every chart. *(TracingInsights, OWID)*
18. Qualifying segment view (Q1/Q2/Q3 cutoffs and margins).
19. Strategy view: stints, pit timing, undercut/overcut verdicts, SC/VSC shading. *(TracingInsights' track status)*
20. Pace analysis with fuel correction, outlier filtering and stated sample size. *(TracingInsights)*
21. Lap-level drill-down from overview charts (click a lap → its sectors and corners). *(F1 Tempo)*
22. A track-domination or corner-delta map that reconciles with the lap times. *(GP Tempo)*
23. A methods page for every derived metric (long-run pace, ratings, key-moment scoring). *(Opta, OWID)*

### D. Storytelling quality
24. Story headlines state a conclusion or ask a fan's question. *(TracingInsights Substack subtitles, The Pudding)*
25. Stories reason as cause → effect → outcome, with few numbers, each made concrete. *(Mark Hughes)*
26. Analysis commits to computed verdicts, and hedges in one sentence only when data is truly missing. *(Hughes, Flighty-style odds)*
27. Midfield and back-of-grid stories are as specific as the winner's. *(Data Paddock's own mission)*
28. Stories about two drivers who raced each other agree with each other.
29. Key moments are the moments that actually decided the race, and none of them are routine pit stops.

### E. Shareability and return visits
30. Every view has a shareable URL that restores the exact state. *(TracingInsights, GP Tempo)*
31. Each page has its own title and social preview image. A shared link previews with the track and headline.
32. A share card for each driver and race. *(Wrapped, Strava, Flighty)*
33. Follow a favourite driver or team, so the home page puts them first. *(FotMob, TracingInsights)*
34. A recurring ritual: a fresh "season so far" after every round, and a season "Wrapped" at the end.
35. A spoiler-free mode for fans who watch delayed. *(MultiViewer)*

### F. Craft and engineering
36. Lighthouse mobile performance ≥90 and accessibility ≥95.
37. Colour is never the only signal (shapes, arrows, patterns or labels as well). *(Savant's ↑↓ arrows)*
38. Pinch-to-zoom isn't blocked, and keyboard navigation works. *(the NGS anti-pattern)*
39. A public changelog with dated entries. *(Savant)*
40. A visible feedback channel that doesn't require a GitHub account. *(GP Tempo)*
41. No marketing filler, stale promos or out-of-date "NEW" badges. *(TracingInsights / GP Tempo staleness)*
42. Raw source data cached by you, so the site survives if an upstream API disappears. *(f1-dash lesson)*

**Scoring:** A rows count double (8 rows × 2 points × 2 = 32). B–F have 34 rows × 2 = 68. The total is out of 100.
- **Ship gate:** no zeros in section A.
- **"Better than the field":** ≥80.
- **"Masterpiece":** ≥92 with every A row at 2.

---

## 8. Things to recheck each time (the landscape moves)

- **TracingInsights' AI app and "Ultra" tier:** your most direct competitor for AI explanations. Check how accurate and how full-grid its explanations are.
- **Nitrous (f1-dash's successor):** check whether it adds post-session analysis.
- **GP Tempo:** check whether its curated examples now refresh automatically.
- **Baseball Savant's changelog:** a reliable source of new ideas for showing data to casual fans.
- **F1 data access:** any OpenF1 or Jolpica changes, licensing changes, or new restrictions (the reason f1-dash gave for sunsetting).

---

## Sources

- [TracingInsights](https://tracinginsights.com/) · [TracingInsights Substack: "Why Hamilton lost out to George in Miami"](https://tracinginsights.substack.com/p/why-hamilton-lost-out-to-george-in)
- [GP Tempo](https://www.gp-tempo.com/) · [F1 Tempo](https://www.f1-tempo.com/)
- [MultiViewer](https://multiviewer.app/) · [f1-dash sunset notice](https://f1-dash.com/)
- [Formula1.com 2026 results](https://www.formula1.com/en/results/2026/races) · [Wikipedia: 2025 Australian Grand Prix](https://en.wikipedia.org/wiki/2025_Australian_Grand_Prix)
- [Pitwall.app](https://pitwall.app/) · [F1 Cosmos](https://f1cosmos.com/) · [F1 The Data](https://f1thedata.com/) · [F1 DataStop](https://f1datastop.com/) · [4mula1stats](https://www.4mula1stats.com/) · [f1-analysis.com](https://f1-analysis.com/) · [F1 Fantasy Tools](https://f1fantasytools.com/)
- [Awesome F1 list (subinium)](https://github.com/subinium/awesome-f1) · [Autosport forum: best website for F1 statistics (2011)](https://forums.autosport.com/topic/157599-best-website-for-f1-statistics)
- [Mark Hughes: Tyre-wrecking Sepang could produce an F1 upset (Motor Sport)](https://www.motorsportmagazine.com/articles/single-seaters/f1/mark-hughes-tyre-wrecking-sepang-could-produce-an-f1-upset/)
- [Baseball Savant player page](https://baseballsavant.mlb.com/savant-player/shohei-ohtani-660271) · [MLB.com: These new-look Statcast player pages are art](https://www.mlb.com/news/baseball-savant-statcast-player-pages-new-look) · [Savant changelog: player comparison tool](https://baseballsavant.mlb.com/changelog/2026-07-20-player-comparison-tool)
- [FBref](https://fbref.com/en/) · [FotMob](https://www.fotmob.com/) · [PerfectionGeeks: FotMob app review](https://www.perfectiongeeks.com/blogs/fotmob-app-review) · [StatMuse](https://www.statmuse.com/) · [Opta Analyst](https://theanalyst.com/) · [MoneyPuck](https://moneypuck.com/) · [NFL Next Gen Stats](https://nextgenstats.nfl.com/)
- [Our World in Data: life expectancy](https://ourworldindata.org/grapher/life-expectancy) · [The Pudding](https://pudding.cool/) · [Flighty](https://flighty.com/)
- [Juice Analytics: How year-in-review personalized data storytelling became a business strategy](https://www.juiceanalytics.com/writing/how-year-in-review-personalized-data-storytelling-became-a-business-strategy)
