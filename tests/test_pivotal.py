from datetime import datetime, timedelta
from types import SimpleNamespace

from f1tracker.analysis.pivotal import Context, compute_moments
from f1tracker.analysis.race_control import cases, classify, neutral_periods, parse_messages, tidy
from f1tracker.analysis.strategy import analyse_stops, neutralisation_relation, pit_battles

T0 = datetime(2026, 3, 8, 4)


def _rc(i, msg, category="Other", flag=None, lap=None, driver_id=None):
    return SimpleNamespace(timestamp=T0 + timedelta(minutes=i), message=msg, category=category, flag=flag, lap_number=lap, driver_id=driver_id)


def test_classifier_types_and_shared_cases():
    msgs = [
        _rc(0, "VSC DEPLOYED", "SafetyCar", lap=12),
        _rc(1, "VSC ENDING", "SafetyCar", lap=14),
        _rc(2, "TURN 3 INCIDENT INVOLVING CARS 31 (OCO) AND 10 (GAS) NOTED", lap=23),
        _rc(3, "FIA STEWARDS: TURN 3 INCIDENT INVOLVING CARS 31 (OCO) AND 10 (GAS) NO FURTHER ACTION", lap=33),
        _rc(4, "FIA STEWARDS: STOP-AND-GO PENALTY FOR CAR 43 (COL) - STARTING PROCEDURE INFRINGEMENT", lap=8),
        _rc(5, "SESSION ABORTED", "SessionStatus", lap=40),
        _rc(6, "VSC DEPLOYED", "SafetyCar", lap=50),
        _rc(7, "VSC ENDING", "SafetyCar", lap=50),
        _rc(8, "PIT EXIT CLOSED", lap=40),
    ]
    incs = parse_messages(msgs, {31: 11, 10: 18, 43: 16})
    assert [i.kind for i in incs] == ["neutralisation", "neutralisation", "investigation", "decision", "penalty", "red_flag", "neutralisation", "neutralisation"]
    assert incs[2].driver_ids == [11, 18] and incs[2].turn == 3
    assert incs[4].reason == "STARTING PROCEDURE INFRINGEMENT" and incs[4].outcome == "stop-and-go penalty"
    periods = neutral_periods(incs)
    assert [(p["kind"], p["start_lap"], p["end_lap"]) for p in periods] == [("VSC", 12, 14), ("RED", 40, 40), ("VSC", 50, 50)]
    (case,) = [c for c in cases(incs) if len(c["driver_ids"]) == 2]  # one shared fact for both drivers (REVIEW #16)
    assert case["driver_ids"] == [11, 18] and case["outcome"] == "no further action"
    assert tidy("FIA STEWARDS: TURN 3 INCIDENT INVOLVING CARS 31 (OCO) AND 10 (GAS) NOTED") == "Stewards: turn 3 incident involving cars 31 (OCO) and 10 (GAS) noted"
    assert classify("BLUE FLAG FOR CAR 2 (SAR)", "Flag", "BLUE") is None


def test_stop_timing_relative_to_a_vsc():
    periods = [{"kind": "VSC", "start_lap": 12, "end_lap": 14}]
    assert neutralisation_relation(13, periods)[0] == "during"
    assert neutralisation_relation(11, periods)[0] == "during"  # race control laps are the leader's
    assert neutralisation_relation(9, periods)[0] == "just_before"  # the unlucky case (REVIEW #5)
    assert neutralisation_relation(16, periods)[0] == "just_after"
    assert neutralisation_relation(30, periods)[0] is None


def _positions(order_by_lap):
    out = {}
    for lap, order in order_by_lap.items():
        for i, d in enumerate(order, start=1):
            out.setdefault(d, {})[lap] = i
    return out


def test_undercut_verdict_and_net_places():
    # car 2 sits right behind car 1, pits first on lap 10; car 1 pits on lap 12; car 2 comes out ahead
    order = {l: [1, 2, 3] for l in range(1, 10)}
    order.update({10: [1, 3, 2], 11: [1, 3, 2], 12: [3, 2, 1], 13: [3, 2, 1], 14: [2, 1, 3], 15: [2, 1, 3], 16: [2, 1, 3]})
    pos = _positions(order)
    pits = [{"driver_id": 2, "lap_number": 10, "lane_duration_ms": 21000}, {"driver_id": 1, "lap_number": 12, "lane_duration_ms": 21000}, {"driver_id": 3, "lap_number": 13, "lane_duration_ms": 21000}]
    starts = {d: {l: T0 + timedelta(seconds=90 * l + 1.5 * (pos[d][l - 1] if l > 1 else 0)) for l in range(2, 17)} for d in (1, 2, 3)}
    (battle,) = [b for b in pit_battles(pits, pos, starts, []) if {b.attacker_id, b.defender_id} == {1, 2}]
    assert battle.verdict == "undercut_worked" and battle.attacker_id == 2
    verdicts = {v.driver_id: v for v in analyse_stops(pits, [], pos, [])}
    assert verdicts[2].net_places == 1 and verdicts[2].position_before == 2


