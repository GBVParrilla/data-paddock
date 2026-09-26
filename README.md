# F1 Data + Storytelling Tracker (backend)

Ingests historical F1 session data (Jolpica + OpenF1), computes two tiers of analytics
(casual `headline_*`, avid `detail_*`), detects pivotal moments with pure data logic, and
generates hedged, data-grounded narratives with Claude Fable 5.1. Built for the 2026 season;
structured so a live-ingestion mode can be added without a rearchitecture.

Published as a static website on GitHub Pages: a daily GitHub Action processes new sessions, has
Claude write every story **as the data is processed**, stores them in the database, and publishes
the site. The site only displays stored stories. Anyone can flag a story; the editor corrects it
by committing a Markdown file under [`stories/`](stories/README.md). See
[Publishing](#publishing-github-pages) below.

## Quick start (one click)

Double-click **`Start F1 Tracker.command`** in Finder. It starts the API, serves the built web UI,
and opens http://127.0.0.1:8000 in your browser. Close the terminal window to stop.
(First run builds the frontend, which takes about a minute.)

## Setup

```bash
# Python 3.12 venv (created with uv; any 3.11+ works)
.venv/bin/python -m pip install -r requirements.txt

# Secrets: copy the template and paste your key. .env is gitignored.
cp .env.example .env
```

The Anthropic key is only ever read from the `ANTHROPIC_API_KEY` environment variable
(via `.env` for local dev). It is never a parameter, never logged, never in code.

## Ingest the season

```bash
.venv/bin/python scripts/ingest_schedule.py --year 2026          # calendar + sprint flags + OpenF1 keys
.venv/bin/python scripts/ingest_full_season.py --year 2026       # everything, resumable, rate-limit aware
```

Per-session scripts (used by the orchestrator, handy for debugging):

```bash
.venv/bin/python scripts/ingest_session_results.py --session-id 5
.venv/bin/python scripts/ingest_session_details.py --session-id 5
.venv/bin/python scripts/run_transforms.py --session-id 5
```

`ingest_full_season.py` skips sessions already fully ingested (see `session_ingestion_state`).
Use `--force` to redo, `--rounds 1,2` to limit, `--no-schedule` to skip the calendar refresh.

## Stories: AI first, human-correctable

`scripts/run_pipeline.py` is the whole flow: ingest -> track outlines + turn deltas (fetched once and
cached, since they need OpenF1 telemetry) -> Claude writes the stories, in order:

1. one story per driver per session (`F1_STORY_SESSION_TYPES`, all sessions by default)
2. teammate head-to-heads (`F1_COMPARISON_SESSION_TYPES`) and each driver's weekend arc
3. a season "story so far" for every driver and team

Stories are stored in the DB and cached by `input_hash`: they're rewritten only when their input data
changes (or `PROMPT_VERSION` in `config.py` is bumped), so re-running is cheap. Claude calls run in
parallel (`--workers`, `F1_STORY_WORKERS`), and `--max-new-stories` / `--time-budget-min` cap a run;
whatever is left is picked up by the next run. A full season is roughly 4,000 stories (most of them
per-driver session stories).

```bash
.venv/bin/python scripts/run_pipeline.py --year 2026                  # everything new
.venv/bin/python scripts/run_pipeline.py --year 2026 --no-ingest      # only write missing stories
.venv/bin/python scripts/export_static.py --out frontend/dist/data    # static JSON for the site
```

**Corrections** are Markdown files under `stories/` (format and layout: [stories/README.md](stories/README.md)).
A correction is shown instead of the AI text; the AI version stays stored underneath, and deleting the
file reverts to it. Corrections to session stories also feed into the driver's weekend arc next time
it's written. If Claude later rewrites a story you corrected (because its data changed), the site flags
the correction as needing review in editor mode.

The local API still generates a missing story on first request (handy while developing):

```bash
.venv/bin/python scripts/generate_narrative.py --session-id 5 --driver-id 3           # one driver
.venv/bin/python scripts/generate_narrative.py --session-id 5 --midfield              # spotlight pick
.venv/bin/python scripts/generate_narrative.py --session-id 5 --driver-id 3 --dry-run # see the input JSON
.venv/bin/python scripts/generate_narrative.py --event-id 1 --driver-id 3 --weekend-arc
.venv/bin/python scripts/generate_narrative.py --season 2026 --subject-type team --subject-id "Alpine" --season-arc
```

## API

```bash
.venv/bin/uvicorn f1tracker.api.main:app --reload
```

| Endpoint | Notes |
|---|---|
| `GET /seasons/{year}/events` | year (2026) or season id |
| `GET /events/{event_id}/sessions` | includes ingestion state per session |
| `GET /sessions/{id}/headline` | templated summary + headline table for the session type |
| `GET /sessions/{id}/detail?driver_id=` | all `detail_*` tables (sector deltas are per lap) |
| `GET /sessions/{id}/drivers/{driver_id}/narrative` | generates on first call (LLM) |
| `GET /events/{event_id}/drivers/{driver_id}/weekend-arc` | built from per-session narratives |
| `GET /seasons/{season_id}/arc?subject_type=driver&subject_id=3` | or `subject_type=team&subject_id=Alpine` |
| `GET /sessions/{id}/pivotal-moments` | top 8 by magnitude, no LLM |
| `GET /sessions/{id}/chart-annotations` | `{lap_number, driver_id, label, moment_type}[]` |
| `GET /sessions/{id}/midfield-spotlight` | `?generate=false` to skip the LLM call |
| `GET /sessions/{id}/compare?driver_a=3&driver_b=4` | position-by-lap, stints, gap-over-time + comparative narrative |

LLM-backed endpoints return the stored story when there is one; they return `503` only when a story has never been written and `ANTHROPIC_API_KEY` is missing. `GET /sessions/{id}/lap-times` and `/sessions/{id}/comparisons` feed the static site's comparison view.

## Web UI (frontend/)

React + Vite + Tailwind + Recharts, TypeScript, talking to the API through a small typed client
(`frontend/src/api/client.ts`). Node is vendored into the venv (`.venv/bin/node`, `.venv/bin/npm`),
so no system Node install is needed.

```bash
# production build - FastAPI serves frontend/dist at / (this is what the launcher uses)
PATH="$PWD/.venv/bin:$PATH" npm --prefix frontend run build

# dev server with hot reload (API proxied to :8000)
PATH="$PWD/.venv/bin:$PATH" npm --prefix frontend run dev
```

Pages: `/` (season picker + track grid), `/race/:eventId` (track detail: session tabs, sector-coloured
outline, leaderboard, midfield spotlight, position-by-lap chart with pivotal-moment markers, driver
stories, two-driver comparison), `/season/:year` (season story for a driver or team).

**Track outlines** are our own asset: one clean lap of OpenF1 car-position telemetry per event, rotated
(PCA on the x/y so the long axis runs horizontal - fixes tracks that would otherwise plot "sideways")
and normalized into an SVG path by `GET /events/{id}/track-outline` (pre-generate with
`scripts/generate_track_outlines.py --force` after backfilling lat/lon via `scripts/ingest_schedule.py`,
run once via `scripts/migrate_add_track_geo.py` for an existing DB). Sector boundaries, the rotation, and
the satellite overlay are all best-effort approximations, not measurements - the API gives no ground
truth for any of them.

- **Sector colouring** follows the F1 timing-screen convention: purple = outright fastest, then
  green/yellow/red graded against the field average for that sector (no driver selected shows purple on
  every sector, since each one there already is the session's fastest by construction).
- **Boost zones** (dashed green stripe) mark sustained full-throttle, near-top-speed running - a proxy
  for DRS zones, used because this OpenF1 mirror doesn't populate the real DRS-open telemetry field for
  2026. If a session ever does carry that field, real DRS-open telemetry is used instead automatically.
- **Satellite toggle** overlays the outline (translucent) on Esri World Imagery, centered on the
  circuit's Jolpica lat/lon. OpenF1's local x/y axes aren't documented against true north, so alignment
  is approximate, not surveyed.
- **Team colours** highlight a selected driver everywhere (leaderboard bar, chart line, story border,
  comparison). Two teammates get the same base hue with the second lightened, so they stay distinguishable.
- **Position-by-lap chart**: background (unselected) lines are limited to drivers who made zero pit
  stops, since pit-stop dips are just clutter until you pick that driver. A selected driver always shows
  in full, with its own pit-stop laps marked, plus a tyre-compound strip underneath.

## Layout

```
f1tracker/
  config.py           model string, DB URL, rate limits, PROMPT_VERSION
  db.py               engine, session, dialect-aware upsert (SQLite/Postgres)
  models.py           raw + headline_* + detail_* + narratives + pivotal_moments
  clients/            jolpica.py, openf1.py (pure fetch/parse; reusable by a live poller)
  ingest/             schedule, results, details, drivers (identity), season orchestrator, state
  transforms/         headline.py, detail.py (pure functions), runner.py (upsert)
  analysis/           pivotal.py (moment detection), midfield.py (spotlight selection)
  narratives/         llm.py (SDK wrapper), prompts.py, inputs.py, driver_session/weekend_arc/season_arc/compare
  api/main.py         FastAPI
scripts/              CLI entry points
tests/                pure-function tests (pytest)
```

## Data-source notes (verified against live responses)

- Jolpica has no sprint-qualifying endpoint; SQ and practice classification come from OpenF1 `session_result`.
- OpenF1 laps carry sector times and speed-trap/intermediate speeds per lap; `top_speed_kph` is the max of those.
  Full `car_data` telemetry is not ingested (tens of thousands of samples per driver per session, no extra value for these analytics).
- OpenF1 `pit.lap_number` is the out-lap; `pit_stops.lap_number` is stored as the in-lap ("pitted at the end of lap N").
- OpenF1 flags lap 1 of a race as a pit-out lap, so lap 1 is excluded from clean-lap analytics.
- Positions per lap are derived from OpenF1's timestamped `position` feed at each lap's end time.
- Driver identity is canonical on Jolpica `driverId`; OpenF1 car numbers map through the season's driver list.

## Publishing (GitHub Pages)

`.github/workflows/site.yml` builds the site and deploys it to `https://<user>.github.io/<repo>/`:

| Trigger | What it does |
|---|---|
| daily 06:17 UTC | full: ingest new sessions, Claude writes their stories, save DB, publish |
| push to `main` touching `stories/`, `frontend/`, `f1tracker/`, `scripts/` | publish-only: re-export with the latest code and corrections, no Claude calls |
| Actions tab -> Site -> Run workflow | pick `full` / `stories-only` / `publish-only`, cap or force story writing |

The database (data + stored stories) persists between runs as `f1.db.gz` on the **`db-snapshot`
release**. Don't delete that release, or every story would have to be written again.

One-time setup:

1. Settings -> Pages -> Build and deployment -> Source: **GitHub Actions**.
2. Settings -> Secrets and variables -> Actions -> New repository secret `ANTHROPIC_API_KEY`.
3. Optional repository variables: `F1_YEAR` (default 2026), `MAX_NEW_STORIES` (per-run cap on Claude calls, default 800).
4. Actions -> Site -> Run workflow (`full`). The first backfill of a season takes a few daily runs,
   because each run is capped by `MAX_NEW_STORIES` and a ~4.5 hour time budget.

**Flagging and fixing a story:** every story has a *Flag a problem* link that opens a prefilled GitHub
issue (label `story-flag`). The issue links back to the story in editor mode (`?editor=1`), where
*Edit* opens `stories/<key>.md` in GitHub's editor prefilled with the AI text. Commit it, and the site
republishes with the correction in a few minutes. *Revert to AI* deletes the file. Editor mode only
shows the links; GitHub itself decides who can commit.

The static build (`VITE_STATIC=1`) reads JSON files instead of the API. It uses hash routes
(`/#/race/3`) because Pages has no server-side routing. Teammate head-to-heads have a written story;
the comparison charts still work for any two drivers.

## Live mode later (not built, not blocked)

- `sessions.status` already supports `upcoming | live | completed`.
- All fetch functions take a session key and are side-effect free; all writes are upserts keyed on natural keys.
- Transforms and narrative generation are safe to re-run on the same session; narratives regenerate only when the input hash changes.
- A poller would loop `ingest_session_details -> run_transforms` for sessions with `status='live'`.
