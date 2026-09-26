"""Track outline generation from OpenF1 location telemetry (our own derived asset).

We take the fastest clean lap with all three sector times from the event's best
session, pull that driver's x/y positions for the lap window, rotate it so the
track's long axis runs horizontally (a plain bounding-box crop often comes out
"sideways"; aligning the principal axis reads much closer to how broadcasts frame
a track map), normalize into a 0-1000 box, and mark where sector 1 and sector 2
END using the lap's actual sector times against the point timestamps. That
boundary is an approximation (timing-loop position != a telemetry sample), not
an exact split - same caveat for the rotation (there's no ground truth for which
way is "up" without a real map reference).

We also derive:
- a geo-projected version of the same lap (for the satellite-photo overlay), by
  treating the circuit's Jolpica lat/lon as the track's local origin and each
  telemetry sample's x/y (meters) as an offset from it. OpenF1 does not document
  the compass alignment of its local x/y frame, so this can be rotated relative
  to true north - it is a best-effort overlay, not a georeferenced survey.
- DRS zones: contiguous stretches of the same lap where car telemetry reports DRS
  open (values 10/12/14), i.e. where the driver could get a "boost" from the
  drag-reduction system.
"""
from __future__ import annotations

import json
import logging
import math
from datetime import timedelta
from itertools import groupby

from sqlalchemy import select
from sqlalchemy.orm import Session as OrmSession

from ..clients import openf1
from ..models import Driver, Event, Lap, Session, TrackOutline
from ..util import parse_iso_utc, utcnow

log = logging.getLogger(__name__)

SESSION_PREFERENCE = ["Q", "SQ", "FP2", "FP3", "FP1", "R", "S"]
BOX = 1000.0
PAD = 20.0
DRS_ACTIVE_VALUES = {10, 12, 14}
DRS_MIN_RUN = 4  # samples (~1s at ~3.7Hz) - filters single-sample noise
M_PER_DEG_LAT = 111_320.0


def _pick_reference_lap(db: OrmSession, event_id: int) -> tuple[Session, Lap] | None:
    sessions = {s.session_type: s for s in db.scalars(select(Session).where(Session.event_id == event_id)).all()}
    for stype in SESSION_PREFERENCE:
        s = sessions.get(stype)
        if not s or not s.openf1_session_key:
            continue
        lap = db.scalar(
            select(Lap)
            .where(Lap.session_id == s.id, Lap.lap_time_ms.is_not(None), Lap.is_pit_lap.is_(False), Lap.lap_start_time.is_not(None),
                   Lap.sector_1_ms.is_not(None), Lap.sector_2_ms.is_not(None), Lap.sector_3_ms.is_not(None))
            .order_by(Lap.lap_time_ms)
            .limit(1)
        )
        if lap:
            return s, lap
    return None


def pca_rotate(raw: list[dict]) -> list[dict]:
    """Rotate x/y so the track's dominant axis is horizontal (fixes "sideways" outlines)."""
    xs = [p["x"] for p in raw]
    ys = [p["y"] for p in raw]
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    cxs = [x - mx for x in xs]
    cys = [y - my for y in ys]
    cov_xx = sum(cx * cx for cx in cxs) / n
    cov_yy = sum(cy * cy for cy in cys) / n
    cov_xy = sum(cx * cy for cx, cy in zip(cxs, cys)) / n
    angle = 0.5 * math.atan2(2 * cov_xy, cov_xx - cov_yy)
    cos_a, sin_a = math.cos(angle), math.sin(angle)
    out = []
    for p, cx, cy in zip(raw, cxs, cys):
        rx = cx * cos_a + cy * sin_a
        ry = -cx * sin_a + cy * cos_a
        out.append({**p, "x": rx, "y": ry})
    return out


