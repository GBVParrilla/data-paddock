"""Classification invariants: statuses, counts, order, qualifying segments, race distance."""
from __future__ import annotations

from collections import Counter

from .conftest import load, params

STATUS_CODES = {"FIN", "LAP", "DNF", "DNS", "DSQ", "NC"}
QUALI_CODES = {"OK", "NO_TIME", "DNS", "DSQ"}


@params("R", "S")
def test_race_status_is_an_enum_and_counts_agree(sid):
    """#6: DNS is never shown as DNF, and the summary counts equal the table rows."""
    h = load(f"sessions/{sid}/headline")
    rows = h["race"]
    codes = [r.get("status_code") for r in rows]
    assert set(codes) <= STATUS_CODES, f"unknown status codes {set(codes) - STATUS_CODES}"
    counts = Counter(codes)
    summary = h.get("summary") or {}
    assert summary.get("dnf") == counts["DNF"] + counts["NC"], f"summary {summary} vs rows {dict(counts)}"
    assert summary.get("dns") == counts["DNS"], f"summary {summary} vs rows {dict(counts)}"
    assert summary.get("dsq") == counts["DSQ"], f"summary {summary} vs rows {dict(counts)}"
    for r in rows:
        if r["status_code"] == "DNS":
            assert r.get("finish_position") is None, f"DNS driver {r['driver_id']} has a finishing position"
            assert not r.get("laps_completed"), f"DNS driver {r['driver_id']} completed laps"


@params("R", "S")
def test_classification_order(sid):
    """#13: classified cars in position order, then the unclassified (most laps first), DNS, DSQ."""
    rows = load(f"sessions/{sid}/headline")["race"]
    classified = [r for r in rows if r.get("finish_position")]
    assert [r["finish_position"] for r in classified] == list(range(1, len(classified) + 1)), "classified positions are not 1..n"
    assert rows[: len(classified)] == classified, "an unclassified car is listed between classified ones"
    rest = rows[len(classified):]
    rank = {"DNF": 0, "NC": 0, "DNS": 1, "DSQ": 2}
    keys = [(rank.get(r["status_code"], 0), -(r.get("laps_completed") or 0)) for r in rest]
    assert keys == sorted(keys), f"unclassified order {[(r['status_code'], r.get('laps_completed')) for r in rest]}"


@params("R", "S")
def test_position_chart_covers_race_distance(sid):
    """#12: the position chart ends on the winner's final lap."""
    h = load(f"sessions/{sid}/headline")
    d = load(f"sessions/{sid}/positions") or load(f"sessions/{sid}/detail")
    winner = next(r for r in h["race"] if r.get("finish_position") == 1)
    distance = winner["laps_completed"]
    laps = [p["lap_number"] for p in d["position_by_lap"]]
    assert max(laps) == distance, f"chart ends at lap {max(laps)}, race distance {distance}"
    for r in h["race"]:
        if r["status_code"] == "FIN":
            mine = [p["lap_number"] for p in d["position_by_lap"] if p["driver_id"] == r["driver_id"]]
            assert mine and max(mine) == distance, f"finisher {r['driver_id']} chart ends at {max(mine) if mine else None}"


@params("Q", "SQ")
def test_qualifying_gaps_are_per_segment_and_ordered(sid):
    """#7: a gap compares times from one segment, and within a segment gaps grow with position."""
    rows = load(f"sessions/{sid}/headline")["qualifying"]
    codes = {r.get("status_code") for r in rows}
    assert codes <= QUALI_CODES, f"unknown quali status codes {codes - QUALI_CODES}"
    by_seg: dict[str, list[dict]] = {}
    for r in rows:
        if r.get("gap_ms") is not None:
            assert r.get("gap_segment") in ("Q1", "Q2", "Q3"), f"driver {r['driver_id']} gap has no segment"
            by_seg.setdefault(r["gap_segment"], []).append(r)
    for seg, lst in by_seg.items():
        lst.sort(key=lambda r: r["position"])
        gaps = [r["gap_ms"] for r in lst]
        assert gaps == sorted(gaps), f"{seg} gaps not increasing with position: {[(r['position'], r['gap_ms']) for r in lst]}"
        assert gaps[0] >= 0


@params("Q", "SQ")
def test_qualifying_lists_every_entrant(sid):
    """#7: every car entered for the weekend appears, including drivers who set no time."""
    h = load(f"sessions/{sid}/headline")
    listed = {r["driver_id"] for r in h["qualifying"]}
    entrants = {int(k) for k in h["drivers"]}
    assert entrants and listed == entrants, f"missing from classification: {sorted(entrants - listed)}"


@params("Q", "SQ")
def test_gap_pole_to_p10_uses_final_segment(sid):
    """#7: the 'gap pole to P10' figure compares two final-segment times."""
    rows = sorted(load(f"sessions/{sid}/headline")["qualifying"], key=lambda r: r["position"] or 99)
    if len(rows) >= 10 and rows[9].get("gap_ms") is not None:
        assert rows[9]["gap_segment"] == "Q3", f"P10 gap measured in {rows[9]['gap_segment']}"
