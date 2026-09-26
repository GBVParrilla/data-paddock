"""Results/classification for one session.

Race, Sprint and Qualifying come from Jolpica. Sprint Qualifying and practice
classification come from OpenF1's session_result (Jolpica has no endpoint).
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session as OrmSession

from ..clients import jolpica, openf1
from ..db import upsert
from ..models import Event, Result, Season, Session
from .drivers import resolve_driver_by_number, upsert_driver_from_jolpica
from .state import mark

log = logging.getLogger(__name__)


def _int(v: Any) -> int | None:
    try:
        return int(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _rows_from_jolpica_race(db: OrmSession, session: Session, results: list[dict[str, Any]]) -> list[dict]:
    rows = []
    winner_ms = None
    for r in results:
        if r.get("position") == "1" and r.get("Time", {}).get("millis"):
            winner_ms = int(r["Time"]["millis"])
    for r in results:
        drv = upsert_driver_from_jolpica(db, r["Driver"], team=r.get("Constructor", {}).get("name"), number=_int(r.get("number")))
        millis = _int(r.get("Time", {}).get("millis"))
        gap = (millis - winner_ms) if (millis is not None and winner_ms is not None) else None
        grid = _int(r.get("grid"))
        rows.append(
            dict(
                session_id=session.id,
                driver_id=drv.id,
                position=_int(r.get("position")),
                points=float(r.get("points") or 0),
                status=r.get("status"),
                grid_position=grid if grid else None,  # grid "0" = pit-lane start
                gap_to_leader_ms=gap,
                laps_completed=_int(r.get("laps")),
                q1_ms=None,
                q2_ms=None,
                q3_ms=None,
            )
        )
    return rows


def _rows_from_jolpica_quali(db: OrmSession, session: Session, results: list[dict[str, Any]]) -> list[dict]:
    rows = []
    for r in results:
        drv = upsert_driver_from_jolpica(db, r["Driver"], team=r.get("Constructor", {}).get("name"), number=_int(r.get("number")))
        q1, q2, q3 = (jolpica.parse_lap_time_ms(r.get(k)) for k in ("Q1", "Q2", "Q3"))
        reached = "Q3" if q3 else "Q2" if q2 else "Q1"
        rows.append(
            dict(
                session_id=session.id,
                driver_id=drv.id,
                position=_int(r.get("position")),
                points=0.0,
                status=reached,
                grid_position=None,
                gap_to_leader_ms=None,
                laps_completed=None,
                q1_ms=q1,
                q2_ms=q2,
                q3_ms=q3,
            )
        )
    return rows


def _rows_from_openf1(db: OrmSession, session: Session, year: int, results: list[dict[str, Any]]) -> list[dict]:
    rows = []
    for r in results:
        drv = resolve_driver_by_number(db, year, int(r["driver_number"]))
        duration = r.get("duration")
        gap = r.get("gap_to_leader")
        q1 = q2 = q3 = None
        gap_ms = None
        if isinstance(duration, list):  # qualifying-style: [q1, q2, q3]
            q1, q2, q3 = (openf1.seconds_to_ms(x) for x in (duration + [None, None, None])[:3])
            status = "Q3" if q3 else "Q2" if q2 else "Q1"
            if isinstance(gap, list):
                last = [g for g in gap if g is not None]
                gap_ms = openf1.seconds_to_ms(last[-1]) if last else None
        else:
            gap_ms = openf1.seconds_to_ms(gap) if not isinstance(gap, str) else None
            status = "DNS" if r.get("dns") else "DSQ" if r.get("dsq") else "Retired" if r.get("dnf") else "Finished"
        rows.append(
            dict(
                session_id=session.id,
                driver_id=drv.id,
                position=_int(r.get("position")),
                points=float(r.get("points") or 0),
                status=status,
                grid_position=None,
                gap_to_leader_ms=gap_ms,
                laps_completed=_int(r.get("number_of_laps")),
                q1_ms=q1,
                q2_ms=q2,
                q3_ms=q3,
            )
        )
    return rows


def ingest_session_results(db: OrmSession, session_id: int) -> bool:
    """Returns True if results were found and stored."""
    session = db.get(Session, session_id)
    if session is None:
        raise ValueError(f"session {session_id} not found")
    event = db.get(Event, session.event_id)
    season = db.get(Season, event.season_id)
    year, rnd, stype = season.year, event.round, session.session_type

    if stype == "R":
        rows = _rows_from_jolpica_race(db, session, jolpica.fetch_race_results(year, rnd))
    elif stype == "S":
        rows = _rows_from_jolpica_race(db, session, jolpica.fetch_sprint_results(year, rnd))
    elif stype == "Q":
        rows = _rows_from_jolpica_quali(db, session, jolpica.fetch_qualifying_results(year, rnd))
    else:  # SQ, FP1-3
        if not session.openf1_session_key:
            log.warning("session %d (%s) has no OpenF1 key; cannot fetch results", session_id, stype)
            rows = []
        else:
            rows = _rows_from_openf1(db, session, year, openf1.fetch_session_result(session.openf1_session_key))

    if not rows:
        log.info("session %d (%s r%d %s): no results available yet", session_id, year, rnd, stype)
        mark(db, session_id, "results", done=False, error="no results available")
        return False

    upsert(db, Result, rows, ["session_id", "driver_id"])
    mark(db, session_id, "results", done=True)
    if session.status != "completed":
        session.status = "completed"
    log.info("session %d (%s r%d %s): %d results stored", session_id, year, rnd, stype, len(rows))
    return True
