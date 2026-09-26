"""Assemble structured narrative inputs from headline_*/detail_* tables (no LLM here)."""
from __future__ import annotations

from collections import defaultdict
from statistics import mean
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session as OrmSession

from ..models import (
    PRACTICE_LIKE,
    QUALI_LIKE,
    RACE_LIKE,
    DetailDegradation,
    DetailLongRunPace,
    DetailPositionByLap,
    DetailQualifyingSegment,
    DetailSectorDelta,
    DetailStintTimeline,
    Driver,
    Event,
    HeadlinePractice,
    HeadlineQualifying,
    HeadlineRace,
    Lap,
    PitStop,
    PivotalMoment,
    RaceControl,
    Result,
    Season,
    Session,
    Weather,
)
from ..util import fmt_ms

SESSION_LABELS = {"FP1": "Free Practice 1", "FP2": "Free Practice 2", "FP3": "Free Practice 3", "SQ": "Sprint Qualifying", "S": "Sprint", "Q": "Qualifying", "R": "Grand Prix"}


def _t(ms: int | None) -> dict | None:
    return None if ms is None else {"ms": ms, "formatted": fmt_ms(ms)}


def _gap(ms: int | None) -> dict | None:
    return None if ms is None else {"ms": ms, "formatted": ("+" if ms >= 0 else "") + fmt_ms(ms) + "s"}


def driver_index(db: OrmSession) -> dict[int, Driver]:
    return {d.id: d for d in db.scalars(select(Driver)).all()}


def _name(drivers: dict[int, Driver], did: int | None) -> str | None:
    d = drivers.get(did) if did is not None else None
    return d.full_name if d else None


def session_meta(db: OrmSession, session: Session) -> dict[str, Any]:
    event = db.get(Event, session.event_id)
    season = db.get(Season, event.season_id)
    return {
        "season": season.year,
        "round": event.round,
        "event": event.name,
        "circuit": event.circuit_name,
        "country": event.country,
        "sprint_weekend": event.has_sprint,
        "session": SESSION_LABELS.get(session.session_type, session.session_type),
        "session_type": session.session_type,
        "date_utc": session.start_time.isoformat() if session.start_time else None,
    }


def weather_summary(db: OrmSession, session_id: int) -> dict[str, Any] | None:
    rows = db.scalars(select(Weather).where(Weather.session_id == session_id)).all()
    if not rows:
        return None
    air = [w.air_temp for w in rows if w.air_temp is not None]
    track = [w.track_temp for w in rows if w.track_temp is not None]
    rain = [w.rainfall for w in rows if w.rainfall is not None]
    return {
        "air_temp_c": {"min": min(air), "max": max(air)} if air else None,
        "track_temp_c": {"min": min(track), "max": max(track)} if track else None,
        "rain_reported": bool(rain and any(r > 0 for r in rain)),
        "humidity_pct_avg": round(mean([w.humidity for w in rows if w.humidity is not None]), 0) if any(w.humidity is not None for w in rows) else None,
    }


def sector_profile(db: OrmSession, session_id: int, driver_id: int) -> dict[str, Any]:
    """Best and average delta to session-best per sector, plus rank of the driver's best sector."""
    rows = db.execute(
        select(DetailSectorDelta.driver_id, DetailSectorDelta.sector, func.min(DetailSectorDelta.delta_ms), func.avg(DetailSectorDelta.delta_ms))
        .where(DetailSectorDelta.session_id == session_id)
        .group_by(DetailSectorDelta.driver_id, DetailSectorDelta.sector)
    ).all()
    per_sector: dict[int, list[tuple[int, int]]] = defaultdict(list)
    mine: dict[int, dict] = {}
    for did, sec, best, avg in rows:
        per_sector[sec].append((did, best))
        if did == driver_id:
            mine[sec] = {"best_delta_to_session_best": _gap(int(best)), "avg_delta_to_session_best": _gap(int(round(avg)))}
    out = {}
    for sec in (1, 2, 3):
        if sec not in mine:
            continue
        ranked = sorted(per_sector[sec], key=lambda x: x[1])
        rank = next((i + 1 for i, (did, _) in enumerate(ranked) if did == driver_id), None)
        out[f"sector_{sec}"] = {**mine[sec], "rank_of_best_sector": rank, "drivers_ranked": len(ranked)}
    return out


