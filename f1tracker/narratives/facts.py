"""Fact sheets: everything a story may say about one driver in one session, computed in code.

The model writes from this and nothing else; the fact-checker (factcheck.py) then verifies every
number, name and claim in its output against the same sheet. Verdicts the data supports are
computed here (stop timing against a VSC, undercut outcomes, fuel-corrected tyre degradation), so
the analysis can state conclusions instead of hedging. What the data can't support is listed in
`insufficient_data`, which is the only licence the analysis has to say "the data doesn't show".
"""
from __future__ import annotations

from collections import defaultdict
from statistics import mean
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session as OrmSession

from ..analysis.race_control import cases, neutral_periods, parse_messages
from ..analysis.strategy import analyse_stops, pit_battles, real_stops
from ..ingest.entries import event_drivers, teammates
from ..models import (
    PRACTICE_LIKE,
    QUALI_LIKE,
    RACE_LIKE,
    DetailDegradation,
    DetailLongRunPace,
    DetailPositionByLap,
    DetailStintTimeline,
    Event,
    HeadlinePractice,
    HeadlineQualifying,
    HeadlineRace,
    Lap,
    PitStop,
    PivotalMoment,
    RaceControl,
    Result,
    Session,
)
from ..util import fmt_ms
from .inputs import session_meta, weather_summary

FUEL_EFFECT_MS_PER_LAP = 30  # a lap's worth of fuel burned makes the car ~0.03s faster
DEG_MIN_LAPS = 6
LONG_RUN_RANK_MIN_LAPS = 8
SESSION_WORD = {"FP1": "FP1", "FP2": "FP2", "FP3": "FP3", "SQ": "sprint qualifying", "S": "the sprint", "Q": "qualifying", "R": "the race"}


def t(ms: int | float | None) -> str | None:
    return None if ms is None else fmt_ms(int(round(ms)))


def gap(ms: int | float | None) -> str | None:
    return None if ms is None else f"{'+' if ms >= 0 else '-'}{fmt_ms(int(round(abs(ms))))}s"


def _ordinal(n: int) -> str:
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def _rows(db, model, session_id: int) -> list[dict]:
    cols = [c.name for c in model.__table__.columns]
    return [{c: getattr(r, c) for c in cols} for r in db.scalars(select(model).where(model.session_id == session_id)).all()]


def _positions(db: OrmSession, session_id: int) -> dict[int, dict[int, int]]:
    out: dict[int, dict[int, int]] = defaultdict(dict)
    for r in db.scalars(select(DetailPositionByLap).where(DetailPositionByLap.session_id == session_id)).all():
        if r.position is not None:
            out[r.driver_id][r.lap_number] = r.position
    return out


def _neutral_laps(periods: list[dict]) -> set[int]:
    laps: set[int] = set()
    for p in periods:
        if p.get("start_lap"):
            laps.update(range(p["start_lap"], (p.get("end_lap") or p["start_lap"]) + 2))
    return laps


def stint_facts(db: OrmSession, session_id: int, driver_id: int, periods: list[dict]) -> list[dict]:
    """Each stint with its fuel-corrected degradation (seconds per lap), when there are enough clean laps."""
    stints = db.scalars(select(DetailStintTimeline).where(DetailStintTimeline.session_id == session_id, DetailStintTimeline.driver_id == driver_id).order_by(DetailStintTimeline.stint_number)).all()
    deg = db.scalars(select(DetailDegradation).where(DetailDegradation.session_id == session_id, DetailDegradation.driver_id == driver_id)).all()
    by_stint: dict[int, list[DetailDegradation]] = defaultdict(list)
    for d in deg:
        by_stint[d.stint_number].append(d)
    neutral = _neutral_laps(periods)
    out = []
    for s in stints:
        laps = sorted(by_stint.get(s.stint_number, []), key=lambda d: d.lap_number_in_stint)
        pts = [(d.lap_number_in_stint, d.lap_time_ms) for d in laps if d.lap_time_ms and (s.lap_start or 0) + d.lap_number_in_stint - 1 not in neutral]
        if pts:
            best = min(v for _, v in pts)
            pts = [(x, v) for x, v in pts if v <= best * 1.04]  # traffic, slow laps and the out-lap go
        entry: dict[str, Any] = {
            "stint": s.stint_number, "compound": s.compound or "UNRECORDED",  # the timing feed didn't say
            "laps": f"{s.lap_start}-{s.lap_end}" if s.lap_start and s.lap_end else None,
            "lap_count": (s.lap_end - s.lap_start + 1) if s.lap_start and s.lap_end else None,
        }
        if pts:
            entry["best_lap"] = t(min(v for _, v in pts))
        if len(pts) >= DEG_MIN_LAPS:
            xs, ys = [x for x, _ in pts], [v for _, v in pts]
            mx, my = mean(xs), mean(ys)
            den = sum((x - mx) ** 2 for x in xs)
            slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / den if den else 0.0
            entry["degradation_s_per_lap"] = round((slope + FUEL_EFFECT_MS_PER_LAP) / 1000, 3)
            entry["degradation_sample_laps"] = len(pts)
            entry["average_lap"] = t(my)
        out.append(entry)
    return out


