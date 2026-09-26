"""Load raw rows for a session, run the pure transforms, upsert derived tables."""
from __future__ import annotations

import logging

from sqlalchemy import delete, select
from sqlalchemy.orm import Session as OrmSession

from ..db import upsert
from ..ingest.state import get_state
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
    Lap,
    PitStop,
    Result,
    Session,
    Stint,
)
from ..util import utcnow
from . import detail, headline

log = logging.getLogger(__name__)


def _rows(db: OrmSession, model, session_id: int) -> list[dict]:
    cols = [c.name for c in model.__table__.columns]
    return [dict(zip(cols, r)) for r in db.execute(select(*[getattr(model, c) for c in cols]).where(model.session_id == session_id)).all()]


def driver_names(db: OrmSession) -> dict[int, str]:
    return {d.id: d.full_name for d in db.scalars(select(Driver)).all()}


def _replace(db: OrmSession, model, session_id: int, rows: list[dict], pk: list[str]) -> int:
    """Upsert rows, then drop any stale rows for the session not in the new set."""
    for r in rows:
        r["session_id"] = session_id
    upsert(db, model, rows, pk)
    if rows:
        keep = {tuple(r[k] for k in pk) for r in rows}
        existing = db.execute(select(*[getattr(model, k) for k in pk]).where(model.session_id == session_id)).all()
        stale = [tuple(e) for e in existing if tuple(e) not in keep]
        for key in stale:
            db.execute(delete(model).where(*[getattr(model, k) == v for k, v in zip(pk, key)]))
    else:
        db.execute(delete(model).where(model.session_id == session_id))
    return len(rows)


def run_transforms(db: OrmSession, session_id: int) -> dict[str, int]:
    session = db.get(Session, session_id)
    if session is None:
        raise ValueError(f"session {session_id} not found")
    event = db.get(Event, session.event_id)
    stype = session.session_type
    laps = _rows(db, Lap, session_id)
    stints = _rows(db, Stint, session_id)
    pits = _rows(db, PitStop, session_id)
    results = _rows(db, Result, session_id)
    names = driver_names(db)
    counts: dict[str, int] = {}

    practice_rows = quali_rows = race_rows = None
    if stype in PRACTICE_LIKE:
        practice_rows = headline.compute_headline_practice(laps)
        counts["headline_practice"] = _replace(db, HeadlinePractice, session_id, practice_rows, ["session_id", "driver_id"])
    if stype in QUALI_LIKE:
        quali_rows = headline.compute_headline_qualifying(results)
        counts["headline_qualifying"] = _replace(db, HeadlineQualifying, session_id, quali_rows, ["session_id", "driver_id"])
        counts["detail_qualifying_segments"] = _replace(
            db, DetailQualifyingSegment, session_id, detail.compute_qualifying_segments(results), ["session_id", "driver_id", "segment"]
        )
    if stype in RACE_LIKE:
        race_rows = headline.compute_headline_race(results, pits)
        counts["headline_race"] = _replace(db, HeadlineRace, session_id, race_rows, ["session_id", "driver_id"])
        counts["detail_position_by_lap"] = _replace(
            db, DetailPositionByLap, session_id, detail.compute_position_by_lap(laps), ["session_id", "driver_id", "lap_number"]
        )

    summary = headline.compute_session_summary(stype, event.name, names, practice=practice_rows, qualifying=quali_rows, race=race_rows)
    upsert(db, HeadlineSessionSummary, [dict(session_id=session_id, summary_text=summary)], ["session_id"])

    # Detail tables common to all session types
    counts["detail_long_run_pace"] = _replace(db, DetailLongRunPace, session_id, detail.compute_long_run_pace(laps, stints), ["session_id", "driver_id", "compound"])
    counts["detail_stint_timeline"] = _replace(db, DetailStintTimeline, session_id, detail.compute_stint_timeline(stints), ["session_id", "driver_id", "stint_number"])
    counts["detail_degradation"] = _replace(
        db, DetailDegradation, session_id, detail.compute_degradation(laps, stints), ["session_id", "driver_id", "stint_number", "lap_number_in_stint"]
    )
    counts["detail_sector_deltas"] = _replace(
        db, DetailSectorDelta, session_id, detail.compute_sector_deltas(laps), ["session_id", "driver_id", "lap_number", "sector"]
    )

    # Pivotal moments are pure data too - recompute alongside transforms.
    from ..analysis.pivotal import detect_pivotal_moments

    counts["pivotal_moments"] = detect_pivotal_moments(db, session_id)

    st = get_state(db, session_id)
    st.transforms_done = True
    st.transforms_at = utcnow()
    log.info("session %d (%s): transforms %s", session_id, stype, counts)
    return counts
