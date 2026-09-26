#!/usr/bin/env python
"""Process a season end to end: ingest -> track outlines / turn deltas -> AI stories (stored in the DB).

This is what the GitHub Actions workflow runs. Resumable: re-running only does new/changed work.

Examples:
  python scripts/run_pipeline.py --year 2026                           # everything
  python scripts/run_pipeline.py --year 2026 --no-ingest               # just (re)write missing stories
  python scripts/run_pipeline.py --year 2026 --max-new-stories 50      # cap Claude calls this run
  python scripts/run_pipeline.py --year 2026 --no-ingest --no-stories  # only sync stories/*.md edits
"""
import argparse
import logging

import _common  # noqa: F401

from f1tracker.config import STORY_WORKERS
from f1tracker.db import init_db
from f1tracker.logging_setup import setup_logging
from f1tracker.pipeline import run_pipeline


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, required=True)
    ap.add_argument("--rounds", type=str, default=None, help="comma-separated rounds to ingest/precompute (stories always cover the whole season)")
    ap.add_argument("--no-ingest", action="store_true", help="skip fetching new data")
    ap.add_argument("--no-stories", action="store_true", help="skip AI story writing")
    ap.add_argument("--force-stories", action="store_true", help="rewrite every story even if its data is unchanged")
    ap.add_argument("--max-new-stories", type=int, default=None, help="cap on Claude calls this run (the rest wait for the next run)")
    ap.add_argument("--time-budget-min", type=float, default=None, help="stop starting new work after this many minutes")
    ap.add_argument("--workers", type=int, default=STORY_WORKERS, help="parallel Claude calls")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()
    setup_logging(logging.DEBUG if args.verbose else logging.INFO)
    init_db()
    report = run_pipeline(
        args.year,
        ingest=not args.no_ingest,
        rounds=[int(x) for x in args.rounds.split(",")] if args.rounds else None,
        stories=not args.no_stories,
        force_stories=args.force_stories,
        max_new_stories=args.max_new_stories,
        time_budget_min=args.time_budget_min,
        workers=args.workers,
    )
    if report and report.failures:
        for f in report.failures[:50]:
            logging.error("  story failed: %s", f)


if __name__ == "__main__":
    main()
