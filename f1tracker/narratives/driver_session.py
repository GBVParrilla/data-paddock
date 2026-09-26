"""Per-driver, per-session narrative: lazy generation with input_hash caching."""
from __future__ import annotations

import json
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session as OrmSession

from ..models import DriverSessionNarrative, Session
from ..util import utcnow
from .inputs import build_driver_session_input
from .llm import generate_json, stable_hash
from .prompts import SCHEMA_DRIVER_SESSION, SYSTEM_DRIVER_SESSION

log = logging.getLogger(__name__)


def get_or_generate_driver_session_narrative(db: OrmSession, session_id: int, driver_id: int, *, force: bool = False) -> DriverSessionNarrative:
    session = db.get(Session, session_id)
    if session is None:
        raise ValueError(f"session {session_id} not found")
    payload = build_driver_session_input(db, session_id, driver_id)
    if not payload.get("headline") and not payload.get("laps_completed"):
        raise ValueError(f"no data for driver {driver_id} in session {session_id}")
    h = stable_hash(payload)
    existing = db.scalar(select(DriverSessionNarrative).where(DriverSessionNarrative.session_id == session_id, DriverSessionNarrative.driver_id == driver_id))
    if existing and existing.input_hash == h and not force:
        return existing

    user = "Session data (JSON):\n" + json.dumps(payload, indent=1, default=str)
    data, model_used = generate_json(SYSTEM_DRIVER_SESSION, user, SCHEMA_DRIVER_SESSION)
    if existing is None:
        existing = DriverSessionNarrative(session_id=session_id, driver_id=driver_id, session_type=session.session_type, narrative_text="", strategy_analysis_text="", generated_at=utcnow(), model_used=model_used, input_hash=h)
        db.add(existing)
    existing.session_type = session.session_type
    existing.narrative_text = data["narrative_text"].strip()
    existing.strategy_analysis_text = data["strategy_analysis_text"].strip()
    existing.generated_at = utcnow()
    existing.model_used = model_used
    existing.input_hash = h
    db.flush()
    log.info("generated narrative session=%d driver=%d (%s)", session_id, driver_id, session.session_type)
    return existing
