"""Stories written by code from the fact sheet alone: the fallback when an AI story can't be verified.

They are plainer than the AI's prose but every word is checkable, so they always pass the
fact-check. A DNS gets only this (there is no session for the AI to describe).
"""
from __future__ import annotations

import re
from typing import Any

WORDS = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight", 9: "nine", 10: "ten"}
GLOSSARY_KEYS = ("DNF", "DNS", "DSQ", "NC", "lapped", "VSC", "SC", "red", "stint", "compound", "undercut", "overcut", "longrun", "Q", "SQ",
                 "sprint", "pole", "sector", "purple", "reference", "stationary", "pitlane", "tracklimits", "grid", "standin", "interpretation")


def _n(x: int) -> str:
    return WORDS.get(x, str(x))


def _times(x: int) -> str:
    return {1: "once", 2: "twice"}.get(x, f"{_n(x)} times")


def _ord(n: int) -> str:
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def _tyre(c: str) -> str:
    return "a compound the feed didn't record" if c == "UNRECORDED" else f"{c.lower()}s"


def _pts(p: float | None) -> str:
    if not p:
        return "no points"
    p = int(p) if float(p).is_integer() else p
    return "one point" if p == 1 else f"{p} points"


def _sectors(sheet: dict) -> str | None:
    s = sheet.get("sectors") or {}
    if not s:
        return None
    parts = [f"{_ord(v['rank'])} in sector {k[-1]}" for k, v in s.items()]
    worst = max(s.items(), key=lambda kv: kv[1]["rank"])
    n = max(v["of"] for v in s.values())
    return f"Of the {n} drivers who set sector times, his best ranked {', '.join(parts[:-1])} and {parts[-1]}, so sector {worst[0][-1]} ({worst[1]['gap_to_session_best']} to the session best) was where he lost most."


def _rivals(sheet: dict) -> str | None:
    r = (sheet.get("rivals_on_track") or [])[:1]
    if not r:
        return None
    x = r[0]
    fin = f", who finished P{x['their_finish']}" if x.get("their_finish") else ""
    return f"He spent {x['laps_running_together']} laps running next to {x['driver']}{fin}."


def _incidents(sheet: dict) -> list[str]:
    out = []
    for i in sheet.get("incidents") or []:
        if i.get("with"):
            where = f" at turn {i['turn']}" if i.get("turn") else ""
            why = f" ({i['reason']})" if i.get("reason") else ""
            out.append(f"The stewards looked at an incident with {', '.join(i['with'])}{where} on lap {i['lap']}{why}: {i['outcome']}." if i.get("lap") else f"The stewards noted an incident with {', '.join(i['with'])}{why}: {i['outcome']}.")
        elif i.get("penalty"):
            out.append(f"He was given a {i['penalty']}" + (f" for {i['reason']}" if i.get("reason") else "") + (f" on lap {i['lap']}." if i.get("lap") else "."))
        elif i.get("track_limits_deletions"):
            k = i["track_limits_deletions"]
            out.append(f"He had {_n(k)} lap time{'s' if k != 1 else ''} deleted for track limits.")
    return out


