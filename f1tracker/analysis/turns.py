"""Turn-by-turn time deltas: how much a driver gained or lost around each corner, vs the
event's reference lap (the same fastest lap the track outline is built from).

Method: project the requested driver's own lap telemetry onto the reference lap's distance
axis (nearest x/y point on the reference polyline, in the same raw meter coordinates used to
build that polyline), then compare elapsed time at matching distances. This is the standard
"delta trace" technique driver-telemetry tools use, just built from OpenF1's public location
feed rather than a factory telemetry stream - so it inherits that feed's sampling noise, and
the corner list itself is a heuristic (see analysis.track.detect_turns), not an official one.
"""
from __future__ import annotations

import bisect
import functools
import math
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session as OrmSession

from ..clients import openf1
from ..models import Driver, Event, Lap, Session, TrackOutline, TurnDeltaCache
from ..util import parse_iso_utc, utcnow
from .track import lap_geometry

WINDOW_M = 60.0  # each turn is measured over the +/- this many meters around its apex


def _pick_driver_lap(db: OrmSession, session: Session, driver_id: int) -> Lap | None:
    return db.scalar(
        select(Lap)
        .where(
            Lap.session_id == session.id,
            Lap.driver_id == driver_id,
            Lap.lap_time_ms.is_not(None),
            Lap.is_pit_lap.is_(False),
            Lap.lap_start_time.is_not(None),
            Lap.sector_1_ms.is_not(None),
            Lap.sector_2_ms.is_not(None),
            Lap.sector_3_ms.is_not(None),
        )
        .order_by(Lap.lap_time_ms)
        .limit(1)
    )


SEARCH_WINDOW = 40  # reference points either side of the running estimate


def _project_onto_reference(ref_raw: list[dict], drv_raw: list[dict], ref_dist: list[float], drv_elapsed: list[float]) -> list[tuple[float, float]]:
    """For each driver sample (in time order), the (matched reference distance, driver elapsed ms).

    Matches sequentially with a local search window around the previous match, not a fresh
    nearest-neighbour search over the whole polyline. A closed loop's start/finish straight sits
    close (in x/y) to other parts of the lap - an unconstrained global nearest-neighbour search can
    snap a late-lap sample onto an early-lap reference point, silently producing a nonsense delta.
    Assumes both driver and reference start their fetch window at the same lap boundary, which the
    calling code arranges (both are the timing-loop crossing that starts the lap).
    """
    n_ref = len(ref_raw)
    out = []
    guess = 0
    for i, p in enumerate(drv_raw):
        lo, hi = max(0, guess - SEARCH_WINDOW), min(n_ref, guess + SEARCH_WINDOW)
        best_j, best_d2 = lo, float("inf")
        for j in range(lo, hi):
            rp = ref_raw[j]
            d2 = (p["x"] - rp["x"]) ** 2 + (p["y"] - rp["y"]) ** 2
            if d2 < best_d2:
                best_d2, best_j = d2, j
        out.append((ref_dist[best_j], drv_elapsed[i]))
        guess = best_j
    return out


def _interp(xs: list[float], ys: list[float], x: float) -> float:
    """Linear interpolation; xs must be sorted ascending. Clamps outside the range."""
    i = bisect.bisect_left(xs, x)
    if i <= 0:
        return ys[0]
    if i >= len(xs):
        return ys[-1]
    x0, x1 = xs[i - 1], xs[i]
    if x1 == x0:
        return ys[i]
    frac = (x - x0) / (x1 - x0)
    return ys[i - 1] + frac * (ys[i] - ys[i - 1])


@functools.lru_cache(maxsize=4)
def _fetch_reference_location(session_key: int, driver_number: int, start: str, end: str) -> tuple[dict, ...]:
    """The reference lap is shared by every driver at an event, so batch precompute fetches it once."""
    return tuple(openf1.fetch_location(session_key, driver_number, start, end))


TURN_DELTA_VERSION = 2  # 2: session-best reference, contiguous corner zones, explicit remainder


