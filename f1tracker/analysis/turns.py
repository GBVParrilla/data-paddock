"""Turn-by-turn time deltas: how much a driver gained or lost around each corner, vs the
session's best lap.

Method: project each lap's telemetry onto the event outline's distance axis (nearest x/y point
on the outline's own lap, in the same raw meter coordinates used to build it), then compare
elapsed time at matching distances. This is the standard "delta trace" technique
driver-telemetry tools use, just built from OpenF1's public location feed rather than a factory
telemetry stream - so it inherits that feed's sampling noise and its faults (a feed that freezes
for a lap, holes, a shifted window), which `lap_trace` detects rather than draws. The corner
list itself is a heuristic (see analysis.track.detect_turns) unless F1's official one is known.
"""
from __future__ import annotations

import bisect
import functools
import math
from datetime import timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session as OrmSession

from ..clients import openf1
from ..models import Driver, Event, Lap, Session, TrackOutline, TurnDeltaCache
from ..util import parse_iso_utc, utcnow

WINDOW_M = 60.0  # each turn is measured over the +/- this many meters around its apex


def _clean_laps(db: OrmSession, session: Session, driver_id: int | None = None, limit: int = 3) -> list[Lap]:
    """The fastest timed laps with all three sectors (one driver's, or anyone's), fastest first."""
    q = select(Lap).where(
        Lap.session_id == session.id,
        Lap.lap_time_ms.is_not(None),
        Lap.is_pit_lap.is_(False),
        Lap.lap_start_time.is_not(None),
        Lap.sector_1_ms.is_not(None),
        Lap.sector_2_ms.is_not(None),
        Lap.sector_3_ms.is_not(None),
    )
    if driver_id is not None:
        q = q.where(Lap.driver_id == driver_id)
    return list(db.scalars(q.order_by(Lap.lap_time_ms, Lap.driver_id, Lap.lap_number).limit(limit)).all())


FALLBACK_SLOWER = 1.01  # another lap stands in for a driver's best only if it's within 1% of it


SEARCH_WINDOW = 40  # reference points either side of the running estimate
PAD_S = 5.0  # seconds of telemetry fetched either side of the lap, so the line crossings are inside it
MAX_TIME_ERROR_MS = 1000.0  # telemetry lap time vs the official one; worse means the trace is broken
MAX_SAMPLE_GAP_MS = 2500.0  # a longer hole in the feed (it runs at ~3.7 Hz) loses a corner
MAX_OFF_LINE_M = 25.0  # median distance from the outline; more means the feed is somewhere else


def _project_lap(polyline: list[dict], poly_dist: list[float], raw: list[dict], times: list[float], start_ms: float) -> list[tuple[float, float]]:
    """(unwrapped distance along the outline, ms) for each sample, the lap starting at `start_ms`.

    Matching is sequential with a local, circular search window around the previous match: a
    closed loop's start/finish straight sits close in x/y to other parts of the lap, so a fresh
    nearest-neighbour search can snap a sample onto the wrong part of the track. The walk starts
    at the sample nearest the lap's official start, matched only against the ends of the outline
    (that sample is near the line), and runs forwards and backwards from there. Distance is
    unwrapped across the line, so the sample before the lap has a negative distance and the one
    after it more than one lap.
    """
    n_ref, total = len(polyline), poly_dist[-1]
    i0 = min(range(len(times)), key=lambda i: abs(times[i] - start_ms))

    def nearest(p: dict, candidates) -> int:
        return min(candidates, key=lambda j: (p["x"] - polyline[j]["x"]) ** 2 + (p["y"] - polyline[j]["y"]) ** 2)

    near_line = [j for j in range(n_ref) if poly_dist[j] < 0.1 * total or poly_dist[j] > 0.9 * total]
    j0 = nearest(raw[i0], near_line)
    u0 = poly_dist[j0] - (total if poly_dist[j0] > 0.5 * total else 0.0)
    out = {i0: u0}
    for step in (1, -1):
        j, u = j0, u0
        i = i0 + step
        while 0 <= i < len(raw):
            k = nearest(raw[i], [(j + o) % n_ref for o in range(-SEARCH_WINDOW, SEARCH_WINDOW + 1)])
            d = poly_dist[k] - poly_dist[j]
            if d < -0.5 * total:  # crossed the line going forwards
                d += total
            elif d > 0.5 * total:  # crossed it going backwards
                d -= total
            j, u = k, u + d
            out[i] = u
            i += step
    return [(out[i], times[i]) for i in range(len(raw))]


