"""Full-season orchestration: results -> details -> transforms for every completed session.

Idempotent and resumable via session_ingestion_state; safe to re-run.
"""
from __future__ import annotations

import logging
import traceback
from dataclasses import dataclass, field

from sqlalchemy import select

from ..db import db_session
from ..ingest.details import ingest_session_details
from ..ingest.results import ingest_session_results
from ..ingest.schedule import ingest_schedule
from ..ingest.state import get_state
from ..models import Event, Season, Session
from ..transforms.runner import run_transforms
from ..util import utcnow

log = logging.getLogger(__name__)

SESSION_ORDER = {"FP1": 0, "FP2": 1, "FP3": 2, "SQ": 3, "S": 4, "Q": 5, "R": 6}


@dataclass
class SeasonRunReport:
    rounds_seen: int = 0
    sessions_seen: int = 0
    sessions_skipped: int = 0
    results_ok: int = 0
    details_ok: int = 0
    transforms_ok: int = 0
    failures: list[tuple[int, str, str]] = field(default_factory=list)


def _step(report: SeasonRunReport, session_id: int, stage: str, fn) -> bool:
    try:
        with db_session() as db:
            ok = fn(db)
        return bool(ok) if ok is not None else True
    except Exception as exc:  # keep going; record the failure
        log.error("session %d %s failed: %s", session_id, stage, exc)
        log.debug(traceback.format_exc())
        report.failures.append((session_id, stage, str(exc)[:300]))
        try:
            with db_session() as db:
                st = get_state(db, session_id)
                st.last_error = f"{stage}: {exc}"[:2000]
        except Exception:
            pass
        return False


def ingest_full_season(year: int, *, rounds: list[int] | None = None, force: bool = False, refresh_schedule: bool = True) -> SeasonRunReport:
    report = SeasonRunReport()
    if refresh_schedule:
        with db_session() as db:
            ingest_schedule(db, year)

    with db_session() as db:
        season = db.scalar(select(Season).where(Season.year == year))
        if season is None:
            raise RuntimeError(f"season {year} not in DB - run ingest_schedule first")
        events = db.scalars(select(Event).where(Event.season_id == season.id).order_by(Event.round)).all()
        plan = []
        for ev in events:
            if rounds and ev.round not in rounds:
                continue
            sessions = db.scalars(select(Session).where(Session.event_id == ev.id)).all()
            sessions.sort(key=lambda s: SESSION_ORDER[s.session_type])
            plan.append((ev.round, ev.name, ev.has_sprint, [(s.id, s.session_type, s.status, s.end_time) for s in sessions]))

    now = utcnow()
    for rnd, name, has_sprint, sessions in plan:
        report.rounds_seen += 1
        log.info("=== Round %d: %s (%s weekend) ===", rnd, name, "sprint" if has_sprint else "standard")
        for sid, stype, status, end_time in sessions:
            report.sessions_seen += 1
            if status != "completed" and (end_time is None or end_time > now):
                log.info("  %s (session %d): %s - skipping", stype, sid, status)
                report.sessions_skipped += 1
                continue
            with db_session() as db:
                st = get_state(db, sid)
                need_results = force or not st.results_done
                need_details = force or not st.details_done
                need_transforms = force or not st.transforms_done or need_results or need_details
            if not (need_results or need_details or need_transforms):
                log.info("  %s (session %d): already ingested - skipping", stype, sid)
                report.sessions_skipped += 1
                continue
            r_ok = d_ok = True
            if need_results:
                r_ok = _step(report, sid, "results", lambda db: ingest_session_results(db, sid))
                report.results_ok += int(r_ok)
            if need_details:
                d_ok = _step(report, sid, "details", lambda db: ingest_session_details(db, sid))
                report.details_ok += int(d_ok)
            if need_transforms and (r_ok or d_ok):
                t_ok = _step(report, sid, "transforms", lambda db: run_transforms(db, sid))
                report.transforms_ok += int(t_ok)
        log.info("=== Round %d done: results=%d details=%d transforms=%d failures=%d ===", rnd, report.results_ok, report.details_ok, report.transforms_ok, len(report.failures))
    return report
