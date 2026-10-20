"""The Expert debrief: an engineer's view of one driver's session, computed in code (REVIEW_ROUND3 D7).

Essential is the short story Claude writes; Expert shows this instead of more prose. Every figure
here is computed from the timing data, so nothing in it can be a model's slip. A value the data
doesn't have is None (the page shows a dash), with at most one note per table saying why: never a
sentence in a story.

- Race and sprint: stint table (tyre, laps, fuel-corrected average pace, degradation, pace against
  the teammate on the same compound), pit stops (lap, pit-lane and stationary time, places once the
  cycle settled, timing against a Safety Car or VSC), sector ranks.
- Qualifying: segment table (best time per segment, margin to the cut line, gap to the teammate),
  sector ranks with the gap to the best in each (where the lap lost time), tyre runs.
- Practice: run plan (tyre, laps, average per run), long-run pace rank on each compound (only when
  at least 3 drivers ran 5 or more laps on it, with the sample size), single-lap rank.
- Findings: the top three verdict candidates, one short line each.

The methods page explains each computed number (fuel correction, degradation, net places, ranks).
"""
from __future__ import annotations

from statistics import mean
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session as OrmSession

from ..ingest.entries import teammates
from ..models import PRACTICE_LIKE, QUALI_LIKE, RACE_LIKE, DetailLongRunPace, DetailStintTimeline, HeadlineQualifying, Lap, Session
from ..util import fmt_ms
from .facts import FUEL_EFFECT_MS_PER_LAP

SLOW_LAP = 1.04  # laps more than 4% off a run's best are traffic, a cool-down or an out-lap
DEBRIEF_LONG_RUN_LAPS = 5
DEBRIEF_MIN_RANKED = 3


def _t(ms: float | None) -> str | None:
    return None if ms is None else fmt_ms(int(round(ms)))


def _gap(ms: float | None) -> str | None:
    return None if ms is None else f"{'+' if ms >= 0 else '-'}{fmt_ms(int(round(abs(ms))))}s"


def _ord(n: int) -> str:
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def _neutral_laps(sheet: dict) -> set[int]:
    """Laps run behind a Safety Car, VSC or red flag, plus the lap after (from the sheet's neutralisations)."""
    out: set[int] = set()
    for n in sheet.get("neutralisations") or []:
        laps = str(n.get("laps") or "")
        if not laps or not laps.replace("-", "").isdigit():
            continue
        a, _, b = laps.partition("-")
        out.update(range(int(a), int(b or a) + 2))
    return out


def _clean_laps(laps: list[Lap], start: int, end: int, skip: set[int]) -> list[Lap]:
    run = [lp for lp in laps if start <= lp.lap_number <= end and lp.lap_time_ms and not lp.is_pit_lap and not lp.is_pit_out_lap and lp.lap_number not in skip]
    if not run:
        return []
    best = min(lp.lap_time_ms for lp in run)
    return [lp for lp in run if lp.lap_time_ms <= best * SLOW_LAP]


def fuel_corrected(laps: list[Lap]) -> float | None:
    """Average lap time as if every lap carried the fuel of lap 1: each lap gets back the ~0.03s a lap
    of burned fuel made it faster. Needs 3 clean laps."""
    if len(laps) < 3:
        return None
    return mean(lp.lap_time_ms + FUEL_EFFECT_MS_PER_LAP * (lp.lap_number - 1) for lp in laps)


def _findings(sheet: dict) -> list[dict[str, Any]]:
    return [{"n": i + 1, "text": c.get("finding") or c["verdict"]} for i, c in enumerate((sheet.get("verdict_candidates") or [])[:3])]


def _sectors(sheet: dict) -> list[dict[str, Any]] | None:
    s = sheet.get("sectors") or {}
    if not s:
        return None
    return [{"sector": int(k[-1]), "best": v.get("best"), "gap": v.get("gap_to_session_best"), "rank": v.get("rank"), "of": v.get("of")} for k, v in sorted(s.items())]


