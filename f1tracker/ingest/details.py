"""Laps (with sectors + speed), stints, pit stops, weather, race control for one session.

Everything here is fetch -> pure parse -> upsert, so a future live poller can call
the same functions repeatedly as more laps arrive.
"""
from __future__ import annotations

import bisect
import logging
import re
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import delete
from sqlalchemy.orm import Session as OrmSession

from ..clients import openf1
from ..db import upsert
from ..models import RACE_LIKE, Event, Lap, PitStop, RaceControl, Season, Session, Stint, Weather
from ..util import parse_iso_utc
from .drivers import resolve_driver_by_number
from .state import mark

log = logging.getLogger(__name__)

_CAR_RE = re.compile(r"\bCARS?\s+(\d+)")


# ---- pure parsing helpers ---------------------------------------------------
def build_stint_lookup(stints: list[dict[str, Any]]) -> dict[int, list[dict[str, Any]]]:
    by_driver: dict[int, list[dict[str, Any]]] = {}
    for s in stints:
        by_driver.setdefault(int(s["driver_number"]), []).append(s)
    for v in by_driver.values():
        v.sort(key=lambda s: (s.get("lap_start") or 0))
    return by_driver


def compound_for_lap(stints_for_driver: list[dict[str, Any]], lap_number: int) -> tuple[str | None, int | None]:
    for s in stints_for_driver:
        start, end = s.get("lap_start"), s.get("lap_end")
        if start is not None and end is not None and start <= lap_number <= end:
            age0 = s.get("tyre_age_at_start") or 0
            return s.get("compound"), age0 + (lap_number - start) + 1
    return None, None


def build_position_lookup(positions: list[dict[str, Any]]) -> dict[int, tuple[list[datetime], list[int]]]:
    """driver_number -> (sorted timestamps, positions)."""
    tmp: dict[int, list[tuple[datetime, int]]] = {}
    for p in positions:
        ts = parse_iso_utc(p["date"])
        if ts is None or p.get("position") is None:
            continue
        tmp.setdefault(int(p["driver_number"]), []).append((ts, int(p["position"])))
    out = {}
    for num, items in tmp.items():
        items.sort()
        out[num] = ([t for t, _ in items], [pos for _, pos in items])
    return out


def position_at(lookup: dict[int, tuple[list[datetime], list[int]]], driver_number: int, at: datetime) -> int | None:
    entry = lookup.get(driver_number)
    if not entry:
        return None
    times, positions = entry
    i = bisect.bisect_right(times, at) - 1
    return positions[i] if i >= 0 else None


def parse_laps(
    laps: list[dict[str, Any]],
    stints: list[dict[str, Any]],
    pits: list[dict[str, Any]],
    positions: list[dict[str, Any]],
    *,
    race_like: bool,
) -> list[dict[str, Any]]:
    """OpenF1 laps -> row dicts keyed by driver_number (driver_id filled in by caller)."""
    stint_lookup = build_stint_lookup(stints)
    pos_lookup = build_position_lookup(positions) if race_like else {}
    # OpenF1 reports the pit stop on the OUT-lap; the in-lap (where time is lost) is lap_number - 1.
    pit_in_laps = {(int(p["driver_number"]), int(p["lap_number"]) - 1) for p in pits if p.get("lap_number") is not None}

    # next-lap start per driver, to know when each lap ended
    by_driver: dict[int, list[dict[str, Any]]] = {}
    for lp in laps:
        by_driver.setdefault(int(lp["driver_number"]), []).append(lp)
    rows = []
    for num, dl in by_driver.items():
        dl.sort(key=lambda x: x["lap_number"])
        for idx, lp in enumerate(dl):
            lap_no = int(lp["lap_number"])
            start = parse_iso_utc(lp.get("date_start"))
            speeds = [v for v in (lp.get("st_speed"), lp.get("i1_speed"), lp.get("i2_speed")) if v is not None]
            compound, tyre_life = compound_for_lap(stint_lookup.get(num, []), lap_no)
            position = None
            if race_like and start is not None:
                if idx + 1 < len(dl) and dl[idx + 1].get("date_start"):
                    end = parse_iso_utc(dl[idx + 1]["date_start"]) - timedelta(milliseconds=200)
                elif lp.get("lap_duration"):
                    end = start + timedelta(seconds=float(lp["lap_duration"]))
                else:
                    end = None
                if end is not None:
                    position = position_at(pos_lookup, num, end)
            rows.append(
                dict(
                    driver_number=num,
                    lap_number=lap_no,
                    lap_time_ms=openf1.seconds_to_ms(lp.get("lap_duration")),
                    sector_1_ms=openf1.seconds_to_ms(lp.get("duration_sector_1")),
                    sector_2_ms=openf1.seconds_to_ms(lp.get("duration_sector_2")),
                    sector_3_ms=openf1.seconds_to_ms(lp.get("duration_sector_3")),
                    top_speed_kph=max(speeds) if speeds else None,
                    compound=compound,
                    tyre_life=tyre_life,
                    is_pit_lap=bool(lp.get("is_pit_out_lap")) or (num, lap_no) in pit_in_laps,
                    position=position,
                    lap_start_time=start,
                )
            )
    return rows


