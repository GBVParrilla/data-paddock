"""Two-driver comparison for one session: data bundle + cached comparative narrative."""
from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session as OrmSession

from ..models import ComparisonNarrative, DetailPositionByLap, DetailStintTimeline, Driver, Lap, Session
from ..util import fmt_ms, utcnow
from .jobs import StoryJob
from ..config import COMPARISON_PROMPT_VERSION
from .llm import stable_hash
from .prompts import SCHEMA_COMPARISON, SYSTEM_COMPARISON

log = logging.getLogger(__name__)


def _position_series(db: OrmSession, session_id: int, driver_id: int) -> list[dict]:
    rows = db.scalars(select(DetailPositionByLap).where(DetailPositionByLap.session_id == session_id, DetailPositionByLap.driver_id == driver_id).order_by(DetailPositionByLap.lap_number)).all()
    return [{"lap": r.lap_number, "position": r.position} for r in rows]


def _stints(db: OrmSession, session_id: int, driver_id: int) -> list[dict]:
    rows = db.scalars(select(DetailStintTimeline).where(DetailStintTimeline.session_id == session_id, DetailStintTimeline.driver_id == driver_id).order_by(DetailStintTimeline.stint_number)).all()
    return [{"stint": r.stint_number, "compound": r.compound, "lap_start": r.lap_start, "lap_end": r.lap_end} for r in rows]


def gap_over_time(db: OrmSession, session_id: int, driver_a: int, driver_b: int) -> list[dict]:
    """Cumulative race-time difference (A minus B) by lap, from lap times. Positive = A behind."""
    def times(d: int) -> dict[int, int]:
        return {l.lap_number: l.lap_time_ms for l in db.scalars(select(Lap).where(Lap.session_id == session_id, Lap.driver_id == d)).all() if l.lap_time_ms}

    ta, tb = times(driver_a), times(driver_b)
    common = sorted(set(ta) & set(tb))
    out, cum = [], 0
    for lap in common:
        cum += ta[lap] - tb[lap]
        out.append({"lap": lap, "gap_ms": cum, "gap_formatted": ("+" if cum >= 0 else "") + fmt_ms(cum) + "s"})
    return out


def build_comparison(db: OrmSession, session_id: int, driver_a: int, driver_b: int) -> dict[str, Any]:
    session = db.get(Session, session_id)
    if session is None:
        raise ValueError(f"session {session_id} not found")
    da, dbv = db.get(Driver, driver_a), db.get(Driver, driver_b)
    if da is None or dbv is None:
        raise ValueError("driver not found")
    from ..ingest.entries import entry_map

    entries = entry_map(db, session.event_id)
    team = {d.id: (entries[d.id].team if d.id in entries else d.team) for d in (da, dbv)}
    return {
        "session_id": session_id,
        "session_type": session.session_type,
        "driver_a": {"id": da.id, "name": da.full_name, "team": team[da.id], "position_by_lap": _position_series(db, session_id, da.id), "stints": _stints(db, session_id, da.id)},
        "driver_b": {"id": dbv.id, "name": dbv.full_name, "team": team[dbv.id], "position_by_lap": _position_series(db, session_id, dbv.id), "stints": _stints(db, session_id, dbv.id)},
        "gap_over_time": gap_over_time(db, session_id, da.id, dbv.id),
    }


def _existing(db: OrmSession, session_id: int, a: int, b: int) -> ComparisonNarrative | None:
    return db.scalar(select(ComparisonNarrative).where(ComparisonNarrative.session_id == session_id, ComparisonNarrative.driver_a_id == a, ComparisonNarrative.driver_b_id == b))


LIMITS = {"comparison_text": 175}


def _seconds(t: str | None) -> float | None:
    if not t:
        return None
    m, _, sec = t.rpartition(":")
    return (int(m) * 60 if m else 0) + float(sec)


def _ranks(sectors: dict | None) -> dict[str, str]:
    return {k: f"{v['rank']} of {v['of']}" for k, v in (sectors or {}).items() if isinstance(v, dict) and v.get("rank") and v.get("of")}


def _sector_gaps(sa: dict | None, sb: dict | None, na: str, nb: str) -> list[str]:
    """'Sector 1: Alonso quicker by 0.143s', one line per sector both drivers set a time in."""
    out = []
    for k in ("sector_1", "sector_2", "sector_3"):
        ta, tb = _seconds((sa or {}).get(k, {}).get("best")), _seconds((sb or {}).get(k, {}).get("best"))
        if ta is None or tb is None:
            continue
        label = k.replace("_", " ").capitalize()
        out.append(f"{label}: level" if round(ta, 3) == round(tb, 3) else f"{label}: {na if ta < tb else nb} quicker by {abs(ta - tb):.3f}s")
    return out


def prompt_pair(pair: dict[str, Any]) -> dict[str, Any]:
    """What Claude sees: each driver's sector ranks and the gaps between them, not the raw sector times (which the
    checker keeps, so stories written before #65 still verify)."""
    return {**pair, "drivers": {n: {k: v for k, v in d.items() if k != "sectors"} for n, d in pair["drivers"].items()}}


