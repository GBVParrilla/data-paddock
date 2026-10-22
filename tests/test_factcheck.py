"""The fact-checker must catch every false claim REVIEW.md found in published stories."""
from f1tracker.narratives import jobs
from f1tracker.narratives.factcheck import check_story
from f1tracker.narratives.template import template_story

SHEET = {
    "meta": {"season": 2026, "session_type": "R"},
    "driver": {"name": "Pierre Gasly", "team": "Alpine", "teammate": "Franco Colapinto"},
    "result": {"status": "finished 1 lap down", "grid": 14, "finish": 10, "places_gained": 4, "points": 1.0, "pit_stops": 1,
               "teammate": {"name": "Franco Colapinto", "grid": 16, "finish": 14}},
    "stops": [{"stop": 1, "in_lap": 10, "pit_lane_time": "18.6s", "position_before": 10, "position_after_cycle": 11, "net_places": -1,
               "neutralisation": {"relation": "just_before", "kind": "Virtual Safety Car", "laps": "12-14"}}],
    "stints": [{"compound": "HARD", "laps": "11-57", "best_lap": "1:24.486"}],
    "sectors": {"sector_3": {"best": "36.748", "gap_to_session_best": "+1.149s", "rank": 16, "of": 20}},
    "rivals_on_track": [{"driver": "Esteban Ocon", "laps_running_together": 55, "their_finish": 11}],
    "neutralisations": [{"kind": "Virtual Safety Car", "laps": "12-14"}],
    "verdicts": ["Stop 1 (lap 10) came just before the Virtual Safety Car on lap 12: unlucky timing."],
    "insufficient_data": ["stationary pit-stop times"],
}
ROSTER = {"Gasly": "Pierre Gasly", "Colapinto": "Franco Colapinto", "Ocon": "Esteban Ocon", "Tsunoda": "Yuki Tsunoda"}
ENTRANTS = {"Pierre Gasly", "Franco Colapinto", "Esteban Ocon"}


def _story(**kw):
    base = {
        "headline": "Pitting just before the VSC was unlucky for Gasly",
        "essential": "Pierre Gasly started P14 and finished P10, scoring a point.",
        "expert": "Gasly ran 55 laps next to Esteban Ocon. His best lap was 1:24.486 on the hard tyres.",
        "analysis": "His lap 10 stop came just before the Virtual Safety Car on lap 12, which was unlucky: rivals stopped for less.",
        "key_numbers": [{"label": "Finish", "value": "P10"}],
        "glossary_terms": ["VSC"],
    }
    base.update(kw)
    return base


def _check(story):
    return [str(v) for v in check_story(story, SHEET, roster=ROSTER, entrants=ENTRANTS)]


def test_a_correct_story_passes():
    assert _check(_story()) == []


def test_wrong_teammate_claim_is_caught():
    bad = _check(_story(expert="He finished one place behind his Alpine teammate Esteban Ocon."))
    assert any("teammate" in v for v in bad)


def test_numbers_not_in_the_data_are_caught():
    bad = _check(_story(expert="His best lap was 1:23.999 and he gained 7 places."))
    assert any("1:23.999" in v for v in bad) and any("gained 7 places" in v or "number 7" in v for v in bad)


def test_points_arithmetic_is_recomputed():
    sheet = {**SHEET, "points_gaps": [243]}
    bad = check_story(_story(expert="He sits 97 points behind the leader's 340."), sheet, roster=ROSTER, entrants=ENTRANTS)
    assert any("97 points behind" in str(v) for v in bad)


def test_vsc_logic_inversion_is_caught():
    bad = _check(_story(analysis="The stop came just before the lap 12 VSC, which may have reduced the time lost in the pit lane."))
    assert any("unlucky, not cheap" in v for v in bad)


def test_leaked_model_output_is_caught():
    bad = _check(_story(analysis="A fine analysis.}<br>BAD_FORMAT_FIXED_BELOW>{}"))
    assert any("formatting" in v for v in bad)
    bad = _check(_story(analysis="Done.</strategy_analysis_text>}. Wait, invalid trailing character"))
    assert any("formatting" in v for v in bad)


def test_unentered_driver_is_caught():
    assert any("Yuki Tsunoda did not take part" in v for v in _check(_story(expert="He finished ahead of Tsunoda.")))


def test_hedging_without_flagged_gaps_is_caught():
    sheet = {**SHEET, "insufficient_data": []}
    bad = check_story(_story(analysis="It is hard to say. The evidence does not support a strong conclusion either way."), sheet, roster=ROSTER, entrants=ENTRANTS)
    assert any("hedging" in str(v) for v in bad)


