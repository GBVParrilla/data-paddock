#!/usr/bin/env python
"""Pull the full season calendar (events + sessions, sprint flags, OpenF1 keys)."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from f1tracker.db import db_session, init_db  # noqa: E402
from f1tracker.ingest.schedule import ingest_schedule  # noqa: E402
from f1tracker.logging_setup import setup_logging  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, required=True)
    args = ap.parse_args()
    setup_logging()
    init_db()
    with db_session() as db:
        ingest_schedule(db, args.year)


if __name__ == "__main__":
    main()