def normalize_points(raw: list[dict]) -> list[list[float]]:
    xs = [p["x"] for p in raw]
    ys = [p["y"] for p in raw]
    min_x, max_x, min_y, max_y = min(xs), max(xs), min(ys), max(ys)
    span = max(max_x - min_x, max_y - min_y) or 1.0
    scale = (BOX - 2 * PAD) / span
    # centre the shorter axis
    off_x = (BOX - (max_x - min_x) * scale) / 2
    off_y = (BOX - (max_y - min_y) * scale) / 2
    return [[round(off_x + (p["x"] - min_x) * scale, 1), round(BOX - (off_y + (p["y"] - min_y) * scale), 1)] for p in raw]


def geo_project(raw: list[dict], lat0: float, lon0: float) -> tuple[list[list[float]], dict[str, float]]:
    """Project raw (unrotated) x/y meters onto the circuit's lat/lon, normalized into a square 0-1000 box.

    Best-effort only: assumes OpenF1's local x/y axes are roughly east/north aligned, which is not
    documented, so the satellite overlay may be rotated relative to the real road.
    """
    xs = [p["x"] for p in raw]
    ys = [p["y"] for p in raw]
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    dxs = [x - mx for x in xs]
    dys = [y - my for y in ys]
    m_per_deg_lon = M_PER_DEG_LAT * math.cos(math.radians(lat0)) or 1.0
    span_m = max(max(dxs) - min(dxs), max(dys) - min(dys))
    half = span_m / 2 * 1.12  # pad so the track doesn't touch the image edge
    bbox = {
        "south": lat0 - half / M_PER_DEG_LAT,
        "north": lat0 + half / M_PER_DEG_LAT,
        "west": lon0 - half / m_per_deg_lon,
        "east": lon0 + half / m_per_deg_lon,
    }
    scale = BOX / (2 * half)
    geo_points = [[round((dx + half) * scale, 1), round(BOX - (dy + half) * scale, 1)] for dx, dy in zip(dxs, dys)]
    return geo_points, bbox


def _nearest_indices(times: list, cd_times: list) -> list[int]:
    """For each t in `times`, the index into `cd_times` (sorted) of the nearest timestamp."""
    out = []
    lo = 0
    for t in times:
        while lo + 1 < len(cd_times) and abs((cd_times[lo + 1] - t).total_seconds()) <= abs((cd_times[lo] - t).total_seconds()):
            lo += 1
        out.append(lo)
    return out


def _runs(active: list[bool], min_run: int) -> list[list[int]]:
    zones, idx = [], 0
    for is_active, group in groupby(enumerate(active), key=lambda x: x[1]):
        members = list(group)
        if is_active and len(members) >= min_run:
            zones.append([members[0][0], members[-1][0]])
        idx += len(members)
    return zones


def lap_geometry(raw: list[dict], times: list) -> tuple[list[float], list[float]]:
    """Cumulative distance (meters, straight-line between consecutive samples) and elapsed ms
    since the first sample, both parallel to `raw`/`points`/`geo_points`."""
    dist = [0.0]
    for i in range(1, len(raw)):
        dist.append(dist[-1] + math.hypot(raw[i]["x"] - raw[i - 1]["x"], raw[i]["y"] - raw[i - 1]["y"]))
    t0 = times[0]
    elapsed_ms = [(t - t0).total_seconds() * 1000 for t in times]
    return dist, elapsed_ms


def _moving_average(values: list[float], window: int) -> list[float]:
    n = len(values)
    out = []
    half = window // 2
    for i in range(n):
        lo, hi = max(0, i - half), min(n, i + half + 1)
        out.append(sum(values[lo:hi]) / (hi - lo))
    return out


