"""Turn-by-turn: lap traces anchored on the line and checked (#48), corners ranked across the session (#49)."""
import math
from datetime import datetime, timedelta, timezone

import pytest

from f1tracker.analysis.turns import lap_trace, plausibility_problem, rank_session_corners

R = 500.0  # a circular "track" of radius 500 m: 3,141.6 m a lap
LAP_MS = 60_000
T0 = datetime(2026, 9, 24, 9, 0, tzinfo=timezone.utc)


def _polyline(n: int = 300) -> tuple[list[dict], list[float]]:
    pts = [{"x": R * math.cos(2 * math.pi * i / n), "y": R * math.sin(2 * math.pi * i / n)} for i in range(n)]
    dist = [2 * math.pi * R * i / n for i in range(n)]
    return pts, dist


def _drive(start: datetime, lap_ms: float = LAP_MS, pad_s: float = 5.0, hz: float = 3.7) -> list[dict]:
    """Samples of a car going round at constant speed, the lap starting at `start` at angle 0."""
    out, t = [], -pad_s * 1000
    while t <= lap_ms + pad_s * 1000:
        a = 2 * math.pi * t / lap_ms
        out.append({"x": R * math.cos(a), "y": R * math.sin(a), "date": (start + timedelta(milliseconds=t)).isoformat()})
        t += 1000 / hz
    return out


def _ms(dt: datetime) -> float:
    return dt.timestamp() * 1000


def test_a_clean_lap_takes_its_official_time_from_line_to_line():
    poly, dist = _polyline()
    xs, ys = lap_trace(poly, dist, _drive(T0), _ms(T0), LAP_MS)
    assert xs[0] == 0 and ys[0] == 0
    assert ys[-1] == pytest.approx(LAP_MS, abs=50)
    # half way round is half the lap
    half = next(y for x, y in zip(xs, ys) if x >= math.pi * R)
    assert half == pytest.approx(LAP_MS / 2, abs=300)


def test_a_lap_whose_official_start_is_seconds_off_is_anchored_on_the_line_itself():
    """#48: the old method assumed the fetch window started on the line, so a shifted start put
    the shift into T1 and took it out of the last corner."""
    poly, dist = _polyline()
    raw = _drive(T0)
    xs, ys = lap_trace(poly, dist, raw, _ms(T0 + timedelta(seconds=3)), LAP_MS)
    quarter = next(y for x, y in zip(xs, ys) if x >= math.pi * R / 2)
    assert quarter == pytest.approx(LAP_MS / 4, abs=300)


def test_a_frozen_feed_is_rejected_not_drawn():
    """#48, Baku FP1 Norris: the car sat at one x/y for the whole lap, so T1 read +98.9s."""
    poly, dist = _polyline()
    raw = [{"x": 120.0, "y": -480.0, "date": (T0 + timedelta(milliseconds=270 * i)).isoformat()} for i in range(260)]
    with pytest.raises(ValueError, match="whole lap"):
        lap_trace(poly, dist, raw, _ms(T0), LAP_MS)


def test_a_trace_that_does_not_match_the_official_lap_time_is_rejected():
    poly, dist = _polyline()
    with pytest.raises(ValueError, match="official"):
        lap_trace(poly, dist, _drive(T0), _ms(T0), LAP_MS + 5000)


def test_a_hole_in_the_feed_is_rejected():
    poly, dist = _polyline()
    raw = [p for p in _drive(T0) if not (T0 + timedelta(seconds=20) < datetime.fromisoformat(p["date"]) < T0 + timedelta(seconds=26))]
    with pytest.raises(ValueError, match="gap"):
        lap_trace(poly, dist, raw, _ms(T0), LAP_MS)


def _payload(deltas, corner_ms=None, lap_delta=None, ref=(7, 14), lap_ms=100_000, unattributed=0.0):
    turns = [{"number": i + 1, "delta_ms": d, **({"corner_ms": c} if corner_ms else {})} for i, (d, c) in enumerate(zip(deltas, corner_ms or deltas))]
    return {"turns": turns, "total_lap_delta_ms": sum(deltas) if lap_delta is None else lap_delta, "unattributed_ms": unattributed,
            "is_reference_lap": False, "reference": {"driver_id": ref[0], "lap_number": ref[1]}, "lap_time_ms": lap_ms}


def test_the_plausibility_gate():
    assert plausibility_problem(_payload([100, -50, 200])) is None
    # Baku FP1 Norris as published: +98.9s at T1, the rest faster than the session best
    assert "T1" in plausibility_problem(_payload([98884.1, -10837.4, -9377.0], lap_delta=1594))
    # 20% of a long corner's own time is allowed (a 10s corner may lose 1.9s), 1.5s is the floor
    assert plausibility_problem(_payload([1900, 0], corner_ms=[10_000, 5_000])) is None
    assert plausibility_problem(_payload([1600, 0], corner_ms=[5_000, 5_000])) is not None
    # corners that cancel out: each under the bound, the lap delta tiny
    assert plausibility_problem(_payload([1400, -1400, 1400, -1400], lap_delta=10)) == "corner deltas cancel out"
    # a long lap may scatter a little more: 20 corners of +-180ms on a 0.4s lap delta is a clean Baku lap
    assert plausibility_problem(_payload([180, -180] * 10, lap_delta=400)) is None
    assert plausibility_problem(_payload([100, 100], unattributed=4000)) is not None


def test_purple_is_the_fastest_of_anyone_through_that_corner():
    """#49: purple used to mean "beat the reference lap by 30ms", so a quarter of all corners were purple."""
    shown, withheld = rank_session_corners({
        1: _payload([0, 0, 0], lap_ms=100_000),
        2: _payload([-40, 120, 300], lap_ms=100_380),
        3: _payload([-40, -60, 10], lap_ms=99_910),
        4: _payload([98884.1, -10837.4, -9377.0], lap_delta=1594),
    })
    assert withheld == {4: "implausible corner delta at T1"}
    ranks = {d: [t["rank"] for t in p["turns"]] for d, p in shown.items()}
    assert ranks == {1: [3, 2, 1], 2: [2, 3, 3], 3: [1, 1, 2]}  # T1 tie: driver 3's faster lap wins
    assert all(t["of"] == 3 for p in shown.values() for t in p["turns"])


def test_breakdowns_against_another_reference_lap_are_not_ranked_with_the_rest():
    shown, withheld = rank_session_corners({1: _payload([0, 0]), 2: _payload([10, 10]), 4: _payload([20, 20]), 3: _payload([5, 5], ref=(9, 3))})
    assert set(shown) == {1, 2, 4} and withheld == {3: "measured against a different reference lap"}


def test_a_session_whose_breakdowns_mostly_fail_shows_none():
    """Session 16 FP1 before the fix: the reference trace covered a quarter of the lap, so 21 of 22
    breakdowns failed and the one left ranked "1st of 1" at every corner."""
    broken = {d: _payload([12000, -37000], lap_delta=29000) for d in range(1, 5)}
    shown, withheld = rank_session_corners({**broken, 9: _payload([0, 0]), 10: _payload([30, 10])})
    assert shown == {} and set(withheld) == {1, 2, 3, 4, 9, 10}
    assert rank_session_corners({1: _payload([0, 0]), 2: _payload([30, 10])})[0] == {}  # nothing ranked of 2
