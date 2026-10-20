"""Turn-by-turn reconciliation (#8) and key moments (#9, #14)."""
from __future__ import annotations

import re

import pytest

from .conftest import DATA_DIR, all_sessions, load, params

TOLERANCE_MS = 50


def _turn_files():
    for _, s in all_sessions():
        d = DATA_DIR / "sessions" / str(s["id"]) / "drivers"
        if d.exists():
            for f in sorted(d.glob("*/turn-deltas.json")):
                yield s["id"], int(f.parent.name)


def test_turn_deltas_reconcile():
    """#8: corner deltas + the unattributed remainder = the stated total = lap time - reference lap time."""
    bad = []
    n = 0
    for sid, did in _turn_files():
        td = load(f"sessions/{sid}/drivers/{did}/turn-deltas")
        n += 1
        if td.get("is_reference_lap"):
            continue
        corners = sum(t["delta_ms"] for t in td["turns"])
        total = td.get("total_lap_delta_ms")
        rest = td.get("unattributed_ms", 0) or 0
        lap, ref = td.get("lap_time_ms"), (td.get("reference") or {}).get("lap_time_ms")
        problems = []
        if total is None or abs(corners + rest - total) > TOLERANCE_MS:
            problems.append(f"corners {corners:.0f} + unattributed {rest:.0f} != total {total}")
        if lap is None or ref is None or total is None or abs((lap - ref) - total) > TOLERANCE_MS:
            problems.append(f"total {total} != lap {lap} - reference {ref}")
        if (td.get("reference") or {}).get("session_id") != sid:
            problems.append("reference lap is from another session")
        if problems:
            bad.append((sid, did, problems))
    if n == 0:  # none published yet (old breakdowns are withheld until recomputed): nothing wrong is shown
        pytest.skip("no turn-by-turn breakdowns exported yet")
    assert not bad, f"{len(bad)}/{n} turn breakdowns don't reconcile, e.g. {bad[:3]}"


def _race_control(sid):
    rc = load(f"sessions/{sid}/race-control")
    assert rc is not None, "race-control timeline not exported"
    return rc


@params("R", "S")
def test_every_neutralisation_is_a_key_moment(sid):
    """#14: each SC, VSC and red flag in race control is among the key moments."""
    rc = _race_control(sid)
    periods = rc["periods"]
    moments = load(f"sessions/{sid}/pivotal-moments")
    neutral = [m for m in moments if m["moment_type"] in ("safety_car", "vsc", "red_flag")]
    missing = [p for p in periods if not any(m["lap_number"] == p["start_lap"] for m in neutral)]
    assert not missing, f"neutralisations without a key moment: {missing} (moments: {[(m['lap_number'], m['moment_type']) for m in neutral]})"


@params("R", "S")
def test_pit_moments_use_known_compounds(sid):
    """#9: a pit-stop moment never says 'compound unknown' when both stints have a compound."""
    detail = load(f"sessions/{sid}/stints") or load(f"sessions/{sid}/detail")
    stints = detail["stint_timeline"]
    known = {(s["driver_id"], s["lap_end"]): s["compound"] for s in stints if s.get("compound")}
    bad = []
    for m in load(f"sessions/{sid}/pivotal-moments"):
        if m["moment_type"] == "pit_stop" and ("unknown" in m["description"].lower() or "?" in m["description"]):
            if (m["driver_id"], m["lap_number"]) in known:
                bad.append(m["description"])
    assert not bad, bad[:3]


@params("R")
def test_key_moments_are_not_routine_stops(sid):
    """#9: a pit stop that only cycles a car back through the order isn't a key moment."""
    for m in load(f"sessions/{sid}/pivotal-moments"):
        if m["moment_type"] == "pit_stop":
            assert re.search(r"slow|lost|gained|undercut|overcut|under the|unsafe|penalty", m["description"], re.I), (
                f"routine stop listed as key: {m['description']}"
            )


def test_turn_delta_index_matches_the_exported_breakdowns():
    """REVIEW_ROUND2 #48: the page asks the index before fetching a breakdown, so the two must agree."""
    for _, s in all_sessions():
        index = load(f"sessions/{s['id']}/turn-deltas")
        assert index is not None, f"session {s['id']} has no turn-deltas index"
        files = sorted(int(p.parent.name) for p in (DATA_DIR / "sessions" / str(s["id"]) / "drivers").glob("*/turn-deltas.json"))
        assert sorted(index["drivers"]) == files, f"session {s['id']}: index {index['drivers']} vs files {files}"