def stints_for(db: OrmSession, session_id: int, driver_id: int) -> list[dict]:
    rows = db.scalars(select(DetailStintTimeline).where(DetailStintTimeline.session_id == session_id, DetailStintTimeline.driver_id == driver_id).order_by(DetailStintTimeline.stint_number)).all()
    deg = db.scalars(select(DetailDegradation).where(DetailDegradation.session_id == session_id, DetailDegradation.driver_id == driver_id)).all()
    by_stint: dict[int, list[DetailDegradation]] = defaultdict(list)
    for d in deg:
        by_stint[d.stint_number].append(d)
    out = []
    for s in rows:
        laps = sorted(by_stint.get(s.stint_number, []), key=lambda d: d.lap_number_in_stint)
        times = [l.lap_time_ms for l in laps if l.lap_time_ms]
        entry = {"stint": s.stint_number, "compound": s.compound, "laps": f"{s.lap_start}-{s.lap_end}", "lap_count": (s.lap_end - s.lap_start + 1) if s.lap_start and s.lap_end else None}
        if len(times) >= 6:
            entry["early_avg"] = _t(int(mean(times[:3])))
            entry["late_avg"] = _t(int(mean(times[-3:])))
            entry["degradation_early_to_late"] = _gap(int(mean(times[-3:]) - mean(times[:3])))
        if times:
            entry["best_lap"] = _t(min(times))
        out.append(entry)
    return out


def long_run_pace_context(db: OrmSession, session_id: int, driver_id: int) -> dict[str, Any]:
    rows = db.scalars(select(DetailLongRunPace).where(DetailLongRunPace.session_id == session_id)).all()
    drivers = driver_index(db)
    by_compound: dict[str, list[DetailLongRunPace]] = defaultdict(list)
    for r in rows:
        by_compound[r.compound].append(r)
    out = {}
    for compound, lst in by_compound.items():
        ranked = sorted(lst, key=lambda r: r.avg_lap_time_ms)
        mine = next((r for r in ranked if r.driver_id == driver_id), None)
        if mine is None:
            continue
        rank = ranked.index(mine) + 1
        out[compound] = {
            "avg_lap": _t(mine.avg_lap_time_ms),
            "lap_count": mine.lap_count,
            "rank": rank,
            "drivers_with_long_runs": len(ranked),
            "best_on_compound": {"driver": _name(drivers, ranked[0].driver_id), "avg_lap": _t(ranked[0].avg_lap_time_ms)},
            "gap_to_best": _gap(mine.avg_lap_time_ms - ranked[0].avg_lap_time_ms),
        }
    return out


def race_control_for(db: OrmSession, session_id: int, driver_id: int, driver_number: int | None) -> list[dict]:
    rows = db.scalars(select(RaceControl).where(RaceControl.session_id == session_id).order_by(RaceControl.timestamp)).all()
    out = []
    for r in rows:
        mine = r.driver_id == driver_id or (driver_number is not None and f"CAR {driver_number} " in r.message.upper())
        general = r.category == "SafetyCar" or r.flag == "RED"
        if mine or general:
            out.append({"lap": r.lap_number, "category": r.category, "flag": r.flag, "message": r.message, "involves_driver": bool(mine)})
    return out


def _positions(db: OrmSession, session_id: int) -> dict[int, dict[int, int]]:
    rows = db.scalars(select(DetailPositionByLap).where(DetailPositionByLap.session_id == session_id)).all()
    out: dict[int, dict[int, int]] = defaultdict(dict)
    for r in rows:
        out[r.driver_id][r.lap_number] = r.position
    return out


