"""Per-driver, per-session story: fact sheet -> Claude (structured) -> fact-check -> store.

Cached by input_hash (the fact sheet + prompt version + model), so a story is rewritten only when
its facts change. A driver who did not start gets no AI story: the code-written one says it all.

Claude writes the headline and the Essential story; the Expert view is the debrief computed in code
(REVIEW_ROUND3 D7). Within a session, a headline whose shape another driver's already has is
rejected and retried (REVIEW_ROUND3 #53, `variety.SessionHeadlines`).
"""
from __future__ import annotations

import json
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session as OrmSession

from ..models import DriverSessionNarrative, Session
from ..util import utcnow
from .factcheck import Violation, check_story
from .facts import build_driver_session_facts, prompt_sheet, story_context
from .jobs import Outcome, StoryJob
from .llm import stable_hash
from .prompts import SCHEMA_DRIVER_STORY, SYSTEM_DRIVER_STORY
from .template import template_story
from .variety import SessionHeadlines

log = logging.getLogger(__name__)


def _existing(db: OrmSession, session_id: int, driver_id: int) -> DriverSessionNarrative | None:
    return db.scalar(select(DriverSessionNarrative).where(DriverSessionNarrative.session_id == session_id, DriverSessionNarrative.driver_id == driver_id))


def plan_driver_session_narrative(db: OrmSession, session_id: int, driver_id: int, *, force: bool = False, sheet: dict | None = None,
                                  headlines: SessionHeadlines | None = None) -> tuple[DriverSessionNarrative | None, StoryJob | None]:
    """(stored narrative, job to (re)write it). The job is None when the stored one is up to date.

    `sheet`: the fact sheet, when the caller built the session's sheets together (to rank candidates
    by how distinctive they are); `headlines`: the session's headline registry."""
    session = db.get(Session, session_id)
    if session is None:
        raise ValueError(f"session {session_id} not found")
    sheet = sheet or build_driver_session_facts(db, session_id, driver_id)
    existing = _existing(db, session_id, driver_id)
    if (sheet.get("result") or {}).get("status") == "did not start":
        return existing, None  # nothing for the model to describe; the published story is the template
    h = stable_hash(sheet)
    if existing and existing.input_hash == h and not force:
        if headlines is not None and existing.headline:
            headlines.seed(driver_id, existing.headline)
        return existing, None
    ctx = story_context(db, session_id)

    def check(data: dict) -> list:
        problems = check_story(data, sheet, roster=ctx["roster"], entrants=ctx["entrants"])
        if not problems and headlines is not None and data.get("headline"):
            other = headlines.claim(driver_id, data["headline"])
            if other:
                problems.append(Violation("headline", f"another driver's headline in this session is built the same way (\"{other}\"): lead with what was distinctive about his session, in a different construction"))
        return problems

    def fallback() -> dict:
        story = template_story(sheet, taken=headlines.clash if headlines is not None else None, driver_id=driver_id)
        if headlines is not None:
            headlines.seed(driver_id, story["headline"])
        return story

    def save(db: OrmSession, outcome: Outcome) -> DriverSessionNarrative:
        data = outcome.data
        row = _existing(db, session_id, driver_id)
        if row is None:
            row = DriverSessionNarrative(session_id=session_id, driver_id=driver_id, session_type=session.session_type, narrative_text="", strategy_analysis_text="", generated_at=utcnow(), model_used=outcome.model, input_hash=h)
            db.add(row)
        row.session_type = session.session_type
        row.headline = data["headline"].strip()
        row.summary = data["essential"].strip()
        # prompt v4 writes no long story or analysis: Expert shows the debrief computed in code. A template
        # (the fallback) still carries both until the debrief replaces them on the page.
        row.narrative_text = (data.get("expert") or "").strip()
        row.strategy_analysis_text = (data.get("analysis") or "").strip()
        row.key_numbers_json = json.dumps(data.get("key_numbers") or [])
        row.glossary_json = json.dumps(data.get("glossary_terms") or [])
        row.is_template = outcome.fallback
        row.attempts = outcome.attempts
        row.rejected_json = json.dumps(outcome.violations) if outcome.violations else None
        row.generated_at = utcnow()
        row.model_used = "template" if outcome.fallback else outcome.model
        row.input_hash = h
        db.flush()
        log.info("story session=%d driver=%d (%s): %s after %d attempt(s)", session_id, driver_id, session.session_type, "template" if outcome.fallback else "claude", outcome.attempts)
        return row

    user = "FACT SHEET (JSON):\n" + json.dumps(prompt_sheet(sheet), indent=1, default=str, ensure_ascii=False)
    written = headlines.written(driver_id) if headlines is not None else []
    if written:
        user += "\n\nHEADLINES ALREADY WRITTEN FOR THIS SESSION (use a different construction):\n" + "\n".join(f"- {h}" for h in written)
    job = StoryJob(f"driver story session={session_id} driver={driver_id}", SYSTEM_DRIVER_STORY, user, SCHEMA_DRIVER_STORY, save,
                   check=check, fallback=fallback)
    return existing, job


def get_or_generate_driver_session_narrative(db: OrmSession, session_id: int, driver_id: int, *, force: bool = False) -> DriverSessionNarrative | None:
    existing, job = plan_driver_session_narrative(db, session_id, driver_id, force=force)
    return existing if job is None else job.run(db)
