"""End-to-end processing for the published site: ingest -> precompute -> AI stories.

AI first: every story is written here, once, right after its data is processed, and stored in
the DB. The site only ever displays stored stories. Human corrections (stories/*.md) are synced
in at the start so arcs that build on session stories use the corrected text.

Everything is resumable: stories are cached by input hash, so a run that hits its time budget or
story cap simply continues where it left off next time.
"""
from __future__ import annotations

import logging
import os
import time
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass, field
from itertools import combinations
from typing import Callable, Iterator

from sqlalchemy import delete, select
from sqlalchemy.orm import Session as OrmSession

from .analysis.track import build_track_outline
from .analysis.turns import get_or_compute_turn_deltas
from .config import COMPARISON_SESSION_TYPES, DATA_VERSION, STORY_SESSION_TYPES, STORY_WORKERS
from .db import db_session
from .models import (
    PRACTICE_LIKE,
    QUALI_LIKE,
    Driver,
    Event,
    HeadlinePractice,
    HeadlineQualifying,
    HeadlineRace,
    Lap,
    Meta,
    Result,
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
from .narratives.llm import NarrativeGenerationError, NarrativeStopError, _get_client
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
    attempts: int = 0  # Claude calls made (retries included)
    templates: int = 0  # stories that failed every check and were replaced by the fact-sheet template
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


def teammate_pairs(db: OrmSession, event_id: int, driver_ids: list[int]) -> list[tuple[int, int]]:
    """Pairs who drove for the same team at this event (a stand-in pairs with his teammate that weekend)."""
    from .ingest.entries import entry_map

    entries = entry_map(db, event_id)
    team = {d: entries[d].team for d in driver_ids if d in entries and not entries[d].practice_only}
    return [(a, b) for a, b in combinations(sorted(team), 2) if team[a] == team[b]]


# ---------------------------------------------------------------------------
def upgrade_derived_data(season_id: int, *, force: bool = False) -> bool:
    """Bring a database built by older code up to DATA_VERSION (idempotent; a no-op once current).

    Re-syncs every event's entry list, refetches race/sprint results stored before positionText
    was kept, and recomputes all derived tables and moments. Needs network (Jolpica, OpenF1).
    """
    from .ingest.details import repair_pit_laps
    from .ingest.entries import sync_event_entries
    from .ingest.results import ingest_session_results
    from .transforms.runner import run_transforms

    with db_session() as db:
        current = db.get(Meta, "data_version")
        if current is not None and current.value == DATA_VERSION and not force:
            return False
        events = db.scalars(select(Event.id).where(Event.season_id == season_id).order_by(Event.round)).all()
        done = processed_sessions(db, season_id)
        stale_results = [
            s.id for s in done
            if s.session_type in ("R", "S") and db.scalar(select(Result.id).where(Result.session_id == s.id, Result.position_text.is_(None)).limit(1))
        ]
        session_ids = [s.id for s in done]
        unaligned = [
            s.id for s in done
            if s.session_type in ("R", "S") and db.scalar(select(Lap.id).where(Lap.session_id == s.id, Lap.is_pit_out_lap.is_(None)).limit(1))
        ]
    log.info("upgrading derived data to version %s: %d events, %d results to refetch, %d sessions to recompute", DATA_VERSION, len(events), len(stale_results), len(session_ids))
    for sid in stale_results:
        with db_session() as db:
            ingest_session_results(db, sid)
    for sid in unaligned:  # pit in-laps before OpenF1's out-lap flag was used
        with db_session() as db:
            log.info("session %d: %d pit stops re-aligned", sid, repair_pit_laps(db, sid))
    for eid in events:
        try:
            with db_session() as db:
                sync_event_entries(db, eid)
        except Exception as exc:  # an event without data yet: its entries arrive with its sessions
            log.warning("entries for event %d: %s", eid, exc)
    for sid in session_ids:
        with db_session() as db:
            run_transforms(db, sid)
    with db_session() as db:
        row = db.get(Meta, "data_version") or Meta(key="data_version", value="")
        row.value = DATA_VERSION
        db.merge(row)
    return True


def precompute_track_outlines(season_id: int, rounds: list[int] | None = None) -> None:
    with db_session() as db:
        events = db.scalars(select(Event).where(Event.season_id == season_id).order_by(Event.round)).all()
        # missing outlines, plus ones drawn before F1's official orientation/corners were available
        missing = [e.id for e in events if (not rounds or e.round in rounds) and ((o := db.get(TrackOutline, e.id)) is None or o.orientation != "f1")]
    for eid in missing:
        try:
            with db_session() as db:
                had = db.get(TrackOutline, eid) is not None
                build_track_outline(db, eid, force=True)
                if had:  # corner numbering changed: turn-by-turn deltas must be recomputed
                    sids = db.scalars(select(Session.id).where(Session.event_id == eid)).all()
                    db.execute(delete(TurnDeltaCache).where(TurnDeltaCache.session_id.in_(sids)))
        except ValueError as exc:
            log.info("track outline for event %d not available yet: %s", eid, exc)
        except Exception as exc:  # network trouble: try again next run
            log.warning("track outline for event %d failed: %s", eid, exc)


def _turns_stale(cached: TurnDeltaCache | None) -> bool:
    """Missing, or computed by an older method (a cached failure stays cached)."""
    import json

    from .analysis.turns import TURN_DELTA_VERSION

    if cached is None:
        return True
    return bool(cached.payload_json) and json.loads(cached.payload_json).get("version") != TURN_DELTA_VERSION


def precompute_turn_deltas(season_id: int, *, rounds: list[int] | None = None, deadline: float | None = None) -> None:
    with db_session() as db:
        todo = []
        for s in processed_sessions(db, season_id):
            if rounds and db.get(Event, s.event_id).round not in rounds:
                continue
            outline = db.get(TrackOutline, s.event_id)
            if outline is None or not outline.turns_json or outline.turns_json == "[]":
                continue
            todo += [(s.id, d) for d in session_driver_ids(db, s) if _turns_stale(db.get(TurnDeltaCache, (s.id, d)))]
    log.info("turn deltas to compute: %d", len(todo))
    for i, (sid, did) in enumerate(todo):
        if deadline is not None and time.monotonic() >= deadline:
            log.warning("time budget reached; %d turn delta(s) left for the next run", len(todo) - i)
            return
        try:
            with db_session() as db:
                try:
                    get_or_compute_turn_deltas(db, sid, did, force=True)
                except ValueError:
                    pass  # cached as unavailable: caught here so the session commits it (and drops the old breakdown)
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
                        outcome = fut.result()
                        job.save(db, outcome)
                        db.commit()
                        report.written += 1
                        report.attempts += outcome.attempts
                        if outcome.fallback:
                            report.templates += 1
                            report.failures.append(f"{job.label}: template published ({'; '.join(outcome.violations[:2])})")
                    except NarrativeStopError:
                        for f in running:
                            f.cancel()
                        raise  # every other call would fail the same way
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


class _SessionStories:
    """One session's fact sheets, built together so each driver's verdict candidates can be ranked by how
    distinctive they are, and the session's headline registry (REVIEW_ROUND3 #53)."""

    def __init__(self, sid: int, dids: list[int]):
        self.sid, self.dids = sid, dids
        self._sheets: dict[int, dict] | None = None
        self._headlines = None

    def _build(self, db: OrmSession) -> None:
        from .narratives.facts import session_sheets
        from .narratives.variety import SessionHeadlines

        sheets, names = session_sheets(db, self.sid, self.dids)
        self._sheets, self._headlines = sheets, SessionHeadlines(names)

    def sheet(self, db: OrmSession, did: int) -> dict | None:
        if self._sheets is None:
            self._build(db)
        return self._sheets.get(did)

    def headlines(self, db: OrmSession):
        if self._headlines is None:
            self._build(db)
        return self._headlines


def generate_season_stories(year: int, *, force: bool = False, workers: int = STORY_WORKERS, max_new: int | None = None, deadline: float | None = None,
                            rounds: list[int] | None = None) -> StoryReport:
    """Write missing/changed stories. `rounds` limits it to those rounds (the pilot set); season arcs
    are written only for a full-season run."""
    report = StoryReport()
    _get_client()  # fail fast (NarrativeStopError) when no credentials are configured
    budget = _Budget(max_new, deadline)
    with db_session() as db:
        season = db.scalar(select(Season).where(Season.year == year))
        if season is None:
            raise RuntimeError(f"season {year} not in DB")
        from .narratives.compare import comparison_pairs

        sessions = [(s.id, s.event_id, s.session_type, session_driver_ids(db, s)) for s in processed_sessions(db, season.id)
                    if not rounds or db.get(Event, s.event_id).round in rounds]
        pairs = {sid: comparison_pairs(db, sid, dids) for sid, eid, stype, dids in sessions if stype in COMPARISON_SESSION_TYPES}
        season_id = season.id
        from .ingest.entries import usual_teams

        team_names = sorted(set(usual_teams(db, season_id).values()))

    # Weekend by weekend, so each finished weekend is complete on the site (session stories, then the
    # teammate head-to-heads and weekend arcs that build on them) even when a run hits its cap.
    by_event: dict[int, list[tuple[int, str, list[int]]]] = {}
    for sid, eid, stype, dids in sessions:
        by_event.setdefault(eid, []).append((sid, stype, dids))

    def driver_plans(event_sessions):
        for sid, stype, dids in event_sessions:
            if stype in STORY_SESSION_TYPES:
                session = _SessionStories(sid, dids)
                for did in dids:
                    yield lambda db, session=session, did=did: plan_driver_session_narrative(db, session.sid, did, force=force, sheet=session.sheet(db, did), headlines=session.headlines(db))

    def weekend_plans(event_id, event_sessions):
        for sid, _, _ in event_sessions:
            for a, b in pairs.get(sid, []):
                yield lambda db, sid=sid, a=a, b=b: plan_comparison_narrative(db, sid, a, b, force=force)
        drivers = sorted({d for _, stype, dids in event_sessions if stype in STORY_SESSION_TYPES for d in dids})
        for did in drivers:
            yield lambda db, eid=event_id, did=did: plan_weekend_arc(db, eid, did, force=force, generate_missing=False)

    for eid, event_sessions in by_event.items():  # sessions are already in round order
        log.info("stories: event %d - session stories, then head-to-heads + weekend arcs", eid)
        _run_jobs(driver_plans(event_sessions), report, budget, workers)
        _run_jobs(weekend_plans(eid, event_sessions), report, budget, workers)

    if rounds:
        return report

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
    story_rounds: list[int] | None = None,
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
    upgrade_derived_data(season_id)
    if ingest:
        precompute_track_outlines(season_id, rounds)
        precompute_turn_deltas(season_id, rounds=rounds, deadline=deadline)
    with db_session() as db:
        log.info("story edits synced: %s", sync_story_edits(db))
    if not stories:
        return None
    try:
        report = generate_season_stories(year, force=force_stories, workers=workers, max_new=max_new_stories, deadline=deadline, rounds=story_rounds)
    except NarrativeStopError as exc:
        log.error("AI stories stopped: %s", exc)
        if os.environ.get("GITHUB_ACTIONS"):
            print(f"::error title=AI stories stopped::{exc}", flush=True)  # shows on the run summary
        return None
    log.info("stories: written=%d up_to_date=%d failed=%d not_attempted=%d claude_calls=%d templates=%d", report.written, report.up_to_date, report.failed, report.skipped, report.attempts, report.templates)
    if os.environ.get("GITHUB_STEP_SUMMARY"):  # LLM usage, for PROGRESS.md and cost tracking
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as fh:
            fh.write(f"### Stories\n\nwritten {report.written} · up to date {report.up_to_date} · failed {report.failed} · not attempted {report.skipped} · "
                     f"Claude calls {report.attempts} · published as fact-sheet templates {report.templates}\n")
    return report
