from f1tracker.clients.jolpica import parse_lap_time_ms
from f1tracker.ingest.details import align_pit_laps, compound_for_lap, parse_laps
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
    rows = {r["driver_id"]: r for r in headline.compute_headline_qualifying(results, entrants=[1, 2, 3, 4])}
    assert rows[1]["eliminated_in"] is None and rows[1]["gap_to_pole_ms"] == 0 and rows[1]["gap_segment"] == "Q3"
    # a Q2 exit is compared with the fastest Q2 time, never with pole's Q3 lap (REVIEW #7)
    assert rows[2]["eliminated_in"] == "Q2" and rows[2]["gap_to_pole_ms"] == 900 and rows[2]["gap_segment"] == "Q2"
    assert rows[3]["eliminated_in"] == "Q1" and rows[3]["gap_to_pole_ms"] == 1000 and rows[3]["gap_segment"] == "Q1"
    # an entrant with no time is still listed
    assert rows[4]["status_code"] == "NO_TIME" and rows[4]["position"] is None and rows[4]["gap_to_pole_ms"] is None


def test_q3_runner_without_a_q3_time_is_still_a_q3_runner():
    results = [{"driver_id": i, "position": i, "q1_ms": 80000 + i, "q2_ms": 79000 + i if i <= 15 else None, "q3_ms": 78000 + i if i < 10 else None} for i in range(1, 21)]
    rows = {r["driver_id"]: r for r in headline.compute_headline_qualifying(results)}
    assert rows[10]["eliminated_in"] is None and rows[10]["gap_to_pole_ms"] is None
    assert rows[11]["eliminated_in"] == "Q2" and rows[16]["eliminated_in"] == "Q1"


def test_race_status_codes():
    rs = headline.race_status
    assert rs("1", "Finished", 58, 58) == ("FIN", 1)
    assert rs("7", "Lapped", 57, 58) == ("LAP", 7)
    assert rs("R", "Lapped", 43, 58) == ("DNF", None)  # running at the end but not classified (REVIEW #6)
    assert rs("R", "Retired", 10, 58) == ("DNF", None)
    assert rs("W", "Did not start", 0, 58) == ("DNS", None)
    assert rs("18", "Retired", 59, 62) == ("DNF", 18)  # classified retirement (REVIEW #13)
    assert rs("D", "Disqualified", 58, 58) == ("DSQ", None)


def test_headline_race_order_and_counts():
    results = [
        {"driver_id": 1, "position": 1, "position_text": "1", "status": "Finished", "laps_completed": 58, "grid_position": 2, "points": 25},
        {"driver_id": 2, "position": 2, "position_text": "2", "status": "Lapped", "laps_completed": 57, "grid_position": 1, "points": 18},
        {"driver_id": 3, "position": 3, "position_text": "R", "status": "Retired", "laps_completed": 10, "grid_position": 3},
        {"driver_id": 4, "position": 4, "position_text": "W", "status": "Did not start", "laps_completed": 0, "grid_position": 5},
    ]
    rows = headline.compute_headline_race(results, [{"driver_id": 1, "lap_number": 20, "lane_duration_ms": 22000}, {"driver_id": 1, "lap_number": 2, "lane_duration_ms": 1_500_000}])
    assert [r["status_code"] for r in rows] == ["FIN", "LAP", "DNF", "DNS"]
    assert rows[0]["pit_stop_count"] == 1  # the red-flag "stop" isn't a pit stop
    assert rows[1]["laps_down"] == 1 and rows[2]["finish_position"] is None and rows[2]["positions_gained"] is None
    assert headline.race_counts(rows) == {"classified": 2, "dnf": 1, "dns": 1, "dsq": 0}


def test_position_by_lap_takes_the_final_lap_from_the_classification():
    laps = [{"driver_id": 1, "lap_number": n, "position": 1} for n in range(1, 58)] + [{"driver_id": 1, "lap_number": 58, "position": None}]
    rows = detail.compute_position_by_lap(laps, {1: (1, 58), 2: (None, 10)})
    assert max(r["lap_number"] for r in rows) == 58  # REVIEW #12


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
    pits = [{"driver_number": 63, "lap_number": 12}]  # OpenF1 reports the out-lap here
    rows = {r["lap_number"]: r for r in parse_laps(laps, stints, pits, [], race_like=False)}
    assert rows[11]["is_pit_lap"] and rows[12]["is_pit_lap"]
    assert rows[11]["compound"] == "MEDIUM" and rows[11]["tyre_life"] == 11
    assert rows[12]["compound"] == "HARD" and rows[12]["tyre_life"] == 1
    assert compound_for_lap(stints, 30) == ("HARD", 19)


def test_pit_in_lap_follows_the_out_lap_flag_whatever_openf1_numbers_the_stop():
    laps = [{"driver_number": 4, "lap_number": n, "is_pit_out_lap": n == 63} for n in range(55, 68)]
    # at some events OpenF1's pit lap_number is the in-lap (62), at others the out-lap (63)
    assert align_pit_laps([{"driver_number": 4, "lap_number": 62}], laps) == {(4, 62): 62}
    assert align_pit_laps([{"driver_number": 4, "lap_number": 63}], laps) == {(4, 63): 62}
    # retired in the pits: no out-lap follows
    assert align_pit_laps([{"driver_number": 4, "lap_number": 67}], laps) == {(4, 67): 67}
