"""Headline variety within a session (REVIEW_ROUND3 #53)."""
import threading

from f1tracker.narratives.variety import SessionHeadlines, mark_shared, name_words, same_shape, shape

NAMES = name_words(["Pierre Gasly", "Esteban Ocon", "Lando Norris", "Max Verstappen", "Alpine", "Haas F1 Team"])


def test_the_same_construction_for_another_driver_is_the_same_shape():
    a = shape("Pitting just before the VSC was unlucky for Gasly", NAMES)
    b = shape("Pitting just before the VSC was unlucky for Ocon", NAMES)
    assert same_shape(a, b)
    assert same_shape(shape("Gasly's long-run pace beat his single-lap place", NAMES), shape("Norris's long-run pace beat his single-lap place", NAMES))
    assert not same_shape(a, shape("Ocon gained 5 places on the opening lap", NAMES))


def test_a_situation_much_of_the_field_shared_moves_behind_his_own_story():
    def sheet(me, own):
        return {"verdict_candidates": [{"kind": "long_run", "headline": f"{me}'s long-run pace beat his single-lap place", "verdict": "v", "weight": 5},
                                       {"kind": "teammate", "headline": own, "verdict": "w", "weight": 3}]}
    sheets = {1: sheet("Gasly", "Gasly out-qualified teammate Ocon"), 2: sheet("Ocon", "Teammate Gasly was quicker than Ocon"),
              3: sheet("Norris", "Norris was quicker than teammate Verstappen"), 4: {"verdict_candidates": [{"kind": "x", "headline": "Verstappen topped the session", "verdict": "z"}]}}
    mark_shared(sheets, NAMES)
    first = sheets[1]["verdict_candidates"][0]
    assert first["kind"] == "teammate" and "shared_with_other_drivers" not in first
    assert sheets[1]["verdict_candidates"][1]["shared_with_other_drivers"] == 2


def test_the_registry_rejects_a_second_headline_of_the_same_shape():
    reg = SessionHeadlines(NAMES)
    assert reg.claim(1, "Pitting just before the VSC was unlucky for Gasly") is None
    assert reg.claim(2, "Pitting just before the VSC was unlucky for Ocon") == "Pitting just before the VSC was unlucky for Gasly"
    assert reg.claim(2, "Ocon's stop came a lap too early for the VSC") is None
    assert reg.claim(1, "Pitting just before the VSC was unlucky for Gasly") is None  # his own headline again is fine
    assert reg.written(except_driver=1) == ["Ocon's stop came a lap too early for the VSC"]


def test_the_registry_is_safe_across_worker_threads():
    reg = SessionHeadlines(NAMES)
    wins = []

    def claim(d):
        if reg.claim(d, "Pitting just before the VSC was unlucky for Gasly") is None:
            wins.append(d)
    threads = [threading.Thread(target=claim, args=(d,)) for d in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(wins) == 1
