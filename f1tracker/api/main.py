"""FastAPI layer (local use). Narrative endpoints return the stored story, generating it on first request
if the pipeline hasn't yet; human edits from stories/*.md are layered on top. The published site
uses the same handlers via scripts/export_static.py and never calls Claude."""
from __future__ import annotations

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
    Lap,
    PitStop,
    PivotalMoment,
    Season,
    Session,
    SessionIngestionState,
)
from ..narratives.compare import build_comparison, plan_comparison_narrative
from ..narratives.driver_session import plan_driver_session_narrative
from ..narratives.edits import present_comparison, present_driver_session, present_season_arc, present_weekend_arc, sync_if_changed
from ..narratives.llm import NarrativeGenerationError
from ..narratives.season_arc import plan_season_arc
from ..narratives.weekend_arc import plan_weekend_arc

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
    return [{**_row(e), "season_year": season.year} for e in events]


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
    s = _session_or_404(db, session_id)
    drivers = _driver_map(db)
    summary = db.get(HeadlineSessionSummary, session_id)
    out: dict[str, Any] = {"session": _row(s), "summary": summary.summary_text if summary else None, "drivers": drivers}
    if s.session_type in PRACTICE_LIKE:
        out["practice"] = [_row(r) for r in db.scalars(select(HeadlinePractice).where(HeadlinePractice.session_id == session_id).order_by(HeadlinePractice.rank)).all()]
    elif s.session_type in QUALI_LIKE:
        out["qualifying"] = [_row(r) for r in db.scalars(select(HeadlineQualifying).where(HeadlineQualifying.session_id == session_id).order_by(HeadlineQualifying.position)).all()]
    elif s.session_type in RACE_LIKE:
        out["race"] = [_row(r) for r in db.scalars(select(HeadlineRace).where(HeadlineRace.session_id == session_id).order_by(HeadlineRace.finish_position)).all()]
    return out


@app.get("/sessions/{session_id}/detail")
def session_detail(session_id: int, driver_id: int | None = Query(None), db: OrmSession = Depends(get_db)) -> dict:
    _session_or_404(db, session_id)

    def rows(model, order):
        q = select(model).where(model.session_id == session_id)
        if driver_id is not None:
            q = q.where(model.driver_id == driver_id)
        return [_row(r) for r in db.scalars(q.order_by(*order)).all()]

    return {
        "long_run_pace": rows(DetailLongRunPace, [DetailLongRunPace.avg_lap_time_ms]),
        "qualifying_segments": rows(DetailQualifyingSegment, [DetailQualifyingSegment.segment, DetailQualifyingSegment.best_lap_ms]),
        "stint_timeline": rows(DetailStintTimeline, [DetailStintTimeline.driver_id, DetailStintTimeline.stint_number]),
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
    return present_driver_session(db, n)


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


@app.get("/sessions/{session_id}/chart-annotations")
def chart_annotations(session_id: int, db: OrmSession = Depends(get_db)) -> list[dict]:
    _session_or_404(db, session_id)
    drivers = _driver_map(db)
    out = []
    for m in db.scalars(select(PivotalMoment).where(PivotalMoment.session_id == session_id).order_by(PivotalMoment.lap_number)).all():
        code = drivers.get(m.driver_id, {}).get("code") if m.driver_id else None
        sc_label = "Red flag" if m.description.startswith("Red flag") else "VSC" if "Virtual" in m.description else "Safety car"
        label = {"safety_car": sc_label, "pit_stop": f"{code or ''} pit".strip(), "position_swing": f"{code or ''} {'+' if 'gained' in m.description else '-'}".strip(), "penalty": f"{code or ''} penalty".strip(), "fastest_lap": f"{code or ''} fastest lap".strip()}.get(m.moment_type, m.moment_type)
        out.append({"lap_number": m.lap_number, "driver_id": m.driver_id, "label": label, "moment_type": m.moment_type, "description": m.description, "magnitude_score": m.magnitude_score})
    return out


@app.get("/sessions/{session_id}/midfield-spotlight")
def midfield_spotlight(session_id: int, generate: bool = True, db: OrmSession = Depends(get_db)) -> dict:
    _session_or_404(db, session_id)
    story = identify_midfield_story(db, session_id)
    if story is None:
        raise HTTPException(404, "no midfield story could be identified for this session")
    if generate:
        n = _narrative_errors(_stored_or_generate, db, plan_driver_session_narrative, session_id, story["driver_id"])
        story["narrative"] = present_driver_session(db, n)
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
def lap_times(session_id: int, db: OrmSession = Depends(get_db)) -> dict[str, list[list[int]]]:
    """{driver_id: [[lap_number, lap_time_ms], ...]} - lets the static site build any two-driver gap chart."""
    _session_or_404(db, session_id)
    out: dict[str, list[list[int]]] = {}
    for lap in db.scalars(select(Lap).where(Lap.session_id == session_id, Lap.lap_time_ms.is_not(None)).order_by(Lap.driver_id, Lap.lap_number)).all():
        out.setdefault(str(lap.driver_id), []).append([lap.lap_number, lap.lap_time_ms])
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