def battles_for(pos: dict[int, dict[int, int]], driver_id: int, drivers: dict[int, Driver], top_n: int = 3) -> list[dict]:
    mine = pos.get(driver_id, {})
    if not mine:
        return []
    counts: dict[int, int] = defaultdict(int)
    for other, by_lap in pos.items():
        if other == driver_id:
            continue
        for lap, p in mine.items():
            q = by_lap.get(lap)
            if q is not None and abs(q - p) == 1:
                counts[other] += 1
    ranked = sorted(counts.items(), key=lambda kv: -kv[1])[:top_n]
    out = []
    last_lap = max(mine)
    for other, n in ranked:
        if n < 3:
            continue
        other_final = pos[other].get(max(pos[other]))
        out.append({"rival": _name(drivers, other), "team": drivers[other].team, "laps_adjacent": n, "rival_final_position": other_final, "driver_final_position": mine[last_lap]})
    return out


def build_driver_session_input(db: OrmSession, session_id: int, driver_id: int) -> dict[str, Any]:
    session = db.get(Session, session_id)
    if session is None:
        raise ValueError(f"session {session_id} not found")
    drivers = driver_index(db)
    driver = drivers.get(driver_id)
    if driver is None:
        raise ValueError(f"driver {driver_id} not found")
    stype = session.session_type
    teammate = next((d for d in drivers.values() if d.team == driver.team and d.id != driver.id), None)

    doc: dict[str, Any] = {
        "meta": session_meta(db, session),
        "driver": {"name": driver.full_name, "team": driver.team, "number": driver.number, "teammate": teammate.full_name if teammate else None},
        "weather": weather_summary(db, session_id),
        "laps_completed": db.scalar(select(func.count()).where(Lap.session_id == session_id, Lap.driver_id == driver_id)),
    }
    doc["sector_profile_vs_session_best"] = sector_profile(db, session_id, driver_id)

    if stype in PRACTICE_LIKE:
        rows = db.scalars(select(HeadlinePractice).where(HeadlinePractice.session_id == session_id).order_by(HeadlinePractice.rank)).all()
        mine = next((r for r in rows if r.driver_id == driver_id), None)
        doc["headline"] = {
            "rank": mine.rank if mine else None,
            "fastest_lap": _t(mine.fastest_lap_ms) if mine else None,
            "gap_to_fastest": _gap(mine.gap_to_fastest_ms) if mine else None,
            "session_leader": {"driver": _name(drivers, rows[0].driver_id), "lap": _t(rows[0].fastest_lap_ms)} if rows else None,
            "teammate_rank": next((r.rank for r in rows if teammate and r.driver_id == teammate.id), None),
            "drivers_classified": len(rows),
        }
        doc["long_run_pace_by_compound"] = long_run_pace_context(db, session_id, driver_id)
        doc["stints"] = stints_for(db, session_id, driver_id)
        doc["race_control"] = race_control_for(db, session_id, driver_id, driver.number)

    elif stype in QUALI_LIKE:
        rows = db.scalars(select(HeadlineQualifying).where(HeadlineQualifying.session_id == session_id)).all()
        mine = next((r for r in rows if r.driver_id == driver_id), None)
        pole = next((r for r in rows if r.position == 1), None)
        doc["headline"] = {
            "position": mine.position if mine else None,
            "gap_to_pole": _gap(mine.gap_to_pole_ms) if mine else None,
            "eliminated_in": (mine.eliminated_in or "reached final segment") if mine else None,
            "pole_sitter": _name(drivers, pole.driver_id) if pole else None,
            "teammate_position": next((r.position for r in rows if teammate and r.driver_id == teammate.id), None),
        }
        segs = db.scalars(select(DetailQualifyingSegment).where(DetailQualifyingSegment.session_id == session_id)).all()
        by_seg: dict[str, list[DetailQualifyingSegment]] = defaultdict(list)
        for s in segs:
            by_seg[s.segment].append(s)
        doc["segments"] = {}
        for seg in ("Q1", "Q2", "Q3"):
            lst = sorted(by_seg.get(seg, []), key=lambda s: s.best_lap_ms)
            me = next((s for s in lst if s.driver_id == driver_id), None)
            if me is None:
                continue
            rank = lst.index(me) + 1
            cutoff_note = None
            if seg == "Q1" and len(lst) > 15:
                cutoff_note = f"cut line after P15; P15 time {fmt_ms(lst[14].best_lap_ms)}"
            elif seg == "Q2" and len(lst) > 10:
                cutoff_note = f"cut line after P10; P10 time {fmt_ms(lst[9].best_lap_ms)}"
            doc["segments"][seg] = {
                "best_lap": _t(me.best_lap_ms),
                "gap_to_segment_leader": _gap(me.gap_to_segment_leader_ms),
                "rank_in_segment": rank,
                "segment_leader": _name(drivers, lst[0].driver_id),
                "cutoff": cutoff_note,
            }
        doc["stints"] = stints_for(db, session_id, driver_id)
        doc["race_control"] = race_control_for(db, session_id, driver_id, driver.number)

    elif stype in RACE_LIKE:
        rows = db.scalars(select(HeadlineRace).where(HeadlineRace.session_id == session_id)).all()
        mine = next((r for r in rows if r.driver_id == driver_id), None)
        res = db.scalar(select(Result).where(Result.session_id == session_id, Result.driver_id == driver_id))
        winner = next((r for r in rows if r.finish_position == 1), None)
        doc["headline"] = {
            "grid": mine.grid_position if mine else None,
            "finish": mine.finish_position if mine else None,
            "positions_gained": mine.positions_gained if mine else None,
            "points": mine.points if mine else None,
            "status": mine.status if mine else None,
            "pit_stops": mine.pit_stop_count if mine else None,
            "gap_to_winner_at_finish": _gap(res.gap_to_leader_ms) if res and res.gap_to_leader_ms is not None else None,
            "winner": _name(drivers, winner.driver_id) if winner else None,
            "teammate": {"finish": next((r.finish_position for r in rows if teammate and r.driver_id == teammate.id), None), "grid": next((r.grid_position for r in rows if teammate and r.driver_id == teammate.id), None)} if teammate else None,
        }
        doc["stints"] = stints_for(db, session_id, driver_id)
        pits = db.scalars(select(PitStop).where(PitStop.session_id == session_id, PitStop.driver_id == driver_id).order_by(PitStop.lap_number)).all()
        doc["pit_stops"] = [{"in_lap": p.lap_number, "stationary_s": round(p.duration_ms / 1000, 1) if p.duration_ms else None, "pit_lane_s": round(p.lane_duration_ms / 1000, 1) if p.lane_duration_ms else None} for p in pits]
        pos = _positions(db, session_id)
        mine_pos = pos.get(driver_id, {})
        doc["position_by_lap"] = [{"lap": l, "pos": mine_pos[l]} for l in sorted(mine_pos)]
        doc["battles"] = battles_for(pos, driver_id, drivers)
        doc["race_pace_by_compound"] = long_run_pace_context(db, session_id, driver_id)
        doc["race_control"] = race_control_for(db, session_id, driver_id, driver.number)

        # Nearby rivals' strategies: cars finishing just ahead/behind + grid neighbours
        finish_order = sorted([r for r in rows if r.finish_position], key=lambda r: r.finish_position)
        neighbours: list[int] = []
        if mine and mine.finish_position:
            for r in finish_order:
                if r.driver_id != driver_id and abs(r.finish_position - mine.finish_position) <= 2:
                    neighbours.append(r.driver_id)
        if teammate and teammate.id not in neighbours:
            neighbours.append(teammate.id)
        rivals = []
        for rid in neighbours[:5]:
            rr = next((r for r in rows if r.driver_id == rid), None)
            rp = db.scalars(select(PitStop).where(PitStop.session_id == session_id, PitStop.driver_id == rid).order_by(PitStop.lap_number)).all()
            rivals.append(
                {
                    "driver": _name(drivers, rid),
                    "team": drivers[rid].team,
                    "grid": rr.grid_position if rr else None,
                    "finish": rr.finish_position if rr else None,
                    "status": rr.status if rr else None,
                    "stints": [{"compound": s["compound"], "laps": s["laps"]} for s in stints_for(db, session_id, rid)],
                    "pit_in_laps": [p.lap_number for p in rp],
                }
            )
        doc["nearby_rivals_strategy"] = rivals
        doc["pivotal_moments_session"] = [
            {"lap": m.lap_number, "type": m.moment_type, "description": m.description}
            for m in db.scalars(select(PivotalMoment).where(PivotalMoment.session_id == session_id).order_by(PivotalMoment.magnitude_score.desc())).all()
        ]
    return doc
