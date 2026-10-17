"""Per-driver, per-session narrative, cached by input_hash."""
from __future__ import annotations

import json
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session as OrmSession

from ..models import DriverSessionNarrative, Session
from ..util import utcnow
from .inputs import build_driver_session_input
from .jobs import StoryJob
from .llm import stable_hash
from .prompts import SCHEMA_DRIVER_SESSION, SYSTEM_DRIVER_SESSION

log = logging.getLogger(__name__)


def _existing(db: OrmSession, session_id: int, driver_id: int) -> DriverSessionNarrative | None:
    return db.scalar(select(DriverSessionNarrative).where(DriverSessionNarrative.session_id == session_id, DriverSessionNarrative.driver_id == driver_id))


def plan_driver_session_narrative(db: OrmSession, session_id: int, driver_id: int, *, force: bool = False) -> tuple[DriverSessionNarrative | None, StoryJob | None]:
    """(stored narrative, job to (re)write it). The job is None when the stored one is up to date."""
    session = db.get(Session, session_id)
    if session is None:
        raise ValueError(f"session {session_id} not found")
    payload = build_driver_session_input(db, session_id, driver_id)
    if not payload.get("headline") and not payload.get("laps_completed"):
        raise ValueError(f"no data for driver {driver_id} in session {session_id}")
    h = stable_hash(payload)
    existing = _existing(db, session_id, driver_id)
    if existing and existing.input_hash == h and not force:
        return existing, None

    def save(db: OrmSession, data: dict, model_used: str) -> DriverSessionNarrative:
        row = _existing(db, session_id, driver_id)
        if row is None:
            row = DriverSessionNarrative(session_id=session_id, driver_id=driver_id, session_type=session.session_type, narrative_text="", strategy_analysis_text="", generated_at=utcnow(), model_used=model_used, input_hash=h)
            db.add(row)
        row.session_type = session.session_type
        row.narrative_text = data["narrative_text"].strip()
        row.strategy_analysis_text = data["strategy_analysis_text"].strip()
        row.generated_at = utcnow()
        row.model_used = model_used
        row.input_hash = h
        db.flush()
        log.info("generated narrative session=%d driver=%d (%s)", session_id, driver_id, session.session_type)
        return row

    user = "Session data (JSON):\n" + json.dumps(payload, indent=1, default=str)
    return existing, StoryJob(f"driver story session={session_id} driver={driver_id}", SYSTEM_DRIVER_SESSION, user, SCHEMA_DRIVER_SESSION, save)


def get_or_generate_driver_session_narrative(db: OrmSession, session_id: int, driver_id: int, *, force: bool = False) -> DriverSessionNarrative:
    existing, job = plan_driver_session_narrative(db, session_id, driver_id, force=force)
    return existing if job is None else job.run(db)
