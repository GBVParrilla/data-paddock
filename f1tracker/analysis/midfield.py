"""Midfield / underdog spotlight: pick the most compelling story outside the top 3."""
from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session as OrmSession

from ..models import (
    PRACTICE_LIKE,
    QUALI_LIKE,
    RACE_LIKE,
    DetailLongRunPace,
    Driver,
    Event,
    HeadlinePractice,
    HeadlineQualifying,
    HeadlineRace,
    Result,
    Session,
)
from ..util import fmt_ms


def _drivers(db: OrmSession) -> dict[int, Driver]:
    return {d.id: d for d in db.scalars(select(Driver)).all()}


def _race_candidates(db: OrmSession, session_id: int, drivers: dict[int, Driver]) -> list[dict[str, Any]]:
    rows = db.scalars(select(HeadlineRace).where(HeadlineRace.session_id == session_id)).all()
    gaps = {r.driver_id: r.gap_to_leader_ms for r in db.scalars(select(Result).where(Result.session_id == session_id)).all()}
    finishers = sorted([r for r in rows if r.finish_position], key=lambda r: r.finish_position)
    cands: list[dict[str, Any]] = []
    # Big movers finishing P8-P15
    for r in finishers:
        if 8 <= r.finish_position <= 15 and (r.positions_gained or 0) >= 4:
            cands.append(
                {
                    "driver_id": r.driver_id,
                    "score": 2.0 + r.positions_gained * 1.0,
                    "kind": "big_mover",
                    "reason": f"{drivers[r.driver_id].full_name} climbed from P{r.grid_position} to P{r.finish_position} ({r.positions_gained} places gained).",
                }
            )
    # Closest finishing gaps between P6 and P12
    for a, b in zip(finishers, finishers[1:]):
        if 6 <= b.finish_position <= 12 and gaps.get(a.driver_id) is not None and gaps.get(b.driver_id) is not None:
            gap = gaps[b.driver_id] - gaps[a.driver_id]
            if 0 <= gap <= 3000:
                for who, other, ahead in ((a, b, True), (b, a, False)):
                    cands.append(
                        {
                            "driver_id": who.driver_id,
                            "score": 1.0 + (3.0 - gap / 1000) + (0.5 if not ahead else 0.0),
                            "kind": "close_battle",
                            "reason": f"{drivers[who.driver_id].full_name} finished P{who.finish_position}, {fmt_ms(gap)}s {'ahead of' if ahead else 'behind'} {drivers[other.driver_id].full_name} (P{other.finish_position}).",
                            "rival_id": other.driver_id,
                        }
                    )
    # Points from outside a top team, i.e. P4-P10 scored with a grid outside the top 10
    for r in finishers:
        if 4 <= r.finish_position <= 10 and (r.grid_position or 0) > 10:
            cands.append(
                {
                    "driver_id": r.driver_id,
                    "score": 3.0 + (r.positions_gained or 0) * 0.8,
                    "kind": "points_from_deep",
                    "reason": f"{drivers[r.driver_id].full_name} scored from P{r.grid_position} on the grid, finishing P{r.finish_position}.",
                }
            )
    return cands


def _quali_candidates(db: OrmSession, session_id: int, drivers: dict[int, Driver]) -> list[dict[str, Any]]:
    rows = db.scalars(select(HeadlineQualifying).where(HeadlineQualifying.session_id == session_id)).all()
    by_id = {r.driver_id: r for r in rows}
    cands = []
    for r in rows:
        if not r.position or r.position <= 3 or r.position > 14:
            continue
        team = drivers[r.driver_id].team
        mate = next((x for x in rows if x.driver_id != r.driver_id and drivers[x.driver_id].team == team), None)
        mate_gap = (mate.position - r.position) if (mate and mate.position) else 0
        score = 1.0 + max(0, mate_gap) * 0.8 + (2.0 if r.eliminated_in is None and r.position >= 6 else 0.0)
        reason = f"{drivers[r.driver_id].full_name} qualified P{r.position}, {fmt_ms(r.gap_to_pole_ms)}s off pole"
        if mate and mate.position:
            n = abs(mate_gap)
            reason += f", {n} place{'s' if n != 1 else ''} {'ahead of' if mate_gap > 0 else 'behind'} teammate {drivers[mate.driver_id].full_name} (P{mate.position})"
        cands.append({"driver_id": r.driver_id, "score": score, "kind": "quali_overperformer", "reason": reason + "."})
    return cands


