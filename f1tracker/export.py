"""Static export: every API response the site needs, written as JSON files for GitHub Pages.

Reads only what is already stored - no Claude calls, no network. File paths mirror the API
(see frontend/src/api/client.ts, which maps each call to its file in static mode).
"""
from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from sqlalchemy import select
from sqlalchemy.orm import Session as OrmSession

from .analysis.track import outline_to_dict
from .analysis.turns import TURN_DELTA_VERSION
from .api import main as api
from .models import DriverSessionNarrative, DriverWeekendArc, Event, Season, SeasonArc, Session, SessionIngestionState, TrackOutline, TurnDeltaCache
from .config import STORY_SESSION_TYPES
from .ingest.entries import usual_teams
from .narratives.edits import (
    present_driver_session,
    present_season_arc,
    present_weekend_arc,
    slug,
    sync_story_edits,
    template_driver_session,
    template_season_arc,
    template_weekend_arc,
)
from .pipeline import session_driver_ids

log = logging.getLogger(__name__)


class _Writer:
    def __init__(self, root: Path):
        self.root, self.files, self.bytes = root, 0, 0
        self.sources: dict[str, int] = {}

    def __call__(self, rel: str, data: Any) -> None:
        if isinstance(data, dict) and isinstance(data.get("source"), str):  # stories: claude / template / edited
            self.sources[data["source"]] = self.sources.get(data["source"], 0) + 1
        path = self.root / f"{rel}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        blob = json.dumps(jsonable_encoder(data), separators=(",", ":"))
        path.write_text(blob, encoding="utf-8")
        self.files += 1
        self.bytes += len(blob)


def _try(write: _Writer, rel: str, fn, *args, **kwargs) -> None:
    """Write fn()'s result; a 404-style 'not available' is simply not exported (the site shows a note)."""
    try:
        write(rel, fn(*args, **kwargs))
    except (HTTPException, ValueError) as exc:
        log.debug("skip %s: %s", rel, exc)


def _best_sectors(rows: list[dict]) -> list[dict]:
    """Each driver's best time per sector (all the site draws from the per-lap sector table)."""
    best: dict[tuple[int, int], int] = {}
    for r in rows:
        v = r.get("driver_sector_ms")
        if v is None:
            continue
        k = (r["driver_id"], r["sector"])
        if k not in best or v < best[k]:
            best[k] = v
    return [{"driver_id": d, "sector": sec, "best_ms": v} for (d, sec), v in sorted(best.items())]


