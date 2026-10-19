"""Three worked examples for the driver-story prompt: a winner, a midfield driver and a retirement,
written by hand from the real 2026 Australian Grand Prix fact sheets and checked by the fact-checker
(tests/test_prompts.py). They show the shape and the voice: verdict first, plain words in Essential,
the data in Expert."""
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
            "expert": "Russell was P2 after lap 1 and never ran lower than P3. He pitted on lap 11, 17.8s in the pit lane and 2.3s stationary, then ran hards for laps 12-58, where his pace faded by only about 0.03s a lap allowing for fuel. Sector 3 was his weakest: 6th of 20, +0.263s to the session best.",
            "analysis": "The stop under the Virtual Safety Car was cheap, but it cost him a place: P2 before, P3 after. The second round of stops won him the race: Hamilton pitted on lap 27 and Russell came out ahead.",
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
            "expert": "Gasly was P9 after lap 1 and ran between P9 and P12. He pitted on lap 10, 18.6s in the pit lane, and his hard-tyre pace over laps 11-57 faded by about 0.04s a lap allowing for fuel. Sector 3 was his weak point: 16th of 20, +1.149s to the session best. He spent 55 laps next to Esteban Ocon; the stewards took no further action over their turn 3 incident on lap 23.",
            "analysis": "His stop on lap 10 came just before the Virtual Safety Car on lap 12: unlucky timing that cost him a place, P10 before and P11 after. The places he made on the opening lap are what kept him in the points.",
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
            "essential": "Isack Hadjar started third and was running P5 when his race ended on lap 11. The timing data gives no reason for the retirement. Until then his pace on medium tyres had held steady. His teammate Max Verstappen came through from P20 on the grid to finish P6.",
            "expert": "Hadjar was P4 after lap 1 and ran P4 or P5 until he stopped. On mediums for laps 1-10 his best lap was 1:25.239, and allowing for fuel his pace held steady. Sector 2 was where he lost most: 20th of 20, +1.195s to the session best.",
            "analysis": "His pace held steady through laps 1-10, so the retirement on lap 11, from P5, was the whole story of his race.",
            "key_numbers": [{"label": "Grid", "value": "P3"}, {"label": "Retired", "value": "Lap 11"}, {"label": "Running", "value": "P5"}],
            "glossary_terms": ["DNF", "compound"],
        },
    },
]
