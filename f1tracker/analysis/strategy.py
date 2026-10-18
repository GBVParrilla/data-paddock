"""Computed strategy verdicts: facts the stories can state instead of hedging around.

Everything here is deterministic and works from positions per lap, pit stops, stints, lap start
times and the neutralisation periods. Conventions:
  - a pit stop's `in_lap` is the lap the car entered the pits at the end of (it rejoins on in_lap + 1);
  - positions are at the end of a lap;
  - race-control laps are the leader's, so neutralisation windows are widened by one lap.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from statistics import median

# A stop counts as "under" a neutralisation if it happened within the period (+1 lap for cars a lap down).
JUST_BEFORE_LAPS = 3  # pitted up to this many laps before a neutralisation: the unlucky case
JUST_AFTER_LAPS = 3  # pitted this soon after one ended: missed the cheap stop
UNDERCUT_MAX_GAP_MS = 3000  # cars this close (or adjacent when no timing) are in a pit battle
UNDERCUT_MAX_LAPS_APART = 8
CYCLE_MAX_LAPS = 25  # a rival stopping later than this isn't part of the same pit cycle
SLOW_STOP_MS = 4000  # stationary
# Under a red flag the whole field waits in the pit lane and OpenF1 logs it as a stop of many minutes.
SUSPENSION_LANE_MS = 120_000


def is_suspension(pit: dict) -> bool:
    return bool(pit.get("lane_duration_ms") and pit["lane_duration_ms"] >= SUSPENSION_LANE_MS)


def real_stops(pits: list[dict]) -> list[dict]:
    """Pit stops a team chose to make (not the field queuing in the pit lane during a red flag)."""
    return [p for p in pits if not is_suspension(p)]
SLOW_LANE_MARGIN_MS = 4000  # pit-lane time this much over the session median


@dataclass
class StopVerdict:
    driver_id: int
    in_lap: int
    stop_number: int
    stationary_ms: int | None
    lane_ms: int | None
    lane_vs_median_ms: int | None
    compound_from: str | None
    compound_to: str | None
    neutralisation: str | None = None  # "during" | "just_before" | "just_after"
    neutralisation_kind: str | None = None  # SC | VSC | RED
    neutralisation_laps: tuple[int | None, int | None] | None = None
    position_before: int | None = None  # end of the lap before the in-lap
    position_after_cycle: int | None = None
    cycle_end_lap: int | None = None
    net_places: int | None = None  # + gained, - lost, once the cars around had stopped too
    slow: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class PitBattle:
    """Two cars running together, stopping within a few laps of each other."""

    attacker_id: int  # stopped first
    defender_id: int
    attacker_lap: int
    defender_lap: int
    attacker_was_behind: bool
    gap_before_ms: int | None
    attacker_ahead_after: bool
    verdict: str  # undercut_worked | undercut_failed | overcut_worked | stayed_ahead
    under_neutralisation: bool = False
    decided_lap: int = 0
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _stint_compounds(stints: list[dict], driver_id: int, in_lap: int) -> tuple[str | None, str | None]:
    mine = sorted((s for s in stints if s["driver_id"] == driver_id), key=lambda s: s["stint_number"])
    before = next((s for s in mine if s.get("lap_start") is not None and s.get("lap_end") is not None and s["lap_start"] <= in_lap <= s["lap_end"]), None)
    after = next((s for s in mine if s.get("lap_start") is not None and s["lap_start"] > in_lap), None)
    # OpenF1 stints sometimes end on the out-lap rather than the in-lap: fall back to stint order
    if before is None or (after is not None and before is after):
        idx = next((i for i, s in enumerate(mine) if (s.get("lap_start") or 0) > in_lap), len(mine))
        before = mine[idx - 1] if idx >= 1 else None
        after = mine[idx] if idx < len(mine) else None
    return (before or {}).get("compound"), (after or {}).get("compound")


def neutralisation_relation(in_lap: int, periods: list[dict]) -> tuple[str | None, dict | None]:
    """How a stop relates to the session's SC/VSC/red-flag periods."""
    best: tuple[str | None, dict | None] = (None, None)
    for p in periods:
        start = p.get("start_lap")
        end = p.get("end_lap") or start
        if start is None:
            continue
        if start - 1 <= in_lap <= end:
            return "during", p
        if start - JUST_BEFORE_LAPS - 1 <= in_lap < start - 1 and best[0] is None:
            best = ("just_before", p)
        elif end < in_lap <= end + JUST_AFTER_LAPS and best[0] is None:
            best = ("just_after", p)
    return best


def _gap_ms(starts: dict[int, dict[int, datetime]], a: int, b: int, lap: int) -> int | None:
    """Time gap a - b at the end of `lap` (positive: a behind b), from the next lap's start times."""
    ta, tb = starts.get(a, {}).get(lap + 1), starts.get(b, {}).get(lap + 1)
    if ta is None or tb is None:
        return None
    return int((ta - tb).total_seconds() * 1000)


