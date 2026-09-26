import math
from datetime import datetime, timedelta

from f1tracker.analysis.track import compute_boost_zones, geo_project, pca_rotate


def test_pca_rotate_aligns_long_axis_horizontal():
    # a tall, narrow "sideways" oval: mostly vertical extent
    raw = [{"x": math.sin(t) * 5, "y": math.cos(t) * 50} for t in [i * 0.1 for i in range(63)]]
    rotated = pca_rotate(raw)
    xs = [p["x"] for p in rotated]
    ys = [p["y"] for p in rotated]
    assert (max(xs) - min(xs)) > (max(ys) - min(ys))  # now wider than tall


def test_geo_project_centers_on_circuit_and_returns_square_bbox():
    raw = [{"x": 100.0, "y": 0.0}, {"x": -100.0, "y": 0.0}, {"x": 0.0, "y": 50.0}, {"x": 0.0, "y": -50.0}]
    points, bbox = geo_project(raw, lat0=45.0, lon0=10.0)
    assert len(points) == 4
    # bbox roughly centred on the circuit reference point
    assert abs((bbox["south"] + bbox["north"]) / 2 - 45.0) < 1e-6
    assert abs((bbox["west"] + bbox["east"]) / 2 - 10.0) < 1e-6
    # square in degrees-of-meters terms isn't exact, but north-south and east-west spans
    # should be within a few percent once corrected for latitude
    lat_span_m = (bbox["north"] - bbox["south"]) * 111_320.0
    lon_span_m = (bbox["east"] - bbox["west"]) * 111_320.0 * math.cos(math.radians(45.0))
    assert abs(lat_span_m - lon_span_m) < 1.0


def test_compute_boost_zones_estimates_from_full_throttle_when_no_drs_field():
    base = datetime(2026, 1, 1)
    times = [base + timedelta(milliseconds=270 * i) for i in range(12)]
    # samples: ramp up, sustained full-throttle/high-speed run (indices 3-8), then off
    car_data = [
        {"date": (base + timedelta(milliseconds=270 * i)).isoformat() + "Z", "throttle": 100 if 3 <= i <= 8 else 40, "speed": 320 if 3 <= i <= 8 else 150, "drs": None}
        for i in range(12)
    ]
    zones, source = compute_boost_zones(times, car_data)
    assert source == "estimated_throttle"
    assert zones == [[3, 8]]


def test_compute_boost_zones_prefers_real_drs_field_when_present():
    base = datetime(2026, 1, 1)
    times = [base + timedelta(milliseconds=270 * i) for i in range(10)]
    car_data = [
        {"date": (base + timedelta(milliseconds=270 * i)).isoformat() + "Z", "throttle": 100, "speed": 300, "drs": 12 if 2 <= i <= 6 else 0}
        for i in range(10)
    ]
    zones, source = compute_boost_zones(times, car_data)
    assert source == "telemetry"
    assert zones == [[2, 6]]
