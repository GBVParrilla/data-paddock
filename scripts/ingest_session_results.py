#!/usr/bin/env python
"""Results/classification for one session (Jolpica; OpenF1 for SQ/practice)."""
import argparse

import _common  # noqa: F401

from f1tracker.db import db_session, init_db
from f1tracker.ingest.results import ingest_session_results
from f1tracker.logging_setup import setup_logging


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--session-id", type=int, required=True)
    args = ap.parse_args()
    setup_logging()
    init_db()
    with db_session() as db:
        ok = ingest_session_results(db, args.session_id)
    raise SystemExit(0 if ok else 2)


if __name__ == "__main__":
    main()
