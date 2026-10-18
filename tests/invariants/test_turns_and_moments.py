"""Turn-by-turn reconciliation (#8) and key moments (#9, #14)."""
from __future__ import annotations

import re

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
    assert n > 0, "no turn-delta files exported"
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