def _sector_ranks(db: OrmSession, session_id: int, driver_id: int) -> dict[str, Any]:
    from ..models import DetailSectorDelta

    rows = db.execute(
        select(DetailSectorDelta.driver_id, DetailSectorDelta.sector, func.min(DetailSectorDelta.driver_sector_ms))
        .where(DetailSectorDelta.session_id == session_id, DetailSectorDelta.driver_sector_ms.is_not(None))
        .group_by(DetailSectorDelta.driver_id, DetailSectorDelta.sector)
    ).all()
    per: dict[int, list[tuple[int, int]]] = defaultdict(list)
    for did, sec, best in rows:
        per[sec].append((best, did))
    out = {}
    for sec in (1, 2, 3):
        ranked = sorted(per.get(sec, []))
        idx = next((i for i, (_, d) in enumerate(ranked) if d == driver_id), None)
        if idx is None:
            continue
        out[f"sector_{sec}"] = {"best": t(ranked[idx][0]), "gap_to_session_best": gap(ranked[idx][0] - ranked[0][0]), "rank": idx + 1, "of": len(ranked)}
    return out


def _incident_facts(incs, cases_, driver_id: int, names: dict[int, str]) -> list[dict]:
    out = []
    for c in cases_:
        if driver_id not in c["driver_ids"]:
            continue
        others = [names.get(d, "another driver") for d in c["driver_ids"] if d != driver_id]
        out.append({
            "lap": c["opened_lap"], "with": others, "turn": c["turn"], "reason": c["reason"],
            "outcome": c["outcome"] or ("to be investigated after the session" if c["after_race"] else "noted, no decision recorded"),
            "case_id": c["id"],
        })
    deleted = [i for i in incs if i.kind == "track_limits" and driver_id in i.driver_ids]
    if deleted:
        out.append({"lap": deleted[0].lap, "track_limits_deletions": len(deleted)})
    for i in incs:
        if i.kind == "penalty" and driver_id in i.driver_ids:
            out.append({"lap": i.lap, "penalty": i.outcome, "reason": (i.reason or "").lower() or None})
    return out


def _stop_text(v, names: dict[int, str]) -> str:
    parts = [f"pitted at the end of lap {v.in_lap}"]
    if v.compound_from or v.compound_to:
        parts.append(f"{(v.compound_from or 'unknown').lower()} to {(v.compound_to or 'unknown').lower()}")
    return ", ".join(parts)