def _practice_candidates(db: OrmSession, session_id: int, drivers: dict[int, Driver]) -> list[dict[str, Any]]:
    rows = db.scalars(select(HeadlinePractice).where(HeadlinePractice.session_id == session_id)).all()
    rank_by_id = {r.driver_id: r.rank for r in rows}
    pace = db.scalars(select(DetailLongRunPace).where(DetailLongRunPace.session_id == session_id)).all()
    cands = []
    by_compound: dict[str, list[DetailLongRunPace]] = {}
    for p in pace:
        by_compound.setdefault(p.compound, []).append(p)
    for compound, lst in by_compound.items():
        ranked = sorted(lst, key=lambda p: p.avg_lap_time_ms)
        for i, p in enumerate(ranked[:6]):
            hr = rank_by_id.get(p.driver_id)
            if hr is None or hr <= 3:
                continue
            score = 1.0 + max(0, hr - (i + 1)) * 0.5 + (1.0 if i == 0 else 0.0)
            cands.append(
                {
                    "driver_id": p.driver_id,
                    "score": score,
                    "kind": "long_run_pace",
                    "reason": f"{drivers[p.driver_id].full_name} was P{hr} on single-lap pace but {i + 1}{'st' if i == 0 else 'nd' if i == 1 else 'rd' if i == 2 else 'th'} on {compound.lower()} long-run pace ({fmt_ms(p.avg_lap_time_ms)} avg over {p.lap_count} laps).",
                }
            )
    return cands


TOP_TEAM_COUNT = 4
TOP_TEAM_MULTIPLIER = 0.45


def top_teams(db: OrmSession, session: Session) -> set[str]:
    """Front-running teams, from season-to-date constructor points (falls back to this session's podium)."""
    event = db.get(Event, session.event_id)
    q = (
        select(Driver.team, func.sum(HeadlineRace.points))
        .join(Driver, Driver.id == HeadlineRace.driver_id)
        .join(Session, Session.id == HeadlineRace.session_id)
        .join(Event, Event.id == Session.event_id)
        .where(Event.season_id == event.season_id, Event.round <= event.round)
        .group_by(Driver.team)
    )
    table = sorted([(t, p or 0) for t, p in db.execute(q).all() if t], key=lambda kv: -kv[1])
    teams = {t for t, p in table[:TOP_TEAM_COUNT] if p > 0}
    if len(teams) < 2:  # season opener: use this session's own top 3 as the "expected" front
        for model, col in ((HeadlineRace, HeadlineRace.finish_position), (HeadlineQualifying, HeadlineQualifying.position), (HeadlinePractice, HeadlinePractice.rank)):
            for r in db.scalars(select(model).where(model.session_id == session.id, col <= 3)).all():
                d = db.get(Driver, r.driver_id)
                if d and d.team:
                    teams.add(d.team)
    return teams


def identify_midfield_story(db: OrmSession, session_id: int) -> dict[str, Any] | None:
    session = db.get(Session, session_id)
    if session is None:
        raise ValueError(f"session {session_id} not found")
    drivers = _drivers(db)
    stype = session.session_type
    strong_teams = top_teams(db, session)
    if stype in RACE_LIKE:
        cands = _race_candidates(db, session_id, drivers)
    elif stype in QUALI_LIKE:
        cands = _quali_candidates(db, session_id, drivers)
    elif stype in PRACTICE_LIKE:
        cands = _practice_candidates(db, session_id, drivers)
    else:
        cands = []
    if not cands:
        return None
    # merge scores per driver, keep the best reason
    merged: dict[int, dict[str, Any]] = {}
    for c in cands:
        m = merged.setdefault(c["driver_id"], {"driver_id": c["driver_id"], "score": 0.0, "reasons": [], "kinds": [], "rival_id": c.get("rival_id")})
        m["score"] += c["score"]
        m["reasons"].append(c["reason"])
        m["kinds"].append(c["kind"])
    # The mission is midfield/underdog coverage: down-weight drivers from front-running teams
    for m in merged.values():
        team = drivers[m["driver_id"]].team
        if team in strong_teams:
            m["score"] *= TOP_TEAM_MULTIPLIER
            m["kinds"].append("front_running_team_downweighted")
    ranked = sorted(merged.values(), key=lambda m: -m["score"])
    best = ranked[0]
    d = drivers[best["driver_id"]]
    return {
        "driver_id": d.id,
        "driver": d.full_name,
        "team": d.team,
        "score": round(best["score"], 2),
        "story_types": best["kinds"],
        "reason": " ".join(best["reasons"]),
        "rival_id": best.get("rival_id"),
        "runners_up": [
            {"driver_id": m["driver_id"], "driver": drivers[m["driver_id"]].full_name, "score": round(m["score"], 2), "reason": " ".join(m["reasons"])}
            for m in ranked[1:4]
        ],
    }