def _australia_like():
    drivers = {i: {"name": f"Driver {i}", "code": f"D{i:02d}", "team": "Top" if i <= 6 else "Mid"} for i in range(1, 23)}
    race = []
    for i in range(1, 23):
        race.append({"driver_id": i, "finish_position": i if i <= 16 else None, "grid_position": i, "status_code": "FIN" if i <= 16 else "DNF", "laps_completed": 58 if i <= 16 else 10, "status": "Retired" if i > 16 else "Finished"})
    # driver 20 recovers from P20 to P6, driver 5 doesn't start from P5, driver 3 retires from P3
    race[19].update(finish_position=6, status_code="FIN", laps_completed=58, status="Finished")
    race[4].update(finish_position=None, status_code="DNS", laps_completed=0, status="Did not start")
    race[2].update(finish_position=None, status_code="DNF", laps_completed=10, status="Retired")
    positions = {r["driver_id"]: {lap: (r["grid_position"]) for lap in range(1, 59)} for r in race}
    positions[20] = {lap: max(6, 20 - lap // 3) for lap in range(1, 59)}
    # a routine stop: P16 drops to P19 while the cars around him haven't stopped, then cycles back
    positions[16] = {lap: (16 if lap < 30 else 19 if lap < 34 else 16) for lap in range(1, 59)}
    pits = [{"driver_id": 16, "lap_number": 30, "lane_duration_ms": 22000, "duration_ms": 2400}]
    pits += [{"driver_id": d, "lap_number": 30 + k, "lane_duration_ms": 22000, "duration_ms": 2400} for k, d in enumerate((13, 14, 15, 17, 18), start=1)]
    incidents = parse_messages([_rc(0, "VSC DEPLOYED", "SafetyCar", lap=12), _rc(1, "VSC ENDING", "SafetyCar", lap=14), _rc(2, "VSC DEPLOYED", "SafetyCar", lap=34), _rc(3, "VSC ENDING", "SafetyCar", lap=34)], {})
    return Context(session_type="R", drivers=drivers, race=race, positions=positions, pits=pits, incidents=incidents, championship={1: 1, 3: 3, 5: 2}, top_teams={"Top"})


def test_race_moments_surface_what_mattered():
    moments = compute_moments(_australia_like())
    heads = [m.headline for m in moments]
    assert any("Driver 5 did not start from P5" in h for h in heads)
    assert any("Driver 3 retired" in h for h in heads)
    assert any("Driver 20 climbed from P20 to P6" in h for h in heads)
    assert sum(1 for m in moments if m.moment_type == "vsc") == 2  # every neutralisation (REVIEW #14)
    assert not any(m.moment_type in ("pit_stop", "pit_cycle") and m.driver_id == 16 for m in moments)  # routine stop (REVIEW #9)
    assert 5 <= len(moments) <= 8 or len(moments) == len({m.headline for m in moments})
    assert all("None" not in m.description for m in moments)


def _zandvoort_like():
    """R12 shape: the lead changed six times and the winner took it for good on lap 54; the championship's
    P4 retired on lap 1 from P7 on the grid; a red flag on lap 2; midfield noise competing for rows."""
    drivers = {i: {"name": f"Driver {i}", "code": f"D{i:02d}", "team": "Top" if i <= 6 else "Mid"} for i in range(1, 23)}
    race = [{"driver_id": i, "finish_position": i, "grid_position": i, "status_code": "FIN", "laps_completed": 72, "status": "Finished"} for i in range(1, 23)]
    race[2].update(finish_position=None, status_code="DNF", laps_completed=0, status="Retired", grid_position=7)
    race[6].update(grid_position=3)
    leader = {}
    for start, end, d in ((1, 4, 1), (5, 21, 2), (22, 25, 4), (26, 40, 2), (41, 47, 1), (48, 53, 4), (54, 72, 1)):
        for lap in range(start, end + 1):
            leader[lap] = d
    positions = {}
    for lap in range(1, 73):
        order = [leader[lap]] + [d for d in (1, 2, 4, 5, 6) if d != leader[lap]] + list(range(7, 23))
        for i, d in enumerate(order, start=1):
            positions.setdefault(d, {})[lap] = i
    # midfield climbers and drops that score well and compete for the 8 rows
    for d, frm, to in ((18, 18, 9), (13, 13, 8), (22, 22, 15), (16, 16, 12), (12, 12, 20)):
        race[d - 1].update(grid_position=frm)
        positions[d] = {lap: round(frm + (to - frm) * lap / 72) for lap in range(1, 73)}
    incidents = parse_messages([_rc(0, "RED FLAG", "Flag", flag="RED", lap=2), _rc(1, "VSC DEPLOYED", "SafetyCar", lap=55), _rc(2, "VSC ENDING", "SafetyCar", lap=57)], {})
    return Context(session_type="R", drivers=drivers, race=race, positions=positions, incidents=incidents, championship={1: 6, 2: 1, 4: 3, 3: 4}, top_teams={"Top"})


def test_the_lead_change_that_won_the_race_and_a_lap_one_exit_are_always_kept():
    # REVIEW_ROUND2 #39: the engine kept only the first three lead changes and one per driver, so the
    # lap-54 move that decided Zandvoort vanished; Verstappen's lap-1 retirement was droppable.
    moments = compute_moments(_zandvoort_like())
    leads = {m.lap: m for m in moments if m.moment_type == "lead_change"}
    assert 54 in leads and leads[54].driver_id == 1 and leads[54].must_include
    assert "on lap 54" in leads[54].headline
    (exit_,) = [m for m in moments if m.moment_type == "dnf" and m.driver_id == 3]
    assert exit_.must_include and exit_.lap == 1
    assert len(moments) <= 8
