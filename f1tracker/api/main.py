"""FastAPI layer (local use). Narrative endpoints return the stored story, generating it on first request
if the pipeline hasn't yet; human edits from stories/*.md are layered on top. The published site
uses the same handlers via scripts/export_static.py and never calls Claude."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterator

from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
from sqlalchemy.orm import Session as OrmSession

from ..analysis.midfield import identify_midfield_story
from ..analysis.track import build_track_outline, outline_to_dict
from ..analysis.turns import get_or_compute_turn_deltas
from ..db import get_sessionmaker, init_db
from ..ingest.entries import entry_map, event_drivers
from ..models import (
    PRACTICE_LIKE,
    QUALI_LIKE,
    RACE_LIKE,
    DetailDegradation,
    DetailLongRunPace,
    DetailPositionByLap,
    DetailQualifyingSegment,
    DetailSectorDelta,
    DetailStintTimeline,
    Driver,
    Event,
    HeadlinePractice,
    HeadlineQualifying,
    HeadlineRace,
    HeadlineSessionSummary,
    ComparisonNarrative,
    Entry,
    Lap,
    PitStop,
    PivotalMoment,
    RaceControl,
    Result,
    Season,
    Session,
    SessionIngestionState,
)
from ..narratives.compare import build_comparison, plan_comparison_narrative
from ..narratives.driver_session import plan_driver_session_narrative
from ..narratives.edits import present_comparison, present_driver_session, present_season_arc, present_weekend_arc, sync_if_changed, template_driver_session
from ..narratives.llm import NarrativeGenerationError
from ..narratives.season_arc import plan_season_arc
from ..narratives.weekend_arc import plan_weekend_arc
from ..transforms.headline import race_counts

app = FastAPI(title="F1 Data + Storytelling Tracker", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET"], allow_headers=["*"])
FRONTEND_DIST = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"


@app.on_event("startup")
def _startup() -> None:
    init_db()


def get_db() -> Iterator[OrmSession]:
    db = get_sessionmaker()()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _row(obj: Any) -> dict[str, Any]:
    return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}


def _driver_map(db: OrmSession) -> dict[int, dict[str, Any]]:
    return {d.id: {"id": d.id, "driver_ref": d.driver_ref, "name": d.full_name, "code": d.code, "team": d.team, "number": d.number} for d in db.scalars(select(Driver)).all()}


def _session_or_404(db: OrmSession, session_id: int) -> Session:
    s = db.get(Session, session_id)
    if s is None:
        raise HTTPException(404, f"session {session_id} not found")
    return s


def _driver_or_404(db: OrmSession, driver_id: int) -> Driver:
    d = db.get(Driver, driver_id)
    if d is None:
        raise HTTPException(404, f"driver {driver_id} not found")
    return d


def _narrative_errors(fn, *args, **kwargs):
    sync_if_changed(args[0])  # pick up stories/*.md edits without a restart
    try:
        return fn(*args, **kwargs)
    except NarrativeGenerationError as exc:
        raise HTTPException(503, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


def _stored_or_generate(db: OrmSession, plan, *args, **kwargs):
    """The stored story, (re)written by Claude first if missing or out of date. If Claude can't be
    reached, an older stored version is still better than an error."""
    existing, job = plan(db, *args, **kwargs)
    if job is None:
        return existing
    try:
        return job.run(db)
    except NarrativeGenerationError:
        if existing is not None:
            return existing
        raise


# ---------------------------------------------------------------------------
@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.get("/drivers")
def list_drivers(db: OrmSession = Depends(get_db)) -> list[dict]:
    return list(_driver_map(db).values())


@app.get("/seasons")
def list_seasons(db: OrmSession = Depends(get_db)) -> list[dict]:
    return [{"id": s.id, "year": s.year} for s in db.scalars(select(Season).order_by(Season.year.desc())).all()]


@app.get("/meta")
def site_meta(db: OrmSession = Depends(get_db)) -> dict:
    """What the site's data covers: the latest season's last completed round, and when this was produced
    (the freshness stamp, REVIEW_ROUND2 #42)."""
    season = db.scalars(select(Season).order_by(Season.year.desc())).first()
    done = [e for e in season_events(season.year, db=db) if e["completed"]] if season else []
    last = max(done, key=lambda e: e["round"]) if done else None
    return {
        "season_year": season.year if season else None,
        "last_round": last["round"] if last else None,
        "last_event": last["name"] if last else None,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


@app.get("/events/{event_id}/track-outline")
def track_outline(event_id: int, force: bool = False, db: OrmSession = Depends(get_db)) -> dict:
    if db.get(Event, event_id) is None:
        raise HTTPException(404, f"event {event_id} not found")
    try:
        return outline_to_dict(build_track_outline(db, event_id, force=force))
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.get("/seasons/{year}/events")
def season_events(year: int, db: OrmSession = Depends(get_db)) -> list[dict]:
    season = db.scalar(select(Season).where(Season.year == year)) if year > 1900 else db.get(Season, year)
    if season is None:
        raise HTTPException(404, f"season {year} not found")
    events = db.scalars(select(Event).where(Event.season_id == season.id).order_by(Event.round)).all()
    out = []
    for e in events:
        race = db.scalar(select(Session).where(Session.event_id == e.id, Session.session_type == "R"))
        top = db.scalars(select(HeadlineRace).where(HeadlineRace.session_id == race.id, HeadlineRace.finish_position.in_([1, 2, 3])).order_by(HeadlineRace.finish_position)).all() if race else []
        drivers = event_drivers(db, e.id, {r.driver_id for r in top})
        podium = [drivers.get(r.driver_id) for r in top]
        out.append({**_row(e), "season_year": season.year, "winner": podium[0] if podium else None, "podium": podium, "completed": bool(podium)})
    return out


@app.get("/seasons/{year}/standings")
def season_standings(year: int, db: OrmSession = Depends(get_db)) -> dict:
    """Championship tables from race + sprint results, with each driver's finish and points scored by round."""
    season = db.scalar(select(Season).where(Season.year == year)) if year > 1900 else db.get(Season, year)
    if season is None:
        raise HTTPException(404, f"season {year} not found")
    drivers = _driver_map(db)
    q = (
        select(HeadlineRace, Session.session_type, Event.round, Event.id)
        .join(Session, Session.id == HeadlineRace.session_id)
        .join(Event, Event.id == Session.event_id)
        .where(Event.season_id == season.id)
        .order_by(Event.round)
    )
    entries: dict[int, dict[int, Entry]] = {}
    table: dict[int, dict] = {}
    teams: dict[str, dict] = {}  # constructor key -> {team, constructor_id, points}
    rounds: set[int] = set()
    for hr, stype, rnd, eid in db.execute(q).all():
        d = drivers.get(hr.driver_id)
        if d is None:
            continue
        entry = entries.setdefault(eid, entry_map(db, eid)).get(hr.driver_id)
        team = entry.team if entry else d["team"]
        rounds.add(rnd)
        row = table.setdefault(hr.driver_id, {"driver_id": hr.driver_id, "name": d["name"], "code": d["code"], "team": team, "teams": [], "points": 0.0, "wins": 0, "podiums": 0, "results": {}, "round_points": {}})
        row["team"] = team  # latest round wins
        if team not in row["teams"]:
            row["teams"].append(team)
        row["points"] += hr.points or 0
        row["round_points"][rnd] = row["round_points"].get(rnd, 0) + (hr.points or 0)
        key = (entry.constructor_id if entry and entry.constructor_id else team) or "unknown"
        t = teams.setdefault(key, {"team": team, "constructor_id": entry.constructor_id if entry else None, "points": 0.0})
        t["team"] = team  # latest display name
        t["points"] += hr.points or 0
        if stype == "R":
            row["results"][rnd] = {"position": hr.finish_position, "status": hr.status_code, "team": team}
            if hr.finish_position == 1:
                row["wins"] += 1
            if hr.finish_position and hr.finish_position <= 3:
                row["podiums"] += 1
    drivers_out = sorted(table.values(), key=lambda r: (-r["points"], -r["wins"], -r["podiums"]))
    for i, r in enumerate(drivers_out):
        r["position"] = i + 1
    teams_out = [{**t, "position": i + 1} for i, t in enumerate(sorted(teams.values(), key=lambda t: -t["points"]))]
    return {"year": season.year, "rounds": sorted(rounds), "drivers": drivers_out, "teams": teams_out}


@app.get("/events/{event_id}")
def get_event(event_id: int, db: OrmSession = Depends(get_db)) -> dict:
    e = db.get(Event, event_id)
    if e is None:
        raise HTTPException(404, f"event {event_id} not found")
    season = db.get(Season, e.season_id)
    return {**_row(e), "season_year": season.year}


@app.get("/events/{event_id}/sessions")
def event_sessions(event_id: int, db: OrmSession = Depends(get_db)) -> list[dict]:
    if db.get(Event, event_id) is None:
        raise HTTPException(404, f"event {event_id} not found")
    order = {"FP1": 0, "FP2": 1, "FP3": 2, "SQ": 3, "S": 4, "Q": 5, "R": 6}
    sessions = db.scalars(select(Session).where(Session.event_id == event_id)).all()
    out = []
    for s in sorted(sessions, key=lambda s: order[s.session_type]):
        st = db.get(SessionIngestionState, s.id)
        out.append({**_row(s), "ingestion": {"results": bool(st and st.results_done), "details": bool(st and st.details_done), "transforms": bool(st and st.transforms_done)}})
    return out


@app.get("/sessions/{session_id}/headline")
def session_headline(session_id: int, db: OrmSession = Depends(get_db)) -> dict:
    """The session's classification, with driver cards for this session's entrants only
    (team and car number as entered for this event)."""
    s = _session_or_404(db, session_id)
    summary = db.get(HeadlineSessionSummary, session_id)
    out: dict[str, Any] = {"session": _row(s), "summary": summary.summary_text if summary else None}
    if s.session_type in PRACTICE_LIKE:
        rows = [_row(r) for r in db.scalars(select(HeadlinePractice).where(HeadlinePractice.session_id == session_id).order_by(HeadlinePractice.rank)).all()]
        out["practice"] = rows
    elif s.session_type in QUALI_LIKE:
        rows = db.scalars(select(HeadlineQualifying).where(HeadlineQualifying.session_id == session_id)).all()
        rows = [_row(r) for r in sorted(rows, key=lambda r: (r.position is None, r.position or 0))]
        out["qualifying"] = rows
    elif s.session_type in RACE_LIKE:
        rows = db.scalars(select(HeadlineRace).where(HeadlineRace.session_id == session_id)).all()
        rows = [_row(r) for r in sorted(rows, key=lambda r: r.classification_order or 999)]
        gaps = {r.driver_id: r.gap_to_leader_ms for r in db.scalars(select(Result).where(Result.session_id == session_id)).all()}
        for r in rows:  # a time gap only on the lead lap; lapped cars show laps down instead
            r["gap_to_winner_ms"] = gaps.get(r["driver_id"]) if r["status_code"] == "FIN" else None
        out["race"] = rows
        out["counts"] = race_counts(rows)
    else:
        rows = []
    out["drivers"] = {str(k): v for k, v in event_drivers(db, s.event_id, {r["driver_id"] for r in rows}).items()}
    return out


@app.get("/sessions/{session_id}/detail")
def session_detail(session_id: int, driver_id: int | None = Query(None), db: OrmSession = Depends(get_db)) -> dict:
    _session_or_404(db, session_id)

    def rows(model, order):
        q = select(model).where(model.session_id == session_id)
        if driver_id is not None:
            q = q.where(model.driver_id == driver_id)
        return [_row(r) for r in db.scalars(q.order_by(*order)).all()]

    # a car that never started has no stint, whatever tyres OpenF1 says it was fitted with (REVIEW_ROUND2 #44)
    dns = set(db.scalars(select(HeadlineRace.driver_id).where(HeadlineRace.session_id == session_id, HeadlineRace.status_code == "DNS")).all())
    return {
        "long_run_pace": rows(DetailLongRunPace, [DetailLongRunPace.avg_lap_time_ms]),
        "qualifying_segments": rows(DetailQualifyingSegment, [DetailQualifyingSegment.segment, DetailQualifyingSegment.best_lap_ms]),
        "stint_timeline": [r for r in rows(DetailStintTimeline, [DetailStintTimeline.driver_id, DetailStintTimeline.stint_number]) if r["driver_id"] not in dns],
        "degradation": rows(DetailDegradation, [DetailDegradation.driver_id, DetailDegradation.stint_number, DetailDegradation.lap_number_in_stint]),
        "position_by_lap": rows(DetailPositionByLap, [DetailPositionByLap.lap_number, DetailPositionByLap.position]),
        "sector_deltas": rows(DetailSectorDelta, [DetailSectorDelta.driver_id, DetailSectorDelta.lap_number, DetailSectorDelta.sector]),
        "pit_stops": rows(PitStop, [PitStop.driver_id, PitStop.lap_number]),
    }


@app.get("/sessions/{session_id}/drivers/{driver_id}/turn-deltas")
def turn_deltas(session_id: int, driver_id: int, db: OrmSession = Depends(get_db)) -> dict:
    _session_or_404(db, session_id)
    _driver_or_404(db, driver_id)
    try:
        return get_or_compute_turn_deltas(db, session_id, driver_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.get("/sessions/{session_id}/drivers/{driver_id}/narrative")
def driver_narrative(session_id: int, driver_id: int, force: bool = False, db: OrmSession = Depends(get_db)) -> dict:
    _session_or_404(db, session_id)
    _driver_or_404(db, driver_id)
    n = _narrative_errors(_stored_or_generate, db, plan_driver_session_narrative, session_id, driver_id, force=force)
    return present_driver_session(db, n) if n is not None else template_driver_session(db, session_id, driver_id)


@app.get("/events/{event_id}/drivers/{driver_id}/weekend-arc")
def weekend_arc(event_id: int, driver_id: int, force: bool = False, db: OrmSession = Depends(get_db)) -> dict:
    _driver_or_404(db, driver_id)
    if db.get(Event, event_id) is None:
        raise HTTPException(404, f"event {event_id} not found")
    arc = _narrative_errors(_stored_or_generate, db, plan_weekend_arc, event_id, driver_id, force=force)
    return present_weekend_arc(db, arc)


@app.get("/seasons/{season_id}/arc")
def season_arc(season_id: int, subject_type: str = Query(..., pattern="^(driver|team)$"), subject_id: str = Query(...), force: bool = False, db: OrmSession = Depends(get_db)) -> dict:
    season = db.scalar(select(Season).where(Season.year == season_id)) if season_id > 1900 else db.get(Season, season_id)
    if season is None:
        raise HTTPException(404, f"season {season_id} not found")
    arc = _narrative_errors(_stored_or_generate, db, plan_season_arc, season.id, subject_type, subject_id, force=force)
    return present_season_arc(db, arc)


@app.get("/sessions/{session_id}/pivotal-moments")
def pivotal_moments(session_id: int, db: OrmSession = Depends(get_db)) -> list[dict]:
    _session_or_404(db, session_id)
    return [_row(m) for m in db.scalars(select(PivotalMoment).where(PivotalMoment.session_id == session_id).order_by(PivotalMoment.magnitude_score.desc())).all()]


@app.get("/sessions/{session_id}/race-control")
def race_control(session_id: int, db: OrmSession = Depends(get_db)) -> dict:
    """The session's incident timeline: neutralisations, red flags, penalties, investigations as
    cases (noted -> decision), and deleted lap times. Routine sector flags and pit-lane notices are dropped."""
    s = _session_or_404(db, session_id)
    from ..analysis.race_control import cases, neutral_periods, parse_messages, tidy

    numbers = {e.car_number: e.driver_id for e in entry_map(db, s.event_id).values() if e.car_number is not None}
    incidents = parse_messages(db.scalars(select(RaceControl).where(RaceControl.session_id == session_id)).all(), numbers)
    events = [
        {"lap_number": i.lap, "time": i.time, "kind": i.kind, "driver_ids": i.driver_ids, "turn": i.turn, "reason": i.reason.lower() if i.reason else None, "outcome": i.outcome, "text": tidy(i.message)}
        for i in incidents
    ]
    return {"periods": [{k: v for k, v in p.items() if k != "time"} for p in neutral_periods(incidents)], "cases": cases(incidents), "events": events}


@app.get("/sessions/{session_id}/chart-annotations")
def chart_annotations(session_id: int, db: OrmSession = Depends(get_db)) -> list[dict]:
    """Key moments placed on the lap axis (neutralisations carry their end lap for shading)."""
    s = _session_or_404(db, session_id)
    drivers = event_drivers(db, s.event_id)
    short = {"safety_car": "SC", "vsc": "VSC", "red_flag": "Red flag", "dnf": "out", "dns": "DNS", "penalty": "penalty", "lead_change": "leads", "undercut": "undercut", "overcut": "overcut", "slow_stop": "slow stop", "pit_cycle": "stops", "incident": "incident", "fastest_lap": "fastest lap"}
    out = []
    for m in db.scalars(select(PivotalMoment).where(PivotalMoment.session_id == session_id).order_by(PivotalMoment.lap_number)).all():
        code = drivers.get(m.driver_id, {}).get("code") if m.driver_id else None
        kind = short.get(m.moment_type, m.moment_type.replace("_", " "))
        label = kind if m.moment_type in ("safety_car", "vsc", "red_flag") else f"{code or ''} {kind}".strip()
        out.append({"lap_number": m.lap_number, "end_lap": m.end_lap, "driver_id": m.driver_id, "label": label, "moment_type": m.moment_type, "description": m.headline or m.description, "magnitude_score": m.magnitude_score})
    return out


@app.get("/sessions/{session_id}/midfield-spotlight")
def midfield_spotlight(session_id: int, generate: bool = True, db: OrmSession = Depends(get_db)) -> dict:
    _session_or_404(db, session_id)
    story = identify_midfield_story(db, session_id)
    if story is None:
        raise HTTPException(404, "no midfield story could be identified for this session")
    if generate:
        n = _narrative_errors(_stored_or_generate, db, plan_driver_session_narrative, session_id, story["driver_id"])
        story["narrative"] = present_driver_session(db, n) if n is not None else template_driver_session(db, session_id, story["driver_id"])
    return story


@app.get("/sessions/{session_id}/compare")
def compare(session_id: int, driver_a: int = Query(...), driver_b: int = Query(...), generate: bool = True, db: OrmSession = Depends(get_db)) -> dict:
    _session_or_404(db, session_id)
    if driver_a == driver_b:
        raise HTTPException(400, "driver_a and driver_b must differ")
    _driver_or_404(db, driver_a)
    _driver_or_404(db, driver_b)
    data = _narrative_errors(build_comparison, db, session_id, driver_a, driver_b)
    if generate:
        n = _narrative_errors(_stored_or_generate, db, plan_comparison_narrative, session_id, driver_a, driver_b)
        data["narrative"] = present_comparison(db, n)
    return data


@app.get("/sessions/{session_id}/lap-times")
def lap_times(session_id: int, db: OrmSession = Depends(get_db)) -> dict[str, list[list[int | None]]]:
    """{driver_id: [[lap_number, lap_time_ms, sector_1_ms, sector_2_ms, sector_3_ms, pit], ...]}: any two-driver gap
    chart, and one lap's sectors when a reader picks it (pit is 1 for an in- or out-lap)."""
    _session_or_404(db, session_id)
    out: dict[str, list[list[int | None]]] = {}
    for lap in db.scalars(select(Lap).where(Lap.session_id == session_id, Lap.lap_time_ms.is_not(None)).order_by(Lap.driver_id, Lap.lap_number)).all():
        out.setdefault(str(lap.driver_id), []).append([lap.lap_number, lap.lap_time_ms, lap.sector_1_ms, lap.sector_2_ms, lap.sector_3_ms, int(bool(lap.is_pit_lap or lap.is_pit_out_lap))])
    return out


@app.get("/sessions/{session_id}/comparisons")
def stored_comparisons(session_id: int, db: OrmSession = Depends(get_db)) -> dict[str, dict]:
    """Every head-to-head story already written for this session, keyed "<low id>-<high id>"."""
    _session_or_404(db, session_id)
    sync_if_changed(db)
    rows = db.scalars(select(ComparisonNarrative).where(ComparisonNarrative.session_id == session_id)).all()
    return {f"{c.driver_a_id}-{c.driver_b_id}": present_comparison(db, c) for c in rows}


# ---------------------------------------------------------------------------
# Built frontend (frontend/dist) served at / when present; API routes take precedence.
if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):
        candidate = FRONTEND_DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(FRONTEND_DIST / "index.html")