def parse_race_control(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for m in messages:
        ts = parse_iso_utc(m.get("date"))
        if ts is None or not m.get("message"):
            continue
        num = m.get("driver_number")
        if num is None:
            found = _CAR_RE.search(m["message"] or "")
            num = int(found.group(1)) if found else None
        rows.append(
            dict(
                driver_number=int(num) if num is not None else None,
                timestamp=ts,
                lap_number=m.get("lap_number"),
                category=m.get("category"),
                message=m["message"],
                flag=m.get("flag"),
                scope=m.get("scope"),
            )
        )
    return rows


# ---- orchestration for one session ----------------------------------------
def ingest_session_details(db: OrmSession, session_id: int) -> bool:
    session = db.get(Session, session_id)
    if session is None:
        raise ValueError(f"session {session_id} not found")
    event = db.get(Event, session.event_id)
    year = db.get(Season, event.season_id).year
    key = session.openf1_session_key
    if not key:
        log.warning("session %d has no OpenF1 session key", session_id)
        mark(db, session_id, "details", done=False, error="no openf1 session key")
        return False

    race_like = session.session_type in RACE_LIKE
    of1_drivers = {int(d["driver_number"]): d for d in openf1.fetch_session_drivers(key)}
    laps = openf1.fetch_laps(key)
    if not laps:
        log.info("session %d (%s): no laps on OpenF1 yet", session_id, session.session_type)
        mark(db, session_id, "details", done=False, error="no laps available")
        return False
    stints = openf1.fetch_stints(key)
    pits = openf1.fetch_pit_stops(key)
    positions = openf1.fetch_positions(key) if race_like else []
    weather = openf1.fetch_weather(key)
    race_control = openf1.fetch_race_control(key)

    def driver_id_for(num: int) -> int:
        return resolve_driver_by_number(db, year, num, of1_drivers.get(num)).id

    numbers = {int(lp["driver_number"]) for lp in laps} | set(of1_drivers)
    driver_ids = {num: driver_id_for(num) for num in numbers}

    lap_rows = []
    for r in parse_laps(laps, stints, pits, positions, race_like=race_like):
        r["driver_id"] = driver_ids[r.pop("driver_number")]
        r["session_id"] = session_id
        lap_rows.append(r)
    upsert(db, Lap, lap_rows, ["session_id", "driver_id", "lap_number"])

    stint_rows = [
        dict(
            session_id=session_id,
            driver_id=driver_ids.get(int(s["driver_number"])) or driver_id_for(int(s["driver_number"])),
            stint_number=int(s["stint_number"]),
            compound=s.get("compound"),
            lap_start=s.get("lap_start"),
            lap_end=s.get("lap_end"),
            tyre_life_start=s.get("tyre_age_at_start"),
        )
        for s in stints
    ]
    upsert(db, Stint, stint_rows, ["session_id", "driver_id", "stint_number"])

    pit_rows = [
        dict(
            session_id=session_id,
            driver_id=driver_ids.get(int(p["driver_number"])) or driver_id_for(int(p["driver_number"])),
            # stored as the IN-lap ("pitted at the end of lap N"); OpenF1 gives the out-lap
            lap_number=max(1, int(p["lap_number"]) - 1),
            duration_ms=openf1.seconds_to_ms(p.get("stop_duration")),
            lane_duration_ms=openf1.seconds_to_ms(p.get("pit_duration") or p.get("lane_duration")),
        )
        for p in pits
        if p.get("lap_number") is not None
    ]
    # dedupe on the natural key in case two OpenF1 records collapse onto one in-lap
    pit_rows = list({(r["driver_id"], r["lap_number"]): r for r in pit_rows}.values())
    # pit stops are few and their natural key can shift between fetches: replace the set wholesale
    db.execute(delete(PitStop).where(PitStop.session_id == session_id))
    upsert(db, PitStop, pit_rows, ["session_id", "driver_id", "lap_number"])

    weather_rows = []
    for w in weather:
        ts = parse_iso_utc(w.get("date"))
        if ts is None:
            continue
        weather_rows.append(
            dict(
                session_id=session_id,
                timestamp=ts,
                air_temp=w.get("air_temperature"),
                track_temp=w.get("track_temperature"),
                humidity=w.get("humidity"),
                wind_speed=w.get("wind_speed"),
                rainfall=w.get("rainfall"),
            )
        )
    upsert(db, Weather, weather_rows, ["session_id", "timestamp"])

    rc_rows = []
    seen = set()
    for r in parse_race_control(race_control):
        num = r.pop("driver_number")
        r["driver_id"] = (driver_ids.get(num) if num is not None else None)
        r["session_id"] = session_id
        k = (r["timestamp"], r["message"])
        if k in seen:
            continue
        seen.add(k)
        rc_rows.append(r)
    upsert(db, RaceControl, rc_rows, ["session_id", "timestamp", "message"])

    mark(db, session_id, "details", done=True)
    log.info(
        "session %d (%s): %d laps, %d stints, %d pits, %d weather, %d race-control",
        session_id, session.session_type, len(lap_rows), len(stint_rows), len(pit_rows), len(weather_rows), len(rc_rows),
    )
    return True
