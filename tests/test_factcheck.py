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
        "headline": "P10 from P14 for Gasly",
        "summary": "Pierre Gasly started P14 and finished P10, scoring a point.",
        "story": "Gasly ran 55 laps next to Esteban Ocon. His best lap was 1:24.486 on the hard tyres.",
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
    bad = _check(_story(story="He finished one place behind his Alpine teammate Esteban Ocon."))
    assert any("teammate" in v for v in bad)


def test_numbers_not_in_the_data_are_caught():
    bad = _check(_story(story="His best lap was 1:23.999 and he gained 7 places."))
    assert any("1:23.999" in v for v in bad) and any("gained 7 places" in v or "number 7" in v for v in bad)


def test_points_arithmetic_is_recomputed():
    sheet = {**SHEET, "points_gaps": [243]}
    bad = check_story(_story(story="He sits 97 points behind the leader's 340."), sheet, roster=ROSTER, entrants=ENTRANTS)
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
    assert any("Yuki Tsunoda did not take part" in v for v in _check(_story(story="He finished ahead of Tsunoda.")))


def test_hedging_without_flagged_gaps_is_caught():
    sheet = {**SHEET, "insufficient_data": []}
    bad = check_story(_story(analysis="It is hard to say. The evidence does not support a strong conclusion either way."), sheet, roster=ROSTER, entrants=ENTRANTS)
    assert any("hedging" in str(v) for v in bad)


def test_summary_has_no_lap_times():
    assert any("no lap times in the summary" in v for v in _check(_story(summary="He set a 1:24.486.")))


def test_template_always_passes():
    sheet = {**SHEET, "meta": {"season": 2026, "session_type": "R"}, "position_trace": {"end_of_lap_1": 9, "best": 9, "worst": 12}}
    t = template_story(sheet)
    assert check_story(t, sheet, roster=ROSTER, entrants=ENTRANTS) == []


def test_job_retries_with_violations_then_falls_back(monkeypatch):
    calls = []

    def fake_generate(system, user, schema, effort=None):
        calls.append(user)
        return ({"headline": "x", "summary": "y", "story": "z <br>", "analysis": "a", "key_numbers": [], "glossary_terms": []}, "model-x")

    monkeypatch.setattr(jobs, "generate_json", fake_generate)
    job = jobs.StoryJob("t", "sys", "facts", {}, save=lambda db, o: o, check=lambda d: ["contains <br>"] if "<br>" in d["story"] else [],
                        fallback=lambda: {"story": "template"}, attempts=3)
    out = job.call()
    assert len(calls) == 3 and "contains <br>" in calls[1]  # the retry tells the model what was wrong
    assert out.fallback and out.data == {"story": "template"} and out.violations == ["contains <br>"]


def test_job_accepts_first_clean_answer(monkeypatch):
    monkeypatch.setattr(jobs, "generate_json", lambda *a, **k: ({"story": "clean"}, "model-x"))
    out = jobs.StoryJob("t", "s", "u", {}, save=lambda db, o: o, check=lambda d: []).call()
    assert out.attempts == 1 and not out.fallback and out.model == "model-x"
