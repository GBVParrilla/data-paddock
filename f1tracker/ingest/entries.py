"""The entry list for one event: which team each driver drove for, that weekend.

Seats change mid-season (a substitute steps up, a driver is promoted), so a driver's team is a
property of the event, never of the driver. Sources:
  - Jolpica race / sprint / qualifying results: the official constructor per driver per round.
  - OpenF1 /drivers for each session: car numbers, the team's display name ("Racing Bulls"),
    and practice-only entries (a rookie running a race driver's car in FP1).
Jolpica wins for the team when both exist; OpenF1 supplies the display name.
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session as OrmSession

from ..clients import jolpica, openf1
from ..models import Driver, Entry, Event, Season, Session
from .drivers import resolve_driver_by_number, upsert_driver_from_jolpica

log = logging.getLogger(__name__)

# Jolpica constructorId -> the display name OpenF1 and the site use. Learned from data when both
# sources are present; this table covers events where OpenF1 has no driver list.
DISPLAY_NAMES = {
    "red_bull": "Red Bull Racing",
    "rb": "Racing Bulls",
    "mercedes": "Mercedes",
    "ferrari": "Ferrari",
    "mclaren": "McLaren",
    "aston_martin": "Aston Martin",
    "alpine": "Alpine",
    "williams": "Williams",
    "haas": "Haas F1 Team",
    "audi": "Audi",
    "sauber": "Audi",
    "cadillac": "Cadillac",
}


def _norm(name: str | None) -> str:
    return "".join(ch for ch in (name or "").lower() if ch.isalnum())


def _jolpica_rows(year: int, rnd: int) -> list[dict[str, Any]]:
    """The weekend's official line-up: race results, else qualifying, else sprint (whichever exists)."""
    for fetch in (jolpica.fetch_race_results, jolpica.fetch_qualifying_results, jolpica.fetch_sprint_results):
        rows = fetch(year, rnd)
        if rows:
            return rows
    return []


def build_entries(
    jolpica_rows: list[dict[str, Any]],
    openf1_by_session: dict[str, list[dict[str, Any]]],
    *,
    driver_for_jolpica,
    driver_for_number,
) -> list[dict[str, Any]]:
    """Pure merge of the two sources into entry rows (driver resolution is injected)."""
    entries: dict[int, dict[str, Any]] = {}
    display_for: dict[str, str] = {}
    by_number_team: dict[int, str] = {}
    # a car number's team: from the race-weekend sessions when available (a number is unique per weekend)
    for stype in sorted(openf1_by_session, key=lambda t: t in ("FP1", "FP2", "FP3")):
        for d in openf1_by_session[stype]:
            if d.get("team_name"):
                by_number_team.setdefault(int(d["driver_number"]), d["team_name"])

    for r in jolpica_rows:
        drv = driver_for_jolpica(r)
        cid = r.get("Constructor", {}).get("constructorId")
        number = int(r["number"]) if str(r.get("number", "")).isdigit() else drv.number
        team = by_number_team.get(number) if number is not None else None
        if team and cid:
            display_for[cid] = team
        entries[drv.id] = dict(driver_id=drv.id, constructor_id=cid, car_number=number, team=team, practice_only=False)
    for e in entries.values():
        if not e["team"]:
            e["team"] = display_for.get(e["constructor_id"]) or DISPLAY_NAMES.get(e["constructor_id"] or "") or e["constructor_id"] or "Unknown"

    # Drivers only OpenF1 knows: practice-only runners, or everyone while Jolpica has no results yet.
    # Without Jolpica, a driver missing from the latest session's list only ran in practice.
    order = ["FP1", "FP2", "FP3", "SQ", "S", "Q", "R"]
    latest = max(openf1_by_session, key=order.index) if openf1_by_session else None
    latest_numbers = {int(d["driver_number"]) for d in openf1_by_session.get(latest, [])}
    cid_for_display = {v: k for k, v in {**DISPLAY_NAMES, **display_for}.items()}
    for drivers in openf1_by_session.values():
        for d in drivers:
            drv = driver_for_number(d)
            if drv.id in entries:
                continue
            number = int(d["driver_number"])
            team = by_number_team.get(number) or d.get("team_name") or "Unknown"
            practice_only = bool(jolpica_rows) or (len(openf1_by_session) > 1 and number not in latest_numbers)
            entries[drv.id] = dict(driver_id=drv.id, constructor_id=cid_for_display.get(team), car_number=number, team=team, practice_only=practice_only)
    return list(entries.values())


