"""Midfield / underdog spotlight: pick the most compelling story outside the top 3."""
from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session as OrmSession

from ..ingest.entries import event_drivers
from ..models import (
    PRACTICE_LIKE,
    QUALI_LIKE,
    RACE_LIKE,
    DetailLongRunPace,
    HeadlinePractice,
    HeadlineQualifying,
    HeadlineRace,
    Result,
    Session,
)
from ..util import fmt_ms

# A long run shorter than this is a programme note, not a pace ranking.
LONG_RUN_RANK_MIN_LAPS = 8


class _D:
    """Driver card for this event (team as entered for the weekend)."""

    def __init__(self, d: dict):
        self.id, self.full_name, self.team = d["id"], d["name"], d.get("team")


def _drivers(db: OrmSession, event_id: int) -> dict[int, _D]:
    return {i: _D(d) for i, d in event_drivers(db, event_id).items()}


def _ordinal(n: int) -> str:
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def _race_candidates(db: OrmSession, session_id: int, drivers: dict[int, _D]) -> list[dict[str, Any]]:
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


def _quali_candidates(db: OrmSession, session_id: int, drivers: dict[int, _D]) -> list[dict[str, Any]]:
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
        seg = r.gap_segment or "Q3"
        gap = f", {fmt_ms(r.gap_to_pole_ms)}s off the fastest {seg} time" if r.gap_to_pole_ms is not None else ""
        reason = f"{drivers[r.driver_id].full_name} qualified P{r.position}{gap}"
        if mate and mate.position:
            n = abs(mate_gap)
            reason += f", {n} place{'s' if n != 1 else ''} {'ahead of' if mate_gap > 0 else 'behind'} teammate {drivers[mate.driver_id].full_name} (P{mate.position})"
        cands.append({"driver_id": r.driver_id, "score": score, "kind": "quali_overperformer", "reason": reason + "."})
    return cands


def _practice_candidates(db: OrmSession, session_id: int, drivers: dict[int, _D]) -> list[dict[str, Any]]:
    rows = db.scalars(select(HeadlinePractice).where(HeadlinePractice.session_id == session_id)).all()
    rank_by_id = {r.driver_id: r.rank for r in rows}
    pace = db.scalars(select(DetailLongRunPace).where(DetailLongRunPace.session_id == session_id)).all()
    cands = []
    by_compound: dict[str, list[DetailLongRunPace]] = {}
    for p in pace:
        by_compound.setdefault(p.compound, []).append(p)
    # one candidate per driver, naming every compound they ranked well on (REVIEW #26)
    per_driver: dict[int, list[tuple[int, str, DetailLongRunPace, int]]] = {}
    for compound, lst in by_compound.items():
        ranked = sorted((p for p in lst if p.lap_count >= LONG_RUN_RANK_MIN_LAPS), key=lambda p: p.avg_lap_time_ms)
        for i, p in enumerate(ranked[:6]):
            hr = rank_by_id.get(p.driver_id)
            if hr is None or hr <= 3:
                continue
            per_driver.setdefault(p.driver_id, []).append((i + 1, compound, p, len(ranked)))
    for did, items in per_driver.items():
        items.sort()
        hr = rank_by_id[did]
        best_rank = items[0][0]
        score = 1.0 + max(0, hr - best_rank) * 0.5 + (1.0 if best_rank == 1 else 0.0) + 0.3 * (len(items) - 1)
        parts = [f"{_ordinal(rank)} of {n} on {compound.lower()} ({fmt_ms(p.avg_lap_time_ms)} over {p.lap_count} laps)" for rank, compound, p, n in items]
        cands.append(
            {
                "driver_id": did,
                "score": score,
                "kind": "long_run_pace",
                "reason": f"{drivers[did].full_name} was P{hr} on a single lap but stronger on long runs: {', '.join(parts)}.",
            }
        )
    return cands


TOP_TEAM_COUNT = 4
TOP_TEAM_MULTIPLIER = 0.45


def top_teams(db: OrmSession, session: Session) -> set[str]:
    """Front-running teams, from season-to-date constructor points (falls back to this session's top 3)."""
    from ..analysis.pivotal import championship_before
    from ..models import Event

    event = db.get(Event, session.event_id)
    _, teams = championship_before(db, event)
    if len(teams) < 2:  # season opener: the teams in this session's top six are the "expected" front
        drivers = _drivers(db, event.id)
        for model, col in ((HeadlineRace, HeadlineRace.finish_position), (HeadlineQualifying, HeadlineQualifying.position), (HeadlinePractice, HeadlinePractice.rank)):
            for r in db.scalars(select(model).where(model.session_id == session.id, col <= 6)).all():
                d = drivers.get(r.driver_id)
                if d and d.team:
                    teams.add(d.team)
    return teams


def identify_midfield_story(db: OrmSession, session_id: int) -> dict[str, Any] | None:
    session = db.get(Session, session_id)
    if session is None:
        raise ValueError(f"session {session_id} not found")
    drivers = _drivers(db, session.event_id)
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
    for m in merged.values():
        m["reasons"] = _join_reasons(drivers[m["driver_id"]].full_name, m["reasons"])
    ranked = sorted(merged.values(), key=lambda m: -m["score"])
    best = ranked[0]
    d = drivers[best["driver_id"]]
    return {
        "driver_id": d.id,
        "driver": d.full_name,
        "team": d.team,
        "score": round(best["score"], 2),
        "story_types": best["kinds"],
        "reason": best["reasons"],
        "rival_id": best.get("rival_id"),
        "runners_up": [
            {"driver_id": m["driver_id"], "driver": drivers[m["driver_id"]].full_name, "team": drivers[m["driver_id"]].team, "score": round(m["score"], 2), "reason": m["reasons"], "story_types": m["kinds"]}
            for m in ranked[1:4]
        ],
    }


def _join_reasons(name: str, reasons: list[str]) -> str:
    """One readable paragraph: no repeated sentences, the name only in the first one."""
    seen, out = set(), []
    for r in reasons:
        if r in seen:
            continue
        seen.add(r)
        if out and r.startswith(name + " "):
            r = "He " + r[len(name) + 1:]
        out.append(r)
    return " ".join(out)
