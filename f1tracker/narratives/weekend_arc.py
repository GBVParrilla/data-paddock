"""Driver weekend arc: FP -> Quali/Sprint -> Race, built from per-session narratives."""
from __future__ import annotations

import json
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session as OrmSession

from ..models import Driver, DriverWeekendArc, Event, HeadlinePractice, HeadlineQualifying, HeadlineRace, Session, SessionIngestionState
from ..util import utcnow
from .driver_session import plan_driver_session_narrative
from .edits import driver_session_key, edited_text
from .inputs import SESSION_LABELS
from .jobs import StoryJob
from .llm import stable_hash
from .prompts import SCHEMA_ARC, SYSTEM_WEEKEND_ARC

log = logging.getLogger(__name__)

ORDER = {"FP1": 0, "FP2": 1, "FP3": 2, "SQ": 3, "S": 4, "Q": 5, "R": 6}


def _headline_for(db: OrmSession, session: Session, driver_id: int) -> dict | None:
    if session.session_type in ("FP1", "FP2", "FP3"):
        r = db.get(HeadlinePractice, (session.id, driver_id))
        return {"rank": r.rank, "gap_to_fastest_ms": r.gap_to_fastest_ms} if r else None
    if session.session_type in ("Q", "SQ"):
        r = db.get(HeadlineQualifying, (session.id, driver_id))
        return {"position": r.position, "gap_to_pole_ms": r.gap_to_pole_ms, "eliminated_in": r.eliminated_in} if r else None
    r = db.get(HeadlineRace, (session.id, driver_id))
    return {"grid": r.grid_position, "finish": r.finish_position, "points": r.points, "status": r.status} if r else None


def _existing(db: OrmSession, event_id: int, driver_id: int) -> DriverWeekendArc | None:
    return db.scalar(select(DriverWeekendArc).where(DriverWeekendArc.event_id == event_id, DriverWeekendArc.driver_id == driver_id))


class MissingSessionStory(ValueError):
    """A session story the arc depends on hasn't been written (and generate_missing was False)."""


def plan_weekend_arc(db: OrmSession, event_id: int, driver_id: int, *, force: bool = False, generate_missing: bool = True) -> tuple[DriverWeekendArc | None, StoryJob | None]:
    """Built from the per-session stories (human-edited versions win, so corrections flow into the arc)."""
    event = db.get(Event, event_id)
    driver = db.get(Driver, driver_id)
    if event is None or driver is None:
        raise ValueError("event or driver not found")
    sessions = db.scalars(select(Session).where(Session.event_id == event_id)).all()
    sessions.sort(key=lambda s: ORDER[s.session_type])
    parts = []
    for s in sessions:
        st = db.get(SessionIngestionState, s.id)
        if not (st and st.transforms_done):
            continue
        headline = _headline_for(db, s, driver_id)
        if headline is None:
            continue
        narrative, job = plan_driver_session_narrative(db, s.id, driver_id)
        if job is not None:
            if not generate_missing:
                raise MissingSessionStory(f"session {s.id} story for driver {driver_id} is missing or out of date")
            narrative = job.run(db)
        recap = edited_text(db, driver_session_key(db, s.id, driver_id), narrative.narrative_text)
        parts.append({"session": SESSION_LABELS[s.session_type], "session_type": s.session_type, "headline": headline, "recap": recap})
    if not parts:
        raise ValueError(f"no session data for driver {driver_id} at event {event_id}")
    payload = {"event": event.name, "round": event.round, "sprint_weekend": event.has_sprint, "driver": driver.full_name, "team": driver.team, "sessions": parts}
    h = stable_hash(payload)
    existing = _existing(db, event_id, driver_id)
    if existing and existing.input_hash == h and not force:
        return existing, None

    def save(db: OrmSession, data: dict, model_used: str) -> DriverWeekendArc:
        row = _existing(db, event_id, driver_id)
        if row is None:
            row = DriverWeekendArc(event_id=event_id, driver_id=driver_id, arc_text="", generated_at=utcnow(), model_used=model_used, input_hash=h)
            db.add(row)
        row.arc_text = data["arc_text"].strip()
        row.generated_at = utcnow()
        row.model_used = model_used
        row.input_hash = h
        db.flush()
        return row

    user = "Weekend data (JSON):\n" + json.dumps(payload, indent=1, default=str)
    return existing, StoryJob(f"weekend arc event={event_id} driver={driver_id}", SYSTEM_WEEKEND_ARC, user, SCHEMA_ARC, save)


def get_or_generate_weekend_arc(db: OrmSession, event_id: int, driver_id: int, *, force: bool = False) -> DriverWeekendArc:
    existing, job = plan_weekend_arc(db, event_id, driver_id, force=force)
    return existing if job is None else job.run(db)
