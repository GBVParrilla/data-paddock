"""Resolve drivers across Jolpica (driverId) and OpenF1 (driver_number).

Canonical identity is Jolpica's driverId (drivers.driver_ref). OpenF1 only has
car numbers, so we map number -> driver via the season's Jolpica driver list,
falling back to creating a driver from OpenF1's name if Jolpica doesn't know them.
Within one season a car number identifies one driver; cross-season reuse would
need a (season, number) map - out of scope for the single-season build.
"""
from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session as OrmSession

from ..clients import jolpica
from ..models import Base, Driver
from ..util import slugify

log = logging.getLogger(__name__)


@lru_cache(maxsize=8)
def _jolpica_drivers_by_number(year: int) -> dict[int, dict[str, Any]]:
    out: dict[int, dict[str, Any]] = {}
    for d in jolpica.fetch_drivers(year):
        num = d.get("permanentNumber")
        if num and num.isdigit():
            out[int(num)] = d
    return out


def upsert_driver_from_jolpica(db: OrmSession, jd: dict[str, Any], team: str | None = None, number: int | None = None) -> Driver:
    ref = jd["driverId"]
    drv = db.scalar(select(Driver).where(Driver.driver_ref == ref))
    full_name = f"{jd.get('givenName', '')} {jd.get('familyName', '')}".strip()
    perm = jd.get("permanentNumber")
    num = number if number is not None else (int(perm) if perm and perm.isdigit() else None)
    if drv is None:
        drv = Driver(driver_ref=ref, full_name=full_name, code=jd.get("code"), team=team, number=num)
        db.add(drv)
        db.flush()
    else:
        drv.full_name = full_name or drv.full_name
        drv.code = jd.get("code") or drv.code
        if team:
            drv.team = team
        if num is not None:
            drv.number = num
    return drv


def resolve_driver_by_number(db: OrmSession, year: int, number: int, openf1_info: dict[str, Any] | None = None) -> Driver:
    """Find (or create) the Driver for an OpenF1 car number."""
    drv = db.scalar(select(Driver).where(Driver.number == number))
    team = (openf1_info or {}).get("team_name")
    if drv is not None:
        if team and drv.team != team:
            drv.team = team
        if drv.driver_ref.startswith("driver_") and openf1_info:
            # a placeholder made when OpenF1's driver list was unavailable: name it, or fold it into
            # the real driver if they already exist under another car number (rookies change numbers)
            known = _known_by_name(db, openf1_info)
            if known is not None and known.id != drv.id:
                _merge_into(db, drv, known)
                return known
            _fill_from_openf1(drv, openf1_info)
        return drv

    jd = _jolpica_drivers_by_number(year).get(number)
    if jd is not None:
        return upsert_driver_from_jolpica(db, jd, team=team, number=number)

    # Fallback: reserve/rookie driver not in Jolpica's list. Try to match by code.
    code = (openf1_info or {}).get("name_acronym")
    if code:
        drv = db.scalar(select(Driver).where(Driver.code == code))
        if drv is not None:
            drv.number = number
            if team:
                drv.team = team
            return drv
    info = openf1_info or {}
    known = _known_by_name(db, info)
    if known is not None:  # same person, new car number
        known.number = number
        return known
    first = info.get("first_name") or ""
    last = info.get("last_name") or ""
    ref = slugify(f"{first}_{last}") if (first or last) else f"driver_{number}"
    drv = Driver(driver_ref=ref, full_name=f"Driver #{number}", code=code, team=team, number=number)
    _fill_from_openf1(drv, info)
    log.warning("Driver #%s (%s) not in Jolpica %d list; creating driver_ref=%s", number, drv.full_name, year, ref)
    db.add(drv)
    db.flush()
    return drv


def _fill_from_openf1(drv: Driver, info: dict[str, Any]) -> None:
    """Name and code from OpenF1 ("Jak CRAWFORD" -> "Jak Crawford")."""
    first, last = (info.get("first_name") or "").strip(), (info.get("last_name") or "").strip()
    if first or last:
        drv.full_name = f"{first} {last.title() if last.isupper() else last}".strip()
        if drv.driver_ref.startswith("driver_"):
            drv.driver_ref = slugify(f"{first}_{last}")
    elif info.get("full_name"):
        full = info["full_name"]
        drv.full_name = full.title() if full.isupper() else full
    drv.code = info.get("name_acronym") or drv.code


def _known_by_name(db: OrmSession, info: dict[str, Any]) -> Driver | None:
    first, last = (info.get("first_name") or "").strip(), (info.get("last_name") or "").strip()
    if not (first or last):
        return None
    return db.scalar(select(Driver).where(Driver.driver_ref == slugify(f"{first}_{last}")))


def _merge_into(db: OrmSession, src: Driver, dst: Driver) -> None:
    """Repoint every row that references `src` at `dst`, then delete `src`."""
    db.flush()
    for table in Base.metadata.sorted_tables:
        for col in table.columns:
            if any(fk.column.table.name == "drivers" for fk in col.foreign_keys):
                db.execute(update(table).where(col == src.id).values({col.name: dst.id}))
    log.warning("merged duplicate driver %s (%s) into %s", src.driver_ref, src.full_name, dst.driver_ref)
    db.delete(src)
    db.flush()