def _stop_verdicts(stops, battles, driver_id: int, names: dict[int, str]) -> tuple[list[dict], list[str]]:
    facts, verdicts = [], []
    for v in stops:
        if v.driver_id != driver_id:
            continue
        f: dict[str, Any] = {
            "stop": v.stop_number, "in_lap": v.in_lap, "from": v.compound_from, "to": v.compound_to,
            "stationary": f"{v.stationary_ms / 1000:.1f}s" if v.stationary_ms else "not published by the timing feed",
            "pit_lane_time": f"{v.lane_ms / 1000:.1f}s" if v.lane_ms else None,
            "position_before": v.position_before, "position_after_cycle": v.position_after_cycle, "net_places": v.net_places,
        }
        if v.neutralisation:
            kind = {"SC": "Safety Car", "VSC": "Virtual Safety Car", "RED": "red flag"}[v.neutralisation_kind]
            s, e = v.neutralisation_laps
            f["neutralisation"] = {"relation": v.neutralisation, "kind": kind, "laps": f"{s}-{e}" if e and e != s else str(s)}
            if v.neutralisation == "during":
                verdicts.append(f"Stop {v.stop_number} (lap {v.in_lap}) came under the {kind}: a cheap stop, because the cars he was racing were also slowed.")
            elif v.neutralisation == "just_before":
                verdicts.append(f"Stop {v.stop_number} (lap {v.in_lap}) came just before the {kind} on lap {s}: unlucky timing, because anyone who waited could stop under it for less time lost.")
            elif v.neutralisation == "just_after":
                verdicts.append(f"Stop {v.stop_number} (lap {v.in_lap}) came just after the {kind} ended on lap {e or s}: the chance of a cheaper stop under it was missed.")
        if v.net_places is not None and v.position_before is not None:
            if v.net_places > 0:
                verdicts.append(f"Stop {v.stop_number} gained him {v.net_places} place{'s' if v.net_places != 1 else ''} once the cars around him had stopped too (P{v.position_before} to P{v.position_after_cycle}).")
            elif v.net_places < 0:
                verdicts.append(f"Stop {v.stop_number} cost him {-v.net_places} place{'s' if v.net_places != -1 else ''} once the cars around him had stopped too (P{v.position_before} to P{v.position_after_cycle}).")
        if v.slow:
            verdicts.append(f"Stop {v.stop_number} was slow: " + (f"{v.stationary_ms / 1000:.1f}s stationary." if v.stationary_ms and v.stationary_ms >= 4000 else f"{v.lane_vs_median_ms / 1000:.1f}s longer in the pit lane than the typical stop."))
        facts.append(f)
    for b in battles:
        if driver_id not in (b.attacker_id, b.defender_id) or b.under_neutralisation:
            continue
        other = b.defender_id if b.attacker_id == driver_id else b.attacker_id
        me_first = b.attacker_id == driver_id
        won = (b.verdict in ("undercut_worked", "stayed_ahead")) == me_first
        what = {
            ("undercut_worked", True): f"his undercut on {names.get(other)} worked: he pitted first (lap {b.attacker_lap}) and was ahead once {names.get(other)} stopped (lap {b.defender_lap})",
            ("undercut_failed", True): f"his undercut attempt on {names.get(other)} failed: he pitted first (lap {b.attacker_lap}) but was still behind once {names.get(other)} stopped (lap {b.defender_lap})",
            ("stayed_ahead", True): f"he pitted first (lap {b.attacker_lap}) and stayed ahead of {names.get(other)}, who stopped on lap {b.defender_lap}",
            ("overcut_worked", True): f"{names.get(other)} overcut him: he pitted first (lap {b.attacker_lap}) and was behind once {names.get(other)} stopped (lap {b.defender_lap})",
            ("undercut_worked", False): f"{names.get(other)} undercut him: they pitted on lap {b.attacker_lap}, he waited until lap {b.defender_lap} and came out behind",
            ("undercut_failed", False): f"he resisted {names.get(other)}'s undercut: they pitted on lap {b.attacker_lap}, he stopped on lap {b.defender_lap} and stayed ahead",
            ("stayed_ahead", False): f"{names.get(other)} pitted first (lap {b.attacker_lap}) and stayed ahead of him",
            ("overcut_worked", False): f"his overcut on {names.get(other)} worked: he stayed out until lap {b.defender_lap} and came out ahead",
        }[(b.verdict, me_first)]
        verdicts.append(what[0].upper() + what[1:] + ("." if not what.endswith(".") else ""))
        del won
    return facts, verdicts


