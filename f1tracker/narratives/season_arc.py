"""Season 'story so far' arcs for a driver or a team, from headline_race across rounds."""
from __future__ import annotations

import json
import logging
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session as OrmSession

from ..models import Driver, Event, HeadlineRace, Season, SeasonArc, Session
from ..util import utcnow
from .jobs import StoryJob
from .llm import stable_hash
from .prompts import SCHEMA_ARC, SYSTEM_SEASON_ARC

log = logging.getLogger(__name__)


def season_results_table(db: OrmSession, season_id: int) -> tuple[list[dict], dict[int, Driver]]:
    """Every race/sprint headline row with event context, ordered by round."""
    drivers = {d.id: d for d in db.scalars(select(Driver)).all()}
    q = (
        select(HeadlineRace, Session.session_type, Event.round, Event.name)
        .join(Session, Session.id == HeadlineRace.session_id)
        .join(Event, Event.id == Session.event_id)
        .where(Event.season_id == season_id)
        .order_by(Event.round, Session.session_type)
    )
    rows = []
    for hr, stype, rnd, name in db.execute(q).all():
        rows.append(
            {
                "round": rnd,
                "event": name,
                "session": "Sprint" if stype == "S" else "Race",
                "driver_id": hr.driver_id,
                "team": drivers[hr.driver_id].team if hr.driver_id in drivers else None,
                "grid": hr.grid_position,
                "finish": hr.finish_position,
                "points": hr.points,
                "pit_stops": hr.pit_stop_count,
                "status": hr.status,
            }
        )
    return rows, drivers


def standings(rows: list[dict], key: str) -> dict[str, float]:
    totals: dict[str, float] = defaultdict(float)
    for r in rows:
        k = r[key]
        if k is not None:
            totals[str(k)] += r["points"] or 0
    return dict(totals)


def build_season_arc_input(db: OrmSession, season_id: int, subject_type: str, subject_id: str) -> dict:
    rows, drivers = season_results_table(db, season_id)
    if not rows:
        raise ValueError("no race results ingested for this season")
    if subject_type == "driver":
        did = int(subject_id)
        if did not in drivers:
            raise ValueError(f"driver {subject_id} not found")
        mine = [r for r in rows if r["driver_id"] == did]
        key = "driver_id"
        subject_key = str(did)
        label = drivers[did].full_name
        team = drivers[did].team
    elif subject_type == "team":
        mine = [r for r in rows if r["team"] == subject_id]
        key = "team"
        subject_key = subject_id
        label = subject_id
        team = None
        if not mine:
            raise ValueError(f"team '{subject_id}' has no results")
    else:
        raise ValueError("subject_type must be 'driver' or 'team'")

    through_round = max(r["round"] for r in rows)
    timeline = []
    running = 0.0
    for r in sorted(mine, key=lambda r: (r["round"], r["session"])):
        running += r["points"] or 0
        # championship position after this round
        upto = [x for x in rows if x["round"] <= r["round"]]
        table = sorted(standings(upto, key).items(), key=lambda kv: -kv[1])
        pos = next((i + 1 for i, (k, _) in enumerate(table) if k == subject_key), None)
        entry = {k2: r[k2] for k2 in ("round", "event", "session", "grid", "finish", "points", "pit_stops", "status")}
        if subject_type == "team":
            entry["driver"] = drivers[r["driver_id"]].full_name
        entry["cumulative_points"] = running
        entry["championship_position_after_round"] = pos
        timeline.append(entry)
    final_table = sorted(standings(rows, key).items(), key=lambda kv: -kv[1])
    leader_pts = final_table[0][1] if final_table else 0
    return {
        "subject_type": subject_type,
        "subject": label,
        "team": team,
        "through_round": through_round,
        "rounds_ingested": sorted({r["round"] for r in rows}),
        "results": timeline,
        "championship": {"points": running, "position": next((i + 1 for i, (k, _) in enumerate(final_table) if k == subject_key), None), "leader_points": leader_pts, "entries": len(final_table)},
    }


def _existing(db: OrmSession, season_id: int, subject_type: str, subject_id: str) -> SeasonArc | None:
    return db.scalar(select(SeasonArc).where(SeasonArc.season_id == season_id, SeasonArc.subject_type == subject_type, SeasonArc.subject_id == str(subject_id)))


def plan_season_arc(db: OrmSession, season_id: int, subject_type: str, subject_id: str, *, force: bool = False) -> tuple[SeasonArc | None, StoryJob | None]:
    if db.get(Season, season_id) is None:
        raise ValueError(f"season {season_id} not found")
    payload = build_season_arc_input(db, season_id, subject_type, subject_id)
    h = stable_hash(payload)
    existing = _existing(db, season_id, subject_type, subject_id)
    if existing and existing.input_hash == h and not force:
        return existing, None

    def save(db: OrmSession, data: dict, model_used: str) -> SeasonArc:
        row = _existing(db, season_id, subject_type, subject_id)
        if row is None:
            row = SeasonArc(season_id=season_id, subject_type=subject_type, subject_id=str(subject_id), through_round=payload["through_round"], arc_text="", generated_at=utcnow(), model_used=model_used, input_hash=h)
            db.add(row)
        row.through_round = payload["through_round"]
        row.arc_text = data["arc_text"].strip()
        row.generated_at = utcnow()
        row.model_used = model_used
        row.input_hash = h
        db.flush()
        return row

    user = "Season data (JSON):\n" + json.dumps(payload, indent=1, default=str)
    return existing, StoryJob(f"season arc {subject_type}={subject_id}", SYSTEM_SEASON_ARC, user, SCHEMA_ARC, save)


def get_or_generate_season_arc(db: OrmSession, season_id: int, subject_type: str, subject_id: str, *, force: bool = False) -> SeasonArc:
    existing, job = plan_season_arc(db, season_id, subject_type, subject_id, force=force)
    return existing if job is None else job.run(db)