def _race(db: OrmSession, session_id: int, driver_id: int, mate_id: int | None, sheet: dict) -> dict[str, Any]:
    out: dict[str, Any] = {"kind": "race", "notes": {}}
    skip = _neutral_laps(sheet) | {1}
    laps = db.scalars(select(Lap).where(Lap.session_id == session_id, Lap.driver_id.in_([d for d in (driver_id, mate_id) if d]))).all()
    mine = [lp for lp in laps if lp.driver_id == driver_id]
    mate_laps = [lp for lp in laps if lp.driver_id == mate_id]
    stints = db.scalars(select(DetailStintTimeline).where(DetailStintTimeline.session_id == session_id, DetailStintTimeline.driver_id.in_([d for d in (driver_id, mate_id) if d]))
                        .order_by(DetailStintTimeline.stint_number)).all()
    deg = {s.get("stint"): s.get("degradation_s_per_lap") for s in sheet.get("stints") or []}
    if sheet.get("stint_records_disagree"):
        out["stints"] = None
        out["notes"]["stints"] = "The timing feed's tyre records disagree with its pit-stop records for this car, so no stint is shown."
    else:
        rows = []
        for s in (x for x in stints if x.driver_id == driver_id):
            if not (s.lap_start and s.lap_end):
                continue
            pace = fuel_corrected(_clean_laps(mine, s.lap_start, s.lap_end, skip))
            vs = None
            if pace is not None and mate_id and s.compound:
                theirs = [lp for t in stints if t.driver_id == mate_id and t.compound == s.compound and t.lap_start and t.lap_end
                          for lp in _clean_laps(mate_laps, t.lap_start, t.lap_end, skip)]
                other = fuel_corrected(theirs)
                vs = _gap(pace - other) if other is not None else None
            rows.append({"stint": s.stint_number, "tyre": s.compound, "laps": f"{s.lap_start}-{s.lap_end}", "lap_count": s.lap_end - s.lap_start + 1,
                         "avg_pace": _t(pace), "degradation_s_per_lap": deg.get(s.stint_number), "vs_teammate_same_tyre": vs})
        out["stints"] = rows or None
        if rows and any(r["avg_pace"] is None or r["degradation_s_per_lap"] is None for r in rows):
            out["notes"]["stints"] = "A dash: too few clean laps in that stint (pace needs 3, degradation 6, outside Safety Car laps)."
    stops = []
    for f in sheet.get("stops") or []:
        n = f.get("neutralisation") or {}
        stops.append({
            "lap": f.get("in_lap"),
            "pit_lane": f.get("pit_lane_time"),
            "stationary": None if str(f.get("stationary") or "").startswith("not published") else f.get("stationary"),
            "positions": f"P{f['position_before']} to P{f['position_after_cycle']}" if f.get("position_before") and f.get("position_after_cycle") else None,
            "net_places": f.get("net_places"),
            "timing": f"{n['relation'].replace('_', ' ')} the {n['kind']} (lap {n['laps']})" if n else None,
        })
    out["stops"] = stops
    if any(s["stationary"] is None for s in stops):
        out["notes"]["stops"] = "Stationary time: the timing feed doesn't publish it for this race."
    out["sectors"] = _sectors(sheet)
    return out


def _qualifying(db: OrmSession, session_id: int, driver_id: int, mate_id: int | None, sheet: dict) -> dict[str, Any]:
    out: dict[str, Any] = {"kind": "qualifying", "notes": {}}
    rows = db.scalars(select(HeadlineQualifying).where(HeadlineQualifying.session_id == session_id)).all()
    me = next((r for r in rows if r.driver_id == driver_id), None)
    mate = next((r for r in rows if r.driver_id == mate_id), None)
    prefix = "SQ" if sheet.get("meta", {}).get("session_type") == "SQ" else "Q"
    segs = []
    for k in (1, 2, 3):
        mine = getattr(me, f"q{k}_ms", None) if me else None
        if mine is None:
            continue
        times = sorted((getattr(r, f"q{k}_ms"), r.driver_id) for r in rows if getattr(r, f"q{k}_ms"))
        survivors = sum(1 for r in rows if getattr(r, f"q{k}_ms") and r.eliminated_in != f"Q{k}")
        margin = None
        if k < 3 and 0 < survivors < len(times):
            last_in, first_out = times[survivors - 1][0], times[survivors][0]
            margin = _gap(first_out - mine) if mine <= last_in else _gap(-(mine - last_in))
        theirs = getattr(mate, f"q{k}_ms", None) if mate else None
        segs.append({"segment": f"{prefix}{k}", "best": _t(mine), "cut_margin": margin, "vs_teammate": _gap(mine - theirs) if theirs else None})
    out["segments"] = segs or None
    if not segs:
        out["notes"]["segments"] = "He set no time."
    out["sectors"] = _sectors(sheet)
    out["runs"] = [{"tyre": r.get("compound") if r.get("compound") != "UNRECORDED" else None, "laps": r.get("laps"), "lap_count": r.get("lap_count"), "best": r.get("best_lap")}
                   for r in sheet.get("runs") or []] or None
    return out


