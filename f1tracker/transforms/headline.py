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


RETIRED_WORDS = ("retired", "accident", "collision", "engine", "gearbox", "hydraulics", "power", "brakes", "suspension", "spun", "damage", "withdrew")


def race_status(position_text: str | None, status: str | None, laps: int | None, winner_laps: int | None) -> tuple[str, int | None]:
    """(status code, classified position) from Jolpica's positionText + status.

    Codes: FIN (lead lap), LAP (classified, laps down), DNF (retired; may still be classified if it
    covered 90% of the distance), NC (running but not classified), DNS, DSQ.
    """
    pt = (position_text or "").strip().upper()
    raw = (status or "").strip().lower()
    position = int(pt) if pt.isdigit() else None
    if pt == "W" or raw in ("did not start", "dns", "withdrew", "withdrawn") or (pt == "" and raw.startswith("did not")):
        return "DNS", None
    if pt in ("D", "E") or raw in ("disqualified", "dsq", "excluded"):
        return "DSQ", None
    if pt == "F":
        return "DNS", None  # failed to qualify: never started
    if pt == "N":
        return "NC", None
    if pt == "R":
        return "DNF", None
    if position is None and not pt:  # older rows without positionText
        if raw in ("finished",) or raw.startswith("+") or raw == "lapped":
            position = -1
        else:
            return "DNF", None
    retired = any(w in raw for w in RETIRED_WORDS)
    if retired:
        return "DNF", position if position and position > 0 else None
    down = (winner_laps - laps) if (winner_laps is not None and laps is not None) else None
    code = "LAP" if (down or 0) > 0 or raw == "lapped" or raw.startswith("+") else "FIN"
    return code, position if position and position > 0 else None


def compute_headline_qualifying(results: list[ResultRow], entrants: list[int] | None = None) -> list[dict]:
    """Every entrant, with the gap measured inside one segment.

    A driver knocked out in Q1 is compared with the fastest Q1 time, a Q2 exit with the fastest Q2
    time, and a Q3 runner with pole - never a Q3 lap against a Q1 lap. Entrants with no result
    (no time set) are listed last as NO_TIME.
    """
    out = []
    seg_best = {}
    field = max(len(results), len(entrants or []))
    q2_cut = 10 + (field - 10) // 2  # 22 cars: 6 out in Q1, 6 in Q2; 20 cars: 5 and 5
    for key in ("q1_ms", "q2_ms", "q3_ms"):
        times = [r[key] for r in results if r.get(key)]
        seg_best[key] = min(times) if times else None
    for r in sorted(results, key=lambda r: r.get("position") or 999):
        q1, q2, q3 = r.get("q1_ms"), r.get("q2_ms"), r.get("q3_ms")
        pos = r.get("position")
        # a Q3 runner who set no Q3 time is still a Q3 runner: the classification position says so
        by_pos = "Q3" if pos and pos <= 10 else "Q2" if pos and pos <= q2_cut else "Q1"
        by_time = "Q3" if q3 else "Q2" if q2 else "Q1"
        reached = max(by_pos, by_time)
        seg_key = {"Q1": "q1_ms", "Q2": "q2_ms", "Q3": "q3_ms"}[reached]
        mine = r.get(seg_key)
        gap = (mine - seg_best[seg_key]) if (mine is not None and seg_best[seg_key] is not None) else None
        status = "OK" if (q1 or q2 or q3) else "NO_TIME"
        out.append(
            dict(
                driver_id=r["driver_id"],
                position=r.get("position"),
                gap_to_pole_ms=gap,
                gap_segment=reached if gap is not None else None,
                eliminated_in=None if reached == "Q3" else reached,
                status_code=status,
                q1_ms=q1,
                q2_ms=q2,
                q3_ms=q3,
            )
        )
    listed = {r["driver_id"] for r in out}
    for did in entrants or []:
        if did not in listed:
            out.append(dict(driver_id=did, position=None, gap_to_pole_ms=None, gap_segment=None, eliminated_in="Q1", status_code="NO_TIME", q1_ms=None, q2_ms=None, q3_ms=None))
    return out


def compute_headline_race(results: list[ResultRow], pit_stops: list[dict]) -> list[dict]:
    from ..analysis.strategy import real_stops

    stops = defaultdict(int)
    for p in real_stops(pit_stops):
        stops[p["driver_id"]] += 1
    ordered = sorted(results, key=lambda r: r.get("position") or 999)
    winner = next((r for r in ordered if (r.get("position_text") or str(r.get("position"))) == "1"), ordered[0] if ordered else None)
    winner_laps = winner.get("laps_completed") if winner else None
    out = []
    for i, r in enumerate(ordered):
        code, pos = race_status(r.get("position_text"), r.get("status"), r.get("laps_completed"), winner_laps)
        if pos == -1:  # legacy row without positionText: trust the stored order
            pos = r.get("position")
        grid = r.get("grid_position")
        laps = r.get("laps_completed")
        gained = (grid - pos) if (grid and pos) else None
        out.append(
            dict(
                driver_id=r["driver_id"],
                finish_position=pos,
                classification_order=i + 1,
                grid_position=grid,
                positions_gained=gained,
                points=float(r.get("points") or 0),
                pit_stop_count=stops.get(r["driver_id"], 0),
                status=r.get("status"),
                status_code=code,
                laps_completed=laps if code != "DNS" else 0,
                laps_down=(winner_laps - laps) if (code == "LAP" and winner_laps is not None and laps is not None) else None,
            )
        )
    return out


def race_counts(rows: list[dict]) -> dict[str, int]:
    """The one place DNF/DNS/DSQ are counted; cards, tables and stories all read this."""
    c = defaultdict(int)
    for r in rows:
        c[r["status_code"]] += 1
    return {"classified": sum(1 for r in rows if r.get("finish_position")), "dnf": c["DNF"] + c["NC"], "dns": c["DNS"], "dsq": c["DSQ"]}


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
        dnfs = [names.get(r["driver_id"], "?") for r in race if r.get("status_code") in ("DNF", "NC")]
        dns = [names.get(r["driver_id"], "?") for r in race if r.get("status_code") == "DNS"]
        if dnfs:
            text += f". Retirements: {', '.join(dnfs)}"
        if dns:
            text += f". Did not start: {', '.join(dns)}"
        return text + "."
    return f"No summary available for {label} at the {event_name}."