def build_driver_session_facts(db: OrmSession, session_id: int, driver_id: int) -> dict[str, Any]:
    session = db.get(Session, session_id)
    if session is None:
        raise ValueError(f"session {session_id} not found")
    event = db.get(Event, session.event_id)
    cards = event_drivers(db, event.id)
    me = cards.get(driver_id)
    if me is None:
        raise ValueError(f"driver {driver_id} was not entered at event {event.id}")
    names = {i: c["name"] for i, c in cards.items()}
    mates = teammates(db, event.id, driver_id)
    mate = mates[0] if mates else None
    stype = session.session_type
    numbers = {c["number"]: i for i, c in cards.items() if c.get("number") is not None}
    incs = parse_messages(db.scalars(select(RaceControl).where(RaceControl.session_id == session_id)).all(), numbers)
    periods = neutral_periods(incs)
    session_cases = cases(incs)

    sheet: dict[str, Any] = {
        "meta": session_meta(db, session),
        "driver": {
            "name": me["name"], "team": me["team"], "car_number": me["number"],
            "teammate": names.get(mate) if mate else None,
            **({"stand_in": True, "usual_team": me["usual_team"]} if me.get("stand_in") else {}),
        },
        "weather": weather_summary(db, session_id),
        "laps_completed": db.scalar(select(func.count()).where(Lap.session_id == session_id, Lap.driver_id == driver_id)),
        "sectors": _sector_ranks(db, session_id, driver_id),
        "neutralisations": [{"kind": {"SC": "Safety Car", "VSC": "Virtual Safety Car", "RED": "Red flag"}[p["kind"]], "laps": (f"{p['start_lap']}-{p['end_lap']}" if p.get("end_lap") and p["end_lap"] != p["start_lap"] else str(p["start_lap"])) if p.get("start_lap") else "during the session"} for p in periods],
        "incidents": _incident_facts(incs, session_cases, driver_id, names),
        "key_moments_involving_him": [m.headline for m in db.scalars(select(PivotalMoment).where(PivotalMoment.session_id == session_id)).all() if m.headline and driver_id in (m.driver_id, m.related_driver_id)],
        "verdicts": [],
        "insufficient_data": [],
    }
    verdicts: list[str] = sheet["verdicts"]
    gaps: list[str] = sheet["insufficient_data"]

    if stype in PRACTICE_LIKE:
        rows = sorted(_rows(db, HeadlinePractice, session_id), key=lambda r: r["rank"] or 99)
        mine = next((r for r in rows if r["driver_id"] == driver_id), None)
        sheet["result"] = {
            "position": mine["rank"] if mine else None, "of": len(rows),
            "best_lap": t(mine["fastest_lap_ms"]) if mine else None,
            "gap_to_fastest": gap(mine["gap_to_fastest_ms"]) if mine else None,
            "fastest": {"driver": names.get(rows[0]["driver_id"]), "lap": t(rows[0]["fastest_lap_ms"])} if rows else None,
            "teammate_position": next((r["rank"] for r in rows if r["driver_id"] == mate), None),
        }
        stints = stint_facts(db, session_id, driver_id, periods)
        sheet["programme"] = {"runs": len(stints), "stints": stints}
        pace = [r for r in _rows(db, DetailLongRunPace, session_id)]
        runs = []
        for compound in sorted({r["compound"] for r in pace}):
            ranked = sorted((r for r in pace if r["compound"] == compound and r["lap_count"] >= LONG_RUN_RANK_MIN_LAPS), key=lambda r: r["avg_lap_time_ms"])
            mine_run = next((r for r in pace if r["compound"] == compound and r["driver_id"] == driver_id), None)
            if mine_run is None:
                continue
            entry = {"compound": compound, "average_lap": t(mine_run["avg_lap_time_ms"]), "laps": mine_run["lap_count"]}
            if mine_run["lap_count"] >= LONG_RUN_RANK_MIN_LAPS and ranked:
                entry["rank"] = next(i + 1 for i, r in enumerate(ranked) if r["driver_id"] == driver_id)
                entry["of_drivers_with_8_plus_laps"] = len(ranked)
            else:
                entry["note"] = f"only {mine_run['lap_count']} laps: too short to rank"
            runs.append(entry)
        sheet["long_runs"] = runs
        gaps.append("fuel loads and engine modes in practice (any pace ranking is indicative only)")
        sheet["result_headline"] = f"P{mine['rank']} in {SESSION_WORD[stype]}" if mine and mine["rank"] else f"No time in {SESSION_WORD[stype]}"

    elif stype in QUALI_LIKE:
        rows = _rows(db, HeadlineQualifying, session_id)
        mine = next((r for r in rows if r["driver_id"] == driver_id), None)
        prefix = "SQ" if stype == "SQ" else "Q"
        result: dict[str, Any] = {"position": mine["position"] if mine else None, "of": len(rows)}
        if mine and mine["status_code"] == "NO_TIME":
            result["note"] = "set no time"
        elif mine:
            seg = mine["gap_segment"]
            result["reached"] = f"{prefix}3" if mine["eliminated_in"] is None else f"knocked out in {prefix}{mine['eliminated_in'][1]}"
            if mine["gap_to_pole_ms"] is not None:
                result[f"gap_to_fastest_in_{prefix}{seg[1]}" if seg else "gap"] = gap(mine["gap_to_pole_ms"])
            result["times"] = {f"{prefix}{k[1]}": t(mine[f"q{k[1]}_ms"]) for k in ("Q1", "Q2", "Q3") if mine.get(f"q{k[1]}_ms")}
        mate_row = next((r for r in rows if r["driver_id"] == mate), None)
        if mate_row:
            result["teammate"] = {"name": names.get(mate), "position": mate_row["position"], "note": "set no time" if mate_row["status_code"] == "NO_TIME" else None}
        pole = next((r for r in rows if r["position"] == 1), None)
        result["pole"] = {"driver": names.get(pole["driver_id"]), "lap": t(pole["q3_ms"])} if pole else None
        # margins at the cut lines
        for k, cut_name in (("q1_ms", "Q1"), ("q2_ms", "Q2")):
            times = sorted((r[k], r["driver_id"]) for r in rows if r.get(k))
            survivors = sum(1 for r in rows if r.get(k) and r["eliminated_in"] != cut_name)
            mine_t = next((tt for tt, d in times if d == driver_id), None)
            if mine_t is None or not (0 < survivors < len(times)):
                continue
            last_in, first_out = times[survivors - 1], times[survivors]
            if mine_t <= last_in[0]:
                result[f"{prefix}{cut_name[1]}_margin"] = f"through by {fmt_ms(first_out[0] - mine_t)}s over the first car knocked out ({names.get(first_out[1])})"
            else:
                result[f"{prefix}{cut_name[1]}_margin"] = f"missed out by {fmt_ms(mine_t - last_in[0])}s to the last car through ({names.get(last_in[1])})"
        sheet["result"] = result
        sheet["runs"] = stint_facts(db, session_id, driver_id, periods)
        sheet["result_headline"] = f"P{mine['position']} in {SESSION_WORD[stype]}" if mine and mine["position"] else f"No time in {SESSION_WORD[stype]}"

    elif stype in RACE_LIKE:
        race = _rows(db, HeadlineRace, session_id)
        mine = next((r for r in race if r["driver_id"] == driver_id), None)
        res = db.scalar(select(Result).where(Result.session_id == session_id, Result.driver_id == driver_id))
        winner = next((r for r in race if r["finish_position"] == 1), None)
        code = mine["status_code"] if mine else None
        result = {
            "status": {"FIN": "finished on the lead lap", "LAP": f"finished {mine['laps_down']} lap{'s' if (mine['laps_down'] or 1) != 1 else ''} down" if mine else None,
                       "DNF": "retired", "NC": "not classified", "DNS": "did not start", "DSQ": "disqualified"}.get(code),
            "grid": mine["grid_position"] if mine else None,
            "finish": mine["finish_position"] if mine else None,
            "places_gained": mine["positions_gained"] if mine else None,
            "points": mine["points"] if mine else None,
            "pit_stops": mine["pit_stop_count"] if mine else None,
            "laps_completed": mine["laps_completed"] if mine else None,
            "winner": names.get(winner["driver_id"]) if winner else None,
        }
        if code == "FIN" and res and res.gap_to_leader_ms:
            result["gap_to_winner"] = gap(res.gap_to_leader_ms)
        if code in ("DNF", "NC") and mine and mine["laps_completed"] is not None:
            result["retired_on_lap"] = mine["laps_completed"] + 1
            result["retirement_reason_given"] = (mine["status"] or "").lower() if (mine["status"] or "").lower() not in ("retired", "lapped") else "not stated"
        if mine and mine["finish_position"] and code in ("DNF", "NC"):
            result["note"] = f"classified P{mine['finish_position']} despite stopping (covered enough of the distance)"
        mate_row = next((r for r in race if r["driver_id"] == mate), None)
        if mate_row:
            result["teammate"] = {"name": names.get(mate), "grid": mate_row["grid_position"], "finish": mate_row["finish_position"], "status": mate_row["status_code"]}
        sheet["result"] = result
        if code == "DNS":
            sheet["result_headline"] = "Did not start"
            sheet["verdicts"] = []
            return sheet
        pos = _positions(db, session_id)
        mine_pos = pos.get(driver_id, {})
        if mine_pos:
            laps = sorted(mine_pos)
            sheet["position_trace"] = {
                "end_of_lap_1": mine_pos.get(1), "best": min(mine_pos.values()), "worst": max(mine_pos.values()),
                "final": mine_pos[laps[-1]], "last_lap_recorded": laps[-1],
            }
        pits = _rows(db, PitStop, session_id)
        stints_all = [{"driver_id": s.driver_id, "stint_number": s.stint_number, "compound": s.compound, "lap_start": s.lap_start, "lap_end": s.lap_end}
                      for s in db.scalars(select(DetailStintTimeline).where(DetailStintTimeline.session_id == session_id)).all()]
        stops = analyse_stops(pits, stints_all, pos, periods)
        starts: dict[int, dict] = defaultdict(dict)
        for lp in db.scalars(select(Lap).where(Lap.session_id == session_id, Lap.lap_start_time.is_not(None))).all():
            starts[lp.driver_id][lp.lap_number] = lp.lap_start_time
        battles = pit_battles(pits, pos, starts, periods)
        stop_facts, stop_verdicts = _stop_verdicts(stops, battles, driver_id, names)
        sheet["stops"] = stop_facts
        verdicts += stop_verdicts
        if any(f["stationary"].startswith("not published") for f in stop_facts):
            gaps.append("stationary pit-stop times (the feed doesn't publish them for this race; pit-lane time is available)")
        sheet["stints"] = stint_facts(db, session_id, driver_id, periods)
        if sheet["stints"] and len(sheet["stints"]) != len(stop_facts) + 1:
            # the feed's stint list and its pit records disagree: say nothing rather than something wrong
            gaps.append("tyre stints (the feed's stint and pit-stop records disagree for this car)")
            sheet["stints"] = []
        for s in sheet["stints"]:
            if "degradation_s_per_lap" in s:
                d = s["degradation_s_per_lap"]
                which = f"{s['compound'].lower()}-tyre stint" if s["compound"] != "UNRECORDED" else "opening stint (compound not recorded)"
                verdicts.append(f"On his {which}, laps {s['laps']}, his pace fell away by about {d:.2f}s per lap once fuel burn is allowed for." if d > 0.02
                                else f"On his {which}, laps {s['laps']}, his pace held steady once fuel burn is allowed for ({d:+.2f}s per lap).")
        # nearest rivals on track
        counts: dict[int, int] = defaultdict(int)
        for other, by_lap in pos.items():
            if other == driver_id:
                continue
            for lap, p in mine_pos.items():
                q = by_lap.get(lap)
                if q is not None and abs(q - p) == 1:
                    counts[other] += 1
        rivals = []
        for other, n in sorted(counts.items(), key=lambda kv: -kv[1])[:3]:
            if n < 5:
                continue
            o = next((r for r in race if r["driver_id"] == other), {})
            rivals.append({"driver": names.get(other), "team": cards.get(other, {}).get("team"), "laps_running_together": n, "their_finish": o.get("finish_position"), "their_status": o.get("status_code")})
        sheet["rivals_on_track"] = rivals
        # what the stops of the cars around him looked like
        sheet["rivals_stops"] = [
            {"driver": r["driver"], "in_laps": [p["lap_number"] for p in sorted(real_stops(pits), key=lambda p: p["lap_number"]) if names.get(p["driver_id"]) == r["driver"]]}
            for r in rivals
        ]
        fin, grid = result["finish"], result["grid"]
        sheet["result_headline"] = (f"P{fin} from P{grid}" if fin and grid else f"P{fin}" if fin
                                    else f"Retired on lap {result['retired_on_lap']}" if result.get("retired_on_lap") else "Retired")
    return sheet