def _practice(db: OrmSession, session_id: int, driver_id: int, sheet: dict) -> dict[str, Any]:
    out: dict[str, Any] = {"kind": "practice", "notes": {}}
    laps = db.scalars(select(Lap).where(Lap.session_id == session_id, Lap.driver_id == driver_id)).all()
    stints = db.scalars(select(DetailStintTimeline).where(DetailStintTimeline.session_id == session_id, DetailStintTimeline.driver_id == driver_id)
                        .order_by(DetailStintTimeline.stint_number)).all()
    plan = []
    for s in stints:
        if not (s.lap_start and s.lap_end):
            continue
        run = _clean_laps(laps, s.lap_start, s.lap_end, set())
        plan.append({"tyre": s.compound, "laps": f"{s.lap_start}-{s.lap_end}", "lap_count": s.lap_end - s.lap_start + 1,
                     "avg": _t(mean(lp.lap_time_ms for lp in run)) if len(run) >= 2 else None})
    out["run_plan"] = plan or None
    pace = db.scalars(select(DetailLongRunPace).where(DetailLongRunPace.session_id == session_id)).all()
    long_runs = []
    for compound in sorted({p.compound for p in pace}):
        field = sorted((p for p in pace if p.compound == compound and p.lap_count >= DEBRIEF_LONG_RUN_LAPS and p.avg_lap_time_ms), key=lambda p: p.avg_lap_time_ms)
        mine = next((p for p in field if p.driver_id == driver_id), None)
        if mine is None:
            continue
        ranked = len(field) >= DEBRIEF_MIN_RANKED
        long_runs.append({"tyre": compound, "avg": _t(mine.avg_lap_time_ms), "laps": mine.lap_count,
                          "rank": field.index(mine) + 1 if ranked else None, "of": len(field) if ranked else None})
    out["long_runs"] = long_runs or None
    if long_runs and any(x["rank"] is None for x in long_runs):
        out["notes"]["long_runs"] = f"Ranked only when at least {DEBRIEF_MIN_RANKED} drivers ran {DEBRIEF_LONG_RUN_LAPS} or more laps on that tyre."
    r = sheet.get("result") or {}
    out["single_lap"] = {"rank": r.get("position"), "of": r.get("of"), "best": r.get("best_lap"), "gap": r.get("gap_to_fastest")}
    out["sectors"] = _sectors(sheet)
    return out


def build_debrief(db: OrmSession, session_id: int, driver_id: int, sheet: dict) -> dict[str, Any] | None:
    """The Expert debrief for one driver-session, from its fact sheet. None for a car that didn't start."""
    stype = (sheet.get("meta") or {}).get("session_type")
    if (sheet.get("result") or {}).get("status") == "did not start":
        return None
    mates = teammates(db, db.get(Session, session_id).event_id, driver_id)  # that weekend's teammate (a stand-in's too)
    mate_id = mates[0] if mates else None
    if stype in RACE_LIKE:
        out = _race(db, session_id, driver_id, mate_id, sheet)
    elif stype in QUALI_LIKE:
        out = _qualifying(db, session_id, driver_id, mate_id, sheet)
    elif stype in PRACTICE_LIKE:
        out = _practice(db, session_id, driver_id, sheet)
    else:
        return None
    out["findings"] = _findings(sheet)
    return out
