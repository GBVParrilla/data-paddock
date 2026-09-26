"""Headline (casual-fan) analytics. Pure functions: row dicts in, row dicts out."""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from ..util import fmt_ms

LapRow = dict[str, Any]
ResultRow = dict[str, Any]


def clean_laps(laps: list[LapRow]) -> list[LapRow]:
    return [lp for lp in laps if lp.get("lap_time_ms") and not lp.get("is_pit_lap")]


def compute_headline_practice(laps: list[LapRow]) -> list[dict]:
    best: dict[int, int] = {}
    for lp in clean_laps(laps):
        d = lp["driver_id"]
        if d not in best or lp["lap_time_ms"] < best[d]:
            best[d] = lp["lap_time_ms"]
    if not best:
        return []
    fastest = min(best.values())
    ranked = sorted(best.items(), key=lambda kv: kv[1])
    return [
        dict(driver_id=d, fastest_lap_ms=t, gap_to_fastest_ms=t - fastest, rank=i + 1)
        for i, (d, t) in enumerate(ranked)
    ]


def _best_quali_time(r: ResultRow) -> int | None:
    times = [r.get(k) for k in ("q1_ms", "q2_ms", "q3_ms") if r.get(k)]
    return min(times) if times else None


def compute_headline_qualifying(results: list[ResultRow]) -> list[dict]:
    pole = next((r for r in results if r.get("position") == 1), None)
    pole_ms = (pole.get("q3_ms") or _best_quali_time(pole)) if pole else None
    out = []
    for r in results:
        if r.get("q3_ms"):
            eliminated = None
        elif r.get("q2_ms"):
            eliminated = "Q2"
        else:
            eliminated = "Q1"
        # gap is measured on the last segment the driver reached (Q3 time for Q3 runners, etc.) vs pole's Q3
        best = r.get("q3_ms") or r.get("q2_ms") or r.get("q1_ms")
        gap = (best - pole_ms) if (best is not None and pole_ms is not None) else None
        out.append(dict(driver_id=r["driver_id"], position=r.get("position"), gap_to_pole_ms=gap, eliminated_in=eliminated))
    return out


def compute_headline_race(results: list[ResultRow], pit_stops: list[dict]) -> list[dict]:
    stops = defaultdict(int)
    for p in pit_stops:
        stops[p["driver_id"]] += 1
    out = []
    for r in results:
        grid = r.get("grid_position")
        pos = r.get("position")
        classified = r.get("status") in ("Finished", "Lapped") or (r.get("status") or "").startswith("+")
        gained = (grid - pos) if (grid and pos and classified) else None
        out.append(
            dict(
                driver_id=r["driver_id"],
                finish_position=pos,
                grid_position=grid,
                positions_gained=gained,
                points=float(r.get("points") or 0),
                pit_stop_count=stops.get(r["driver_id"], 0),
                status=r.get("status"),
            )
        )
    return out


def compute_session_summary(
    session_type: str,
    event_name: str,
    names: dict[int, str],
    *,
    practice: list[dict] | None = None,
    qualifying: list[dict] | None = None,
    race: list[dict] | None = None,
) -> str:
    """Templated one-liner. No LLM."""
    label = {"FP1": "FP1", "FP2": "FP2", "FP3": "FP3", "Q": "qualifying", "SQ": "sprint qualifying", "S": "the sprint", "R": "the race"}[session_type]
    if session_type in ("FP1", "FP2", "FP3") and practice:
        top = sorted(practice, key=lambda r: r["rank"])[:3]
        parts = [f"{names.get(top[0]['driver_id'], '?')} topped {label} at the {event_name} with a {fmt_ms(top[0]['fastest_lap_ms'])}"]
        if len(top) > 1:
            parts.append(f"{fmt_ms(top[1]['gap_to_fastest_ms'])}s clear of {names.get(top[1]['driver_id'], '?')}")
        if len(top) > 2:
            parts.append(f"with {names.get(top[2]['driver_id'], '?')} third (+{fmt_ms(top[2]['gap_to_fastest_ms'])}s)")
        return ", ".join(parts) + "."
    if session_type in ("Q", "SQ") and qualifying:
        ordered = sorted([r for r in qualifying if r.get("position")], key=lambda r: r["position"])
        if not ordered:
            return f"No classification available for {label} at the {event_name}."
        pole = ordered[0]
        text = f"{names.get(pole['driver_id'], '?')} took pole for {label} at the {event_name}"
        if len(ordered) > 1:
            text += f", {fmt_ms(ordered[1]['gap_to_pole_ms'])}s ahead of {names.get(ordered[1]['driver_id'], '?')}"
        q1_out = [names.get(r["driver_id"], "?") for r in ordered if r.get("eliminated_in") == "Q1"]
        if q1_out:
            text += f". Out in Q1: {', '.join(q1_out)}"
        return text + "."
    if session_type in ("R", "S") and race:
        ordered = sorted([r for r in race if r.get("finish_position")], key=lambda r: r["finish_position"])
        if not ordered:
            return f"No classification available for {label} at the {event_name}."
        w = ordered[0]
        text = f"{names.get(w['driver_id'], '?')} won {label} at the {event_name}"
        if w.get("grid_position"):
            text += " from pole" if w["grid_position"] == 1 else f" from P{w['grid_position']}"
        if len(ordered) > 2:
            text += f", ahead of {names.get(ordered[1]['driver_id'], '?')} and {names.get(ordered[2]['driver_id'], '?')}"
        movers = [r for r in ordered if r.get("positions_gained") is not None]
        if movers:
            m = max(movers, key=lambda r: r["positions_gained"])
            if m["positions_gained"] >= 3:
                text += f". Biggest mover: {names.get(m['driver_id'], '?')} (P{m['grid_position']} to P{m['finish_position']})"
        dnfs = [names.get(r["driver_id"], "?") for r in race if (r.get("status") or "").lower() in ("retired", "accident", "collision", "engine", "gearbox", "hydraulics", "disqualified")]
        if dnfs:
            text += f". Retirements: {', '.join(dnfs)}"
        return text + "."
    return f"No summary available for {label} at the {event_name}."
