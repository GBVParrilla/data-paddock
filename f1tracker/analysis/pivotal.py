"""Pivotal moment detection - pure data logic, no LLM.

Sources: detail_position_by_lap (swings), pit_stops (stops that moved a driver),
race_control (SC/VSC/red flags, penalties), laps (fastest lap).
Descriptions are templated from the structured facts only.
"""
from __future__ import annotations

import logging
import re
from collections import defaultdict
from dataclasses import dataclass, field

from sqlalchemy import delete, select
from sqlalchemy.orm import Session as OrmSession

from ..models import (
    RACE_LIKE,
    DetailPositionByLap,
    Driver,
    Lap,
    PitStop,
    PivotalMoment,
    RaceControl,
    Session,
    Stint,
)
from ..util import fmt_ms

log = logging.getLogger(__name__)

MAX_MOMENTS = 8
MIN_SWING = 2


@dataclass
class Moment:
    moment_type: str
    magnitude_score: float
    description: str
    lap_number: int | None = None
    driver_id: int | None = None
    extra: dict = field(default_factory=dict)


def _pos_map(rows: list[DetailPositionByLap]) -> dict[int, dict[int, int]]:
    m: dict[int, dict[int, int]] = defaultdict(dict)
    for r in rows:
        if r.position is not None:
            m[r.driver_id][r.lap_number] = r.position
    return m


def detect_position_swings(pos: dict[int, dict[int, int]], pit_laps: set[tuple[int, int]], names: dict[int, str]) -> list[Moment]:
    out = []
    for driver_id, by_lap in pos.items():
        laps = sorted(by_lap)
        for prev, cur in zip(laps, laps[1:]):
            if cur != prev + 1:
                continue
            delta = by_lap[prev] - by_lap[cur]  # positive = gained places
            if abs(delta) < MIN_SWING:
                continue
            # attribute swings on the driver's own in-lap / out-lap (and the lap after, where the
            # position feed settles) to the pit stop instead
            if any((driver_id, cur - k) in pit_laps for k in (0, 1, 2)):
                continue
            score = abs(delta) * 1.5
            if min(by_lap[prev], by_lap[cur]) <= 3:
                score += 1.5
            elif by_lap[prev] > 10 >= by_lap[cur] or by_lap[cur] > 10 >= by_lap[prev]:
                score += 1.0  # crossed the points boundary
            verb = "gained" if delta > 0 else "lost"
            out.append(
                Moment(
                    "position_swing",
                    round(score, 2),
                    f"{names.get(driver_id, '?')} {verb} {abs(delta)} places on lap {cur} (P{by_lap[prev]} to P{by_lap[cur]}).",
                    lap_number=cur,
                    driver_id=driver_id,
                )
            )
    return out


def detect_pit_moments(
    pits: list[PitStop], pos: dict[int, dict[int, int]], stints: list[Stint], names: dict[int, str]
) -> list[Moment]:
    stint_by_driver: dict[int, list[Stint]] = defaultdict(list)
    for s in stints:
        stint_by_driver[s.driver_id].append(s)
    out = []
    for p in pits:
        by_lap = pos.get(p.driver_id, {})
        before = by_lap.get(p.lap_number - 1)  # position at end of the lap before the in-lap
        after_lap = next((l for l in (p.lap_number + 2, p.lap_number + 3, p.lap_number + 1) if l in by_lap), None)
        after = by_lap.get(after_lap) if after_lap else None
        delta = (before - after) if (before is not None and after is not None) else 0
        stationary_s = (p.duration_ms or 0) / 1000
        slow = stationary_s >= 4.0
        score = 1.0 + abs(delta) * 1.2 + (2.0 if slow else 0.0)
        compounds = [s.compound for s in sorted(stint_by_driver.get(p.driver_id, []), key=lambda s: s.stint_number)]
        old = next((s.compound for s in stint_by_driver.get(p.driver_id, []) if s.lap_end == p.lap_number), None)
        new = next((s.compound for s in stint_by_driver.get(p.driver_id, []) if s.lap_start == p.lap_number + 1), None)
        tyres = f"{old or '?'} to {new or '?'}" if (old or new) else "compound unknown"
        pos_txt = f"P{before} before the stop, P{after} on lap {after_lap}" if (before and after) else "position change unknown"
        stop_txt = f"{stationary_s:.1f}s stationary" if p.duration_ms else "stop time unknown"
        desc = f"{names.get(p.driver_id, '?')} pitted at the end of lap {p.lap_number} ({tyres}, {stop_txt}): {pos_txt}."
        if slow:
            desc += " Slow stop."
        out.append(Moment("pit_stop", round(score, 2), desc, lap_number=p.lap_number, driver_id=p.driver_id, extra={"compounds": compounds}))
    return out


_PENALTY_RE = re.compile(r"PENALTY", re.I)