def _clean_location(raw) -> list[dict]:
    raw = [p for p in raw if p.get("x") is not None and p.get("y") is not None and p.get("date")]
    raw = [p for p in raw if not (p["x"] == 0 and p["y"] == 0)]
    raw.sort(key=lambda p: p["date"])
    return openf1.location_to_meters(raw)


def _lap_location(session: Session, driver: Driver, lap: Lap, *, cached: bool = False) -> list[dict]:
    start = lap.lap_start_time
    end = start + timedelta(milliseconds=lap.lap_time_ms + 300)
    fetch = _fetch_reference_location if cached else (lambda *a: openf1.fetch_location(*a))
    return _clean_location(fetch(session.openf1_session_key, driver.number, start.isoformat(), end.isoformat()))


def _elapsed_along(polyline: list[dict], poly_dist: list[float], raw: list[dict]) -> tuple[list[float], list[float]]:
    """A lap's elapsed time as a function of distance along the event's outline polyline."""
    times = [parse_iso_utc(p["date"]) for p in raw]
    _, elapsed = lap_geometry(raw, times)
    pairs = sorted(_project_onto_reference(polyline, raw, poly_dist, elapsed))
    return [p[0] for p in pairs], [p[1] for p in pairs]


def corner_zones(turns: list[dict], total_m: float) -> list[tuple[float, float]]:
    """Contiguous zones, one per corner, covering the whole lap: each runs from midway after the
    previous apex to midway before the next (the first starts at the line, the last ends there)."""
    apexes = [t["distance_m"] for t in turns]
    bounds = [0.0] + [(a + b) / 2 for a, b in zip(apexes, apexes[1:])] + [total_m]
    return list(zip(bounds, bounds[1:]))