def test_essential_has_no_lap_times_or_raw_expressions():
    assert any("no lap times" in v for v in _check(_story(essential="He set a 1:24.486.")))
    # REVIEW_ROUND2 #40: "(-0.06s per lap)" is for Expert, not for a new fan
    assert any("plain words" in v for v in _check(_story(essential="His pace held steady (-0.06s per lap).")))


def test_a_headline_that_only_states_the_result_is_rejected():
    # REVIEW_ROUND2 B2: the headline says what the result meant or why it happened
    for h in ("P10 from P14 for one point", "P10 from P14", "P14 in qualifying", "Retired on lap 11", "P1 in FP2"):
        assert any("[headline]" in v and "verdict" in v for v in _check(_story(headline=h))), h
    for h in ("Pitting just before the VSC was unlucky for Gasly", "Gasly gained 5 places on the opening lap", "Gasly missed the Q2 cut by 0.280s"):
        assert not any("[headline]" in v and "verdict" in v for v in _check(_story(headline=h))), h


def test_template_always_passes():
    sheet = {**SHEET, "meta": {"season": 2026, "session_type": "R"}, "position_trace": {"end_of_lap_1": 9, "best": 9, "worst": 12}}
    t = template_story(sheet)
    assert check_story(t, sheet, roster=ROSTER, entrants=ENTRANTS) == []


def test_template_leads_with_the_verdict_and_never_repeats_it():
    first_lap = {"kind": "first_lap", "headline": "Gasly gained 5 places on the opening lap", "verdict": "He gained 5 places on the opening lap, from P14 to P9."}
    stop = {"kind": "stop_timing", "headline": "Pitting just before the VSC was unlucky for Gasly",
            "verdict": "His only stop, on lap 10, came just before the Virtual Safety Car on lap 12: unlucky timing, because the cars that waited stopped for less."}
    other = "His only stop cost him a place once the cars around him had stopped too: P10 before, P11 after."
    sheet = {**SHEET, "position_trace": {"end_of_lap_1": 9, "best": 9, "worst": 12}, "allowed_place_counts": [5],
             "verdict_candidates": [first_lap, stop], "verdicts": [stop["verdict"], other]}
    t = template_story(sheet)
    assert t["headline"] == first_lap["headline"]
    # Essential: the result, then the next part of the story; the headline's fact isn't repeated
    assert t["essential"].startswith("Pierre Gasly started P14") and stop["verdict"] in t["essential"] and first_lap["verdict"] not in t["essential"]
    # the analysis states what Essential didn't
    assert other in t["analysis"] and stop["verdict"] not in t["analysis"]
    assert check_story(t, sheet, roster=ROSTER, entrants=ENTRANTS) == []


def test_job_retries_with_violations_then_falls_back(monkeypatch):
    calls = []

    def fake_generate(system, user, schema, effort=None):
        calls.append(user)
        return ({"headline": "x", "essential": "y", "expert": "z <br>", "analysis": "a", "key_numbers": [], "glossary_terms": []}, "model-x")

    monkeypatch.setattr(jobs, "generate_json", fake_generate)
    job = jobs.StoryJob("t", "sys", "facts", {}, save=lambda db, o: o, check=lambda d: ["contains <br>"] if "<br>" in d["expert"] else [],
                        fallback=lambda: {"story": "template"}, attempts=3)
    out = job.call()
    assert len(calls) == 3 and "contains <br>" in calls[1]  # the retry tells the model what was wrong
    assert out.fallback and out.data == {"story": "template"} and out.violations == ["contains <br>"]


def test_job_accepts_first_clean_answer(monkeypatch):
    monkeypatch.setattr(jobs, "generate_json", lambda *a, **k: ({"story": "clean"}, "model-x"))
    out = jobs.StoryJob("t", "s", "u", {}, save=lambda db, o: o, check=lambda d: []).call()
    assert out.attempts == 1 and not out.fallback and out.model == "model-x"


# --- REVIEW_ROUND3: the slips the prompt v3 pilot published, and the patterns its review counted ----

def test_a_v4_story_is_headline_and_essential_only():
    assert _check({k: v for k, v in _story().items() if k not in ("expert", "analysis")}) == []


def test_unit_suffixes_are_numbers():
    sheet = {**SHEET, "weather": {"track_temp_c": {"max": 35.9}}}
    assert check_story(_story(expert="Track temperature reached 35.9C."), sheet, roster=ROSTER, entrants=ENTRANTS) == []
    assert any("36.9C" in str(v) for v in check_story(_story(expert="Track temperature reached 36.9C."), sheet, roster=ROSTER, entrants=ENTRANTS))