def detect_race_control_moments(msgs: list[RaceControl], pits: list[PitStop], names: dict[int, str]) -> list[Moment]:
    out: list[Moment] = []
    pit_laps = [p.lap_number for p in pits]
    open_period: tuple[str, int, int] | None = None  # (kind, start_lap, moment_index)

    def close_period(end_lap: int | None) -> None:
        nonlocal open_period
        if open_period is None:
            return
        kind, start_lap, idx = open_period
        m = out[idx]
        if end_lap is not None:
            # race-control laps are the leader's; cars behind pit on their own (possibly previous) lap
            stops = sum(1 for l in pit_laps if start_lap - 1 <= l <= end_lap)
            m.description = m.description.rstrip(".") + f"; ended lap {end_lap}. {stops} pit stop(s) were made under it."
            m.magnitude_score = round(m.magnitude_score + 0.4 * stops, 2)
        open_period = None

    for m in sorted(msgs, key=lambda r: r.timestamp):
        text = (m.message or "").upper()
        lap = m.lap_number
        if m.category == "SafetyCar" or "SAFETY CAR" in text or text.startswith("VSC"):
            if "DEPLOYED" in text:
                kind = "VSC" if "VIRTUAL" in text or text.startswith("VSC") else "SC"
                base = 4.5 if kind == "VSC" else 6.5
                label = "Virtual Safety Car" if kind == "VSC" else "Safety Car"
                close_period(lap)
                out.append(Moment("safety_car", base, f"{label} deployed on lap {lap}", lap_number=lap))
                open_period = (kind, lap or 0, len(out) - 1)
            elif "ENDING" in text or "IN THIS LAP" in text:
                close_period(lap)
        elif m.flag == "RED":
            when = f"on lap {lap}" if lap else f"at {m.timestamp.strftime('%H:%M')} UTC"
            out.append(Moment("safety_car", 7.0, f"Red flag {when} - session stopped.", lap_number=lap))
        elif _PENALTY_RE.search(text) and "UNDER INVESTIGATION" not in text and "PENALTY SERVED" not in text and "NO FURTHER" not in text:
            score = 6.0 if ("STOP-AND-GO" in text or "STOP/GO" in text or "DRIVE THROUGH" in text) else 4.5
            clean = re.sub(r"^FIA STEWARDS:\s*", "", m.message).strip()
            who = names.get(m.driver_id, None) if m.driver_id else None
            desc = f"Lap {lap}: {clean}" if lap else clean
            if who:
                desc = f"{who} - {desc}"
            out.append(Moment("penalty", score, desc + ".", lap_number=lap, driver_id=m.driver_id))
    close_period(None)
    return out


def detect_fastest_lap(laps: list[Lap], names: dict[int, str]) -> list[Moment]:
    clean = [lp for lp in laps if lp.lap_time_ms and not lp.is_pit_lap]
    if not clean:
        return []
    best = min(clean, key=lambda lp: lp.lap_time_ms)
    return [
        Moment(
            "fastest_lap",
            2.0,
            f"Fastest lap of the session: {names.get(best.driver_id, '?')}, {fmt_ms(best.lap_time_ms)} on lap {best.lap_number}"
            + (f" ({best.compound.lower()} tyres, {best.tyre_life} laps old)." if best.compound else "."),
            lap_number=best.lap_number,
            driver_id=best.driver_id,
        )
    ]


def compute_pivotal_moments(
    session_type: str,
    pos_rows: list[DetailPositionByLap],
    pits: list[PitStop],
    stints: list[Stint],
    msgs: list[RaceControl],
    laps: list[Lap],
    names: dict[int, str],
) -> list[Moment]:
    moments: list[Moment] = []
    if session_type in RACE_LIKE:
        pos = _pos_map(pos_rows)
        pit_laps = {(p.driver_id, p.lap_number) for p in pits}
        moments += detect_position_swings(pos, pit_laps, names)
        moments += detect_pit_moments(pits, pos, stints, names)
    moments += detect_race_control_moments(msgs, pits, names)
    moments += detect_fastest_lap(laps, names)
    # de-duplicate identical moments (e.g. repeated race-control lines)
    seen: set[tuple] = set()
    unique = []
    for m in moments:
        k = (m.moment_type, m.lap_number, m.driver_id, m.description)
        if k not in seen:
            seen.add(k)
            unique.append(m)
    unique.sort(key=lambda m: (-m.magnitude_score, m.lap_number or 0))
    return unique[:MAX_MOMENTS]


def detect_pivotal_moments(db: OrmSession, session_id: int) -> int:
    session = db.get(Session, session_id)
    names = {d.id: d.full_name for d in db.scalars(select(Driver)).all()}
    moments = compute_pivotal_moments(
        session.session_type,
        db.scalars(select(DetailPositionByLap).where(DetailPositionByLap.session_id == session_id)).all(),
        db.scalars(select(PitStop).where(PitStop.session_id == session_id)).all(),
        db.scalars(select(Stint).where(Stint.session_id == session_id)).all(),
        db.scalars(select(RaceControl).where(RaceControl.session_id == session_id)).all(),
        db.scalars(select(Lap).where(Lap.session_id == session_id)).all(),
        names,
    )
    db.execute(delete(PivotalMoment).where(PivotalMoment.session_id == session_id))
    for m in moments:
        db.add(PivotalMoment(session_id=session_id, lap_number=m.lap_number, driver_id=m.driver_id, moment_type=m.moment_type, magnitude_score=m.magnitude_score, description=m.description))
    return len(moments)
