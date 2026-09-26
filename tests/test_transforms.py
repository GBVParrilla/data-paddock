from f1tracker.analysis.pivotal import Moment, detect_position_swings
from f1tracker.clients.jolpica import parse_lap_time_ms
from f1tracker.ingest.details import compound_for_lap, parse_laps
from f1tracker.transforms import detail, headline


def test_parse_lap_time():
    assert parse_lap_time_ms("1:18.518") == 78518
    assert parse_lap_time_ms("78.5") == 78500
    assert parse_lap_time_ms(None) is None


def test_headline_practice_ranks_and_gaps():
    laps = [
        {"driver_id": 1, "lap_number": 1, "lap_time_ms": 80000, "is_pit_lap": False},
        {"driver_id": 1, "lap_number": 2, "lap_time_ms": 79000, "is_pit_lap": False},
        {"driver_id": 2, "lap_number": 1, "lap_time_ms": 79500, "is_pit_lap": False},
        {"driver_id": 3, "lap_number": 1, "lap_time_ms": 70000, "is_pit_lap": True},  # pit lap ignored
    ]
    rows = headline.compute_headline_practice(laps)
    assert [(r["driver_id"], r["rank"], r["gap_to_fastest_ms"]) for r in rows] == [(1, 1, 0), (2, 2, 500)]


def test_headline_qualifying_elimination():
    results = [
        {"driver_id": 1, "position": 1, "q1_ms": 80000, "q2_ms": 79500, "q3_ms": 79000},
        {"driver_id": 2, "position": 12, "q1_ms": 80500, "q2_ms": 80400, "q3_ms": None},
        {"driver_id": 3, "position": 18, "q1_ms": 81000, "q2_ms": None, "q3_ms": None},
    ]
    rows = {r["driver_id"]: r for r in headline.compute_headline_qualifying(results)}
    assert rows[1]["eliminated_in"] is None and rows[1]["gap_to_pole_ms"] == 0
    assert rows[2]["eliminated_in"] == "Q2" and rows[2]["gap_to_pole_ms"] == 1400
    assert rows[3]["eliminated_in"] == "Q1"


def test_sector_deltas_use_session_best():
    laps = [
        {"driver_id": 1, "lap_number": 1, "sector_1_ms": 30000, "sector_2_ms": 18000, "sector_3_ms": 36000, "is_pit_lap": False},
        {"driver_id": 2, "lap_number": 1, "sector_1_ms": 29500, "sector_2_ms": 18200, "sector_3_ms": 36500, "is_pit_lap": False},
    ]
    rows = detail.compute_sector_deltas(laps)
    d = {(r["driver_id"], r["sector"]): r["delta_ms"] for r in rows}
    assert d[(1, 1)] == 500 and d[(2, 1)] == 0
    assert d[(1, 2)] == 0 and d[(2, 2)] == 200


def test_long_run_pace_requires_five_clean_laps():
    stints = [{"driver_id": 1, "stint_number": 1, "compound": "HARD", "lap_start": 1, "lap_end": 8}]
    laps = [{"driver_id": 1, "lap_number": i, "lap_time_ms": 80000 + i * 10, "is_pit_lap": i == 1} for i in range(1, 9)]
    laps.append({"driver_id": 1, "lap_number": 9, "lap_time_ms": 120000, "is_pit_lap": False})  # outside stint
    rows = detail.compute_long_run_pace(laps, stints)
    assert len(rows) == 1 and rows[0]["compound"] == "HARD" and rows[0]["lap_count"] == 7


def test_parse_laps_pit_in_lap_from_openf1_out_lap():
    laps = [
        {"driver_number": 63, "lap_number": 11, "date_start": "2026-03-08T04:20:00+00:00", "lap_duration": 90.0, "duration_sector_1": 30.0, "duration_sector_2": 18.0, "duration_sector_3": 42.0, "st_speed": 300, "is_pit_out_lap": False},
        {"driver_number": 63, "lap_number": 12, "date_start": "2026-03-08T04:21:30+00:00", "lap_duration": 95.0, "duration_sector_1": 35.0, "duration_sector_2": 18.0, "duration_sector_3": 42.0, "st_speed": 280, "is_pit_out_lap": True},
    ]
    stints = [{"driver_number": 63, "stint_number": 1, "compound": "MEDIUM", "lap_start": 1, "lap_end": 11, "tyre_age_at_start": 0}, {"driver_number": 63, "stint_number": 2, "compound": "HARD", "lap_start": 12, "lap_end": 58, "tyre_age_at_start": 0}]
    pits = [{"driver_number": 63, "lap_number": 12}]  # OpenF1 reports the out-lap
    rows = {r["lap_number"]: r for r in parse_laps(laps, stints, pits, [], race_like=False)}
    assert rows[11]["is_pit_lap"] and rows[12]["is_pit_lap"]
    assert rows[11]["compound"] == "MEDIUM" and rows[11]["tyre_life"] == 11
    assert rows[12]["compound"] == "HARD" and rows[12]["tyre_life"] == 1
    assert compound_for_lap(stints, 30) == ("HARD", 19)


def test_position_swings_skip_pit_laps():
    pos = {1: {1: 10, 2: 10, 3: 6, 4: 6, 5: 9}}
    names = {1: "Test Driver"}
    swings = detect_position_swings(pos, pit_laps={(1, 5)}, names=names)
    assert len(swings) == 1
    m: Moment = swings[0]
    assert m.lap_number == 3 and "gained 4 places" in m.description
