"""Jolpica-F1 (Ergast-compatible) client. Pure fetch/parse; no DB access.

Response shapes were verified against the live API (2026 season):
  /{year}.json                 -> MRData.RaceTable.Races[] with Circuit, date/time,
                                  FirstPractice/SecondPractice/ThirdPractice/Qualifying,
                                  Sprint + SprintQualifying on sprint weekends
  /{year}/{round}/results.json -> Races[0].Results[] {number, position, positionText,
                                  points, Driver{driverId,permanentNumber,code,...},
                                  Constructor{constructorId,name}, grid, laps, status,
                                  Time{millis}?, FastestLap{rank,lap,Time{time}}?}
  /{year}/{round}/sprint.json  -> Races[0].SprintResults[] (same shape)
  /{year}/{round}/qualifying.json -> Races[0].QualifyingResults[] {number, position,
                                  Driver, Constructor, Q1?, Q2?, Q3?}
  /{year}/drivers.json         -> DriverTable.Drivers[]
Jolpica has no sprint-qualifying endpoint; that comes from OpenF1.
"""
from __future__ import annotations

import re
from typing import Any

from ..config import JOLPICA_BASE_URL, JOLPICA_MIN_INTERVAL_S
from .http import RateLimitedClient

_client = RateLimitedClient(JOLPICA_BASE_URL, JOLPICA_MIN_INTERVAL_S, name="jolpica")

_TIME_RE = re.compile(r"^(?:(\d+):)?(\d+)\.(\d{1,3})$")


def parse_lap_time_ms(text: str | None) -> int | None:
    """'1:18.518' -> 78518 ; '78.518' -> 78518 ; None/'' -> None."""
    if not text:
        return None
    m = _TIME_RE.match(text.strip())
    if not m:
        return None
    minutes = int(m.group(1) or 0)
    seconds = int(m.group(2))
    frac = m.group(3).ljust(3, "0")
    return minutes * 60_000 + seconds * 1000 + int(frac)


def fetch_schedule(year: int) -> list[dict[str, Any]]:
    data = _client.get_json(f"{year}.json", params={"limit": 100})
    return data["MRData"]["RaceTable"]["Races"]


def fetch_drivers(year: int) -> list[dict[str, Any]]:
    data = _client.get_json(f"{year}/drivers.json", params={"limit": 100})
    return data["MRData"]["DriverTable"]["Drivers"]


def _race_block(year: int, rnd: int, endpoint: str) -> dict[str, Any] | None:
    data = _client.get_json(f"{year}/{rnd}/{endpoint}.json", params={"limit": 100})
    races = data["MRData"]["RaceTable"]["Races"]
    return races[0] if races else None


def fetch_race_results(year: int, rnd: int) -> list[dict[str, Any]]:
    block = _race_block(year, rnd, "results")
    return block["Results"] if block else []


def fetch_sprint_results(year: int, rnd: int) -> list[dict[str, Any]]:
    block = _race_block(year, rnd, "sprint")
    return block["SprintResults"] if block else []


def fetch_qualifying_results(year: int, rnd: int) -> list[dict[str, Any]]:
    block = _race_block(year, rnd, "qualifying")
    return block["QualifyingResults"] if block else []
