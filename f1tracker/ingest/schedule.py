"""Season calendar: Jolpica schedule + OpenF1 meeting/session keys."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session as OrmSession

from ..clients import jolpica, openf1
from ..models import Event, Season, Session
from ..util import parse_iso_utc, utcnow

log = logging.getLogger(__name__)

# Jolpica schedule key -> our session type
_JOLPICA_SESSION_KEYS = {
    "FirstPractice": "FP1",
    "SecondPractice": "FP2",
    "ThirdPractice": "FP3",
    "SprintQualifying": "SQ",
    "Sprint": "S",
    "Qualifying": "Q",
}
# Nominal durations used only when OpenF1 doesn't supply date_end.
_NOMINAL_MINUTES = {"FP1": 60, "FP2": 60, "FP3": 60, "SQ": 44, "S": 60, "Q": 60, "R": 120}


def _dt(date: str | None, time: str | None) -> datetime | None:
    if not date:
        return None
    return parse_iso_utc(f"{date}T{time or '00:00:00Z'}")


def _status_for(end_time: datetime | None, now: datetime) -> str:
    if end_time is None:
        return "upcoming"
    return "completed" if end_time < now else "upcoming"


def ingest_schedule(db: OrmSession, year: int) -> Season:
    now = utcnow()
    season = db.scalar(select(Season).where(Season.year == year))
    if season is None:
        season = Season(year=year)
        db.add(season)
        db.flush()

    races = jolpica.fetch_schedule(year)
    log.info("Jolpica: %d rounds for %d", len(races), year)

    # OpenF1 meeting/session keys, keyed by race date
    meetings = openf1.fetch_meetings(year)
    of1_sessions = openf1.fetch_sessions(year)
    sessions_by_meeting: dict[int, list[dict[str, Any]]] = {}
    for s in of1_sessions:
        sessions_by_meeting.setdefault(s["meeting_key"], []).append(s)

    def find_meeting(race_date: datetime) -> dict[str, Any] | None:
        for m in meetings:
            start = parse_iso_utc(m["date_start"])
            end = parse_iso_utc(m["date_end"])
            if start and end and (start.date() - timedelta(days=1)) <= race_date.date() <= (end.date() + timedelta(days=1)):
                if "TESTING" not in (m.get("meeting_official_name") or "").upper():
                    return m
        return None

    for race in races:
        rnd = int(race["round"])
        race_dt = _dt(race.get("date"), race.get("time"))
        has_sprint = "Sprint" in race
        circuit = race.get("Circuit", {})
        event = db.scalar(select(Event).where(Event.season_id == season.id, Event.round == rnd))
        if event is None:
            event = Event(season_id=season.id, round=rnd, name=race["raceName"])
            db.add(event)
        event.name = race["raceName"]
        event.circuit_name = circuit.get("circuitName")
        event.country = circuit.get("Location", {}).get("country")
        try:
            event.lat = float(circuit["Location"]["lat"])
            event.lon = float(circuit["Location"]["long"])
        except (KeyError, TypeError, ValueError):
            log.warning("Round %d (%s): no usable circuit lat/long from Jolpica", rnd, race["raceName"])
        event.event_date = race_dt
        event.has_sprint = has_sprint
        meeting = find_meeting(race_dt) if race_dt else None
        if meeting:
            event.openf1_meeting_key = meeting["meeting_key"]
        else:
            log.warning("Round %d (%s): no OpenF1 meeting found", rnd, race["raceName"])
        db.flush()

        # Sessions from Jolpica
        wanted: dict[str, datetime | None] = {}
        for key, stype in _JOLPICA_SESSION_KEYS.items():
            if key in race:
                wanted[stype] = _dt(race[key].get("date"), race[key].get("time"))
        wanted["R"] = race_dt

        of1_by_type: dict[str, dict[str, Any]] = {}
        if meeting:
            for s in sessions_by_meeting.get(meeting["meeting_key"], []):
                stype = openf1.SESSION_NAME_TO_TYPE.get(s["session_name"])
                if stype:
                    of1_by_type[stype] = s

        for stype, start in wanted.items():
            sess = db.scalar(select(Session).where(Session.event_id == event.id, Session.session_type == stype))
            if sess is None:
                sess = Session(event_id=event.id, session_type=stype)
                db.add(sess)
            of1 = of1_by_type.get(stype)
            if of1:
                sess.openf1_session_key = of1["session_key"]
                sess.start_time = parse_iso_utc(of1["date_start"]) or start
                sess.end_time = parse_iso_utc(of1["date_end"])
            else:
                sess.start_time = start
                sess.end_time = (start + timedelta(minutes=_NOMINAL_MINUTES[stype])) if start else None
            # Don't downgrade a session already marked live/completed by another path.
            if sess.status != "completed":
                sess.status = _status_for(sess.end_time, now)
        db.flush()
        log.info("Round %2d %-32s sprint=%s meeting=%s sessions=%s", rnd, race["raceName"], has_sprint, event.openf1_meeting_key, sorted(wanted))
    return season