def sync_event_entries(db: OrmSession, event_id: int) -> int:
    event = db.get(Event, event_id)
    year = db.get(Season, event.season_id).year
    sessions = db.scalars(select(Session).where(Session.event_id == event_id, Session.openf1_session_key.is_not(None))).all()
    openf1_by_session = {s.session_type: openf1.fetch_session_drivers(s.openf1_session_key) for s in sessions}
    openf1_by_session = {k: v for k, v in openf1_by_session.items() if v}
    rows = build_entries(
        _jolpica_rows(year, event.round),
        openf1_by_session,
        driver_for_jolpica=lambda r: upsert_driver_from_jolpica(db, r["Driver"]),
        driver_for_number=lambda d: resolve_driver_by_number(db, year, int(d["driver_number"]), d),
    )
    if not rows:
        return 0
    db.execute(delete(Entry).where(Entry.event_id == event_id))
    for r in rows:
        db.add(Entry(event_id=event_id, **r))
    db.flush()
    # keep Driver.team as "latest team" for anything that only needs a default
    latest = db.scalars(select(Event).where(Event.season_id == event.season_id).order_by(Event.round.desc())).first()
    if latest is not None and latest.id == event_id:
        for r in rows:
            if not r["practice_only"]:
                db.get(Driver, r["driver_id"]).team = r["team"]
    log.info("event %d (r%d): %d entries", event_id, event.round, len(rows))
    return len(rows)


def entry_map(db: OrmSession, event_id: int) -> dict[int, Entry]:
    return {e.driver_id: e for e in db.scalars(select(Entry).where(Entry.event_id == event_id)).all()}


def team_of(db: OrmSession, event_id: int, driver_id: int) -> str | None:
    e = db.get(Entry, (event_id, driver_id))
    return e.team if e else None


def usual_teams(db: OrmSession, season_id: int) -> dict[int, str]:
    """Each driver's regular seat this season (the team of most of their race-weekend entries)."""
    from collections import Counter

    rows = db.execute(
        select(Entry.driver_id, Entry.team).join(Event, Event.id == Entry.event_id).where(Event.season_id == season_id, Entry.practice_only.is_(False))
    ).all()
    counts: dict[int, Counter] = {}
    for did, team in rows:
        counts.setdefault(did, Counter())[team] += 1
    return {did: c.most_common(1)[0][0] for did, c in counts.items()}


def event_drivers(db: OrmSession, event_id: int, only: set[int] | None = None) -> dict[int, dict[str, Any]]:
    """Driver cards for one event: name, code, and the team and car number *at this event*.

    `stand_in` marks a driver racing for a team other than their usual one (a substitute or a
    promotion), with `usual_team` saying where they normally drive.
    """
    event = db.get(Event, event_id)
    usual = usual_teams(db, event.season_id)
    entries = entry_map(db, event_id)
    ids = set(entries) if only is None else set(only)
    out = {}
    for d in db.scalars(select(Driver).where(Driver.id.in_(ids))).all():
        e = entries.get(d.id)
        team = e.team if e else d.team
        out[d.id] = {
            "id": d.id,
            "driver_ref": d.driver_ref,
            "name": d.full_name,
            "code": d.code,
            "team": team,
            "number": (e.car_number if e and e.car_number is not None else d.number),
            "stand_in": bool(e and not e.practice_only and usual.get(d.id) and usual[d.id] != team),
            "usual_team": usual.get(d.id),
            "practice_only": bool(e and e.practice_only),
        }
    return out


def teammates(db: OrmSession, event_id: int, driver_id: int) -> list[int]:
    """Drivers who raced for the same team as `driver_id` at this event (practice-only runners excluded)."""
    entries = entry_map(db, event_id)
    me = entries.get(driver_id)
    if me is None:
        return []
    return [d for d, e in entries.items() if d != driver_id and e.team == me.team and not e.practice_only]