def test_misspelt_ordinals_are_caught():
    sheet = {**SHEET, "sectors": {"sector_1": {"rank": 21, "of": 22}, "sector_2": {"rank": 22, "of": 22}, "sector_3": {"rank": 20, "of": 22}}}
    bad = check_story(_story(expert="His sectors ranked 21st, 22nd and 20nd of 22."), sheet, roster=ROSTER, entrants=ENTRANTS)
    assert any("20nd" in str(v) and "20th" in str(v) for v in bad)


def test_sector_claims_must_match_the_ranks():
    # R17 Q Verstappen: 1st in S1 and S3, 6th in S2, but "fastest in both final sectors"
    sheet = {**SHEET, "sectors": {"sector_1": {"rank": 1, "of": 22}, "sector_2": {"rank": 6, "of": 22}, "sector_3": {"rank": 1, "of": 22}}}
    check = lambda text: [str(v) for v in check_story(_story(expert=text), sheet, roster=ROSTER, entrants=ENTRANTS)]  # noqa: E731
    assert any("sector 2" in v for v in check("He was fastest in both final sectors."))
    assert check("He was fastest in sectors 1 and 3.") == []
    assert any("weakest" in v for v in check("Sector 1 was his weakest."))  # a top-5 sector isn't weak
    assert check("Sector 2 was his weakest.") == []
    assert check("He was fastest through sector 1, but lost time in sectors 2 and 3.") == []  # not a claim about S2


def test_segment_wording_must_match_the_exit():
    # R1 Q Gasly: knocked out in Q2, but the analysis said he "missed Q2"
    sheet = {**SHEET, "meta": {"season": 2026, "session_type": "Q"}, "result": {"position": 12, "reached": "knocked out in Q2"}}
    check = lambda text: [str(v) for v in check_story(_story(expert=text), sheet, roster=ROSTER, entrants=ENTRANTS)]  # noqa: E731
    assert any("missed Q2" in v and "missed Q3" in v for v in check("He missed Q2 by a fraction."))
    assert check("He missed Q3 by a fraction.") == []
    assert check("He was knocked out in Q2.") == []
    assert check("He missed the Q2 cut.") == []  # the cut he faced, not a segment he missed


def test_stand_in_claims_are_checked_against_the_entry_list():
    # REVIEW_ROUND3 #60: Lawson really was Red Bull's stand-in at round 12, so this is checked, not banned
    text = "Standing in for Red Bull, he was P12."
    assert any("stand-in" in str(v) for v in check_story(_story(expert=text), SHEET, roster=ROSTER, entrants=ENTRANTS))
    stand_in = {**SHEET, "driver": {**SHEET["driver"], "stand_in": True, "usual_team": "Racing Bulls"}}
    assert check_story(_story(expert=text), stand_in, roster=ROSTER, entrants=ENTRANTS) == []


def test_motives_and_missing_data_talk_are_caught():
    assert any("guess" in v for v in _check(_story(essential="He was looking for a better start and finished P10.")))
    assert any("guess" in v for v in _check(_story(expert="A clean final push gave him P10.")))
    for text in ("Stationary times are not published for this race.", "The pace order is only indicative.", "His race ended with no stated reason."):
        assert any("isn't there" in v for v in _check(_story(essential=text))), text


def test_a_headline_must_not_misread_the_race():
    # R17 Russell: P19 to P9 was not "undone"; R12 Colapinto finished where he started, so a stop that "cost 10 places" isn't the story
    climb = {**SHEET, "result": {**SHEET["result"], "grid": 19, "finish": 9, "places_gained": 10}}
    bad = check_story(_story(headline="Russell's climb was undone by a stop under the VSC"), climb, roster=ROSTER, entrants=ENTRANTS)
    assert any("misreads" in str(v) for v in bad)
    level = {**SHEET, "result": {**SHEET["result"], "grid": 15, "finish": 15, "places_gained": 0}, "allowed_place_counts": [10]}
    assert any("lost 10 places" in str(v) for v in check_story(_story(headline="The first stop cost Gasly 10 places"), level, roster=ROSTER, entrants=ENTRANTS))
    assert not any("[headline]" in str(v) for v in check_story(_story(headline="Gasly recovered from a stop that cost him 10 places"), level, roster=ROSTER, entrants=ENTRANTS))


