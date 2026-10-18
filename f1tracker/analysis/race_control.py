"""Race-control messages as typed, shared incident facts.

One parser feeds the incident timeline on the site, the key-moment engine and the story fact
sheets, so two drivers involved in the same incident are always told the same thing.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime

_CARS_RE = re.compile(r"\bCARS?\s+((?:\d+\s*(?:\([A-Z]{3}\))?(?:\s*,\s*|\s+AND\s+)?)+)")
_NUM_RE = re.compile(r"(\d+)\s*(?:\(([A-Z]{3})\))?")
_TURN_RE = re.compile(r"\bTURN\s+(\d+)\b")
_REASON_RE = re.compile(r"\s-\s(?!LAP\b)([A-Z][A-Z ,/'-]+?)(?:\s+\d{1,2}:\d{2}:\d{2})?$")


@dataclass
class Incident:
    kind: str  # neutralisation | red_flag | penalty | investigation | decision | track_limits | warning | info
    lap: int | None
    time: datetime | None
    message: str
    car_numbers: list[int] = field(default_factory=list)
    driver_ids: list[int] = field(default_factory=list)
    turn: int | None = None
    reason: str | None = None  # "STARTING PROCEDURE INFRINGEMENT", "FORCING ANOTHER DRIVER OFF THE TRACK"
    outcome: str | None = None  # for decisions: "no further action", "5 second time penalty", ...
    neutralisation: str | None = None  # SC | VSC, with deployed/ending in `phase`
    phase: str | None = None


def car_numbers(message: str) -> list[int]:
    m = _CARS_RE.search(message.upper())
    if not m:
        return []
    return [int(n) for n, _ in _NUM_RE.findall(m.group(1))]


def classify(message: str, category: str | None, flag: str | None, lap: int | None = None, time: datetime | None = None) -> Incident | None:
    """Typed incident for a race-control message, or None for routine traffic (sector flags, DRS, pit lane open...)."""
    text = (message or "").strip()
    up = text.upper()
    inc = Incident(kind="info", lap=lap, time=time, message=text, car_numbers=car_numbers(up))
    t = _TURN_RE.search(up)
    inc.turn = int(t.group(1)) if t else None
    if category == "SafetyCar" or up.startswith("VSC") or "SAFETY CAR" in up:
        inc.kind = "neutralisation"
        inc.neutralisation = "VSC" if ("VIRTUAL" in up or up.startswith("VSC")) else "SC"
        inc.phase = "deployed" if "DEPLOYED" in up else "ending" if ("ENDING" in up or "IN THIS LAP" in up) else "other"
        return inc if inc.phase != "other" else None
    if (flag or "").upper() == "RED" or (category == "SessionStatus" and ("ABORTED" in up or "SUSPENDED" in up)):
        inc.kind = "red_flag"
        return inc
    if (flag or "").upper() == "BLACK AND WHITE":
        inc.kind = "warning"
        return inc
    if "DELETED" in up and "TRACK LIMITS" in up:
        inc.kind = "track_limits"
        return inc
    rm = _REASON_RE.search(up)
    if "PENALTY" in up and "SERVED" not in up and "NO FURTHER" not in up and "UNDER INVESTIGATION" not in up:
        inc.kind = "penalty"
        inc.outcome = re.sub(r"^FIA STEWARDS:\s*", "", up).split(" FOR ")[0].strip().lower()
        inc.reason = rm.group(1).strip() if rm else None
        return inc
    if "NO FURTHER" in up or "REVIEWED" in up:
        inc.kind = "decision"
        inc.outcome = "no further action"
        inc.reason = rm.group(1).strip() if rm else None
        return inc
    if "INCIDENT" in up and ("NOTED" in up or "INVESTIGAT" in up):
        inc.kind = "investigation"
        inc.reason = rm.group(1).strip() if rm else None
        return inc
    if "MEDICAL CAR" in up or "SLIPPERY" in up:
        return inc
    return None


def parse_messages(rows, number_to_driver: dict[int, int]) -> list[Incident]:
    """rows: objects with message/category/flag/lap_number/timestamp/driver_id (RaceControl)."""
    out = []
    for r in sorted(rows, key=lambda r: r.timestamp):
        inc = classify(r.message, r.category, r.flag, r.lap_number, r.timestamp)
        if inc is None:
            continue
        ids = [number_to_driver[n] for n in inc.car_numbers if n in number_to_driver]
        if not ids and r.driver_id:
            ids = [r.driver_id]
        inc.driver_ids = ids
        out.append(inc)
    return out


def neutral_periods(incidents: list[Incident]) -> list[dict]:
    """[{kind: SC|VSC|RED, start_lap, end_lap}] - each deployment paired with its end."""
    periods: list[dict] = []
    open_p: dict | None = None
    for inc in incidents:
        if inc.kind == "neutralisation" and inc.phase == "deployed":
            if open_p:
                periods.append(open_p)
            open_p = {"kind": inc.neutralisation, "start_lap": inc.lap, "end_lap": None}
        elif inc.kind == "neutralisation" and inc.phase == "ending" and open_p:
            open_p["end_lap"] = inc.lap
            periods.append(open_p)
            open_p = None
        elif inc.kind == "red_flag":
            if open_p:
                periods.append(open_p)
                open_p = None
            periods.append({"kind": "RED", "start_lap": inc.lap, "end_lap": inc.lap, "time": inc.time})
    if open_p:
        periods.append(open_p)
    # a red flag repeats (one message per marshal post): keep one per lap/minute
    seen, unique = set(), []
    for p in periods:
        key = (p["kind"], p["start_lap"], p.get("time").strftime("%H:%M") if p.get("time") else None)
        if key not in seen:
            seen.add(key)
            unique.append(p)
    return unique


_KEEP_UPPER = {"VSC", "SC", "FIA", "DRS", "DNF", "DNS", "DSQ", "F1"}


def tidy(message: str) -> str:
    """Race control writes in capitals; readers get sentence case with driver codes kept."""
    words = []
    for w in message.strip().split():
        core = w.strip("(),.:;")
        if re.fullmatch(r"\(?[A-Z]{3}\)?[,.]?", w) and w.startswith("("):
            words.append(w)  # (OCO)
        elif core in _KEEP_UPPER:
            words.append(w)
        else:
            words.append(w.lower())
    text = " ".join(words)
    text = re.sub(r"^FIA stewards:\s*", "Stewards: ", text)
    text = re.sub(r"\s\d{1,2}:\d{2}:\d{2}$", "", text)  # trailing wall-clock time
    return text[:1].upper() + text[1:]


def cases(incidents: list[Incident]) -> list[dict]:
    """Investigations grouped into one case per (cars, turn, reason): noted -> investigated -> decision.

    A case is the shared fact both drivers' stories reference (REVIEW #16).
    """
    out: dict[tuple, dict] = {}
    for inc in incidents:
        if inc.kind not in ("investigation", "decision", "penalty") or not inc.driver_ids:
            continue
        key = (tuple(sorted(inc.driver_ids)), inc.turn, inc.reason)
        c = out.get(key)
        if c is None:
            c = out[key] = {
                "id": f"{inc.lap or 0}-{'-'.join(map(str, sorted(inc.driver_ids)))}-{inc.turn or 0}",
                "driver_ids": sorted(inc.driver_ids),
                "turn": inc.turn,
                "reason": inc.reason.lower() if inc.reason else None,
                "opened_lap": inc.lap,
                "decided_lap": None,
                "outcome": None,
                "after_race": False,
            }
        if "AFTER THE RACE" in inc.message.upper():
            c["after_race"] = True
        if inc.kind in ("decision", "penalty"):
            c["decided_lap"] = inc.lap
            c["outcome"] = inc.outcome
    return list(out.values())