def build_pair_facts(db: OrmSession, session_id: int, a: int, b: int) -> dict[str, Any]:
    """Two drivers in one session: both results, how they compared, and any incident they shared."""
    from ..analysis.race_control import cases, parse_messages
    from ..analysis.strategy import pit_battles
    from ..ingest.entries import event_drivers
    from ..models import PitStop, RaceControl
    from .facts import build_driver_session_facts

    session = db.get(Session, session_id)
    fa, fb = build_driver_session_facts(db, session_id, a), build_driver_session_facts(db, session_id, b)
    na, nb = fa["driver"]["name"], fb["driver"]["name"]
    ra, rb = fa.get("result") or {}, fb.get("result") or {}
    pair: dict[str, Any] = {
        "meta": fa["meta"],
        "drivers": {
            na: {"team": fa["driver"]["team"], "result": fa.get("result_headline"), "sector_ranks": _ranks(fa.get("sectors")), "sectors": fa.get("sectors")},
            nb: {"team": fb["driver"]["team"], "result": fb.get("result_headline"), "sector_ranks": _ranks(fb.get("sectors")), "sectors": fb.get("sectors")},
        },
        # who was quicker in each sector and by how much, rather than both times: the stories read raw times aloud (#65)
        "sector_gaps": _sector_gaps(fa.get("sectors"), fb.get("sectors"), na, nb),
        "teammates": fa["driver"]["team"] == fb["driver"]["team"],
        "verdicts": [], "insufficient_data": [],
    }
    v = pair["verdicts"]
    if session.session_type in ("R", "S"):
        pa, pb = ra.get("finish"), rb.get("finish")
        if pa and pb:
            first, second = (na, nb) if pa < pb else (nb, na)
            v.append(f"{first} finished ahead: P{min(pa, pb)} to P{max(pa, pb)}.")
        for f, n in ((fa, na), (fb, nb)):
            pair["drivers"][n]["stops"] = [s["in_lap"] for s in f.get("stops") or []]
            pair["drivers"][n]["stints"] = [f"{s['compound'].lower()} {s['laps']}" for s in f.get("stints") or []]
        gap = gap_over_time(db, session_id, a, b)
        if gap:
            last = gap[-1]
            pair["cumulative_gap_after_lap"] = {"lap": last["lap"], "gap": last["gap_formatted"], "meaning": f"positive means {na} was behind"}
        from .facts import _positions

        pos = _positions(db, session_id)
        together = sum(1 for lap, p in pos.get(a, {}).items() if pos.get(b, {}).get(lap) is not None and abs(pos[b][lap] - p) == 1)
        pair["laps_running_next_to_each_other"] = together
        pits = [{c.name: getattr(x, c.name) for c in x.__table__.columns} for x in db.scalars(select(PitStop).where(PitStop.session_id == session_id)).all()]
        starts: dict[int, dict] = {}
        for lp in db.scalars(select(Lap).where(Lap.session_id == session_id, Lap.driver_id.in_((a, b)), Lap.lap_start_time.is_not(None))).all():
            starts.setdefault(lp.driver_id, {})[lp.lap_number] = lp.lap_start_time
        for bt in pit_battles(pits, pos, starts, []):
            if {bt.attacker_id, bt.defender_id} == {a, b} and not bt.under_neutralisation:
                att, dfn = (na, nb) if bt.attacker_id == a else (nb, na)
                v.append({
                    "undercut_worked": f"{att} undercut {dfn}: he pitted first (lap {bt.attacker_lap}) and was ahead once {dfn} stopped (lap {bt.defender_lap}).",
                    "undercut_failed": f"{att} pitted first (lap {bt.attacker_lap}) to undercut {dfn} but was still behind once {dfn} stopped (lap {bt.defender_lap}).",
                    "stayed_ahead": f"{att} pitted first (lap {bt.attacker_lap}) and stayed ahead of {dfn}, who stopped on lap {bt.defender_lap}.",
                    "overcut_worked": f"{dfn} overcut {att}: he stayed out until lap {bt.defender_lap} and came out ahead.",
                }[bt.verdict])
    elif session.session_type in ("Q", "SQ"):
        pa, pb = ra.get("position"), rb.get("position")
        if pa and pb:
            first, second = (na, nb) if pa < pb else (nb, na)
            v.append(f"{first} out-qualified {second}: P{min(pa, pb)} to P{max(pa, pb)}.")
        for f, n in ((fa, na), (fb, nb)):
            pair["drivers"][n]["times"] = (f.get("result") or {}).get("times")
    else:
        pa, pb = ra.get("position"), rb.get("position")
        if pa and pb:
            v.append(f"{na if pa < pb else nb} was faster: P{min(pa, pb)} to P{max(pa, pb)}.")
        for f, n in ((fa, na), (fb, nb)):
            pair["drivers"][n]["best_lap"] = (f.get("result") or {}).get("best_lap")
    cards = event_drivers(db, session.event_id)
    numbers = {c["number"]: i for i, c in cards.items() if c.get("number") is not None}
    shared = [c for c in cases(parse_messages(db.scalars(select(RaceControl).where(RaceControl.session_id == session_id)).all(), numbers)) if {a, b} <= set(c["driver_ids"])]
    incidents = [{"lap": c["opened_lap"], "turn": c["turn"], "reason": c["reason"], "outcome": c["outcome"] or ("investigated after the race" if c["after_race"] else "noted")} for c in shared]
    if incidents:  # an empty list only invited "No shared incidents were recorded" (#65)
        pair["shared_incidents"] = incidents
    for c in incidents:
        v.append(f"The stewards looked at an incident between them{' at turn ' + str(c['turn']) if c['turn'] else ''}{' on lap ' + str(c['lap']) if c['lap'] else ''}: {c['outcome']}.")
    return pair