def analyse_stops(
    pits: list[dict],
    stints: list[dict],
    positions: dict[int, dict[int, int]],
    periods: list[dict],
) -> list[StopVerdict]:
    pits = real_stops(pits)
    lanes = [p["lane_duration_ms"] for p in pits if p.get("lane_duration_ms")]
    lane_median = median(lanes) if lanes else None
    by_driver: dict[int, list[dict]] = {}
    for p in sorted(pits, key=lambda p: p["lap_number"]):
        by_driver.setdefault(p["driver_id"], []).append(p)
    stop_laps = {d: [p["lap_number"] for p in ps] for d, ps in by_driver.items()}
    out = []
    for did, ps in by_driver.items():
        for n, p in enumerate(ps, start=1):
            lap = p["lap_number"]
            c_from, c_to = _stint_compounds(stints, did, lap)
            rel, period = neutralisation_relation(lap, periods)
            lane = p.get("lane_duration_ms")
            v = StopVerdict(
                driver_id=did,
                in_lap=lap,
                stop_number=n,
                stationary_ms=p.get("duration_ms"),
                lane_ms=lane,
                lane_vs_median_ms=int(lane - lane_median) if (lane and lane_median) else None,
                compound_from=c_from,
                compound_to=c_to,
                neutralisation=rel,
                neutralisation_kind=period["kind"] if period else None,
                neutralisation_laps=(period["start_lap"], period.get("end_lap")) if period else None,
            )
            v.slow = bool((v.stationary_ms and v.stationary_ms >= SLOW_STOP_MS) or (v.lane_vs_median_ms and v.lane_vs_median_ms >= SLOW_LANE_MARGIN_MS))
            mine = positions.get(did, {})
            v.position_before = mine.get(lap - 1)
            if v.position_before is not None:
                # the cycle ends once every car that was within 3 places has made its own stop
                # (cars that don't stop again within CYCLE_MAX_LAPS aren't part of this cycle)
                around = [
                    o for o, pos in positions.items()
                    if o != did and pos.get(lap - 1) is not None and abs(pos[lap - 1] - v.position_before) <= 3
                ]
                end = lap + 2
                for o in around:
                    nxt = next((l for l in stop_laps.get(o, []) if lap - 3 <= l <= lap + CYCLE_MAX_LAPS), None)
                    if nxt is not None:
                        end = max(end, nxt + 2)
                after_lap = max((l for l in mine if l <= end), default=None)
                if after_lap is not None and after_lap > lap:
                    v.cycle_end_lap = after_lap
                    v.position_after_cycle = mine[after_lap]
                    v.net_places = v.position_before - v.position_after_cycle
            out.append(v)
    return out


def pit_battles(
    pits: list[dict],
    positions: dict[int, dict[int, int]],
    lap_starts: dict[int, dict[int, datetime]],
    periods: list[dict],
) -> list[PitBattle]:
    """Undercut/overcut verdicts for cars that were running together when the first of them pitted."""
    first_stop: dict[int, list[int]] = {}
    for p in sorted(real_stops(pits), key=lambda p: p["lap_number"]):
        first_stop.setdefault(p["driver_id"], []).append(p["lap_number"])
    out = []
    seen = set()
    for a, a_laps in first_stop.items():
        for la in a_laps:
            pa = positions.get(a, {}).get(la - 1)
            if pa is None:
                continue
            for b, b_laps in first_stop.items():
                if b == a or (b, a) in seen:
                    continue
                lb = next((l for l in b_laps if la < l <= la + UNDERCUT_MAX_LAPS_APART), None)
                if lb is None:
                    continue
                pb = positions.get(b, {}).get(la - 1)
                if pb is None or abs(pa - pb) != 1:
                    continue
                gap = _gap_ms(lap_starts, a, b, la - 1)
                if gap is not None and abs(gap) > UNDERCUT_MAX_GAP_MS:
                    continue
                decided = lb + 2
                pa_after, pb_after = positions.get(a, {}).get(decided), positions.get(b, {}).get(decided)
                if pa_after is None or pb_after is None:
                    continue
                behind = pa > pb
                ahead_after = pa_after < pb_after
                if behind:
                    verdict = "undercut_worked" if ahead_after else "undercut_failed"
                else:
                    verdict = "stayed_ahead" if ahead_after else "overcut_worked"
                neutral = any(neutralisation_relation(l, periods)[0] == "during" for l in (la, lb))
                seen.add((a, b))
                out.append(PitBattle(a, b, la, lb, behind, gap, ahead_after, verdict, neutral, decided))
    return out
