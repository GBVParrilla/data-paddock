"""Driver weekend arc: practice -> qualifying -> race in a few sentences, from each session's fact
sheet (never from the session stories, so one story's error can't carry into the next)."""
from __future__ import annotations

import json
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session as OrmSession

from ..models import Driver, DriverWeekendArc, Event, Session, SessionIngestionState
from ..util import utcnow
from .factcheck import check_story
from .facts import build_driver_session_facts, story_context
from .jobs import Outcome, StoryJob
from .llm import stable_hash
from .prompts import SCHEMA_ARC, SYSTEM_WEEKEND_ARC

log = logging.getLogger(__name__)

ORDER = {"FP1": 0, "FP2": 1, "FP3": 2, "SQ": 3, "S": 4, "Q": 5, "R": 6}
LIMITS = {"arc_text": 95}


class MissingSessionStory(ValueError):
    """Kept for callers that still catch it; arcs no longer depend on session stories."""


def _existing(db: OrmSession, event_id: int, driver_id: int) -> DriverWeekendArc | None:
    return db.scalar(select(DriverWeekendArc).where(DriverWeekendArc.event_id == event_id, DriverWeekendArc.driver_id == driver_id))


def build_weekend_facts(db: OrmSession, event_id: int, driver_id: int) -> dict:
    event = db.get(Event, event_id)
    driver = db.get(Driver, driver_id)
    if event is None or driver is None:
        raise ValueError("event or driver not found")
    sessions = sorted(db.scalars(select(Session).where(Session.event_id == event_id)).all(), key=lambda s: ORDER[s.session_type])
    parts, team, mate = [], None, None
    for s in sessions:
        st = db.get(SessionIngestionState, s.id)
        if not (st and st.transforms_done):
            continue
        try:
            sheet = build_driver_session_facts(db, s.id, driver_id)
        except ValueError:
            continue
        if not sheet.get("result") or (sheet["result"].get("position") is None and sheet["result"].get("finish") is None and sheet["result"].get("status") is None and not sheet["result"].get("note")):
            continue
        team, mate = sheet["driver"]["team"], sheet["driver"].get("teammate")
        r = sheet["result"]
        part = {"session": s.session_type, "result": sheet.get("result_headline")}
        if s.session_type in ("Q", "SQ"):
            margins = [v for k, v in sorted(r.items()) if k.endswith("_margin")]
            part["margin"] = margins[-1] if margins else None  # the last cut he faced decided his session
            part["teammate_position"] = (r.get("teammate") or {}).get("position")
        if s.session_type in ("R", "S"):
            part["teammate_finish"] = (r.get("teammate") or {}).get("finish")
            part["points"] = r.get("points")
            part["deciding_fact"] = (sheet.get("verdicts") or [None])[0]
        if s.session_type in ("FP1", "FP2", "FP3") and sheet.get("long_runs"):
            ranked = [x for x in sheet["long_runs"] if x.get("rank")]
            if ranked:
                part["long_run"] = f"{ranked[0]['compound'].lower()} long run ranked {ranked[0]['rank']} of {ranked[0]['of_drivers_with_8_plus_laps']}"
        parts.append({k: v for k, v in part.items() if v is not None})
    if not parts:
        raise ValueError(f"no session data for driver {driver_id} at event {event_id}")
    return {"event": event.name, "round": event.round, "driver": driver.full_name, "team": team, "teammate": mate, "sessions": parts, "verdicts": [], "insufficient_data": []}


def weekend_template(facts: dict) -> dict:
    label = {"FP1": "FP1", "FP2": "FP2", "FP3": "FP3", "SQ": "sprint qualifying", "S": "the sprint", "Q": "qualifying", "R": "the race"}
    bits = []
    for p in facts["sessions"]:
        res = (p.get("result") or "").replace(f" in {label[p['session']]}", "")
        bits.append(f"{res} in {label[p['session']]}" if res else label[p["session"]])
    text = f"{facts['driver']}'s weekend: " + ", ".join(bits) + "."
    q = next((p for p in facts["sessions"] if p["session"] == "Q" and p.get("margin")), None)
    if q:
        text += f" In qualifying he {q['margin']}."
    return {"arc_text": text}


def plan_weekend_arc(db: OrmSession, event_id: int, driver_id: int, *, force: bool = False, generate_missing: bool = True) -> tuple[DriverWeekendArc | None, StoryJob | None]:
    facts = build_weekend_facts(db, event_id, driver_id)
    h = stable_hash(facts)
    existing = _existing(db, event_id, driver_id)
    if existing and existing.input_hash == h and not force:
        return existing, None
    any_session = db.scalar(select(Session.id).where(Session.event_id == event_id).limit(1))
    ctx = story_context(db, any_session)
    del generate_missing

    def save(db: OrmSession, outcome: Outcome) -> DriverWeekendArc:
        row = _existing(db, event_id, driver_id)
        if row is None:
            row = DriverWeekendArc(event_id=event_id, driver_id=driver_id, arc_text="", generated_at=utcnow(), model_used=outcome.model, input_hash=h)
            db.add(row)
        row.arc_text = outcome.data["arc_text"].strip()
        row.generated_at = utcnow()
        row.model_used = "template" if outcome.fallback else outcome.model
        row.input_hash = h
        db.flush()
        return row

    user = "WEEKEND FACTS (JSON):\n" + json.dumps(facts, indent=1, default=str, ensure_ascii=False)
    sheet = {**facts, "driver": {"name": facts["driver"], "teammate": facts["teammate"]}}
    job = StoryJob(f"weekend arc event={event_id} driver={driver_id}", SYSTEM_WEEKEND_ARC, user, SCHEMA_ARC, save,
                   check=lambda data: check_story(data, sheet, roster=ctx["roster"], entrants=ctx["entrants"], limits=LIMITS),
                   fallback=lambda: weekend_template(facts))
    return existing, job


def get_or_generate_weekend_arc(db: OrmSession, event_id: int, driver_id: int, *, force: bool = False) -> DriverWeekendArc:
    existing, job = plan_weekend_arc(db, event_id, driver_id, force=force)
    return existing if job is None else job.run(db)