def pair_template(pair: dict[str, Any]) -> dict[str, str]:
    (na, da), (nb, db_) = list(pair["drivers"].items())
    text = f"{na}: {da['result']}. {nb}: {db_['result']}. " + " ".join(pair["verdicts"])
    if pair.get("laps_running_next_to_each_other"):
        text += f" They ran next to each other for {pair['laps_running_next_to_each_other']} laps."
    return {"comparison_text": text.strip()}


def comparison_pairs(db: OrmSession, session_id: int, driver_ids: list[int]) -> list[tuple[int, int]]:
    """Pairs worth a written head-to-head: teammates; in races also cars that finished next to each
    other and cars the stewards looked at together (REVIEW #15). Other pairs get the charts only."""
    from ..analysis.race_control import cases, parse_messages
    from ..ingest.entries import event_drivers
    from ..models import HeadlineRace, RaceControl
    from itertools import combinations

    session = db.get(Session, session_id)
    cards = event_drivers(db, session.event_id, set(driver_ids))
    pairs = {(x, y) for x, y in combinations(sorted(cards), 2) if cards[x]["team"] == cards[y]["team"] and not cards[x]["practice_only"] and not cards[y]["practice_only"]}
    if session.session_type == "R":
        fin = sorted((r.finish_position, r.driver_id) for r in db.scalars(select(HeadlineRace).where(HeadlineRace.session_id == session_id)).all() if r.finish_position)
        pairs |= {tuple(sorted((x[1], y[1]))) for x, y in zip(fin, fin[1:]) if y[0] <= 12}
        numbers = {c["number"]: i for i, c in event_drivers(db, session.event_id).items() if c.get("number") is not None}
        for c in cases(parse_messages(db.scalars(select(RaceControl).where(RaceControl.session_id == session_id)).all(), numbers)):
            if len(c["driver_ids"]) == 2:
                pairs.add(tuple(sorted(c["driver_ids"])))
    return sorted(pairs)


def plan_comparison_narrative(db: OrmSession, session_id: int, driver_a: int, driver_b: int, *, force: bool = False) -> tuple[ComparisonNarrative | None, StoryJob | None]:
    from .factcheck import check_story
    from .facts import story_context
    from .jobs import Outcome

    a, b = sorted((driver_a, driver_b))
    pair = build_pair_facts(db, session_id, a, b)
    h = stable_hash({"comparison_prompt": COMPARISON_PROMPT_VERSION, **pair})
    existing = _existing(db, session_id, a, b)
    if existing and existing.input_hash == h and not force:
        return existing, None
    ctx = story_context(db, session_id)

    def save(db: OrmSession, outcome: Outcome) -> ComparisonNarrative:
        row = _existing(db, session_id, a, b)
        if row is None:
            row = ComparisonNarrative(session_id=session_id, driver_a_id=a, driver_b_id=b, comparison_text="", generated_at=utcnow(), model_used=outcome.model, input_hash=h)
            db.add(row)
        row.comparison_text = outcome.data["comparison_text"].strip()
        row.generated_at = utcnow()
        row.model_used = "template" if outcome.fallback else outcome.model
        row.input_hash = h
        db.flush()
        return row

    user = "HEAD-TO-HEAD FACTS (JSON):\n" + json.dumps(prompt_pair(pair), indent=1, default=str, ensure_ascii=False)
    sheet = {**pair, "driver": {"teammate": " and ".join(pair["drivers"]) if pair["teammates"] else None}}
    job = StoryJob(f"comparison session={session_id} {a} vs {b}", SYSTEM_COMPARISON, user, SCHEMA_COMPARISON, save,
                   check=lambda data: check_story(data, sheet, roster=ctx["roster"], entrants=ctx["entrants"], limits=LIMITS),
                   fallback=lambda: pair_template(pair))
    return existing, job


def get_or_generate_comparison_narrative(db: OrmSession, session_id: int, driver_a: int, driver_b: int, *, force: bool = False) -> ComparisonNarrative:
    existing, job = plan_comparison_narrative(db, session_id, driver_a, driver_b, force=force)
    return existing if job is None else job.run(db)
