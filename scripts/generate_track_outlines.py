#!/usr/bin/env python
"""Pre-generate and cache a track outline for every event with ingested lap data."""
import argparse
import logging

import _common  # noqa: F401

from sqlalchemy import select

from f1tracker.analysis.track import build_track_outline
from f1tracker.db import db_session, init_db
from f1tracker.logging_setup import setup_logging
from f1tracker.models import Event, Season


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, required=True)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    setup_logging()
    init_db()
    with db_session() as db:
        season = db.scalar(select(Season).where(Season.year == args.year))
        ids = [e.id for e in db.scalars(select(Event).where(Event.season_id == season.id).order_by(Event.round)).all()]
    for eid in ids:
        with db_session() as db:
            try:
                build_track_outline(db, eid, force=args.force)
            except ValueError as exc:
                logging.warning("event %d: %s", eid, exc)


if __name__ == "__main__":
    main()