def compute_turn_deltas(db: OrmSession, session_id: int, driver_id: int) -> dict:
    """Where on the lap a driver's best lap gained or lost time against the session's best lap.

    Each corner owns a contiguous slice of track (its braking zone, apex and exit to halfway down
    the next straight), so the corner figures add up to the whole-lap telemetry delta. The official
    timing delta (lap time minus the reference lap time) differs from the telemetry one by a little
    sampling noise; that difference is reported as `unattributed_ms` rather than hidden, so
    corners + unattributed = total, always.
    """
    import json

    session = db.get(Session, session_id)
    if session is None:
        raise ValueError(f"session {session_id} not found")
    event = db.get(Event, session.event_id)
    outline = db.get(TrackOutline, event.id)
    if outline is None or not outline.ref_distance_m_json or not outline.turns_json or outline.turns_json == "[]":
        raise ValueError("no turn geometry available for this event yet - generate the track outline first")
    turns = json.loads(outline.turns_json)
    if not turns:
        raise ValueError("no corners were detected on the reference lap for this circuit")
    poly_dist = json.loads(outline.ref_distance_m_json)
    total_distance = poly_dist[-1]

    lap = _pick_driver_lap(db, session, driver_id)
    if lap is None:
        raise ValueError("no clean lap with full sector times for this driver in this session")
    ref_lap = db.scalar(
        select(Lap)
        .where(Lap.session_id == session_id, Lap.lap_time_ms.is_not(None), Lap.is_pit_lap.is_(False), Lap.lap_start_time.is_not(None),
               Lap.sector_1_ms.is_not(None), Lap.sector_2_ms.is_not(None), Lap.sector_3_ms.is_not(None))
        .order_by(Lap.lap_time_ms)
        .limit(1)
    )
    driver = db.get(Driver, driver_id)
    ref_driver = db.get(Driver, ref_lap.driver_id)
    is_reference_lap = ref_lap.driver_id == driver_id and ref_lap.lap_number == lap.lap_number

    s1_dist = poly_dist[min(outline.sector_1_end_index, len(poly_dist) - 1)]
    s2_dist = poly_dist[min(outline.sector_2_end_index, len(poly_dist) - 1)]

    def sector_for(distance_m: float) -> int:
        return 1 if distance_m <= s1_dist else 2 if distance_m <= s2_dist else 3

    zones = corner_zones(turns, total_distance)
    timing_delta = lap.lap_time_ms - ref_lap.lap_time_ms
    if is_reference_lap:
        zone_deltas = [0.0 for _ in zones]
    else:
        # the outline's own lap gives the polyline both laps are projected onto
        src_session = db.get(Session, outline.source_session_id)
        src_lap = db.scalar(select(Lap).where(Lap.session_id == outline.source_session_id, Lap.driver_id == outline.source_driver_id, Lap.lap_number == outline.source_lap_number))
        if src_lap is None:
            raise ValueError("the outline's source lap is no longer available")
        polyline = _lap_location(src_session, db.get(Driver, outline.source_driver_id), src_lap, cached=True)
        ref_raw = _lap_location(session, ref_driver, ref_lap, cached=True)
        drv_raw = _lap_location(session, driver, lap)
        if len(drv_raw) < 20 or len(ref_raw) < 20 or len(polyline) < 20:
            raise ValueError("too little telemetry for this lap to compute turn deltas")
        if len(polyline) != len(poly_dist):
            raise ValueError("outline geometry and its source telemetry disagree - regenerate the outline")
        d_x, d_y = _elapsed_along(polyline, poly_dist, drv_raw)
        r_x, r_y = _elapsed_along(polyline, poly_dist, ref_raw)

        def at(xs, ys, d):
            return _interp(xs, ys, d)

        zone_deltas = [
            (at(d_x, d_y, hi) - at(d_x, d_y, lo)) - (at(r_x, r_y, hi) - at(r_x, r_y, lo))
            for lo, hi in zones
        ]

    out_turns = []
    for t, (lo, hi), d in zip(turns, zones, zone_deltas):
        out_turns.append({
            "number": t["number"], "sector": sector_for(t["distance_m"]), "distance_m": t["distance_m"],
            "from_m": round(lo, 1), "to_m": round(hi, 1), "apex_speed_kph": t["apex_speed_kph"], "delta_ms": round(d, 1),
        })
    corners_total = sum(t["delta_ms"] for t in out_turns)
    return {
        "version": TURN_DELTA_VERSION,
        "session_id": session_id,
        "driver_id": driver_id,
        "lap_number": lap.lap_number,
        "lap_time_ms": lap.lap_time_ms,
        "is_reference_lap": is_reference_lap,
        "reference": {"session_id": session_id, "driver_id": ref_lap.driver_id, "lap_number": ref_lap.lap_number, "lap_time_ms": ref_lap.lap_time_ms},
        "turns": out_turns,
        "total_lap_delta_ms": timing_delta,
        "unattributed_ms": round(timing_delta - corners_total, 1) if not is_reference_lap else 0.0,
        "note": "Each corner covers the track from halfway after the previous corner to halfway before the next, so the corners add up to the lap. The remainder is telemetry sampling noise between the timing loops.",
    }


def get_or_compute_turn_deltas(db: OrmSession, session_id: int, driver_id: int, *, force: bool = False) -> dict:
    """Cached compute_turn_deltas (it downloads telemetry). A cached failure re-raises its ValueError."""
    import json

    cached = db.get(TurnDeltaCache, (session_id, driver_id))
    if cached is not None and not force:
        if cached.payload_json:
            payload = json.loads(cached.payload_json)
            if payload.get("version") == TURN_DELTA_VERSION:
                return payload
        else:
            raise ValueError(cached.error or "turn deltas unavailable")
    if cached is None:
        cached = TurnDeltaCache(session_id=session_id, driver_id=driver_id, computed_at=utcnow())
        db.add(cached)
    cached.computed_at = utcnow()
    try:
        out = compute_turn_deltas(db, session_id, driver_id)
    except ValueError as exc:
        cached.payload_json, cached.error = None, str(exc)
        db.flush()
        raise
    cached.payload_json, cached.error = json.dumps(out, separators=(",", ":")), None
    db.flush()
    return out