def _line_crossing(trace: list[tuple[float, float]], u: float) -> float | None:
    """When the trace first passes distance `u` (ms, interpolated), or None if it never does."""
    for (u0, t0), (u1, t1) in zip(trace, trace[1:]):
        if u0 < u <= u1:
            return t0 + (u - u0) / (u1 - u0) * (t1 - t0)
    return None


def lap_trace(polyline: list[dict], poly_dist: list[float], raw: list[dict], start_ms: float, lap_ms: int) -> tuple[list[float], list[float]]:
    """A lap's elapsed time as a function of distance along the outline, from line to line.

    `raw` covers the lap plus a few seconds either side; `start_ms` is the official lap start on
    the same clock. The lap is anchored on where the telemetry itself crosses the line, not on the
    official timestamp, and the trace is checked before use: it must cross the line twice, take
    the official lap time to within a second, have no long hole and stay on the track. A trace
    that fails raises ValueError with the reason (a frozen feed, a gap, a shifted window).
    """
    total = poly_dist[-1]
    times = [(parse_iso_utc(p["date"]).timestamp() * 1000.0) for p in raw]
    t_ref = times[0]
    times = [t - t_ref for t in times]
    start_ms -= t_ref
    trace = _project_lap(polyline, poly_dist, raw, times, start_ms)
    t_start, t_end = _line_crossing(trace, 0.0), _line_crossing(trace, total)
    if t_start is None or t_end is None:
        raise ValueError("the telemetry for this lap doesn't cover the whole lap")
    if abs((t_end - t_start) - lap_ms) > MAX_TIME_ERROR_MS:
        raise ValueError(f"the telemetry lap takes {(t_end - t_start) / 1000:.1f}s against an official {lap_ms / 1000:.3f}s")
    inside = [(u, t) for u, t in trace if t_start - 1000 <= t <= t_end + 1000]
    if max((b[1] - a[1] for a, b in zip(inside, inside[1:])), default=0.0) > MAX_SAMPLE_GAP_MS:
        raise ValueError("the telemetry for this lap has a gap")
    off = sorted(min(math.hypot(p["x"] - q["x"], p["y"] - q["y"]) for q in polyline) for p in raw[:: max(1, len(raw) // 40)])
    if off[len(off) // 2] > MAX_OFF_LINE_M:
        raise ValueError("the telemetry for this lap is off the track outline")
    # a monotonic curve for interpolation: the line crossings, and the samples strictly between them
    xs, ys = [0.0], [0.0]
    for u, t in inside:
        if 0.0 < u < total and u > xs[-1]:
            xs.append(u)
            ys.append(t - t_start)
    xs.append(total)
    ys.append(t_end - t_start)
    return xs, ys


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


@functools.lru_cache(maxsize=16)
def _fetch_reference_location(session_key: int, driver_number: int, start: str, end: str) -> tuple[dict, ...]:
    """The reference lap is shared by every driver at an event, so batch precompute fetches it once."""
    return tuple(openf1.fetch_location(session_key, driver_number, start, end))


TURN_DELTA_VERSION = 3  # 3: laps anchored on their own line crossings and checked; corner times; 2: session-best reference
# version 2 stays publishable behind the plausibility gate until the recompute replaces it
TURN_DELTA_VERSIONS_SHOWN = (2, 3)


def _clean_location(raw) -> list[dict]:
    raw = [p for p in raw if p.get("x") is not None and p.get("y") is not None and p.get("date")]
    raw = [p for p in raw if not (p["x"] == 0 and p["y"] == 0)]
    raw.sort(key=lambda p: p["date"])
    return openf1.location_to_meters(raw)


def _lap_location(session: Session, driver: Driver, lap: Lap, *, cached: bool = False, pad_s: float = 0.0) -> list[dict]:
    start = lap.lap_start_time - timedelta(seconds=pad_s)
    end = lap.lap_start_time + timedelta(milliseconds=lap.lap_time_ms + 300) + timedelta(seconds=pad_s)
    fetch = _fetch_reference_location if cached else (lambda *a: openf1.fetch_location(*a))
    return _clean_location(fetch(session.openf1_session_key, driver.number, start.isoformat(), end.isoformat()))


def _lap_curve(session: Session, driver: Driver, lap: Lap, polyline: list[dict], poly_dist: list[float], *, cached: bool = False) -> tuple[list[float], list[float]]:
    raw = _lap_location(session, driver, lap, cached=cached, pad_s=PAD_S)
    if len(raw) < 20:
        raise ValueError("too little telemetry for this lap to compute turn deltas")
    start_ms = lap.lap_start_time.replace(tzinfo=lap.lap_start_time.tzinfo or timezone.utc).timestamp() * 1000.0
    return lap_trace(polyline, poly_dist, raw, start_ms, lap.lap_time_ms)


def corner_zones(turns: list[dict], total_m: float) -> list[tuple[float, float]]:
    """Contiguous zones, one per corner, covering the whole lap: each runs from midway after the
    previous apex to midway before the next (the first starts at the line, the last ends there)."""
    apexes = [t["distance_m"] for t in turns]
    bounds = [0.0] + [(a + b) / 2 for a, b in zip(apexes, apexes[1:])] + [total_m]
    return list(zip(bounds, bounds[1:]))


_REFERENCE_CURVES: dict[tuple[int, int], tuple[Lap, tuple[list[float], list[float]]]] = {}


def _outline_polyline(db: OrmSession, outline: TrackOutline, poly_dist: list[float]) -> list[dict]:
    """The outline's own lap: the polyline every lap is projected onto."""
    src_lap = db.scalar(select(Lap).where(Lap.session_id == outline.source_session_id, Lap.driver_id == outline.source_driver_id, Lap.lap_number == outline.source_lap_number))
    if src_lap is None:
        raise ValueError("the outline's source lap is no longer available")
    polyline = _lap_location(db.get(Session, outline.source_session_id), db.get(Driver, outline.source_driver_id), src_lap, cached=True)
    if len(polyline) < 20:
        raise ValueError("too little telemetry for the outline's own lap")
    if len(polyline) != len(poly_dist):
        raise ValueError("outline geometry and its source telemetry disagree - regenerate the outline")
    return polyline


def corner_implausible(delta_ms: float, corner_ms: float | None) -> bool:
    """A corner delta no real lap produces: more than max(1.5s, 20% of the corner's own time)."""
    return abs(delta_ms) > max(1500.0, 0.2 * corner_ms if corner_ms else 0.0)


def cancel_slack_ms(n_corners: int) -> float:
    """How far a breakdown's absolute corner deltas may exceed its lap delta: 3s, or 0.2s a corner on
    a long lap. Clean laps at Baku (20 corners) measure 1.0-3.9s over; misaligned ones 13s and more."""
    return max(3000.0, 200.0 * n_corners)


def plausibility_problem(payload: dict) -> str | None:
    """Why a breakdown must not be shown, or None. The export withholds any breakdown with one:
    an implausible corner, corners whose absolute deltas add up to more than the lap delta plus
    `cancel_slack_ms` (they cancel out: the alignment is wrong), or a remainder over 3s (the trace
    missed time)."""
    turns = payload.get("turns") or []
    if not turns:
        return "no corners"
    if payload.get("is_reference_lap"):
        return None
    bad = [t["number"] for t in turns if corner_implausible(t["delta_ms"], t.get("corner_ms"))]
    if bad:
        return f"implausible corner delta at T{bad[0]}"
    if sum(abs(t["delta_ms"]) for t in turns) > abs(payload["total_lap_delta_ms"]) + cancel_slack_ms(len(turns)):
        return "corner deltas cancel out"
    if abs(payload.get("unattributed_ms") or 0.0) > 3000:
        return "the corners miss part of the lap"
    return None


def _zone_times(curve: tuple[list[float], list[float]], zones: list[tuple[float, float]]) -> list[float]:
    xs, ys = curve
    return [_interp(xs, ys, hi) - _interp(xs, ys, lo) for lo, hi in zones]


def _reference(db: OrmSession, session: Session, polyline: list[dict], poly_dist: list[float], zones: list[tuple[float, float]]) -> tuple[Lap, tuple[list[float], list[float]]]:
    """The session's fastest lap whose telemetry passes the checks and agrees, corner by corner,
    with another clean lap: a trace can reproduce its lap time and still put time in the wrong
    corner (a timestamp hiccup mid-lap), and every driver's figures inherit the reference's.
    Shared by every driver at the session, so it is cached."""
    key = (session.id, len(poly_dist))
    if key not in _REFERENCE_CURVES:
        valid: list[tuple[Lap, tuple[list[float], list[float]], list[float]]] = []
        for lap in _clean_laps(db, session, limit=6):
            try:
                curve = _lap_curve(session, db.get(Driver, lap.driver_id), lap, polyline, poly_dist, cached=True)
            except ValueError:
                continue
            valid.append((lap, curve, _zone_times(curve, zones)))
        for lap, curve, times in valid:
            if any(not any(corner_implausible(b - a, a) for a, b in zip(times, other)) for o, _, other in valid if o.id != lap.id):
                _REFERENCE_CURVES[key] = (lap, curve)
                break
        else:
            if len(valid) == 1:  # nothing to cross-check against
                _REFERENCE_CURVES[key] = valid[0][:2]
            else:
                raise ValueError("no lap in this session has telemetry clean enough to be the reference")
    return _REFERENCE_CURVES[key]


def compute_turn_deltas(db: OrmSession, session_id: int, driver_id: int) -> dict:
    """Where on the lap a driver's best lap gained or lost time against the session's best lap.

    Each corner owns a contiguous slice of track (its braking zone, apex and exit to halfway down
    the next straight), so the corner figures add up to the whole-lap telemetry delta. Every lap is
    anchored on its own line crossings and must reproduce its official lap time to within a second
    (`lap_trace`), so the telemetry delta and the timing delta differ only by sampling noise; that
    difference is reported as `unattributed_ms` rather than hidden, so corners + unattributed =
    total, always. A driver whose best lap has broken telemetry is measured on their next lap
    within 1% of it, or not at all. `corner_ms` is the driver's own time through each corner,
    which the export ranks across the session.
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

    laps = _clean_laps(db, session, driver_id)
    if not laps:
        raise ValueError("no clean lap with full sector times for this driver in this session")
    polyline = _outline_polyline(db, outline, poly_dist)
    zones = corner_zones(turns, total_distance)
    ref_lap, (r_x, r_y) = _reference(db, session, polyline, poly_dist, zones)
    driver = db.get(Driver, driver_id)
    lap, curve, problem = None, None, None
    for candidate in laps:
        if candidate.lap_time_ms > laps[0].lap_time_ms * FALLBACK_SLOWER:
            break
        if candidate.id == ref_lap.id:
            lap, curve = candidate, (r_x, r_y)
            break
        try:
            lap, curve = candidate, _lap_curve(session, driver, candidate, polyline, poly_dist)
            break
        except ValueError as exc:
            problem = problem or exc
    if curve is None:
        raise ValueError(f"lap {laps[0].lap_number}: {problem}")
    d_x, d_y = curve
    is_reference_lap = lap.id == ref_lap.id

    s1_dist = poly_dist[min(outline.sector_1_end_index, len(poly_dist) - 1)]
    s2_dist = poly_dist[min(outline.sector_2_end_index, len(poly_dist) - 1)]

    def sector_for(distance_m: float) -> int:
        return 1 if distance_m <= s1_dist else 2 if distance_m <= s2_dist else 3

    def through(xs, ys, lo, hi):
        return _interp(xs, ys, hi) - _interp(xs, ys, lo)

    timing_delta = lap.lap_time_ms - ref_lap.lap_time_ms
    out_turns = []
    for t, (lo, hi) in zip(turns, zones):
        mine = through(d_x, d_y, lo, hi)
        out_turns.append({
            "number": t["number"], "sector": sector_for(t["distance_m"]), "distance_m": t["distance_m"],
            "from_m": round(lo, 1), "to_m": round(hi, 1), "apex_speed_kph": t["apex_speed_kph"],
            "corner_ms": round(mine, 1), "delta_ms": 0.0 if is_reference_lap else round(mine - through(r_x, r_y, lo, hi), 1),
        })
    corners_total = sum(t["delta_ms"] for t in out_turns)
    return {
        "version": TURN_DELTA_VERSION,
        "session_id": session_id,
        "driver_id": driver_id,
        "lap_number": lap.lap_number,
        "best_lap_number": laps[0].lap_number,
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


MIN_RANKED = 3


def rank_session_corners(payloads: dict[int, dict]) -> tuple[dict[int, dict], dict[int, str]]:
    """Gate a session's breakdowns, then rank every driver through every corner, as sector colours
    rank best sectors: `rank` 1 is the fastest of anyone there, `of` how many were measured.

    Returns (shown, withheld): shown maps driver id -> payload with `rank`/`of` on each corner;
    withheld maps driver id -> why it is not shown. Ranks compare drivers measured against the same
    reference lap (the session's most common one), so a delta ranks exactly as the corner time
    would; corner times are used when every breakdown has them. Ties go to the faster lap, then
    the lower driver id, so exactly one driver is fastest at each corner.

    When most of a session's breakdowns fail the gate, the reference lap they share is the likely
    fault, so none is shown; nor is any group of fewer than 3, since a rank "of 1" says nothing.
    """
    withheld = {d: why for d, p in payloads.items() if (why := plausibility_problem(p))}
    kept = {d: p for d, p in payloads.items() if d not in withheld}
    if len(withheld) > len(kept):
        return {}, {**withheld, **{d: "most breakdowns in this session failed the check, so its reference lap is suspect" for d in kept}}
    refs: dict[tuple, list[int]] = {}
    for d, p in kept.items():
        refs.setdefault((p["reference"]["driver_id"], p["reference"]["lap_number"], len(p["turns"])), []).append(d)
    if not refs:
        return {}, withheld
    main = max(refs.values(), key=len)
    for group in refs.values():
        if group is not main:
            withheld.update({d: "measured against a different reference lap" for d in group})
    if len(main) < MIN_RANKED:
        withheld.update({d: f"fewer than {MIN_RANKED} drivers measured" for d in main})
        return {}, withheld
    use_time = all(all("corner_ms" in t for t in kept[d]["turns"]) for d in main)
    shown = {d: {**kept[d], "turns": [dict(t) for t in kept[d]["turns"]]} for d in main}
    for i in range(len(next(iter(shown.values()))["turns"])):
        order = sorted(main, key=lambda d: (shown[d]["turns"][i]["corner_ms" if use_time else "delta_ms"], shown[d]["lap_time_ms"], d))
        for rank, d in enumerate(order, start=1):
            shown[d]["turns"][i]["rank"], shown[d]["turns"][i]["of"] = rank, len(order)
    return shown, withheld