def test_every_session_page_finds_its_midfield_file():
    """REVIEW_ROUND2 #48: always present (null when no story stood out), never a 404 on the live site."""
    missing = [s["id"] for _, s in all_sessions() if not (DATA_DIR / "sessions" / str(s["id"]) / "midfield-spotlight.json").exists()]
    assert not missing, f"sessions without midfield-spotlight.json: {missing}"


# --- REVIEW_ROUND3 #48, #49: corner colours that tell the truth --------------------------------

def _corner_bound_ms(t: dict) -> float:
    """The export's plausibility bound (analysis.turns.corner_implausible): max(1.5s, 20% of the corner)."""
    return max(1500.0, 0.2 * t["corner_ms"] if t.get("corner_ms") else 0.0)


def _purple(t: dict) -> bool:
    """What the map paints purple. Exports from before #49 have no rank; the site then painted any
    corner that beat the reference lap by 30ms purple, so that is what is checked for them."""
    return t["rank"] == 1 if "rank" in t else t["delta_ms"] <= -30


def _session_breakdowns():
    by_session: dict[int, dict[int, dict]] = {}
    for sid, did in _turn_files():
        by_session.setdefault(sid, {})[did] = load(f"sessions/{sid}/drivers/{did}/turn-deltas")
    return by_session


def test_no_exported_corner_delta_is_implausible():
    """#48: Baku FP1 Norris read +98.9s at T1 and 0.6-12.5s faster than the session best everywhere else."""
    bad = []
    for sid, drivers in _session_breakdowns().items():
        for did, td in drivers.items():
            if td.get("is_reference_lap"):
                continue
            worst = max(td["turns"], key=lambda t: abs(t["delta_ms"]) - _corner_bound_ms(t))
            if abs(worst["delta_ms"]) > _corner_bound_ms(worst):
                bad.append((sid, did, f"T{worst['number']} {worst['delta_ms']:+.0f}ms"))
            elif sum(abs(t["delta_ms"]) for t in td["turns"]) > abs(td["total_lap_delta_ms"]) + max(3000, 200 * len(td["turns"])):
                bad.append((sid, did, "corner deltas cancel out"))
    assert not bad, f"{len(bad)} breakdowns shown with impossible corners, e.g. {bad[:5]}"


def test_exactly_one_driver_is_purple_at_each_corner():
    """#49: purple means the fastest of anyone through that corner, as it does for sectors."""
    bad = []
    for sid, drivers in _session_breakdowns().items():
        n_turns = len(next(iter(drivers.values()))["turns"])
        for i in range(n_turns):
            purple = [d for d, td in drivers.items() if i < len(td["turns"]) and _purple(td["turns"][i])]
            if len(purple) != 1:
                bad.append((sid, f"corner {i + 1}", len(purple)))
    assert not bad, f"{len(bad)} corners with other than one purple driver, e.g. {bad[:5]}"


def test_a_slow_sector_is_never_purple_all_the_way_through():
    """#48/#49: a driver ranked 15th or worse in a sector can't be fastest of all at every corner in it."""
    bad = []
    for sid, drivers in _session_breakdowns().items():
        best = (load(f"sessions/{sid}/sectors") or {}).get("best", [])
        ranks = {}
        for sec in (1, 2, 3):
            order = sorted((b for b in best if b["sector"] == sec and b["best_ms"]), key=lambda b: b["best_ms"])
            ranks.update({(b["driver_id"], sec): i + 1 for i, b in enumerate(order)})
        for did, td in drivers.items():
            for sec in (1, 2, 3):
                corners = [t for t in td["turns"] if t["sector"] == sec]
                if corners and ranks.get((did, sec), 0) >= 15 and all(_purple(t) for t in corners):
                    bad.append((sid, did, f"S{sec} ranked {ranks[(did, sec)]}"))
    assert not bad, f"{len(bad)} slow sectors painted purple throughout, e.g. {bad[:5]}"


def test_purple_corners_are_rare():
    """#49: a quarter of all corners on the site were purple. One per corner per session is ~5%."""
    corners = [t for drivers in _session_breakdowns().values() for td in drivers.values() for t in td["turns"]]
    if not corners:
        pytest.skip("no turn-by-turn breakdowns exported yet")
    share = sum(_purple(t) for t in corners) / len(corners)
    assert share < 0.10, f"{share:.1%} of all corners are purple"
