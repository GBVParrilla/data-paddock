#!/usr/bin/env python
"""Generate (or fetch cached) narratives for manual quality review.

Examples:
  python scripts/generate_narrative.py --session-id 5 --driver-id 3          # one driver/session
  python scripts/generate_narrative.py --session-id 5 --midfield              # whoever the spotlight picks
  python scripts/generate_narrative.py --session-id 5 --driver-id 3 --dry-run # print the structured input only
  python scripts/generate_narrative.py --event-id 1 --driver-id 3 --weekend-arc
  python scripts/generate_narrative.py --season 2026 --subject-type driver --subject-id 3 --season-arc
"""
import argparse
import json

import _common  # noqa: F401

from f1tracker.analysis.midfield import identify_midfield_story
from f1tracker.db import db_session, init_db
from f1tracker.logging_setup import setup_logging
from f1tracker.narratives.driver_session import get_or_generate_driver_session_narrative
from f1tracker.narratives.inputs import build_driver_session_input
from f1tracker.narratives.season_arc import get_or_generate_season_arc
from f1tracker.narratives.weekend_arc import get_or_generate_weekend_arc
from f1tracker.models import Season
from sqlalchemy import select


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--session-id", type=int)
    ap.add_argument("--driver-id", type=int)
    ap.add_argument("--midfield", action="store_true")
    ap.add_argument("--dry-run", action="store_true", help="print structured input, no LLM call")
    ap.add_argument("--force", action="store_true", help="regenerate even if cached")
    ap.add_argument("--event-id", type=int)
    ap.add_argument("--weekend-arc", action="store_true")
    ap.add_argument("--season", type=int)
    ap.add_argument("--subject-type", choices=["driver", "team"])
    ap.add_argument("--subject-id")
    ap.add_argument("--season-arc", action="store_true")
    args = ap.parse_args()
    setup_logging()
    init_db()

    with db_session() as db:
        if args.weekend_arc:
            arc = get_or_generate_weekend_arc(db, args.event_id, args.driver_id, force=args.force)
            print(f"\n=== WEEKEND ARC (event {args.event_id}, driver {args.driver_id}, {arc.model_used}) ===\n{arc.arc_text}\n")
            return
        if args.season_arc:
            season = db.scalar(select(Season).where(Season.year == args.season))
            arc = get_or_generate_season_arc(db, season.id, args.subject_type, args.subject_id, force=args.force)
            print(f"\n=== SEASON ARC ({args.subject_type} {args.subject_id}, through round {arc.through_round}, {arc.model_used}) ===\n{arc.arc_text}\n")
            return

        driver_id = args.driver_id
        if args.midfield:
            story = identify_midfield_story(db, args.session_id)
            if story is None:
                raise SystemExit("no midfield story identified")
            print(f"\n=== MIDFIELD SPOTLIGHT: {story['driver']} ({story['team']}) score={story['score']} ===\n{story['reason']}\n")
            driver_id = story["driver_id"]
        if driver_id is None:
            raise SystemExit("--driver-id or --midfield required")
        if args.dry_run:
            print(json.dumps(build_driver_session_input(db, args.session_id, driver_id), indent=1, default=str))
            return
        n = get_or_generate_driver_session_narrative(db, args.session_id, driver_id, force=args.force)
        print(f"\n=== NARRATIVE (session {args.session_id}, driver {driver_id}, {n.session_type}, {n.model_used}, generated {n.generated_at:%Y-%m-%d %H:%M}) ===\n{n.narrative_text}\n")
        print(f"=== STRATEGY ANALYSIS (hedged inference) ===\n{n.strategy_analysis_text}\n")


if __name__ == "__main__":
    main()