def numbers_in(obj: Any) -> set[float]:
    """Every number a story may quote from this sheet (values, and numbers inside its text)."""
    import re

    out: set[float] = set()

    def add_text(s: str) -> None:
        for m in re.finditer(r"(\d+):(\d{2})\.(\d{3})", s):
            out.add(int(m.group(1)) * 60 + int(m.group(2)) + int(m.group(3)) / 1000)
        for m in re.finditer(r"\d+(?:\.\d+)?", s):
            out.add(float(m.group()))

    def walk(o: Any) -> None:
        if isinstance(o, bool) or o is None:
            return
        if isinstance(o, (int, float)):
            out.add(float(o))
        elif isinstance(o, str):
            add_text(o)
        elif isinstance(o, dict):
            for k, v in o.items():
                add_text(str(k))
                walk(v)
        elif isinstance(o, (list, tuple)):
            for v in o:
                walk(v)

    walk(obj)
    return out


def story_context(db: OrmSession, session_id: int) -> dict[str, Any]:
    """What the fact-checker needs beyond the sheet: the season roster and who took part here."""
    from ..models import Driver, Entry

    session = db.get(Session, session_id)
    roster = {}
    for d in db.scalars(select(Driver).join(Entry, Entry.driver_id == Driver.id).join(Event, Event.id == Entry.event_id).where(Event.season_id == db.get(Event, session.event_id).season_id)).unique().all():
        surname = d.full_name.split(" ")[-1]
        if len(surname) >= 3:
            roster[surname] = d.full_name
    entrants = {c["name"] for c in event_drivers(db, session.event_id).values()}
    return {"roster": roster, "entrants": entrants}
