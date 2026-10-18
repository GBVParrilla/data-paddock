# Architecture

Data Paddock is a static site. A Python pipeline turns public F1 timing data into a SQLite
database, Claude writes the stories into the same database, and an exporter writes every API
response the site needs as JSON. GitHub Pages serves those files and the React app. Nothing runs
on a server at view time.

```
Jolpica (results, quali, entry lists)  ─┐
OpenF1 (laps, stints, pits, positions,  ├─► ingest ─► raw tables ─► transforms ─► headline_* / detail_*
        race control, weather, location)│                                          pivotal_moments
MultiViewer (circuit rotation, corners)─┘                                          track_outlines, turn deltas
                                                                                         │
                                                         narratives (Claude) ◄────────────┤
                                                         stories/*.md edits ──────────────┤
                                                                                         ▼
                                                         export_static ─► frontend/dist/data/*.json
                                                         vite build    ─► frontend/dist (GitHub Pages)
```

## Stages

| Stage | Code | Command |
|---|---|---|
| Ingest schedule, results, details | `f1tracker/ingest/` (`season.py` orchestrates), clients in `f1tracker/clients/` | `make ingest YEAR=2026` |
| Transforms (headline, detail, moments) | `f1tracker/transforms/`, `f1tracker/analysis/pivotal.py`, `analysis/midfield.py` | `make transform YEAR=2026` |
| Track outlines, turn deltas | `f1tracker/analysis/track.py`, `analysis/turns.py` (in `pipeline.py`) | part of `make ingest` |
| Stories | `f1tracker/narratives/` (plan → Claude call → save), `pipeline.generate_season_stories` | `make stories YEAR=2026` |
| Story corrections | `stories/**/*.md` → `story_edits` (`narratives/edits.py`) | synced by every pipeline run and export |
| Export | `f1tracker/export.py` (calls the FastAPI handlers in `api/main.py` directly) | `make export` |
| Frontend dev server (live API) | `frontend/` (Vite, React 19, Tailwind 4, Recharts) + `scripts/serve.py` | `make dev` |
| Production build + preview | `VITE_STATIC=1` build with exported data in `dist/data` | `make build && make preview` |
| Checks | pytest (unit + data invariants), oxlint, tsc, Playwright crawl | `make check` |

The GitHub workflow `.github/workflows/site.yml` runs ingest → stories → save DB → export →
build → deploy. The database lives as an asset on the `db-snapshot` release between runs.

## Database (f1tracker/models.py)

- Core: `seasons`, `events`, `sessions` (`status` upcoming/live/completed is the seam for live
  mode), `drivers`, `entries` (team and car number per driver per event).
- Raw: `results`, `laps`, `stints`, `pit_stops`, `race_control`, `weather`.
- Derived: `headline_practice|qualifying|race`, `headline_session_summary`,
  `detail_long_run_pace|qualifying_segments|stint_timeline|degradation|position_by_lap|sector_deltas`,
  `pivotal_moments`, `track_outlines`, `turn_delta_cache`.
- Stories: `driver_session_narratives`, `driver_weekend_arcs`, `season_arcs`,
  `comparison_narratives`, each cached by `input_hash`; `story_edits` layers human corrections on top.

## Published JSON (frontend/dist/data)

| File | Built by (`api/main.py`) | Read by (frontend) |
|---|---|---|
| `seasons.json` | `list_seasons` | Shell (year select), Home |
| `drivers.json` | `list_drivers` | (unused by pages) |
| `seasons/{year}/events.json` | `season_events` | Home, SeasonPage |
| `seasons/{year}/standings.json` | `season_standings` | Home (championship), SeasonPage |
| `seasons/{year}/arc/{driver\|team}/{id}.json` | `present_season_arc` | SeasonPage story |
| `events/{id}.json` | `get_event` | RaceWeekend header |
| `events/{id}/sessions.json` | `event_sessions` | RaceWeekend, Home (latest race) |
| `events/{id}/track-outline.json` | `outline_to_dict` | TrackMap (Home cards, RaceWeekend) |
| `events/{id}/drivers/{d}/weekend-arc.json` | `present_weekend_arc` | DriverStory |
| `sessions/{id}/headline.json` | `session_headline` | Classification, tiles, everything that names drivers |
| `sessions/{id}/detail.json` | `session_detail` | PositionChart, DeepDive, sectors, CompareView |
| `sessions/{id}/pivotal-moments.json` | `pivotal_moments` | Key moments |
| `sessions/{id}/chart-annotations.json` | `chart_annotations` | PositionChart (SC/VSC bands) |
| `sessions/{id}/lap-times.json` | `lap_times` | CompareView (gap chart) |
| `sessions/{id}/comparisons.json` | `stored_comparisons` | CompareView story |
| `sessions/{id}/midfield-spotlight.json` | `midfield_spotlight` | Tiles, Beyond the podium, Home |
| `sessions/{id}/drivers/{d}/narrative.json` | `present_driver_session` | DriverStory |
| `sessions/{id}/drivers/{d}/turn-deltas.json` | cached `compute_turn_deltas` | Turn-by-turn tab, circuit corner colours |

The frontend maps each API call to its file in `frontend/src/api/client.ts` (`STATIC` mode).

## Live mode (future)

`sessions.status` and the fetch → parse → upsert ingest functions are designed so a poller can
call them repeatedly during a session; the export/site would then need a refresh loop.
