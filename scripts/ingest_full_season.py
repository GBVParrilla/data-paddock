#!/usr/bin/env python
"""Orchestrate schedule -> results -> details -> transforms for a whole season.

Resumable: sessions already fully ingested are skipped unless --force is given.
"""
import argparse
import logging

import _common  # noqa: F401

from f1tracker.db import init_db
from f1tracker.ingest.season import ingest_full_season
from f1tracker.logging_setup import setup_logging


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, required=True)
    ap.add_argument("--rounds", type=str, default=None, help="comma-separated round numbers to limit to")
    ap.add_argument("--force", action="store_true", help="re-ingest even if already done")
    ap.add_argument("--no-schedule", action="store_true", help="skip refreshing the schedule first")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()
    setup_logging(logging.DEBUG if args.verbose else logging.INFO)
    init_db()
    rounds = [int(x) for x in args.rounds.split(",")] if args.rounds else None
    report = ingest_full_season(args.year, rounds=rounds, force=args.force, refresh_schedule=not args.no_schedule)
    logging.info(
        "DONE: rounds=%d sessions=%d skipped=%d results=%d details=%d transforms=%d failures=%d",
        report.rounds_seen, report.sessions_seen, report.sessions_skipped, report.results_ok, report.details_ok, report.transforms_ok, len(report.failures),
    )
    for sid, stage, err in report.failures:
        logging.error("  FAILED session %d at %s: %s", sid, stage, err)


if __name__ == "__main__":
    main()
