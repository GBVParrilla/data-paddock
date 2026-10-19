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


def _fit(sentences: list[str | None], limit: int) -> str:
    """As many of the sentences, in order, as fit the word limit (the fact-checker's budget)."""
    out, n = [], 0
    for x in sentences:
        if not x:
            continue
        w = len(re.findall(r"[\w'’.-]+", x))
        if n + w > limit:
            continue
        out.append(x)
        n += w
    return " ".join(out)


def _lead(sheet: dict) -> dict | None:
    return (sheet.get("verdict_candidates") or [None])[0]


def _words(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


# candidates that explain a cause or a margin can open Essential; outcomes (a climb, a retirement, a
# teammate result) are already in the result line, so leading with them would say the same thing twice
OPENERS = {"win", "stop_timing", "pit_cycle", "cut_line", "long_run", "sectors", "first_lap"}
FILLER = {"he", "his", "him", "the", "a", "an", "and", "from", "to", "in", "on", "of", "by", "at", "for", "with", "was", "is"}


def _adds_to(verdict: str, headline: str) -> bool:
    """True when the verdict brings at least two words the headline doesn't have, beyond positions and
    filler: a rival's name, a cause ("through the pit stops"), not just "from P14 to P9"."""
    extra = {w for w in _words(verdict) - _words(headline) - FILLER if not re.fullmatch(r"p?\d+", w)}
    return len(extra) >= 2


def _essential(lead: dict | None, headline: str, result_line: str, cands: list[dict], verdicts: list[str], mate_line: str | None) -> tuple[str, set[str]]:
    """Cause, then effect, for a new fan: the lead verdict when it adds to the headline, the result, then the
    next part of the story. Returns the text and the verdicts it used (the analysis states the rest)."""
    opening = lead["verdict"] if lead and lead["kind"] in OPENERS and _adds_to(lead["verdict"], headline) and (lead["verdict"] not in verdicts or len(verdicts) > 1) else None
    used = {opening} if opening else set()
    left = [v for v in verdicts if v not in used]
    second = next((c for c in cands[1:] if c["kind"] != "teammate" and (c["verdict"] not in left or len(left) > 1)), None)
    if second:
        used.add(second["verdict"])
    return _fit([opening, result_line, second["verdict"] if second else None, mate_line], 85), used


def _mate_line(mate: dict, key: str) -> str | None:
    if not mate.get("name"):
        return None
    if key == "finish":
        return f"Teammate {mate['name']} " + (f"finished P{mate['finish']}." if mate.get("finish") else "did not finish.")
    return f"Teammate {mate['name']} " + (f"was P{mate['position']}." if mate.get("position") else "set no time.")


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
        return {"headline": f"Did not start{grid}", "essential": story, "expert": story, "analysis": "", "key_numbers": [{"label": "Grid", "value": f"P{r['grid']}"}] if r.get("grid") else [], "glossary_terms": ["DNS"]}

    grid, fin, gained = r.get("grid"), r.get("finish"), r.get("places_gained")
    lead = _lead(sheet)
    if lead:
        headline = lead["headline"]
    else:
        headline = f"No single turning point in {last}'s run to P{fin}" if fin else f"{last}'s race ended early"
    if status in ("retired", "not classified"):
        terms.append("DNF")
        reason = r.get("retirement_reason_given")
        when = f" on lap {r['retired_on_lap']}" if r.get("retired_on_lap") else ""
        at = (sheet.get("position_trace") or {}).get("final")
        result_line = f"He started {f'P{grid}' if grid else 'from the pit lane'} and retired{when}" + (f" while running P{at}" if at else "") + (f" ({reason})" if reason and reason != "not stated" else "") + "."
        if fin:
            result_line = f"He stopped{when}, but had covered enough of the distance to be classified P{fin}."
    else:
        down = "down" in (status or "")
        if down:
            terms.append("lapped")
        down_txt = f", {status.replace('finished ', '')}" if down else ""
        if fin == 1:
            result_line = f"He started from {'pole' if grid == 1 else f'P{grid}' if grid else 'the pit lane'} and took {_pts(r.get('points'))}."
        elif grid == fin:
            result_line = f"He started and finished P{fin}{down_txt}, scoring {_pts(r.get('points'))}."
        else:
            result_line = f"He started {f'P{grid}' if grid else 'from the pit lane'} and finished P{fin}{down_txt}, scoring {_pts(r.get('points'))}."
    all_verdicts = sheet.get("verdicts") or []
    essential, used = _essential(lead, headline, result_line, sheet.get("verdict_candidates") or [], all_verdicts,
                                 None if (lead or {}).get("kind") == "teammate" else _mate_line(mate, "finish"))
    essential = f"{name} " + essential[3:] if essential.startswith("He ") else essential
    verdicts = [v for v in all_verdicts if v not in used]

    expert = []
    if r.get("gap_to_winner"):
        expert.append(f"He finished {r['gap_to_winner']} behind the winner.")
    trace = sheet.get("position_trace") or {}
    if trace.get("end_of_lap_1"):
        expert.append(f"He was P{trace['end_of_lap_1']} after lap 1 and ran between P{trace['best']} and P{trace['worst']}.")
    strat = []
    for st in sheet.get("stints") or []:
        if st.get("laps"):
            strat.append(f"{_tyre(st['compound'])} for laps {st['laps']}")
            if st["compound"] != "UNRECORDED":
                terms.append("compound")
    if strat:
        expert.append("He ran " + ", then ".join(strat) + ".")
    for st in stops:
        lane = f", {st['pit_lane_time']} in the pit lane" if st.get("pit_lane_time") else ""
        expert.append(f"He pitted on lap {st['in_lap']}{lane}.")
    for st in sheet.get("stints") or []:
        dg = st.get("degradation_s_per_lap")
        if dg is not None and st.get("laps"):
            # the same rounding as the verdict, so the number is one the sheet states
            expert.append(f"Allowing for fuel, his pace on laps {st['laps']} faded by about {dg:.2f}s a lap." if dg > 0.02
                          else f"Allowing for fuel, his pace on laps {st['laps']} held steady.")
            break
    expert += [_sectors(sheet), _rivals(sheet)] + _incidents(sheet)
    if any("Virtual Safety Car" in (n.get("kind") or "") for n in sheet.get("neutralisations") or []):
        terms.append("VSC")
    analysis = _fit(verdicts + ([f"Not known: {sheet['insufficient_data'][0]}."] if sheet.get("insufficient_data") else []), 75) \
        or ("His race ended before the strategy could play out." if status in ("retired", "not classified") and not fin
            else "No stop gained or cost him places, and no neutralisation changed his race: his result came down to his pace.")
    keys = [{"label": "Finish", "value": f"P{fin}" if fin else "DNF"}, {"label": "Grid", "value": f"P{grid}" if grid else "Pit lane"}]
    if gained:
        keys.append({"label": "Places", "value": f"{gained:+d}"})
    keys.append({"label": "Stops", "value": str(len(stops))})
    return {"headline": headline, "essential": essential, "expert": _fit(expert, 105), "analysis": analysis, "key_numbers": keys[:4], "glossary_terms": sorted(set(terms))}


def quali_story(sheet: dict) -> dict[str, Any]:
    d, r = sheet["driver"], sheet["result"]
    name, last = d["name"], d["name"].split(" ")[-1]
    sq = sheet["meta"]["session_type"] == "SQ"
    label = "sprint qualifying" if sq else "qualifying"
    pos = r.get("position")
    mate = r.get("teammate") or {}
    lead = _lead(sheet)
    if r.get("note") == "set no time":
        result_line = f"He set no time in {label}."
        headline = lead["headline"] if lead else f"{last} never got a timed lap in {label}"
    else:
        reached = r.get("reached", "")
        gap_key = next((k for k in r if k.startswith("gap_to_fastest_in_")), None)
        result_line = "He qualified on pole." if pos == 1 else f"He qualified P{pos}" + (f" and was {reached}" if reached and not reached.endswith("3") else " and reached the final segment") + "."
        headline = lead["headline"] if lead else f"No single deciding moment in {last}'s {label}"
    margins = [v for k, v in r.items() if k.endswith("_margin")]
    analysis = f"What decided his session: he {margins[-1]}." if margins else "His position came down to raw pace: no cut line was close."
    essential, _ = _essential(lead, headline, result_line, sheet.get("verdict_candidates") or [], [analysis] if margins else [],
                              None if (lead or {}).get("kind") == "teammate" else _mate_line(mate, "position"))
    essential = re.sub(r"^(In S?Q\d) he ", rf"\1 {name} ", essential)  # "In Q2 Pierre Gasly missed out..."
    if margins and margins[-1] in essential:  # Essential already gave the margin: the analysis adds the next finding
        nxt = next((c["verdict"] for c in sheet.get("verdict_candidates") or [] if c["verdict"] not in essential and c["kind"] != "teammate"), None)
        analysis = nxt or _sectors(sheet) or analysis
    essential = f"{name} " + essential[3:] if essential.startswith("He ") else essential
    expert = []
    gap_key = next((k for k in r if k.startswith("gap_to_fastest_in_")), None)
    if gap_key:
        expert.append(f"He was {r[gap_key]} off the fastest time in {gap_key.rsplit('_', 1)[-1]}.")
    times = r.get("times") or {}
    if times:
        expert.append("His best times: " + ", ".join(f"{k} {v}" for k, v in times.items()) + ".")
    if margins and not (lead and lead["kind"] == "cut_line"):
        expert.append("At the cut lines he " + "; then ".join(margins) + ".")
    expert.append(_sectors(sheet))
    expert += _incidents(sheet)
    if not any(expert):
        expert.append(f"Without a timed lap there are no sector or segment times to compare from {label}.")
    keys = [{"label": "Position", "value": f"P{pos}" if pos else "No time"}]
    if gap_key:
        keys.append({"label": f"Gap in {gap_key.rsplit('_', 1)[-1]}", "value": r[gap_key]})
    return {"headline": headline, "essential": essential, "expert": _fit(expert, 105), "analysis": analysis, "key_numbers": keys, "glossary_terms": ["SQ" if sq else "Q"]}


def practice_story(sheet: dict) -> dict[str, Any]:
    d, r = sheet["driver"], sheet["result"]
    name, last = d["name"], d["name"].split(" ")[-1]
    session = sheet["meta"]["session_type"]
    pos = r.get("position")
    prog = sheet.get("programme") or {}
    runs = [st for st in prog.get("stints") or [] if st.get("lap_count")]
    lead = _lead(sheet)
    headline = lead["headline"] if lead else (f"{last}'s {session} programme: {_n(len(runs))} run{'s' if len(runs) != 1 else ''}" if runs else f"{last} never got a timed lap in {session}")
    result_line = f"He was P{pos} of {r.get('of')} in {session}." if pos else f"He set no time in {session}."
    mate_pos, mate_name = r.get("teammate_position"), d.get("teammate")
    essential, _ = _essential(lead, headline, result_line, sheet.get("verdict_candidates") or [], [],
                              f"Teammate {mate_name} was P{mate_pos}." if mate_pos and mate_name else None)
    essential = f"{name} " + essential[3:] if essential.startswith("He ") else essential
    expert = []
    if r.get("best_lap") and r.get("gap_to_fastest"):
        expert.append(f"His best lap was {r['best_lap']}, {r['gap_to_fastest']} off the fastest.")
    if runs:
        expert.append(f"His programme was {_n(len(runs))} run{'s' if len(runs) != 1 else ''}: " + "; ".join(f"{st['lap_count']} laps on {_tyre(st['compound'])}" for st in runs) + ".")
    lr = [x for x in sheet.get("long_runs") or [] if x.get("rank")]
    if lr:
        x = lr[0]
        expert.append(f"On his {x['compound'].lower()} long run he averaged {x['average_lap']} over {x['laps']} laps, {_ord(x['rank'])} of the {x['of_drivers_with_8_plus_laps']} drivers who ran 8 laps or more.")
    expert.append(_sectors(sheet))
    expert += _incidents(sheet)
    if not any(expert):
        expert.append(f"Without a timed lap there are no sector or long-run times to compare from {session}.")
    analysis = "Practice pace is a guide, not a ranking: fuel loads and engine modes aren't published."
    keys = [{"label": "Position", "value": f"P{pos}" if pos else "No time"}]
    if r.get("best_lap"):
        keys.append({"label": "Best lap", "value": r["best_lap"]})
    return {"headline": headline, "essential": essential, "expert": _fit(expert, 105), "analysis": analysis, "key_numbers": keys, "glossary_terms": ["longrun"] if lr else []}


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
    for k in ("headline", "essential", "expert", "analysis"):  # a missing value must never print as "None"
        story[k] = re.sub(r"\s*\b(?:P|lap |laps )?None\b", "", story[k]).replace(" ,", ",").replace(" .", ".")
    return story
