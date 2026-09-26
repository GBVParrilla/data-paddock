"""Detail (avid-fan) analytics. Pure functions: row dicts in, row dicts out."""
from __future__ import annotations

from collections import defaultdict
from statistics import mean
from typing import Any

LapRow = dict[str, Any]
StintRow = dict[str, Any]
ResultRow = dict[str, Any]

LONG_RUN_MIN_LAPS = 5
# Laps slower than this fraction of the stint's best are treated as traffic/SC/cool-down.
REPRESENTATIVE_THRESHOLD = 1.07


def _stint_lookup(stints: list[StintRow]) -> dict[int, list[StintRow]]:
    out: dict[int, list[StintRow]] = defaultdict(list)
    for s in stints:
        out[s["driver_id"]].append(s)
    for v in out.values():
        v.sort(key=lambda s: s.get("lap_start") or 0)
    return out


def _stint_for_lap(stints: list[StintRow], lap_number: int) -> StintRow | None:
    for s in stints:
        if s.get("lap_start") is not None and s.get("lap_end") is not None and s["lap_start"] <= lap_number <= s["lap_end"]:
            return s
    return None


def representative_laps(laps: list[LapRow]) -> list[LapRow]:
    """Drop pit laps, missing times and laps >7% off the group's best."""
    valid = [lp for lp in laps if lp.get("lap_time_ms") and not lp.get("is_pit_lap")]
    if not valid:
        return []
    best = min(lp["lap_time_ms"] for lp in valid)
    return [lp for lp in valid if lp["lap_time_ms"] <= best * REPRESENTATIVE_THRESHOLD]


def compute_long_run_pace(laps: list[LapRow], stints: list[StintRow]) -> list[dict]:
    """Per driver + compound: average of representative laps from stints of >= 5 laps."""
    by_driver_stint: dict[tuple[int, int], list[LapRow]] = defaultdict(list)
    lookup = _stint_lookup(stints)
    for lp in laps:
        st = _stint_for_lap(lookup.get(lp["driver_id"], []), lp["lap_number"])
        if st is None:
            continue
        by_driver_stint[(lp["driver_id"], st["stint_number"])].append(lp)

    per_compound: dict[tuple[int, str], list[int]] = defaultdict(list)
    for (driver_id, stint_number), stint_laps in by_driver_stint.items():
        rep = representative_laps(stint_laps)
        if len(rep) < LONG_RUN_MIN_LAPS:
            continue
        st = next(s for s in lookup[driver_id] if s["stint_number"] == stint_number)
        compound = st.get("compound") or "UNKNOWN"
        per_compound[(driver_id, compound)].extend(lp["lap_time_ms"] for lp in rep)

    return [
        dict(driver_id=d, compound=c, avg_lap_time_ms=int(round(mean(times))), lap_count=len(times))
        for (d, c), times in per_compound.items()
    ]


def compute_qualifying_segments(results: list[ResultRow]) -> list[dict]:
    out = []
    for seg, key in (("Q1", "q1_ms"), ("Q2", "q2_ms"), ("Q3", "q3_ms")):
        times = [(r["driver_id"], r[key]) for r in results if r.get(key)]
        if not times:
            continue
        leader = min(t for _, t in times)
        out.extend(dict(driver_id=d, segment=seg, best_lap_ms=t, gap_to_segment_leader_ms=t - leader) for d, t in times)
    return out


def compute_stint_timeline(stints: list[StintRow]) -> list[dict]:
    return [
        dict(driver_id=s["driver_id"], stint_number=s["stint_number"], compound=s.get("compound"), lap_start=s.get("lap_start"), lap_end=s.get("lap_end"))
        for s in stints
    ]


def compute_degradation(laps: list[LapRow], stints: list[StintRow]) -> list[dict]:
    lookup = _stint_lookup(stints)
    out = []
    for lp in laps:
        if not lp.get("lap_time_ms") or lp.get("is_pit_lap"):
            continue
        st = _stint_for_lap(lookup.get(lp["driver_id"], []), lp["lap_number"])
        if st is None:
            continue
        out.append(
            dict(
                driver_id=lp["driver_id"],
                stint_number=st["stint_number"],
                lap_number_in_stint=lp["lap_number"] - st["lap_start"] + 1,
                lap_time_ms=lp["lap_time_ms"],
            )
        )
    return out


def compute_position_by_lap(laps: list[LapRow]) -> list[dict]:
    return [
        dict(driver_id=lp["driver_id"], lap_number=lp["lap_number"], position=lp["position"])
        for lp in laps
        if lp.get("position") is not None
    ]


def compute_sector_deltas(laps: list[LapRow]) -> list[dict]:
    """Every lap, every sector, vs the session-best sector time (from clean laps)."""
    keys = {1: "sector_1_ms", 2: "sector_2_ms", 3: "sector_3_ms"}
    best: dict[int, int] = {}
    for lp in laps:
        if lp.get("is_pit_lap"):
            continue
        for sec, k in keys.items():
            v = lp.get(k)
            # ignore implausibly short sectors (< 5s) which are data glitches
            if v and v >= 5000 and (sec not in best or v < best[sec]):
                best[sec] = v
    out = []
    for lp in laps:
        for sec, k in keys.items():
            v = lp.get(k)
            if not v or sec not in best:
                continue
            out.append(
                dict(
                    driver_id=lp["driver_id"],
                    lap_number=lp["lap_number"],
                    sector=sec,
                    driver_sector_ms=v,
                    session_best_sector_ms=best[sec],
                    delta_ms=v - best[sec],
                )
            )
    return out