def race_story(sheet: dict) -> dict[str, Any]:
    d, r = sheet["driver"], sheet["result"]
    name, last = d["name"], d["name"].split(" ")[-1]
    status = r.get("status")
    mate = r.get("teammate") or {}
    stops = sheet.get("stops") or []
    terms: list[str] = []
    if status == "did not start":
        grid = f" from P{r['grid']}" if r.get("grid") else ""
        story = f"{name} was due to start{grid} but did not take the start."
        if mate.get("name"):
            story += f" His teammate {mate['name']} " + (f"finished P{mate['finish']}." if mate.get("finish") else "did not finish.")
        return {"headline": f"Did not start{grid}", "summary": story, "story": story, "analysis": "", "key_numbers": [{"label": "Grid", "value": f"P{r['grid']}"}] if r.get("grid") else [], "glossary_terms": ["DNS"]}

    grid, fin, gained = r.get("grid"), r.get("finish"), r.get("places_gained")
    if fin:
        headline = f"P{fin} from P{grid}" if grid else f"P{fin} from the pit lane"
        if r.get("points"):
            headline += f" for {_pts(r['points'])}"
    else:
        headline = ("Retired" + (f" on lap {r['retired_on_lap']}" if r.get("retired_on_lap") else "")) + (f" from P{grid} on the grid" if grid else "")
    if status == "retired" or status == "not classified":
        terms.append("DNF")
        reason = r.get("retirement_reason_given")
        when = f" on lap {r['retired_on_lap']}" if r.get("retired_on_lap") else ""
        start = f"started P{grid} and " if grid else ""
        opening = f"{name} {start}retired{when}" + (f" ({reason})" if reason and reason != "not stated" else "") + "."
        if fin:
            opening = f"{name} {start}stopped{when}, but had covered enough of the distance to be classified P{fin}."
    else:
        how = f", {r['gap_to_winner']} behind the winner" if r.get("gap_to_winner") else (f", {r['status'].replace('finished ', '')}" if "down" in (r.get("status") or "") else "")
        if "down" in (r.get("status") or ""):
            terms.append("lapped")
        opening = f"{name} started {f'P{grid}' if grid else 'from the pit lane'} and finished P{fin}{how}, scoring {_pts(r.get('points'))}."
    summary = opening
    if stops:
        laps = " and ".join(f"lap {s['in_lap']}" for s in stops)
        summary += f" He stopped {_times(len(stops))}, on {laps}."
    if mate.get("name"):
        summary += f" Teammate {mate['name']} " + (f"finished P{mate['finish']}." if mate.get("finish") else "did not finish.")

    paras = [opening]
    trace = sheet.get("position_trace") or {}
    if trace.get("end_of_lap_1"):
        paras[0] += f" He was P{trace['end_of_lap_1']} after the first lap and ran between P{trace['best']} and P{trace['worst']}."
    strat = []
    for s in sheet.get("stints") or []:
        if s.get("laps"):
            strat.append(f"{_tyre(s['compound'])} for laps {s['laps']}")
            if s["compound"] != "UNRECORDED":
                terms.append("compound")
    if strat:
        paras.append("He ran " + ", then ".join(strat) + ".")
    for s in stops:
        lane = f" ({s['pit_lane_time']} in the pit lane)" if s.get("pit_lane_time") else ""
        paras.append(f"His stop on lap {s['in_lap']}{lane} took him from P{s['position_before']} to P{s['position_after_cycle']} once the cars around him had stopped." if s.get("position_before") and s.get("position_after_cycle") else f"He pitted at the end of lap {s['in_lap']}{lane}.")
    for x in (_sectors(sheet), _rivals(sheet)):
        if x:
            paras.append(x)
    paras += _incidents(sheet)
    if any("Virtual Safety Car" in (n.get("kind") or "") for n in sheet.get("neutralisations") or []):
        terms.append("VSC")
    analysis = " ".join(sheet.get("verdicts")[:3]) if sheet.get("verdicts") else "The data shows no strategic turning point for him: no stop that gained or cost places, and no neutralisation that changed his race."
    if sheet.get("insufficient_data"):
        analysis += f" Not available: {sheet['insufficient_data'][0]}."
    keys = [{"label": "Finish", "value": f"P{fin}" if fin else "DNF"}, {"label": "Grid", "value": f"P{grid}" if grid else "Pit lane"}]
    if gained:
        keys.append({"label": "Places", "value": f"{gained:+d}"})
    keys.append({"label": "Stops", "value": str(len(stops))})
    return {"headline": headline, "summary": summary, "story": "\n\n".join(_merge(paras)), "analysis": analysis, "key_numbers": keys[:4], "glossary_terms": sorted(set(terms))}


