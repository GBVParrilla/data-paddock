"""Stories and the Expert debrief (REVIEW_ROUND3 #51-#58, D7)."""
from __future__ import annotations

import json
import re
from collections import defaultdict

from .conftest import DATA_DIR, load


def _stories():
    for f in DATA_DIR.glob("sessions/*/drivers/*/narrative.json"):
        yield int(f.parent.parent.parent.name), int(f.parent.name), json.loads(f.read_text(encoding="utf-8"))


def _arcs():
    for f in list(DATA_DIR.glob("events/*/drivers/*/weekend-arc.json")) + list(DATA_DIR.glob("seasons/*/arc/*/*.json")):
        yield f, json.loads(f.read_text(encoding="utf-8")).get("arc_text") or ""


def test_essential_and_arcs_never_talk_about_missing_data():
    """#54: "Stationary times are not published for this race", "the pace order is only indicative"."""
    from f1tracker.narratives.factcheck import MISSING_DATA

    bad = [f"session {sid} driver {did}: {s['summary'][:100]}" for sid, did, s in _stories() if not s.get("edited") and MISSING_DATA.search(s.get("summary") or "")]
    bad += [f"{f.relative_to(DATA_DIR)}: {t[:100]}" for f, t in _arcs() if MISSING_DATA.search(t)]
    assert not bad, f"{len(bad)} texts about missing data, e.g.\n" + "\n".join(bad[:6])


def test_no_rank_out_of_fewer_than_three_no_decimal_points_no_misspelt_ordinals():
    """#55: "1st of 1 on medium", "for 1.0 points"; and R12 Q Bottas's "20nd"."""
    from f1tracker.narratives.factcheck import OUT_OF, POINTS_DECIMAL, check_ordinals

    texts = [(f"session {sid} driver {did}", " ".join(str(s.get(k) or "") for k in ("headline", "summary", "narrative_text", "strategy_analysis_text")))
             for sid, did, s in _stories() if not s.get("edited")]
    texts += [(str(f.relative_to(DATA_DIR)), t) for f, t in _arcs()]
    bad = [f"{where}: {m.group()}" for where, t in texts for m in OUT_OF.finditer(t) if int(m.group(2)) < 3]
    bad += [f"{where}: {m.group()}" for where, t in texts for m in POINTS_DECIMAL.finditer(t)]
    bad += [f"{where}: {v}" for where, t in texts for v in check_ordinals("x", t)]
    assert not bad, f"{len(bad)} problems, e.g.\n" + "\n".join(bad[:6])


def test_every_starter_has_a_debrief_and_a_dns_has_no_repeated_story():
    """D7: Expert is the debrief, computed for every driver who took part. #58: a DNS's full story
    repeated its summary word for word."""
    missing, repeats = [], []
    for sid, did, s in _stories():
        if s.get("headline", "").startswith("Did not start"):
            if s.get("narrative_text") and s["narrative_text"] == s.get("summary"):
                repeats.append(f"session {sid} driver {did}")
            continue
        d = s.get("debrief")
        if not d or not d.get("kind") or "findings" not in d:
            missing.append(f"session {sid} driver {did}")
    assert not missing, f"{len(missing)} stories without a debrief, e.g. {missing[:5]}"
    assert not repeats, f"{len(repeats)} DNS stories repeat their summary: {repeats[:5]}"


def test_no_debrief_stint_spans_a_pit_stop():
    """Hadjar, R17: "softs over laps 2-62" with a stop on lap 33. A stint with a stop inside it is a
    gap in the feed's records and is shown as a dash, never as a stint."""
    bad = []
    for sid, did, s in _stories():
        d = s.get("debrief") or {}
        for st in d.get("stints") or []:
            a, _, b = (st.get("laps") or "").partition("-")
            if a.isdigit() and b.isdigit():
                bad += [f"session {sid} driver {did}: stint {st['laps']}, stop on lap {p['lap']}" for p in d.get("stops") or [] if p.get("lap") and int(a) + 1 < p["lap"] < int(b) - 1]  # a stop at either end of a stint is its boundary
    assert not bad, f"{len(bad)} stints with a stop inside them, e.g. {bad[:5]}"


def test_debrief_ranks_are_among_three_or_more():
    """A long-run rank needs at least 3 drivers with 5 or more laps on that tyre, and says how many."""
    bad = []
    for sid, did, s in _stories():
        for x in (s.get("debrief") or {}).get("long_runs") or []:
            if x.get("rank") is not None and (x.get("of") or 0) < 3:
                bad.append(f"session {sid} driver {did}: {x}")
    assert not bad, f"{len(bad)} ranks among fewer than 3, e.g. {bad[:5]}"


def test_a_lap_one_or_two_retirement_is_never_without_its_context():
    """#56, Zandvoort Verstappen: "ended on lap 1 with no stated reason", with a red flag on lap 2."""
    bad = []
    for sid, did, s in _stories():
        text = " ".join(str(s.get(k) or "") for k in ("headline", "summary"))
        if re.search(r"no stated reason|no reason (was )?given", text, re.I):
            bad.append(f"session {sid} driver {did}: {text[:120]}")
    assert not bad, f"{len(bad)} retirements with 'no stated reason', e.g. {bad[:5]}"


def test_claude_headlines_in_a_session_rarely_share_a_shape():
    """#53: 10 drivers in R12 FP1 got "X's long-run pace beat his single-lap place". The pilot gate: no
    more than 10% of a session's Claude-written headlines share a shape with another."""
    from f1tracker.narratives.variety import name_words, same_shape, shape

    drivers = load("drivers") or []
    names = name_words([d["name"] for d in drivers] + [d.get("team") for d in drivers])
    by_session = defaultdict(list)
    for sid, did, s in _stories():
        if s.get("source") == "claude" and not s.get("narrative_text"):  # written by prompt v4 (it writes no long story)
            by_session[sid].append(shape(s["headline"], names))
    bad = []
    for sid, shapes in by_session.items():
        shared = sum(1 for i, a in enumerate(shapes) if any(same_shape(a, b) for j, b in enumerate(shapes) if j != i))
        if len(shapes) >= 5 and shared / len(shapes) > 0.10:
            bad.append(f"session {sid}: {shared} of {len(shapes)}")
    assert not bad, f"{len(bad)} sessions over 10%: {bad[:6]}"
