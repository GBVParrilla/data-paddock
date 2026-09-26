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


def compute_turn_deltas(db: OrmSession, session_id: int, driver_id: int) -> dict:
    session = db.get(Session, session_id)
    if session is None:
        raise ValueError(f"session {session_id} not found")
    event = db.get(Event, session.event_id)
    outline = db.get(TrackOutline, event.id)
    if outline is None or not outline.ref_distance_m_json or not outline.turns_json or outline.turns_json == "[]":
        raise ValueError("no turn geometry available for this event yet - generate the track outline first")
    import json

    turns = json.loads(outline.turns_json)
    if not turns:
        raise ValueError("no corners were detected on the reference lap for this circuit")
    ref_dist = json.loads(outline.ref_distance_m_json)
    ref_elapsed = json.loads(outline.ref_elapsed_ms_json)
    ref_session = db.get(Session, outline.source_session_id)
    ref_driver = db.get(Driver, outline.source_driver_id)

    lap = _pick_driver_lap(db, session, driver_id)
    if lap is None:
        raise ValueError("no clean lap with full sector times for this driver in this session")
    driver = db.get(Driver, driver_id)

    is_reference_lap = session.id == ref_session.id and driver_id == outline.source_driver_id and lap.lap_number == outline.source_lap_number

    total_distance = ref_dist[-1]
    total_delta = 0.0

    if is_reference_lap:
        def window_delta(_center: float) -> float:
            return 0.0
    else:
        start = lap.lap_start_time
        end = start + timedelta(milliseconds=lap.lap_time_ms + 300)
        raw = openf1.fetch_location(session.openf1_session_key, driver.number, start.isoformat(), end.isoformat())
        raw = [p for p in raw if p.get("x") is not None and p.get("y") is not None and p.get("date")]
        raw = [p for p in raw if not (p["x"] == 0 and p["y"] == 0)]
        if len(raw) < 20:
            raise ValueError("too little telemetry for this driver's lap to compute turn deltas")
        raw.sort(key=lambda p: p["date"])
        raw = openf1.location_to_meters(raw)
        times = [parse_iso_utc(p["date"]) for p in raw]

        ref_lap_row = db.scalar(select(Lap).where(Lap.session_id == outline.source_session_id, Lap.driver_id == outline.source_driver_id, Lap.lap_number == outline.source_lap_number))
        if ref_lap_row is None:
            raise ValueError("reference lap no longer available")
        ref_start = ref_lap_row.lap_start_time
        ref_end = ref_start + timedelta(milliseconds=ref_lap_row.lap_time_ms + 300)
        ref_raw = _fetch_reference_location(ref_session.openf1_session_key, ref_driver.number, ref_start.isoformat(), ref_end.isoformat())
        ref_raw = [p for p in ref_raw if p.get("x") is not None and p.get("y") is not None and p.get("date")]
        ref_raw = [p for p in ref_raw if not (p["x"] == 0 and p["y"] == 0)]
        ref_raw.sort(key=lambda p: p["date"])
        ref_raw = openf1.location_to_meters(ref_raw)

        _, drv_elapsed = lap_geometry(raw, times)
        # sequential matching keeps this already close to distance-ascending; sort defends
        # against the odd small jitter so interpolation (which assumes ascending x) stays correct
        pairs = sorted(_project_onto_reference(ref_raw, raw, ref_dist, drv_elapsed))
        drv_dist_sorted = [p[0] for p in pairs]
        drv_elapsed_sorted = [p[1] for p in pairs]

        def window_delta(center: float) -> float:
            lo, hi = max(0.0, center - WINDOW_M), min(total_distance, center + WINDOW_M)
            drv_dt = _interp(drv_dist_sorted, drv_elapsed_sorted, hi) - _interp(drv_dist_sorted, drv_elapsed_sorted, lo)
            ref_dt = _interp(ref_dist, ref_elapsed, hi) - _interp(ref_dist, ref_elapsed, lo)
            return drv_dt - ref_dt

        total_delta = round(
            (_interp(drv_dist_sorted, drv_elapsed_sorted, total_distance) - _interp(drv_dist_sorted, drv_elapsed_sorted, 0.0))
            - (ref_elapsed[-1] - ref_elapsed[0]),
            1,
        )

    s1_dist = ref_dist[min(outline.sector_1_end_index, len(ref_dist) - 1)]
    s2_dist = ref_dist[min(outline.sector_2_end_index, len(ref_dist) - 1)]

    def sector_for(distance_m: float) -> int:
        if distance_m <= s1_dist:
            return 1
        if distance_m <= s2_dist:
            return 2
        return 3

    out_turns = []
    for t in turns:
        d = round(window_delta(t["distance_m"]), 1)
        out_turns.append({"number": t["number"], "sector": sector_for(t["distance_m"]), "distance_m": t["distance_m"], "apex_speed_kph": t["apex_speed_kph"], "delta_ms": d})

    return {
        "session_id": session_id,
        "driver_id": driver_id,
        "lap_number": lap.lap_number,
        "is_reference_lap": is_reference_lap,
        "reference": {"session_id": outline.source_session_id, "driver_id": outline.source_driver_id, "lap_number": outline.source_lap_number},
        "turns": out_turns,
        "total_lap_delta_ms": total_delta,
        "note": "Delta per turn is the time gained/lost in the ~120m window around that corner's apex, vs the event's reference lap. Corners are detected from a speed trace, not an official list; small telemetry-sampling noise is expected.",
    }


def get_or_compute_turn_deltas(db: OrmSession, session_id: int, driver_id: int, *, force: bool = False) -> dict:
    """Cached compute_turn_deltas (it downloads telemetry). A cached failure re-raises its ValueError."""
    import json

    cached = db.get(TurnDeltaCache, (session_id, driver_id))
    if cached is not None and not force:
        if cached.payload_json:
            return json.loads(cached.payload_json)
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
