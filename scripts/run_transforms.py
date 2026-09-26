#!/usr/bin/env python
"""Populate headline_* / detail_* / pivotal_moments for one session (or --all ingested sessions)."""
import argparse
import logging

import _common  # noqa: F401

from sqlalchemy import select

from f1tracker.db import db_session, init_db
from f1tracker.logging_setup import setup_logging
from f1tracker.models import SessionIngestionState
from f1tracker.transforms.runner import run_transforms


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--session-id", type=int)
    ap.add_argument("--all", action="store_true", help="re-run for every session whose raw data is ingested")
    args = ap.parse_args()
    setup_logging()
    init_db()
    if args.all:
        with db_session() as db:
            ids = [st.session_id for st in db.scalars(select(SessionIngestionState).where(SessionIngestionState.details_done == True)).all()]  # noqa: E712
        for sid in ids:
            with db_session() as db:
                try:
                    run_transforms(db, sid)
                except Exception as exc:
                    logging.error("session %d transforms failed: %s", sid, exc)
        return
    if args.session_id is None:
        raise SystemExit("--session-id or --all required")
    with db_session() as db:
        run_transforms(db, args.session_id)


if __name__ == "__main__":
    main()
