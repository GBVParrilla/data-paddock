"""End-to-end processing for the published site: ingest -> precompute -> AI stories.

AI first: every story is written here, once, right after its data is processed, and stored in
the DB. The site only ever displays stored stories. Human corrections (stories/*.md) are synced
in at the start so arcs that build on session stories use the corrected text.

Everything is resumable: stories are cached by input hash, so a run that hits its time budget or
story cap simply continues where it left off next time.
"""
from __future__ import annotations

import logging
import time
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass, field
from itertools import combinations
from typing import Callable, Iterator

from sqlalchemy import select
from sqlalchemy.orm import Session as OrmSession

from .analysis.track import build_track_outline
from .analysis.turns import get_or_compute_turn_deltas
from .config import COMPARISON_SESSION_TYPES, STORY_SESSION_TYPES, STORY_WORKERS
from .db import db_session
from .models import (
    PRACTICE_LIKE,
    QUALI_LIKE,
    Driver,
    Event,
    HeadlinePractice,
    HeadlineQualifying,
    HeadlineRace,
    Season,
    Session,
    SessionIngestionState,
    TrackOutline,
    TurnDeltaCache,
)
from .narratives.compare import plan_comparison_narrative
from .narratives.driver_session import plan_driver_session_narrative
from .narratives.edits import sync_story_edits
from .narratives.jobs import StoryJob
from .narratives.llm import NarrativeGenerationError, _get_client
from .narratives.season_arc import plan_season_arc
from .narratives.weekend_arc import MissingSessionStory, plan_weekend_arc

log = logging.getLogger(__name__)

SESSION_ORDER = {"FP1": 0, "FP2": 1, "FP3": 2, "SQ": 3, "S": 4, "Q": 5, "R": 6}


@dataclass
class StoryReport:
    written: int = 0
    up_to_date: int = 0
    failed: int = 0
    skipped: int = 0  # not attempted: budget/time ran out, or a dependency is missing
    failures: list[str] = field(default_factory=list)


class _Budget:
    def __init__(self, max_new: int | None, deadline: float | None):
        self.max_new, self.deadline, self.used = max_new, deadline, 0

    def take(self) -> bool:
        if self.max_new is not None and self.used >= self.max_new:
            return False
        if self.deadline is not None and time.monotonic() >= self.deadline:
            return False
        self.used += 1
        return True


# ---------------------------------------------------------------------------
def processed_sessions(db: OrmSession, season_id: int) -> list[Session]:
    q = (
        select(Session)
        .join(Event, Event.id == Session.event_id)
        .join(SessionIngestionState, SessionIngestionState.session_id == Session.id)
        .where(Event.season_id == season_id, SessionIngestionState.transforms_done.is_(True))
        .order_by(Event.round)
    )
    return sorted(db.scalars(q).all(), key=lambda s: (db.get(Event, s.event_id).round, SESSION_ORDER[s.session_type]))


def session_driver_ids(db: OrmSession, session: Session) -> list[int]:
    model = HeadlinePractice if session.session_type in PRACTICE_LIKE else HeadlineQualifying if session.session_type in QUALI_LIKE else HeadlineRace
    return sorted(db.scalars(select(model.driver_id).where(model.session_id == session.id)).all())


def teammate_pairs(db: OrmSession, driver_ids: list[int]) -> list[tuple[int, int]]:
    drivers = {d.id: d for d in db.scalars(select(Driver).where(Driver.id.in_(driver_ids))).all()}
    return [(a, b) for a, b in combinations(sorted(driver_ids), 2) if drivers[a].team and drivers[a].team == drivers[b].team]


# ---------------------------------------------------------------------------
def precompute_track_outlines(season_id: int, rounds: list[int] | None = None) -> None:
    with db_session() as db:
        events = db.scalars(select(Event).where(Event.season_id == season_id).order_by(Event.round)).all()
        missing = [e.id for e in events if db.get(TrackOutline, e.id) is None and (not rounds or e.round in rounds)]
    for eid in missing:
        try:
            with db_session() as db:
                build_track_outline(db, eid)
        except ValueError as exc:
            log.info("track outline for event %d not available yet: %s", eid, exc)
        except Exception as exc:  # network trouble: try again next run
            log.warning("track outline for event %d failed: %s", eid, exc)


def precompute_turn_deltas(season_id: int, *, rounds: list[int] | None = None, deadline: float | None = None) -> None:
    with db_session() as db:
        todo = []
        for s in processed_sessions(db, season_id):
            if rounds and db.get(Event, s.event_id).round not in rounds:
                continue
            outline = db.get(TrackOutline, s.event_id)
            if outline is None or not outline.turns_json or outline.turns_json == "[]":
                continue
            todo += [(s.id, d) for d in session_driver_ids(db, s) if db.get(TurnDeltaCache, (s.id, d)) is None]
    log.info("turn deltas to compute: %d", len(todo))
    for i, (sid, did) in enumerate(todo):
        if deadline is not None and time.monotonic() >= deadline:
            log.warning("time budget reached; %d turn delta(s) left for the next run", len(todo) - i)
            return
        try:
            with db_session() as db:
                get_or_compute_turn_deltas(db, sid, did)
        except ValueError:
            pass  # cached as unavailable
        except Exception as exc:
            log.warning("turn deltas session=%d driver=%d failed (will retry next run): %s", sid, did, exc)