def _outline_preview(outline: TrackOutline) -> dict:
    """A light outline for thumbnails: about 120 points, integers."""
    pts = json.loads(outline.points_json)
    step = max(1, len(pts) // 120)
    keep = pts[::step]
    if keep[-1] != pts[-1]:
        keep.append(pts[-1])
    return {"points": [[round(x), round(y)] for x, y in keep]}


def export_site_data(db: OrmSession, out: Path) -> _Writer:
    sync_story_edits(db)
    if out.exists():
        shutil.rmtree(out)
    write = _Writer(out)

    write("seasons", api.list_seasons(db=db))
    write("drivers", api.list_drivers(db=db))

    for season in db.scalars(select(Season)).all():
        events = api.season_events(season.year, db=db)
        for e in events:  # thumbnails ship with the event list instead of 20+ outline requests
            o = db.get(TrackOutline, e["id"])
            e["outline_preview"] = _outline_preview(o) if o is not None else None
        write(f"seasons/{season.year}/events", events)
        standings = api.season_standings(season.year, db=db)
        write(f"seasons/{season.year}/standings", standings)
        stored = {(a.subject_type, a.subject_id): a for a in db.scalars(select(SeasonArc).where(SeasonArc.season_id == season.id)).all()}
        subjects = [("driver", str(d["driver_id"])) for d in standings["drivers"]] + [("team", t) for t in sorted(set(usual_teams(db, season.id).values()))]
        for stype, sid in subjects:
            subject = sid if stype == "driver" else slug(sid)
            arc = stored.get((stype, sid))
            _try(write, f"seasons/{season.year}/arc/{stype}/{subject}", lambda a=arc, st=stype, si=sid: present_season_arc(db, a) if a else template_season_arc(db, season.id, st, si))

    for event in db.scalars(select(Event)).all():
        write(f"events/{event.id}", api.get_event(event.id, db=db))
        write(f"events/{event.id}/sessions", api.event_sessions(event.id, db=db))
        outline = db.get(TrackOutline, event.id)
        if outline is not None:
            write(f"events/{event.id}/track-outline", outline_to_dict(outline))
        arcs = {a.driver_id: a for a in db.scalars(select(DriverWeekendArc).where(DriverWeekendArc.event_id == event.id)).all()}
        weekend_drivers = {d for s in db.scalars(select(Session).where(Session.event_id == event.id)).all() if s.session_type in STORY_SESSION_TYPES for d in session_driver_ids(db, s)}
        for did in sorted(weekend_drivers):
            a = arcs.get(did)
            _try(write, f"events/{event.id}/drivers/{did}/weekend-arc", lambda a=a, did=did: present_weekend_arc(db, a) if a else template_weekend_arc(db, event.id, did))

    ready = select(Session).join(SessionIngestionState, SessionIngestionState.session_id == Session.id).where(SessionIngestionState.transforms_done.is_(True))
    for s in db.scalars(ready).all():
        base = f"sessions/{s.id}"
        write(f"{base}/headline", api.session_headline(s.id, db=db))
        # detail split per view so a page loads only what it draws (REVIEW #25); /detail stays for the live API
        detail = api.session_detail(s.id, driver_id=None, db=db)
        strip = lambda rows, keep: [{k: r[k] for k in keep} for r in rows]  # noqa: E731
        if s.session_type in ("R", "S"):
            write(f"{base}/positions", {"position_by_lap": strip(detail["position_by_lap"], ("driver_id", "lap_number", "position"))})
        write(f"{base}/stints", {
            "stint_timeline": strip(detail["stint_timeline"], ("driver_id", "stint_number", "compound", "lap_start", "lap_end")),
            "pit_stops": strip(detail["pit_stops"], ("driver_id", "lap_number", "duration_ms", "lane_duration_ms")),
        })
        write(f"{base}/sectors", {"best": _best_sectors(detail["sector_deltas"])})
        write(f"{base}/pace", {"long_run_pace": strip(detail["long_run_pace"], ("driver_id", "compound", "avg_lap_time_ms", "lap_count"))})
        write(f"{base}/pivotal-moments", api.pivotal_moments(s.id, db=db))
        write(f"{base}/chart-annotations", api.chart_annotations(s.id, db=db))
        write(f"{base}/race-control", api.race_control(s.id, db=db))
        write(f"{base}/lap-times", api.lap_times(s.id, db=db))
        write(f"{base}/comparisons", api.stored_comparisons(s.id, db=db))
        _try(write, f"{base}/midfield-spotlight", api.midfield_spotlight, s.id, generate=False, db=db)
        if s.session_type in STORY_SESSION_TYPES:
            stories = {n.driver_id: n for n in db.scalars(select(DriverSessionNarrative).where(DriverSessionNarrative.session_id == s.id)).all()}
            for did in session_driver_ids(db, s):
                n = stories.get(did)
                _try(write, f"{base}/drivers/{did}/narrative", lambda n=n, did=did: present_driver_session(db, n) if n else template_driver_session(db, s.id, did))
        for td in db.scalars(select(TurnDeltaCache).where(TurnDeltaCache.session_id == s.id, TurnDeltaCache.payload_json.is_not(None))).all():
            payload = json.loads(td.payload_json)
            if payload.get("version") == TURN_DELTA_VERSION:  # older breakdowns didn't add up; wait for the recompute
                write(f"{base}/drivers/{td.driver_id}/turn-deltas", payload)

    log.info("exported %d files (%.1f MB) to %s; stories by source: %s", write.files, write.bytes / 1e6, out, write.sources)
    return write
