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

from sqlalchemy import select
from sqlalchemy.orm import Session as OrmSession

from ..clients import jolpica
from ..models import Driver
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
    first = info.get("first_name") or ""
    last = info.get("last_name") or ""
    full = info.get("full_name") or f"{first} {last}".strip() or f"Driver #{number}"
    ref = slugify(f"{first}_{last}") if (first or last) else f"driver_{number}"
    log.warning("Driver #%s (%s) not in Jolpica %d list; creating driver_ref=%s", number, full, year, ref)
    drv = Driver(driver_ref=ref, full_name=full.title() if full.isupper() else full, code=code, team=team, number=number)
    db.add(drv)
    db.flush()
    return drv