# ---------------------------------------------------------------------------
def _run_jobs(plans: Iterator[Callable[[OrmSession], tuple[object, StoryJob | None]]], report: StoryReport, budget: _Budget, workers: int) -> None:
    """Plan (main thread) -> Claude calls (thread pool) -> save (main thread), committing as results land."""
    with db_session() as db, ThreadPoolExecutor(max_workers=workers) as pool:
        running: dict[Future, StoryJob] = {}

        def drain(block_until_below: int) -> None:
            while len(running) >= block_until_below and running:
                done, _ = wait(list(running), return_when=FIRST_COMPLETED)
                for fut in done:
                    job = running.pop(fut)
                    try:
                        data, model_used = fut.result()
                        job.save(db, data, model_used)
                        db.commit()
                        report.written += 1
                    except NarrativeGenerationError as exc:
                        report.failed += 1
                        report.failures.append(f"{job.label}: {exc}")
                        log.error("%s failed: %s", job.label, exc)
                    except Exception as exc:
                        db.rollback()
                        report.failed += 1
                        report.failures.append(f"{job.label}: {exc}")
                        log.exception("%s failed", job.label)

        for plan in plans:
            try:
                _, job = plan(db)
            except MissingSessionStory:
                report.skipped += 1
                continue
            except ValueError as exc:
                log.debug("nothing to write: %s", exc)
                continue
            if job is None:
                report.up_to_date += 1
                continue
            if not budget.take():
                report.skipped += 1
                continue
            drain(workers)
            running[pool.submit(job.call)] = job
        drain(1)


def generate_season_stories(year: int, *, force: bool = False, workers: int = STORY_WORKERS, max_new: int | None = None, deadline: float | None = None) -> StoryReport:
    report = StoryReport()
    _get_client()  # fail fast (NarrativeGenerationError) when there is no API key
    budget = _Budget(max_new, deadline)
    with db_session() as db:
        season = db.scalar(select(Season).where(Season.year == year))
        if season is None:
            raise RuntimeError(f"season {year} not in DB")
        sessions = [(s.id, s.event_id, s.session_type, session_driver_ids(db, s)) for s in processed_sessions(db, season.id)]
        pairs = {sid: teammate_pairs(db, dids) for sid, _, stype, dids in sessions if stype in COMPARISON_SESSION_TYPES}
        season_id = season.id
        team_names = sorted({d.team for d in db.scalars(select(Driver)).all() if d.team})

    # 1) one story per driver per session - everything else builds on these
    def driver_plans():
        for sid, _, stype, dids in sessions:
            if stype in STORY_SESSION_TYPES:
                for did in dids:
                    yield lambda db, sid=sid, did=did: plan_driver_session_narrative(db, sid, did, force=force)

    log.info("stories: per-driver session stories")
    _run_jobs(driver_plans(), report, budget, workers)

    # 2) teammate head-to-heads + each driver's weekend arc
    def second_plans():
        for sid, pl in pairs.items():
            for a, b in pl:
                yield lambda db, sid=sid, a=a, b=b: plan_comparison_narrative(db, sid, a, b, force=force)
        by_event: dict[int, set[int]] = {}
        for _, eid, stype, dids in sessions:
            if stype in STORY_SESSION_TYPES:
                by_event.setdefault(eid, set()).update(dids)
        for eid, dids in by_event.items():
            for did in sorted(dids):
                yield lambda db, eid=eid, did=did: plan_weekend_arc(db, eid, did, force=force, generate_missing=False)

    log.info("stories: teammate comparisons + weekend arcs")
    _run_jobs(second_plans(), report, budget, workers)

    # 3) season "story so far" for every driver and team with results
    def season_plans():
        with db_session() as db:
            driver_ids = sorted(set(db.scalars(select(HeadlineRace.driver_id).join(Session, Session.id == HeadlineRace.session_id).join(Event, Event.id == Session.event_id).where(Event.season_id == season_id)).all()))
        for did in driver_ids:
            yield lambda db, did=did: plan_season_arc(db, season_id, "driver", str(did), force=force)
        for team in team_names:
            yield lambda db, team=team: plan_season_arc(db, season_id, "team", team, force=force)

    log.info("stories: season arcs")
    _run_jobs(season_plans(), report, budget, workers)
    return report


# ---------------------------------------------------------------------------
def run_pipeline(
    year: int,
    *,
    ingest: bool = True,
    rounds: list[int] | None = None,
    stories: bool = True,
    force_stories: bool = False,
    max_new_stories: int | None = None,
    time_budget_min: float | None = None,
    workers: int = STORY_WORKERS,
) -> StoryReport | None:
    from .ingest.season import ingest_full_season

    deadline = time.monotonic() + time_budget_min * 60 if time_budget_min else None
    if ingest:
        rep = ingest_full_season(year, rounds=rounds)
        log.info("ingest: sessions=%d skipped=%d transforms=%d failures=%d", rep.sessions_seen, rep.sessions_skipped, rep.transforms_ok, len(rep.failures))
    with db_session() as db:
        season = db.scalar(select(Season).where(Season.year == year))
        if season is None:
            raise RuntimeError(f"season {year} not in DB - run with ingest enabled first")
        season_id = season.id
    if ingest:
        precompute_track_outlines(season_id, rounds)
        precompute_turn_deltas(season_id, rounds=rounds, deadline=deadline)
    with db_session() as db:
        log.info("story edits synced: %s", sync_story_edits(db))
    if not stories:
        return None
    try:
        report = generate_season_stories(year, force=force_stories, workers=workers, max_new=max_new_stories, deadline=deadline)
    except NarrativeGenerationError as exc:
        log.warning("skipping AI stories: %s", exc)
        return None
    log.info("stories: written=%d up_to_date=%d failed=%d not_attempted=%d", report.written, report.up_to_date, report.failed, report.skipped)
    return report