def quali_story(sheet: dict) -> dict[str, Any]:
    d, r = sheet["driver"], sheet["result"]
    name = d["name"]
    sq = sheet["meta"]["session_type"] == "SQ"
    label = "sprint qualifying" if sq else "qualifying"
    pos = r.get("position")
    mate = r.get("teammate") or {}
    if r.get("note") == "set no time":
        headline = f"No time set in {label}"
        opening = f"{name} set no time in {label}."
    else:
        reached = r.get("reached", "")
        headline = f"P{pos} in {label}" + (", into the final segment" if reached.endswith("3") else f", {reached}" if reached else "")
        gap_key = next((k for k in r if k.startswith("gap_to_fastest_in_")), None)
        gap_txt = f", {r[gap_key]} off the fastest time in {gap_key.rsplit('_', 1)[-1]}" if gap_key else ""
        opening = f"{name} qualified P{pos}" + (f" and was {reached}" if reached and not reached.endswith("3") else " and reached the final segment") + gap_txt + "."
    summary = opening
    if mate.get("name"):
        summary += f" Teammate {mate['name']} " + (f"was P{mate['position']}." if mate.get("position") else "set no time.")
    paras = [opening]
    times = r.get("times") or {}
    if times:
        paras.append("His best times: " + ", ".join(f"{k} {v}" for k, v in times.items()) + ".")
    margins = [v for k, v in r.items() if k.endswith("_margin")]
    if margins:
        paras.append("At the cut lines he was " + "; ".join(margins) + ".")
    s = _sectors(sheet)
    if s:
        paras.append(s)
    paras += _incidents(sheet)
    analysis = " ".join(margins[-1:]).capitalize() + "." if margins else "The data gives no single deciding factor beyond his raw pace."
    if margins:
        analysis = f"The margin that decided his session: {margins[-1]}."
    keys = [{"label": "Position", "value": f"P{pos}" if pos else "No time"}]
    gk = next((k for k in r if k.startswith("gap_to_fastest_in_")), None)
    if gk:
        keys.append({"label": f"Gap in {gk.rsplit('_', 1)[-1]}", "value": r[gk]})
    return {"headline": headline, "summary": summary, "story": "\n\n".join(_merge(paras)), "analysis": analysis, "key_numbers": keys, "glossary_terms": ["SQ" if sq else "Q"]}


def practice_story(sheet: dict) -> dict[str, Any]:
    d, r = sheet["driver"], sheet["result"]
    name = d["name"]
    session = sheet["meta"]["session_type"]
    pos = r.get("position")
    headline = f"P{pos} in {session}" if pos else f"No time in {session}"
    opening = f"{name} was P{pos} of {r.get('of')} in {session}" + (f" with a {r['best_lap']}, {r['gap_to_fastest']} off the fastest time." if r.get("best_lap") and r.get("gap_to_fastest") else ".") if pos else f"{name} set no time in {session}."
    prog = sheet.get("programme") or {}
    runs = [s for s in prog.get("stints") or [] if s.get("lap_count")]
    paras = [opening]
    if runs:
        paras.append(f"His programme was {_n(len(runs))} run{'s' if len(runs) != 1 else ''}: " + "; ".join(f"{s['lap_count']} laps on {_tyre(s['compound'])}" for s in runs) + ".")
    lr = [x for x in sheet.get("long_runs") or [] if x.get("rank")]
    if lr:
        x = lr[0]
        paras.append(f"On his {x['compound'].lower()} long run he averaged {x['average_lap']} over {x['laps']} laps, {_ord(x['rank'])} of the {x['of_drivers_with_8_plus_laps']} drivers who ran 8 laps or more.")
    s = _sectors(sheet)
    if s:
        paras.append(s)
    paras += _incidents(sheet)
    summary = opening.split(" with a ")[0] + "." if " with a " in opening else opening
    analysis = "Practice pace is a guide, not a ranking: fuel loads and engine modes aren't published."
    keys = [{"label": "Position", "value": f"P{pos}" if pos else "No time"}]
    if r.get("best_lap"):
        keys.append({"label": "Best lap", "value": r["best_lap"]})
    return {"headline": headline, "summary": summary, "story": "\n\n".join(_merge(paras)), "analysis": analysis, "key_numbers": keys, "glossary_terms": ["longrun"] if lr else []}


def _merge(paras: list[str]) -> list[str]:
    """Short sentences grouped into paragraphs of two or three."""
    out: list[str] = []
    for p in paras:
        if out and len(out[-1]) < 220:
            out[-1] += " " + p
        else:
            out.append(p)
    return out


def template_story(sheet: dict) -> dict[str, Any]:
    stype = sheet["meta"]["session_type"]
    story = race_story(sheet) if stype in ("R", "S") else quali_story(sheet) if stype in ("Q", "SQ") else practice_story(sheet)
    for k in ("headline", "summary", "story", "analysis"):  # a missing value must never print as "None"
        story[k] = re.sub(r"\s*\b(?:P|lap |laps )?None\b", "", story[k]).replace(" ,", ",").replace(" .", ".")
    return story
