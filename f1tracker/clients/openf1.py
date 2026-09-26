"""OpenF1 client. Pure fetch/parse; reusable by batch scripts and a future live poller.

Verified shapes (2026):
  /sessions?year=   -> [{session_key, session_type, session_name, date_start, date_end,
                         meeting_key, circuit_short_name, country_name, location, ...}]
  /meetings?year=   -> [{meeting_key, meeting_name, date_start, date_end, country_name, ...}]
  /drivers?session_key= -> [{driver_number, full_name, name_acronym, team_name, first_name, last_name}]
  /laps?session_key=    -> [{driver_number, lap_number, date_start, lap_duration (s|null),
                             duration_sector_1/2/3 (s|null), i1_speed, i2_speed, st_speed,
                             is_pit_out_lap, segments_sector_*}]
  /stints?session_key=  -> [{driver_number, stint_number, compound|null, lap_start, lap_end, tyre_age_at_start}]
  /pit?session_key=     -> [{driver_number, lap_number, pit_duration (lane, s), stop_duration (s), date}]
  /weather?session_key= -> [{date, air_temperature, track_temperature, humidity, wind_speed, rainfall}]
  /race_control?session_key= -> [{date, lap_number, driver_number|null, category, flag, scope, message}]
  /position?session_key= -> [{date, driver_number, position}]  (timestamped changes)
  /session_result?session_key= -> [{position, driver_number, number_of_laps, points?, dnf, dns, dsq,
                             duration (s | [q1,q2,q3]), gap_to_leader (s | [..])}]
Empty results return HTTP 404 {"detail": "No results found."}.
"""
from __future__ import annotations

from typing import Any

from ..config import OPENF1_BASE_URL, OPENF1_MIN_INTERVAL_S
from .http import RateLimitedClient

_client = RateLimitedClient(OPENF1_BASE_URL, OPENF1_MIN_INTERVAL_S, name="openf1")

SESSION_NAME_TO_TYPE = {
    "Practice 1": "FP1",
    "Practice 2": "FP2",
    "Practice 3": "FP3",
    "Sprint Qualifying": "SQ",
    "Sprint Shootout": "SQ",
    "Sprint": "S",
    "Qualifying": "Q",
    "Race": "R",
}


def _get(path: str, **params: Any) -> list[dict[str, Any]]:
    return _client.get_json(path, params=params or None, empty_on_404=True)


def fetch_meetings(year: int) -> list[dict[str, Any]]:
    return _get("meetings", year=year)


def fetch_sessions(year: int) -> list[dict[str, Any]]:
    return _get("sessions", year=year)


def fetch_session_drivers(session_key: int) -> list[dict[str, Any]]:
    return _get("drivers", session_key=session_key)


def fetch_laps(session_key: int) -> list[dict[str, Any]]:
    return _get("laps", session_key=session_key)


def fetch_stints(session_key: int) -> list[dict[str, Any]]:
    return _get("stints", session_key=session_key)


def fetch_pit_stops(session_key: int) -> list[dict[str, Any]]:
    return _get("pit", session_key=session_key)


def fetch_weather(session_key: int) -> list[dict[str, Any]]:
    return _get("weather", session_key=session_key)


def fetch_race_control(session_key: int) -> list[dict[str, Any]]:
    return _get("race_control", session_key=session_key)


def fetch_positions(session_key: int) -> list[dict[str, Any]]:
    return _get("position", session_key=session_key)


def fetch_session_result(session_key: int) -> list[dict[str, Any]]:
    return _get("session_result", session_key=session_key)


def fetch_car_data(session_key: int, driver_number: int, date_from: str, date_to: str) -> list[dict[str, Any]]:
    """Car telemetry (~3.7 Hz) for one driver in a time window: speed, throttle, brake, drs, n_gear, rpm.

    drs values observed: 0/1 = off, 8 = detected/eligible (not open), 10/12/14 = open ("boost").
    """
    return _client.get_json(
        "car_data",
        params={"session_key": session_key, "driver_number": driver_number, "date>": date_from, "date<": date_to},
        empty_on_404=True,
    )


# OpenF1's location x/y/z are in decimeters (0.1 m units), not meters - verified against several
# circuits' well-known official lap lengths (consistently ~10x too large if treated as meters).
LOCATION_UNITS_PER_METER = 10.0


def location_to_meters(points: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Copy of `points` with x/y (and z, if present) rescaled from decimeters to meters."""
    out = []
    for p in points:
        q = dict(p)
        for axis in ("x", "y", "z"):
            if q.get(axis) is not None:
                q[axis] = q[axis] / LOCATION_UNITS_PER_METER
        out.append(q)
    return out


def seconds_to_ms(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(round(float(value) * 1000))
    except (TypeError, ValueError):
        return None


def fetch_location(session_key: int, driver_number: int, date_from: str, date_to: str) -> list[dict[str, Any]]:
    """Car x/y/z positions (~3.7 Hz) for one driver in a time window (ISO timestamps)."""
    return _client.get_json(
        "location",
        # OpenF1 parses the operator as part of the key: "date>" + "=value". A "date>=" key 500s.
        params={"session_key": session_key, "driver_number": driver_number, "date>": date_from, "date<": date_to},
        empty_on_404=True,
    )