def detect_turns(dist: list[float], times: list, car_data: list[dict], *, min_gap_m: float = 70.0, prominence_kph: float = 8.0) -> list[dict]:
    """Corner apexes as local minima of the reference lap's speed trace.

    A heuristic, not an official corner list: it finds meaningful dips in speed at least
    `min_gap_m` apart, which is what a driver actually slowing down for a corner looks like in
    this data. Two apexes closer together than that keep only the slower (more pronounced) one.
    """
    samples = [(parse_iso_utc(d["date"]), d.get("speed")) for d in car_data if d.get("date") and d.get("speed") is not None]
    samples = [s for s in samples if s[0] is not None]
    if len(samples) < 5:
        return []
    samples.sort(key=lambda s: s[0])
    cd_times = [s[0] for s in samples]
    nearest = _nearest_indices(times, cd_times)
    speed = _moving_average([samples[i][1] for i in nearest], window=3)

    n = len(speed)
    minima: list[int] = []
    for i in range(1, n - 1):
        if not (speed[i] <= speed[i - 1] and speed[i] <= speed[i + 1]):
            continue
        back_max = max(speed[max(0, i - 15) : i], default=speed[i])
        fwd_max = max(speed[i + 1 : i + 16], default=speed[i])
        prominence = min(back_max, fwd_max) - speed[i]
        if prominence < prominence_kph:
            continue
        if minima and dist[i] - dist[minima[-1]] < min_gap_m:
            if speed[i] < speed[minima[-1]]:
                minima[-1] = i
            continue
        minima.append(i)
    return [{"number": k + 1, "index": idx, "distance_m": round(dist[idx], 1), "apex_speed_kph": round(speed[idx], 1)} for k, idx in enumerate(minima)]


def compute_boost_zones(times: list, car_data: list[dict]) -> tuple[list[list[int]], str]:
    """Index ranges into `times` (same filtered list backing `points`) that read as "boost" spots.

    OpenF1's `drs` telemetry field is used when populated (values 10/12/14 = DRS open). In practice
    it is null across this dataset, so we fall back to a proxy: sustained full-throttle running near
    the lap's top speed, which is where a real DRS zone on a straight would show up anyway. The
    fallback is clearly labelled - it is an estimate, not a measurement of the actual system.
    """
    samples = [d for d in car_data if d.get("date")]
    samples = [(parse_iso_utc(d["date"]), d) for d in samples]
    samples = [(t, d) for t, d in samples if t is not None]
    if not samples:
        return [], "none"
    samples.sort(key=lambda s: s[0])
    cd_times = [t for t, _ in samples]
    nearest = _nearest_indices(times, cd_times)

    has_drs_field = any(d.get("drs") is not None for _, d in samples)
    if has_drs_field:
        active = [samples[i][1].get("drs") in DRS_ACTIVE_VALUES for i in nearest]
        zones = _runs(active, DRS_MIN_RUN)
        return zones, "telemetry"

    speeds = [d.get("speed") for _, d in samples if d.get("speed") is not None]
    if not speeds:
        return [], "none"
    top_speed = max(speeds)
    active = [
        (samples[i][1].get("throttle") or 0) >= 99 and (samples[i][1].get("speed") or 0) >= 0.8 * top_speed
        for i in nearest
    ]
    zones = _runs(active, DRS_MIN_RUN + 2)  # a bit stricter - this is an estimate, keep it to real straights
    return zones, "estimated_throttle"


