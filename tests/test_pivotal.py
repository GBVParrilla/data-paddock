from datetime import datetime, timedelta
from types import SimpleNamespace

from f1tracker.analysis.pivotal import compute_pivotal_moments, detect_race_control_moments


def _rc(i, msg, category=None, flag=None, lap=None, driver_id=None):
    return SimpleNamespace(timestamp=datetime(2026, 3, 8, 4) + timedelta(minutes=i), message=msg, category=category, flag=flag, lap_number=lap, driver_id=driver_id)


def test_vsc_period_counts_pit_stops_and_penalties():
    msgs = [
        _rc(0, "VSC DEPLOYED", category="SafetyCar", lap=12),
        _rc(1, "FIA STEWARDS: STOP-AND-GO PENALTY FOR CAR 43 (COL) - STARTING PROCEDURE INFRINGEMENT", category="Other", lap=8, driver_id=16),
        _rc(2, "FIA STEWARDS: INCIDENT INVOLVING CAR 27 (HUL) UNDER INVESTIGATION", category="Other", lap=9),
        _rc(3, "VSC ENDING", category="SafetyCar", lap=14),
        _rc(4, "RED FLAG", flag="RED", category="Flag", lap=None),
    ]
    pits = [SimpleNamespace(lap_number=12, driver_id=1), SimpleNamespace(lap_number=13, driver_id=2), SimpleNamespace(lap_number=30, driver_id=3)]
    moments = detect_race_control_moments(msgs, pits, {16: "Franco Colapinto"})
    by_type = {m.moment_type: m for m in moments}
    assert "2 pit stop(s)" in by_type["safety_car"].description or any("2 pit stop(s)" in m.description for m in moments)
    assert by_type["penalty"].magnitude_score == 6.0 and "Colapinto" in by_type["penalty"].description
    assert sum(1 for m in moments if m.moment_type == "penalty") == 1  # investigation notice ignored
    assert any("Red flag at" in m.description for m in moments)


def test_compute_pivotal_moments_caps_and_dedupes():
    laps = [SimpleNamespace(driver_id=1, lap_number=n, lap_time_ms=80000 - n, is_pit_lap=False, compound="SOFT", tyre_life=n) for n in range(1, 30)]
    msgs = [_rc(0, "RED FLAG", flag="RED", category="Flag") for _ in range(3)]  # identical -> deduped
    moments = compute_pivotal_moments("Q", [], [], [], msgs, laps, {1: "A"})
    assert [m.moment_type for m in moments] == ["safety_car", "fastest_lap"]
