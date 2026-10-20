"""Three worked examples for the driver-story prompt: a winner, a midfield driver and a retirement,
written by hand from the real 2026 Australian Grand Prix fact sheets and checked by the fact-checker
(tests/test_prompts.py). They show the shape and the voice: a verdict headline, then Essential in
plain words, cause before effect. The data goes in the Expert debrief, which code writes."""
from __future__ import annotations

EXAMPLES = [
    {
        "who": "the winner",
        "facts_excerpt": {
            "driver": {"name": "George Russell", "team": "Mercedes", "teammate": "Andrea Kimi Antonelli"},
            "result": {"status": "finished on the lead lap", "grid": 1, "finish": 1, "points": 25.0, "pit_stops": 1},
            "position_trace": {"end_of_lap_1": 2, "best": 1, "worst": 3},
            "verdict_candidates": [{"kind": "win", "verdict": "He took the lead for good on lap 27, from Hamilton through the pit stops, and won."}],
            "verdicts": ["His only stop, on lap 11, came under the Virtual Safety Car: a cheap stop, because the cars he was racing were slowed too.",
                         "His only stop cost him a place once the cars around him had stopped too: P2 before, P3 after.",
                         "His pace fell away through his hard-tyre stint (laps 12-58), by about 0.03s a lap allowing for the fuel he burned."],
            "stops": [{"in_lap": 11, "stationary": "2.3s", "pit_lane_time": "17.8s"}],
            "stints": [{"compound": "HARD", "laps": "12-58", "degradation_s_per_lap": 0.026}],
            "sectors": {"sector_3": {"gap_to_session_best": "+0.263s", "rank": 6, "of": 20}},
            "rivals_stops": [{"driver": "Lewis Hamilton", "in_laps": [18, 27]}],
        },
        "story": {
            "headline": "Russell won the race in the pit stops",
            "essential": "George Russell started from pole but was second after the first lap. His only stop came under the Virtual Safety Car, a cheap moment to pit, yet it still cost him a place once the cars around him had stopped too. The race turned on lap 27, when he took the lead from Hamilton through the pit stops and kept it to the flag.",
            "key_numbers": [{"label": "Finish", "value": "P1"}, {"label": "Grid", "value": "P1"}, {"label": "Stops", "value": "1"}],
            "glossary_terms": ["VSC", "compound"],
        },
    },
    {
        "who": "a midfield driver",
        "facts_excerpt": {
            "driver": {"name": "Pierre Gasly", "team": "Alpine", "teammate": "Franco Colapinto"},
            "result": {"status": "finished 1 lap down", "grid": 14, "finish": 10, "places_gained": 4, "points": 1.0, "teammate": {"name": "Franco Colapinto", "finish": 14}},
            "position_trace": {"end_of_lap_1": 9, "best": 9, "worst": 12},
            "verdict_candidates": [{"kind": "first_lap", "verdict": "He gained 5 places on the opening lap, from P14 to P9."},
                                   {"kind": "stop_timing", "verdict": "His only stop, on lap 10, came just before the Virtual Safety Car on lap 12: unlucky timing, because the cars that waited stopped for less."}],
            "verdicts": ["His only stop cost him a place once the cars around him had stopped too: P10 before, P11 after.",
                         "His pace fell away through his hard-tyre stint (laps 11-57), by about 0.04s a lap allowing for the fuel he burned."],
            "stops": [{"in_lap": 10, "pit_lane_time": "18.6s"}],
            "stints": [{"compound": "HARD", "laps": "11-57", "degradation_s_per_lap": 0.041}],
            "sectors": {"sector_3": {"gap_to_session_best": "+1.149s", "rank": 16, "of": 20}},
            "rivals_on_track": [{"driver": "Esteban Ocon", "laps_running_together": 55, "their_finish": 11}],
            "incidents": [{"lap": 23, "with": ["Esteban Ocon"], "turn": 3, "outcome": "no further action"}],
        },
        "story": {
            "headline": "Pitting before the VSC cost Gasly a place",
            "essential": "Pierre Gasly made a strong start, gaining 5 places on the opening lap to run P9. His only stop, on lap 10, came just before a Virtual Safety Car: unlucky, because the cars that waited stopped for less, and it cost him a place. He still finished P10 from P14 on the grid for one point, ahead of teammate Franco Colapinto.",
            "key_numbers": [{"label": "Finish", "value": "P10"}, {"label": "Grid", "value": "P14"}, {"label": "Places", "value": "+4"}],
            "glossary_terms": ["VSC", "compound", "lapped"],
        },
    },
    {
        "who": "a retirement",
        "facts_excerpt": {
            "driver": {"name": "Isack Hadjar", "team": "Red Bull Racing", "teammate": "Max Verstappen"},
            "result": {"status": "retired", "grid": 3, "retired_on_lap": 11, "retirement_reason_given": "not stated", "teammate": {"name": "Max Verstappen", "grid": 20, "finish": 6}},
            "position_trace": {"end_of_lap_1": 4, "best": 4, "worst": 5, "final": 5},
            "verdict_candidates": [{"kind": "retirement", "verdict": "His race ended on lap 11 while running P5."}],
            "verdicts": ["His pace held steady through his medium-tyre stint (laps 1-10), allowing for the fuel he burned."],
            "stints": [{"compound": "MEDIUM", "laps": "1-10", "best_lap": "1:25.239"}],
            "sectors": {"sector_2": {"gap_to_session_best": "+1.195s", "rank": 20, "of": 20}},
        },
        "story": {
            "headline": "A lap-11 retirement cut short Hadjar's run in P5",
            "essential": "Isack Hadjar started third and was running P5 when his race ended on lap 11. Until then his pace on medium tyres had held steady. His teammate Max Verstappen came through from P20 on the grid to finish P6.",
            "key_numbers": [{"label": "Grid", "value": "P3"}, {"label": "Retired", "value": "Lap 11"}, {"label": "Running", "value": "P5"}],
            "glossary_terms": ["DNF", "compound"],
        },
    },
]