def build_track_outline(db: OrmSession, event_id: int, *, force: bool = False) -> TrackOutline:
    existing = db.get(TrackOutline, event_id)
    if existing and not force:
        return existing
    event = db.get(Event, event_id)
    if event is None:
        raise ValueError(f"event {event_id} not found")
    picked = _pick_reference_lap(db, event_id)
    if picked is None:
        raise ValueError(f"no lap data ingested for event {event_id}; ingest a session first")
    session, lap = picked
    driver = db.get(Driver, lap.driver_id)
    start = lap.lap_start_time
    end = start + timedelta(milliseconds=lap.lap_time_ms + 300)
    raw = openf1.fetch_location(session.openf1_session_key, driver.number, start.isoformat(), end.isoformat())
    raw = [p for p in raw if p.get("x") is not None and p.get("y") is not None and p.get("date")]
    if len(raw) < 50:
        raise ValueError(f"too few location samples ({len(raw)}) for event {event_id}")
    raw.sort(key=lambda p: p["date"])
    # drop stationary garbage (x=y=0) sometimes present at window edges
    raw = [p for p in raw if not (p["x"] == 0 and p["y"] == 0)]
    raw = openf1.location_to_meters(raw)  # decimeters -> meters (see openf1.location_to_meters)
    times = [parse_iso_utc(p["date"]) for p in raw]
    s1_end_t = start + timedelta(milliseconds=lap.sector_1_ms)
    s2_end_t = s1_end_t + timedelta(milliseconds=lap.sector_2_ms)
    s1_idx = next((i for i, t in enumerate(times) if t >= s1_end_t), len(raw) // 3)
    s2_idx = next((i for i, t in enumerate(times) if t >= s2_end_t), 2 * len(raw) // 3)

    points = normalize_points(pca_rotate(raw))

    geo_points_json = geo_bbox_json = None
    if event.lat is not None and event.lon is not None:
        geo_points, geo_bbox = geo_project(raw, event.lat, event.lon)
        geo_points_json = json.dumps(geo_points, separators=(",", ":"))
        geo_bbox_json = json.dumps(geo_bbox)

    ref_dist, ref_elapsed_ms = lap_geometry(raw, times)
    try:
        car_data = openf1.fetch_car_data(session.openf1_session_key, driver.number, start.isoformat(), end.isoformat())
        drs_zones, drs_source = compute_boost_zones(times, car_data)
        turns = detect_turns(ref_dist, times, car_data)
    except Exception as exc:  # boost zones / turns are a nice-to-have; never fail outline generation over them
        log.warning("event %d: could not compute boost zones / turns (%s)", event_id, exc)
        drs_zones, drs_source, turns = [], "none", []

    if existing is None:
        existing = TrackOutline(event_id=event_id, points_json="[]", sector_1_end_index=0, sector_2_end_index=0, source_session_id=session.id, source_driver_id=driver.id, source_lap_number=lap.lap_number, generated_at=utcnow())
        db.add(existing)
    existing.points_json = json.dumps(points, separators=(",", ":"))
    existing.sector_1_end_index = s1_idx
    existing.sector_2_end_index = s2_idx
    existing.source_session_id = session.id
    existing.source_driver_id = driver.id
    existing.source_lap_number = lap.lap_number
    existing.generated_at = utcnow()
    existing.geo_points_json = geo_points_json
    existing.geo_bbox_json = geo_bbox_json
    existing.drs_zones_json = json.dumps(drs_zones)
    existing.drs_zone_source = drs_source
    existing.ref_distance_m_json = json.dumps([round(d, 1) for d in ref_dist])
    existing.ref_elapsed_ms_json = json.dumps([round(t, 1) for t in ref_elapsed_ms])
    existing.turns_json = json.dumps(turns)
    db.flush()
    log.info(
        "track outline for event %d (%s): %d points from %s lap %d (%s), sector idx %d/%d, %d boost zone(s) [%s], geo=%s",
        event_id, event.name, len(points), session.session_type, lap.lap_number, driver.full_name, s1_idx, s2_idx, len(drs_zones), drs_source, geo_points_json is not None,
    )
    return existing


def outline_to_dict(o: TrackOutline) -> dict:
    return {
        "event_id": o.event_id,
        "points": json.loads(o.points_json),
        "sector_1_end_index": o.sector_1_end_index,
        "sector_2_end_index": o.sector_2_end_index,
        "drs_zones": json.loads(o.drs_zones_json or "[]"),
        "drs_zone_source": o.drs_zone_source,
        "geo_points": json.loads(o.geo_points_json) if o.geo_points_json else None,
        "geo_bbox": json.loads(o.geo_bbox_json) if o.geo_bbox_json else None,
        "turns": json.loads(o.turns_json or "[]"),
        "source": {"session_id": o.source_session_id, "driver_id": o.source_driver_id, "lap_number": o.source_lap_number},
        "note": "Outline derived from one lap of car position telemetry; rotation, sector boundaries, boost zones and the satellite overlay are all best-effort approximations, not official measurements. Boost zones are estimated from sustained full-throttle, near-top-speed running when the API's own DRS-open telemetry isn't populated for that session.",
    }
