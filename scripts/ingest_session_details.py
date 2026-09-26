#!/usr/bin/env python
"""Laps (sectors + speed), stints, pit stops, weather, race control for one session (OpenF1)."""
import argparse

import _common  # noqa: F401

from f1tracker.db import db_session, init_db
from f1tracker.ingest.details import ingest_session_details
from f1tracker.logging_setup import setup_logging


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--session-id", type=int, required=True)
    args = ap.parse_args()
    setup_logging()
    init_db()
    with db_session() as db:
        ok = ingest_session_details(db, args.session_id)
    raise SystemExit(0 if ok else 2)


if __name__ == "__main__":
    main()
