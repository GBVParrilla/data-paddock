"""Season "story so far" for a driver or a team, from computed facts (never from earlier prose).

Teams come from the per-event entry list, so a stand-in's points go to the team he drove for, and a
regular driver's missed rounds are stated with who took his seat (REVIEW #3, #4). Points gaps are
computed here, so the story can't miscount them.
"""
from __future__ import annotations

import json
import logging
from collections import defaultdict
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session as OrmSession

from ..ingest.entries import entry_map, usual_teams
from ..models import Driver, Event, HeadlineRace, Season, SeasonArc, Session
from ..util import utcnow
from .factcheck import check_story
from .jobs import Outcome, StoryJob
from .llm import stable_hash
from .prompts import SCHEMA_ARC, SYSTEM_SEASON_ARC

log = logging.getLogger(__name__)
LIMITS = {"arc_text": 170}
STATUS = {"FIN": "finished", "LAP": "finished, lapped", "DNF": "retired", "NC": "not classified", "DNS": "did not start", "DSQ": "disqualified"}


def _season_rows(db: OrmSession, season_id: int) -> list[dict[str, Any]]:
    q = (
        select(HeadlineRace, Session.session_type, Event.round, Event.name, Event.id)
        .join(Session, Session.id == HeadlineRace.session_id)
        .join(Event, Event.id == Session.event_id)
        .where(Event.season_id == season_id)
        .order_by(Event.round, Session.session_type)
    )
    entries: dict[int, dict] = {}
    rows = []
    for hr, stype, rnd, name, eid in db.execute(q).all():
        e = entries.setdefault(eid, entry_map(db, eid)).get(hr.driver_id)
        rows.append({
            "round": rnd, "event": name, "event_id": eid, "session": "Sprint" if stype == "S" else "Race", "driver_id": hr.driver_id,
            "team": e.team if e else None, "grid": hr.grid_position, "finish": hr.finish_position, "status": STATUS.get(hr.status_code or "", hr.status),
            "points": hr.points or 0.0,
        })
    return rows


def _table(rows: list[dict], key: str, through: int) -> list[tuple[Any, float]]:
    pts: dict[Any, float] = defaultdict(float)
    for r in rows:
        if r["round"] <= through and r[key] is not None:
            pts[r[key]] += r["points"]
    return sorted(pts.items(), key=lambda kv: -kv[1])


def _fmt(p: float) -> int | float:
    return int(p) if float(p).is_integer() else p


def build_season_facts(db: OrmSession, season_id: int, subject_type: str, subject_id: str) -> dict[str, Any]:
    rows = _season_rows(db, season_id)
    if not rows:
        raise ValueError("no race results ingested for this season")
    names = {d.id: d.full_name for d in db.scalars(select(Driver)).all()}
    rounds = sorted({r["round"] for r in rows})
    through = rounds[-1]
    usual = usual_teams(db, season_id)
    key = "driver_id" if subject_type == "driver" else "team"
    subject = int(subject_id) if subject_type == "driver" else subject_id
    mine = [r for r in rows if r[key] == subject]
    if not mine:
        raise ValueError(f"{subject_type} {subject_id} has no results")
    table = _table(rows, key, through)
    pos = next(i + 1 for i, (k, _) in enumerate(table) if k == subject)
    pts = dict(table)[subject]
    leader, leader_pts = table[0]
    label = (lambda k: names.get(k, str(k))) if subject_type == "driver" else (lambda k: k)

    timeline, running = [], 0.0
    for r in mine:
        running += r["points"]
        t = _table(rows, key, r["round"])
        entry = {"round": r["round"], "event": r["event"], "session": r["session"], "grid": r["grid"], "finish": r["finish"], "status": r["status"], "points": _fmt(r["points"]), "total_after": _fmt(running),
                 "championship_position_after": next(i + 1 for i, (k, _) in enumerate(t) if k == subject)}
        if subject_type == "driver" and r["team"] and r["team"] != usual.get(subject):
            entry["drove_for"] = r["team"]
        if subject_type == "team":
            entry["driver"] = names.get(r["driver_id"])
        timeline.append(entry)

    facts: dict[str, Any] = {
        "season": db.get(Season, season_id).year, "subject_type": subject_type, "subject": label(subject), "through_round": through,
        "rounds_so_far": len(rounds), "results": timeline,
        "championship": {"position": pos, "of": len(table), "points": _fmt(pts), "leader": label(leader), "leader_points": _fmt(leader_pts)},
        "verdicts": [], "insufficient_data": [],
    }
    gaps = set()
    if pos > 1:
        ahead, ahead_pts = table[pos - 2]
        facts["championship"]["points_behind_leader"] = _fmt(leader_pts - pts)
        facts["championship"]["next_ahead"] = {"name": label(ahead), "points_behind": _fmt(ahead_pts - pts)}
        gaps |= {leader_pts - pts, ahead_pts - pts}
    if pos < len(table):
        behind, behind_pts = table[pos]
        facts["championship"]["next_behind"] = {"name": label(behind), "points_ahead": _fmt(pts - behind_pts)}
        gaps.add(pts - behind_pts)
    facts["points_gaps"] = sorted(_fmt(g) for g in gaps)

    races = [t for t in timeline if t["session"] == "Race"]
    finishes = [t["finish"] for t in races if t["finish"]]
    if finishes:
        facts["best_race_finish"] = min(finishes)
    facts["race_retirements"] = sum(1 for t in races if t["status"] in ("retired", "not classified", "did not start"))
    last3 = races[-3:]
    facts["last_three_races_points"] = _fmt(sum(t["points"] for t in last3))

    if subject_type == "driver":
        did = subject
        facts["usual_team"] = usual.get(did)
        raced = {t["round"] for t in races}
        regular = len(raced) >= len(rounds) / 2
        if regular:
            missed = [r for r in rounds if r not in raced]
            if missed:
                cover = []
                for rnd in missed:
                    eid = next(r["event_id"] for r in rows if r["round"] == rnd)
                    seat = [names.get(d) for d, e in entry_map(db, eid).items() if e.team == usual.get(did) and not e.practice_only and d != did and usual.get(d) != usual.get(did)]
                    cover.append({"round": rnd, "seat_taken_by": seat[0] if seat else None})
                facts["missed_rounds"] = cover
                who = {c["seat_taken_by"] for c in cover if c["seat_taken_by"]}
                facts["verdicts"].append(f"He missed {len(missed)} round{'s' if len(missed) != 1 else ''} ({', '.join(str(r) for r in missed)})" + (f"; {', '.join(sorted(who))} drove his {usual.get(did)} car." if who else "."))
        stand = [t for t in timeline if t.get("drove_for")]
        if stand:
            facts["verdicts"].append(f"He raced for {stand[0]['drove_for']} in round{'s' if len(stand) > 1 else ''} {', '.join(sorted({str(t['round']) for t in stand}))}" + (f", away from his usual seat at {usual.get(did)}." if usual.get(did) else "."))
    else:
        drivers = sorted({names.get(r["driver_id"]) for r in mine})
        facts["drivers_used"] = drivers
        by_driver: dict[str, float] = defaultdict(float)
        for r in mine:
            by_driver[names.get(r["driver_id"])] += r["points"]
        facts["points_by_driver"] = {k: _fmt(v) for k, v in by_driver.items()}
    return facts


