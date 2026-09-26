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
from .api import main as api
from .models import DriverSessionNarrative, DriverWeekendArc, Event, Season, SeasonArc, Session, SessionIngestionState, TrackOutline, TurnDeltaCache
from .narratives.edits import present_driver_session, present_season_arc, present_weekend_arc, slug, sync_story_edits

log = logging.getLogger(__name__)


class _Writer:
    def __init__(self, root: Path):
        self.root, self.files, self.bytes = root, 0, 0

    def __call__(self, rel: str, data: Any) -> None:
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


def export_site_data(db: OrmSession, out: Path) -> _Writer:
    sync_story_edits(db)
    if out.exists():
        shutil.rmtree(out)
    write = _Writer(out)

    write("seasons", api.list_seasons(db=db))
    write("drivers", api.list_drivers(db=db))

    for season in db.scalars(select(Season)).all():
        write(f"seasons/{season.year}/events", api.season_events(season.year, db=db))
        for arc in db.scalars(select(SeasonArc).where(SeasonArc.season_id == season.id)).all():
            subject = arc.subject_id if arc.subject_type == "driver" else slug(arc.subject_id)
            write(f"seasons/{season.year}/arc/{arc.subject_type}/{subject}", present_season_arc(db, arc))

    for event in db.scalars(select(Event)).all():
        write(f"events/{event.id}", api.get_event(event.id, db=db))
        write(f"events/{event.id}/sessions", api.event_sessions(event.id, db=db))
        outline = db.get(TrackOutline, event.id)
        if outline is not None:
            write(f"events/{event.id}/track-outline", outline_to_dict(outline))
        for arc in db.scalars(select(DriverWeekendArc).where(DriverWeekendArc.event_id == event.id)).all():
            write(f"events/{event.id}/drivers/{arc.driver_id}/weekend-arc", present_weekend_arc(db, arc))

    ready = select(Session).join(SessionIngestionState, SessionIngestionState.session_id == Session.id).where(SessionIngestionState.transforms_done.is_(True))
    for s in db.scalars(ready).all():
        base = f"sessions/{s.id}"
        write(f"{base}/headline", api.session_headline(s.id, db=db))
        write(f"{base}/detail", api.session_detail(s.id, driver_id=None, db=db))
        write(f"{base}/pivotal-moments", api.pivotal_moments(s.id, db=db))
        write(f"{base}/chart-annotations", api.chart_annotations(s.id, db=db))
        write(f"{base}/lap-times", api.lap_times(s.id, db=db))
        write(f"{base}/comparisons", api.stored_comparisons(s.id, db=db))
        _try(write, f"{base}/midfield-spotlight", api.midfield_spotlight, s.id, generate=False, db=db)
        for n in db.scalars(select(DriverSessionNarrative).where(DriverSessionNarrative.session_id == s.id)).all():
            write(f"{base}/drivers/{n.driver_id}/narrative", present_driver_session(db, n))
        for td in db.scalars(select(TurnDeltaCache).where(TurnDeltaCache.session_id == s.id, TurnDeltaCache.payload_json.is_not(None))).all():
            write(f"{base}/drivers/{td.driver_id}/turn-deltas", json.loads(td.payload_json))

    log.info("exported %d files (%.1f MB) to %s", write.files, write.bytes / 1e6, out)
    return write