def test_ranks_out_of_fewer_than_three_and_decimal_points_are_caught():
    assert any("fewer than 3" in v for v in _check(_story(expert="He was 1st of 1 on the medium tyre.")))
    assert any("1 point" in v for v in _check(_story(essential="He finished P10 for 1.0 points.")))


def test_essential_leaves_sector_ranks_and_pit_lane_times_to_the_debrief():
    assert any("debrief" in v for v in _check(_story(essential="He was 16th in sector 3 and finished P10.")))
    assert any("debrief" in v for v in _check(_story(essential="He spent 18.6s in the pit lane and finished P10.")))


def test_a_dns_story_has_no_full_story_repeating_it():
    # REVIEW_ROUND3 #58: Piastri (R1) - the full story equalled the summary
    sheet = {**SHEET, "result": {"status": "did not start", "grid": 5, "teammate": {"name": "Franco Colapinto", "finish": 14}}}
    t = template_story(sheet)
    assert t["essential"] and t["expert"] == ""


def test_slips_from_the_prompt_v4_pilot_are_caught():
    # R17 Q Verstappen: "sector-perfect" with a 6th-best sector 2; R12 Q Bottas: "slowest" in a sector he was 20th of 22 in
    q = {**SHEET, "sectors": {"sector_1": {"rank": 1, "of": 22}, "sector_2": {"rank": 6, "of": 22}, "sector_3": {"rank": 1, "of": 22}}}
    assert any("sector-perfect" in str(v) for v in check_story(_story(headline="Verstappen's sector-perfect lap put him on pole"), q, roster=ROSTER, entrants=ENTRANTS))
    b = {**SHEET, "sectors": {"sector_1": {"rank": 21, "of": 22}, "sector_2": {"rank": 22, "of": 22}, "sector_3": {"rank": 20, "of": 22}}}
    bad = [str(v) for v in check_story(_story(expert="His time was slowest in the middle and final sectors."), b, roster=ROSTER, entrants=ENTRANTS)]
    assert any("slowest in sector 3" in v for v in bad) and not any("slowest in sector 2" in v for v in bad)
    # R1 R Hadjar and R17 S Pérez: missing-data talk in new words
    for text in ("Race control reported no cause for the retirement.", "No decision was recorded on it."):
        assert any("isn't there" in v for v in _check(_story(essential=text))), text


def test_filler_from_the_prompt_v5_pilot_is_caught():
    # Piastri R12 S, Stroll R17 R, three stories with "Rain was reported"
    for text in ("No incidents or safety periods were recorded for him.", "The stop came away from any Virtual Safety Car period.", "Rain was reported during the session.",
                 "He finished on top, with no incidents or Safety Cars involved in his laps."):  # full-season run, a Q story
        assert any("didn't happen" in v for v in _check(_story(essential=text))), text
    assert _check(_story(essential="Pierre Gasly started P14 and finished P10, scoring a point.")) == []


def test_a_lead_taken_in_the_pit_stops_is_not_a_pass():
    # R1 Russell: "A lap-27 pass on Hamilton gave Russell the win"
    win = {**SHEET, "verdict_candidates": [{"kind": "win", "headline": "Russell took the lead for good on lap 27", "verdict": "He took the lead for good on lap 27, from Lewis Hamilton through the pit stops, and won."}]}
    assert any("not by passing" in str(v) for v in check_story(_story(headline="A lap-27 pass on Hamilton gave Russell the win"), win, roster=ROSTER, entrants=ENTRANTS))
    assert not any("not by passing" in str(v) for v in check_story(_story(headline="The pit stops on lap 27 gave Russell the win"), win, roster=ROSTER, entrants=ENTRANTS))


def test_top_half_must_fit_the_position():
    # R1 Q Gasly (prompt v6 pilot): "a place in the top half of the grid" for P14 of 22
    quali = {**SHEET, "result": {"position": 14, "of": 22}}
    assert any("doesn't fit P14 of 22" in str(v) for v in check_story(_story(essential="He ended the session in the top half of the grid."), quali, roster=ROSTER, entrants=ENTRANTS))
    assert not any("doesn't fit" in str(v) for v in check_story(_story(essential="He qualified in the bottom half of the grid."), quali, roster=ROSTER, entrants=ENTRANTS))
    race = {**SHEET, "result": {"grid": 17, "finish": 10}}
    assert not any("doesn't fit" in str(v) for v in check_story(_story(essential="He started from the back half of the grid."), race, roster=ROSTER, entrants=ENTRANTS))
    assert not any("doesn't fit" in str(v) for v in check_story(_story(essential="He was in the bottom half of the field in all three sectors."), quali, roster=ROSTER, entrants=ENTRANTS))