def season_template(facts: dict[str, Any]) -> dict[str, str]:
    c = facts["championship"]
    who, n = facts["subject"], facts["through_round"]
    pts = f"{c['points']} point{'s' if c['points'] != 1 else ''}"
    lead = f"After round {n}, {who} {'leads the championship' if c['position'] == 1 else 'is ' + _ord(c['position']) + ' in the championship'} with {pts}"
    lead += f", {c['next_behind']['points_ahead']} clear of {c['next_behind']['name']}." if c["position"] == 1 and c.get("next_behind") else f", {c.get('points_behind_leader')} behind {c['leader']}." if c["position"] > 1 else "."
    parts = [lead]
    if facts.get("best_race_finish"):
        p3 = facts["last_three_races_points"]
        parts.append(f"The best race finish so far is P{facts['best_race_finish']}, and the last three races brought {p3} point{'s' if p3 != 1 else ''}.")
    parts += facts.get("verdicts", [])
    if facts.get("race_retirements"):
        k = facts["race_retirements"]
        parts.append(f"{k} race{'s' if k != 1 else ''} ended without a finish.")
    return {"arc_text": " ".join(parts)}


def _ord(n: int) -> str:
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def _existing(db: OrmSession, season_id: int, subject_type: str, subject_id: str) -> SeasonArc | None:
    return db.scalar(select(SeasonArc).where(SeasonArc.season_id == season_id, SeasonArc.subject_type == subject_type, SeasonArc.subject_id == str(subject_id)))


def season_check_context(db: OrmSession, season_id: int) -> dict:
    names = [d.full_name for d in db.scalars(select(Driver)).all()]
    return {"roster": {n.split(" ")[-1]: n for n in names if len(n.split(" ")[-1]) >= 3}, "entrants": set(names)}


def plan_season_arc(db: OrmSession, season_id: int, subject_type: str, subject_id: str, *, force: bool = False) -> tuple[SeasonArc | None, StoryJob | None]:
    if db.get(Season, season_id) is None:
        raise ValueError(f"season {season_id} not found")
    facts = build_season_facts(db, season_id, subject_type, subject_id)
    h = stable_hash(facts)
    existing = _existing(db, season_id, subject_type, subject_id)
    if existing and existing.input_hash == h and not force:
        return existing, None
    ctx = season_check_context(db, season_id)

    def save(db: OrmSession, outcome: Outcome) -> SeasonArc:
        row = _existing(db, season_id, subject_type, subject_id)
        if row is None:
            row = SeasonArc(season_id=season_id, subject_type=subject_type, subject_id=str(subject_id), through_round=facts["through_round"], arc_text="", generated_at=utcnow(), model_used=outcome.model, input_hash=h)
            db.add(row)
        row.through_round = facts["through_round"]
        row.arc_text = outcome.data["arc_text"].strip()
        row.generated_at = utcnow()
        row.model_used = "template" if outcome.fallback else outcome.model
        row.input_hash = h
        db.flush()
        return row

    user = "SEASON FACTS (JSON):\n" + json.dumps(facts, indent=1, default=str, ensure_ascii=False)
    job = StoryJob(f"season arc {subject_type}={subject_id}", SYSTEM_SEASON_ARC, user, SCHEMA_ARC, save,
                   check=lambda data: check_story(data, facts, roster=ctx["roster"], entrants=ctx["entrants"], limits=LIMITS),
                   fallback=lambda: season_template(facts))
    return existing, job


def get_or_generate_season_arc(db: OrmSession, season_id: int, subject_type: str, subject_id: str, *, force: bool = False) -> SeasonArc:
    existing, job = plan_season_arc(db, season_id, subject_type, subject_id, force=force)
    return existing if job is None else job.run(db)
