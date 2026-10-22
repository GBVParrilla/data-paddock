"""Deterministic checks on a generated story before it can be published.

A story passes only if:
  - it is clean text (no markup, JSON, self-talk or code tokens),
  - each section is within its word limit; Essential has no lap times or raw expressions,
  - the headline is a verdict (what the result meant or why), not only the result,
  - every number it quotes (times, gaps, positions, laps, counts) is in the fact sheet,
  - arithmetic claims ("97 points behind", "gained 4 places") match the computed values,
  - every driver it names took part in the session, and "teammate X" is the real teammate,
  - it doesn't contradict the result (a car that lost places never "climbed"),
  - stop-timing claims about a Safety Car or VSC agree with the computed verdicts,
  - the analysis hedges only where the sheet lists insufficient data, and (REVIEW_ROUND3):
  - ordinals are spelled right ("20th", never "20nd"),
  - sector claims ("fastest in the final sectors", "his weakest sector") match the sector ranks,
  - Q1/Q2/Q3 wording matches the segment he went out in,
  - a "stand-in" claim matches the entry list, and no motive or role is invented,
  - the headline doesn't misread the result ("undone" for a driver who gained places),
  - nothing is ranked out of fewer than 3, and points are whole numbers when they are,
  - Essential and arcs don't talk about missing or unpublished data.
Each failure is a Violation with a message the model can act on when it retries.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

import json

from .facts import numbers_in

# Claude writes the headline and Essential; Expert is the debrief computed in code (REVIEW_ROUND3 D7).
LIMITS = {"headline": 12, "essential": 90}
# stories written before prompt v4 also carry expert prose and an analysis, still checked when published
LEGACY_LIMITS = {"headline": 12, "essential": 90, "expert": 110, "analysis": 80}
LIMIT_SLACK = 1.15  # a sentence's worth over is tolerated; the gate is the prompt's limit + 15%

LEAK = re.compile(r"</?[a-z_]+>|<br\s*/?>|```|\{\s*\"|\"\s*\}|\}\s*$|^\s*\{|BAD_FORMAT|\bnull\b|\bundefined\b|\bNaN\b|\[object|"
                  r"note to (the )?reviewer|invalid (trailing|json)|let me (correct|fix|redo)|corrected below|as an ai\b|i (cannot|can't) (produce|generate)|^answer:|\(unlikely\)", re.I | re.M)
LAP_TIME = re.compile(r"\b\d:\d{2}\.\d{3}\b")
HEDGES = [
    "it is hard to say", "it's hard to say", "hard to know", "difficult to say", "the evidence does not support a strong conclusion",
    "does not support a strong conclusion", "cannot be confirmed", "can't be confirmed", "it is not possible to judge", "it's not possible to judge",
    "impossible to say", "not possible to say", "speculative", "it is unclear whether", "it's unclear whether",
]
# "(-0.06s per lap)", "(+1.149s)": data notation, fine for Expert, not for a new fan (REVIEW_ROUND2 #40)
RAW = re.compile(r"\([+-]?\d|\bper lap\b|\d+ms\b")
# what a result-only headline is made of: positions, session names, points (REVIEW_ROUND2 B2)
RESULT_WORDS = re.compile(r"^(p\d+|\d+|from|in|for|on|of|at|the|a|an|and|to|lap|laps|point|points|one|two|qualifying|sprint|race|fp[123]|q[123]|sq[123]|"
                          r"grid|pole|pit|lane|no|time|set|retired|did|not|start|finish|finished|started|classified|down|up|place|places|"
                          r"his|he|after|with|top|ten|[a-z]+'s)$")
CLIMB = re.compile(r"\b(climbed|gained|made up|moved up)\b")
# numbers as prose writes them: P10, +0.810s, 10th, 55%, 1.2 - not identifiers like Q2, FP1, T3
NUMBER = re.compile(r"(?<![\w.:])P?[+-]?\d+(?:\.\d+)?(?:s|%|st|nd|rd|th|°?C|kph|km/h)?(?![\w:])")  # "35.9C" is 35.9 (REVIEW_ROUND3)
ORDINAL = re.compile(r"\b(\d+)(st|nd|rd|th)\b")
# talk about what the data doesn't have: fine in an Expert note, never in Essential or an arc (REVIEW_ROUND3 #54)
MISSING_DATA = re.compile(r"\b(not|never|isn't|aren't|wasn't|weren't) (published|available|recorded|given|stated|reported)\b|\bno (stated |published |recorded )?(reason|figure|data|cause)\b|"
                          r"\breported no (cause|reason)\b|\bno decision (was )?(recorded|given|published)\b|"
                          r"\bindicative\b|\bthe (timing )?(data|feed) (gives|shows|says|has) no\b|\bunpublished\b|\bunrecorded\b|\bdoesn't (say|show|give)\b|\bdoes not (say|show|give)\b", re.I)
STAND_IN = re.compile(r"\bstand(ing)?[- ]in\b|\bstood in\b|\bin place of\b|\bdeputi[sz]\w*|\bsubstitut\w*|\breplac(ing|ed) (the )?(injured|regular|usual)\b|\bfilling in\b", re.I)
# motives and inner states the timing data can't show (REVIEW_ROUND2 pilot: "a clean final push", "the place he would have been looking for")
MOTIVE = re.compile(r"\b(looking for|hoping|hoped|wanted|frustrat\w*|determined|confident|confidence|happy|disappointed|under pressure|felt|feeling|clean final push|"
                    r"desperate|delighted|relieved|motivated)\b", re.I)
OUT_OF = re.compile(r"\b(\d+)(?:st|nd|rd|th)? (?:of|out of) (\d+)\b")
POINTS_DECIMAL = re.compile(r"\b(\d+)\.0 points?\b")
UNDONE = re.compile(r"\b(undone|undid|ruined|wrecked|derailed|spoiled|thrown away|threw away|cost him the race)\b", re.I)
# Essential leaves the data to the debrief: "14th in sector 2", "S3 rank", "18.6s in the pit lane"
RE_ESSENTIAL_DATA = re.compile(r"\b\d+(?:st|nd|rd|th)(?: of \d+)? in (?:sector|s)\s?[123]\b|\b(?:sector|s)\s?[123] (?:rank|ranked)\b|\d+\.\d+s (?:in|through) the pit ?lane\b", re.I)
# sentences about what didn't happen to him: filler in a short story (prompt v5 pilot: "No incidents or safety
# periods were recorded for him", "The stop came away from any Virtual Safety Car period")
NON_EVENT = re.compile(r"\bno (?:shared |other |further )?(incidents?|safety (car )?periods?|safety cars?|penalt(y|ies)|investigations?)\b[^.]*\b(recorded|reported|noted|involv\w*)\b|"
                       r"\baway from any\b|\bwas not (affected|involved)\b|\bnothing (else )?(happened|of note)\b|\brain was reported\b", re.I)
TIMES_READ_OUT = re.compile(r"\b\d{1,2}\.\d{3}\b(?!s)[^.]*?\b(?:against|to|and|vs)\b[^.]*?\b\d{1,2}\.\d{3}\b(?!s)")  # "29.139 against 29.282"
PASS_WORD = re.compile(r"\b(pass|passed|passes|passing|overtak\w*)\b", re.I)
RECOVERY = re.compile(r"\b(recover\w*|won back|despite|still|yet|but|anyway|regardless)\b", re.I)


@dataclass
class Violation:
    section: str
    message: str

    def __str__(self) -> str:
        return f"[{self.section}] {self.message}"


def _words(text: str) -> int:
    return len(re.findall(r"[\w'’.-]+", text))


def _close(x: float, allowed: set[float]) -> bool:
    for a in allowed:
        if abs(a - x) <= 0.0015 or (x != 0 and abs(a - x) <= 0.051 and str(x).count(".") and len(str(x).split(".")[1]) == 1):
            return True
    return False


def _allowed_numbers(sheet: dict, extra: set[float]) -> set[float]:
    nums = numbers_in(sheet) | extra
    out = set(nums)
    for n in list(nums):
        out.add(round(n / 1000, 3))  # ms in the sheet, seconds in prose
        out.add(abs(n))
    out |= {float(sheet.get("meta", {}).get("season") or 0), 1.0, 2.0}  # "one-two", "1-2 finish", the year
    return out


def check_numbers(section: str, text: str, allowed: set[float]) -> list[Violation]:
    out = []
    stripped = LAP_TIME.sub(lambda m: "", text)
    for m in LAP_TIME.finditer(text):
        mm, rest = m.group().split(":")
        v = int(mm) * 60 + float(rest)
        if not _close(round(v, 3), allowed):
            out.append(Violation(section, f"the lap time {m.group()} is not in the data"))
    for m in NUMBER.finditer(stripped):
        raw = re.sub(r"^P|[+-]|(s|%|st|nd|rd|th|°?C|kph|km/h)$", "", m.group())
        v = float(raw)
        if not _close(v, allowed):
            ctx = stripped[max(0, m.start() - 30): m.end() + 20].replace("\n", " ")
            out.append(Violation(section, f"the number {m.group()} (in \"...{ctx.strip()}...\") is not in the data"))
    return out


def check_names(section: str, text: str, roster: dict[str, str], entrants: set[str], sheet_text: str) -> list[Violation]:
    """roster: every season driver's surname -> full name. A surname not entered here is a hallucination."""
    out = []
    for surname, full in roster.items():
        if re.search(rf"\b{re.escape(surname)}\b", text) and full not in entrants and full not in sheet_text:
            out.append(Violation(section, f"{full} did not take part in this session"))
    return out


def check_teammate(section: str, text: str, teammate: str | None) -> list[Violation]:
    out = []
    for m in re.finditer(r"teammate,?\s+((?:[A-Z][\w'’-]+\s?){1,3})", text):
        named = m.group(1).strip()
        if teammate is None or named.split()[-1] not in teammate:
            out.append(Violation(section, f"\"teammate {named}\" is wrong: his teammate here is {teammate or 'nobody'}"))
    return out


def check_arithmetic(section: str, text: str, sheet: dict) -> list[Violation]:
    out = []
    res = sheet.get("result") or {}
    gained = res.get("places_gained")
    for m in re.finditer(r"\b(gained|climbed|made up|lost|dropped)\s+(\d+)\s+(places?|positions?|spots?)", text):
        verb, n = m.group(1), int(m.group(2))
        ok_values = {abs(s.get("net_places") or 0) for s in sheet.get("stops", [])}
        if gained is not None:
            ok_values.add(abs(gained))
        ok_values |= {abs(x) for x in sheet.get("allowed_place_counts", [])}
        if n not in ok_values:
            out.append(Violation(section, f"\"{m.group()}\" doesn't match the data (places gained grid-to-flag: {gained})"))
        if verb in ("gained", "climbed", "made up") and gained is not None and gained < 0 and n == abs(gained):
            out.append(Violation(section, f"\"{m.group()}\": he lost {abs(gained)} places, he didn't gain them"))
    for m in re.finditer(r"(\d+(?:\.\d+)?)\s+points?\s+(behind|ahead of|clear of|adrift of|off)\b", text):
        n = float(m.group(1))
        allowed = {float(x) for x in sheet.get("points_gaps", [])}
        if n not in allowed:
            out.append(Violation(section, f"\"{m.group()}\" doesn't match the standings (gaps: {sorted(allowed) or 'none given'})"))
    return out


def check_status(section: str, text: str, sheet: dict) -> list[Violation]:
    out = []
    res = sheet.get("result") or {}
    status = res.get("status")
    own = " ".join(x for x in re.split(r"(?<=[.!?])\s+", text) if not re.search(r"\bteammate\b", x, re.I))  # his own sentences
    if status == "did not start" and re.search(r"\b(finished|retired|pitted|laps? \d+|overtook)\b", own):
        out.append(Violation(section, "he did not start: describe only what happened before the start"))
    name = (sheet.get("driver") or {}).get("name") or ""
    about_him = [x for x in re.split(r"(?<=[.!?])\s+", own) if re.match(rf"^(He|His|{re.escape(name)}|{re.escape(name.split(' ')[-1])})\b", x)]
    if status == "retired" and not res.get("finish") and any(re.search(r"\b(?<!who )finished (in |the race )?P\d+", x) for x in about_him):
        out.append(Violation(section, "he retired; he did not finish the race"))
    gained = res.get("places_gained")
    first = re.split(r"(?<=[.!?])\s", text.strip(), maxsplit=1)[0] if text.strip() else ""
    if section in ("headline", "essential") and gained is not None and gained < 0 and CLIMB.search(first) and "place" in first:
        out.append(Violation(section, f"he finished {abs(gained)} places lower than he started; don't open with a climb"))
    return out


def check_neutralisation_logic(section: str, text: str, sheet: dict) -> list[Violation]:
    """REVIEW #5: a stop just *before* a VSC is the unlucky case; only a stop *under* it is cheap."""
    out = []
    rel = {s["in_lap"]: s.get("neutralisation", {}).get("relation") for s in sheet.get("stops", [])}
    for sent in re.split(r"(?<=[.!?])\s+", text):
        if not re.search(r"\b(VSC|Virtual Safety Car|Safety Car|red flag)\b", sent, re.I):
            continue
        if re.search(r"\b(unlucky|missed|cost|anyone who waited|rivals who waited|those who waited)\b", sent, re.I):
            continue  # the sentence already describes the bad timing
        cheap = re.search(r"\b(reduc\w* the time|cheaper|cheap|saved time|less time lost|minimi[sz]\w*|benefit\w*|helped)\b", sent, re.I)
        before = re.search(r"\b(just )?before the\b", sent, re.I)
        laps = [int(x) for x in re.findall(r"\blap (\d+)", sent)]
        stop_rel = next((rel[l] for l in laps if l in rel), None)
        if cheap and before:
            out.append(Violation(section, f"pitting just before a neutralisation is unlucky, not cheap: \"{sent.strip()[:120]}\""))
        elif cheap and stop_rel in ("just_before", "just_after"):
            out.append(Violation(section, f"the lap-{laps[0]} stop was {stop_rel.replace('_', ' ')} the neutralisation, so it wasn't cheap"))
    return out


def _ordinal(n: int) -> str:
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def check_ordinals(section: str, text: str) -> list[Violation]:
    """'20nd' is wrong whatever the number means."""
    return [Violation(section, f"\"{m.group()}\" is misspelt: write {_ordinal(int(m.group(1)))}")
            for m in ORDINAL.finditer(text) if _ordinal(int(m.group(1))) != m.group()]


def check_out_of(section: str, text: str) -> list[Violation]:
    """'1st of 1', 'ranked 1 of 2': a rank among fewer than 3 says nothing (REVIEW_ROUND3 #55)."""
    return [Violation(section, f"\"{m.group()}\": don't rank anything out of fewer than 3") for m in OUT_OF.finditer(text) if int(m.group(2)) < 3]


def check_points(section: str, text: str) -> list[Violation]:
    return [Violation(section, f"\"{m.group()}\": write whole points as {m.group(1)} point{'s' if m.group(1) != '1' else ''}") for m in POINTS_DECIMAL.finditer(text)]


def check_missing_data(section: str, text: str) -> list[Violation]:
    m = MISSING_DATA.search(text)
    return [Violation(section, f"don't write about data that isn't there (\"{m.group()}\"): say what the data does show, or leave it out")] if m else []


def check_motives(section: str, text: str) -> list[Violation]:
    m = MOTIVE.search(text)
    return [Violation(section, f"\"{m.group()}\" is a guess at what he thought or wanted: the timing data can't show that")] if m else []


HALF = re.compile(r"\b(top|front|upper|bottom|back|lower) half of the (grid|field|order|timesheet|classification)\b", re.I)


def check_half(section: str, text: str, sheet: dict, field: int) -> list[Violation]:
    """'Top half of the grid' must match the position: P14 of 22 is not (R1 Q Gasly, prompt v6 pilot). Checked
    against the grid slot in a race, the classified position elsewhere; a sector claim is left to check_sectors."""
    res = sheet.get("result") or {}
    out = []
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        m = HALF.search(sentence)
        if not m or "sector" in sentence.lower():
            continue
        race = "grid" in res
        pos = res.get("grid") if race and m.group(2).lower() == "grid" else None if race else res.get("position")
        n = res.get("of") or field
        if not pos or not n:
            continue
        top = m.group(1).lower() in ("top", "front", "upper")
        if (top and pos > (n + 1) // 2) or (not top and pos <= n // 2):
            out.append(Violation(section, f"\"{m.group()}\" doesn't fit P{pos} of {n}"))
    return out


def check_stand_in(section: str, text: str, sheet: dict) -> list[Violation]:
    """A stand-in claim must match the entry list: Lawson really was Red Bull's stand-in at round 12
    (REVIEW_ROUND3 #60), so the claim is checked, not banned."""
    m = STAND_IN.search(text)
    if not m:
        return []
    d = sheet.get("driver") or {}
    if d.get("stand_in") or "stand_in" in json.dumps(sheet.get("result") or {}, default=str):
        return []
    return [Violation(section, f"\"{m.group()}\": he is not a stand-in here (the entry list says he drives his own seat)")]


SECTOR_WORD = {"first": [1], "opening": [1], "middle": [2], "second": [2], "third": [3], "last": [3], "final": [3]}
_SW = r"(?:first|opening|middle|second|third|last|final)"
# only explicit claims: "fastest in the final two sectors", "quickest in sectors 1 and 3", "sector 3 was his fastest"
FASTEST_IN = re.compile(rf"\b(?:fastest|quickest)\s+(?:of all\s+)?(?:in|through)\s+(?:both\s+)?(?:the\s+)?"
                        rf"(?:(?P<words>{_SW}(?:\s+(?:and|&)\s+{_SW})?)(?P<two>\s+two)?\s+sectors?|sectors?\s+(?P<nums>[123](?:\s*(?:,|and|&)\s*[123])*)|s(?P<s>[123])\b)", re.I)
SECTOR_WAS_FASTEST = re.compile(r"\bsector\s+([123])\s+(?:was|were)\s+(?:his\s+|the\s+)?(?:fastest|quickest)\b(?!\s+of\s+his)", re.I)
WEAKEST = re.compile(r"\b(?:weakest|worst)\s+(?:sector\s+)?(?:was\s+)?(?:sector\s+|s)([123])\b|\bsector\s+([123])\s+(?:was|remained)\s+(?:his\s+|the\s+)?(?:weakest|worst|weak point)\b|"
                     r"\blost\s+(?:the\s+)?most(?:\s+time)?\s+in\s+sector\s+([123])\b", re.I)
SLOWEST_IN = re.compile(rf"\bslowest\s+(?:of all\s+)?(?:in|through)\s+(?:both\s+)?(?:the\s+)?"
                        rf"(?:(?P<words>{_SW}(?:\s+(?:and|&)\s+{_SW})?)(?P<two>\s+two)?\s+sectors?|sectors?\s+(?P<nums>[123](?:\s*(?:,|and|&)\s*[123])*))", re.I)
PERFECT = re.compile(r"\b(sector[- ]perfect|perfect lap|flawless lap|fastest in every sector|fastest in all three sectors)\b", re.I)
NEGATED = re.compile(r"\b(never|not|n't|no)\b[^.;]{0,25}$", re.I)


def _fastest_claims(sent: str, pattern: re.Pattern = FASTEST_IN) -> list[int]:
    out = []
    for m in pattern.finditer(sent):
        if NEGATED.search(sent[: m.start()]):
            continue  # "never the fastest in any sector"
        if m.group("words"):
            words = re.findall(_SW, m.group("words").lower())
            secs = [s for w in words for s in SECTOR_WORD[w]]
            if m.group("two") and len(words) == 1:  # "final two sectors", "first two sectors"
                secs = [1, 2] if words[0] in ("first", "opening") else [2, 3]
            elif "sectors" in m.group().lower() and len(words) == 1 and words[0] in ("final", "last"):
                secs = [2, 3]  # "both final sectors"
            out += secs
        elif m.group("nums"):
            out += [int(x) for x in re.findall(r"[123]", m.group("nums"))]
        elif m.group("s"):
            out.append(int(m.group("s")))
    if pattern is FASTEST_IN:
        for m in SECTOR_WAS_FASTEST.finditer(sent):
            if not NEGATED.search(sent[: m.start()]):
                out.append(int(m.group(1)))
    return out


def check_sectors(section: str, text: str, sheet: dict) -> list[Violation]:
    """'Fastest in both final sectors' needs rank 1 in S2 and S3; 'his weakest sector was 2' needs S2 near
    the bottom of his own ranks and outside the top 5; 'Nth in sector K' needs that rank (REVIEW_ROUND3 #52,
    R17 Q Verstappen). Only explicit claims are read: a sentence naming several sectors isn't guessed at."""
    ranks = {int(k[-1]): v["rank"] for k, v in (sheet.get("sectors") or {}).items() if isinstance(v, dict) and v.get("rank")}
    if not ranks:
        return []
    out = []
    for sent in re.split(r"(?<=[.!?;])\s+", text):
        for k in _fastest_claims(sent):
            if k in ranks and ranks[k] != 1:
                out.append(Violation(section, f"he wasn't fastest in sector {k} (he ranked {_ordinal(ranks[k])}): \"{sent.strip()[:100]}\""))
        # "slowest in the middle and final sectors" for 22nd and 20th of 22 (R12 Q Bottas, prompt v4 pilot)
        of = {int(k[-1]): v.get("of") for k, v in (sheet.get("sectors") or {}).items() if isinstance(v, dict)}
        for k in _fastest_claims(sent, SLOWEST_IN):
            if k in ranks and of.get(k) and ranks[k] != of[k]:
                out.append(Violation(section, f"he wasn't slowest in sector {k} ({_ordinal(ranks[k])} of {of[k]}): \"{sent.strip()[:100]}\""))
        # "sector-perfect lap" for a pole with a 6th-best sector 2 (R17 Q Verstappen, prompt v4 pilot)
        if PERFECT.search(sent) and any(r != 1 for r in ranks.values()):
            out.append(Violation(section, f"\"{PERFECT.search(sent).group()}\" is wrong: his sector ranks were " + ", ".join(f"S{s} {_ordinal(r)}" for s, r in sorted(ranks.items()))))
        for m in WEAKEST.finditer(sent):
            k = int(next(g for g in m.groups() if g))
            worst = max(ranks.values())
            if k in ranks and (ranks[k] <= 5 or worst - ranks[k] >= 3):
                out.append(Violation(section, f"sector {k} wasn't his weakest (ranks: " + ", ".join(f"S{s} {_ordinal(r)}" for s, r in sorted(ranks.items())) + ")"))
        for m in re.finditer(r"\b(\d+)(?:st|nd|rd|th) (?:of \d+ )?in (?:sector |s)([123])\b|\b(?:sector |s)([123]) (?:was |in )?(\d+)(?:st|nd|rd|th)\b", sent, re.I):
            rank, sec = (int(m.group(1)), int(m.group(2))) if m.group(1) else (int(m.group(4)), int(m.group(3)))
            if sec in ranks and ranks[sec] != rank:
                out.append(Violation(section, f"he was {_ordinal(ranks[sec])} in sector {sec}, not {_ordinal(rank)}"))
    return out


def check_segments(section: str, text: str, sheet: dict) -> list[Violation]:
    """'Missed Q2' for a Q2 exit is wrong: he reached Q2 and missed Q3 (REVIEW_ROUND3 #52, R1 Q Gasly)."""
    reached = ((sheet.get("result") or {}).get("reached") or "")
    m = re.match(r"(?:knocked out in )?(S?Q)([123])$", reached)
    if not m:
        return []
    prefix, last = m.group(1), int(m.group(2))  # the last segment he ran in
    out_in = None if reached == f"{prefix}3" else last
    out = []
    # "missed the Q1 cut" is a Q1 exit, not a claim about reaching Q1: a segment followed by "cut" isn't read
    for c in re.finditer(r"\b(missed|missing|failed to reach|didn't make|did not make|short of|out of|knocked out (?:in|of)|eliminated in|out in|went out in|reached|made it (?:in)?to|into|through to|advanced to)\s+(?:the\s+)?(S?Q)([123])\b(?![\s-]+cut)", text, re.I):
        verb, seg = c.group(1).lower(), int(c.group(3))
        if verb in ("missed", "missing", "failed to reach", "didn't make", "did not make", "short of"):
            wrong = out_in is None or seg != out_in + 1
        elif verb.startswith(("knocked out", "eliminated", "out in", "went out", "out of")):
            wrong = out_in is None or seg != out_in
        else:  # reached / made it to / into / through to / advanced to
            wrong = seg > last
        if wrong:
            truth = f"he reached {prefix}3" if out_in is None else f"he went out in {prefix}{out_in} (so he missed {prefix}{out_in + 1})"
            out.append(Violation(section, f"\"{c.group()}\" is wrong: {truth}"))
    return out


def check_headline_reading(text: str, sheet: dict) -> list[Violation]:
    """A headline that reads the result backwards: 'undone' for a driver who climbed P19 to P9, or
    'cost him N places' for one who finished where he started (REVIEW_ROUND3 #52)."""
    gained = (sheet.get("result") or {}).get("places_gained")
    if gained is None:
        return []
    if gained > 0 and UNDONE.search(text):
        return [Violation("headline", f"\"{UNDONE.search(text).group()}\" misreads his race: he finished {gained} places higher than he started")]
    lost = re.search(r"\bcost\b[^.]*?\b(\d+) places\b", text, re.I)
    if gained >= 0 and lost and int(lost.group(1)) >= 3 and not RECOVERY.search(text):  # "cost Gasly a place" can be the story; "cost Colapinto 10 places" for a P15-to-P15 race isn't
        return [Violation("headline", f"the headline says he lost {lost.group(1)} places, but he finished no lower than he started: say what he recovered, or lead with something else")]
    return []


def _names(sheet: dict) -> str:
    d = sheet.get("driver") or {}
    return " ".join(x for x in (d.get("name"), d.get("teammate"), d.get("team")) if x)


def check_headline(text: str, sheet: dict) -> list[Violation]:
    """A verdict says what the result meant or why it happened ("Alpine's early stop cost Gasly a place
    he won back"), not only the result ("P10 from P14"): at least two words beyond result vocabulary."""
    name_words = {w.lower() for w in re.findall(r"[\w'’-]+", _names(sheet))}
    content = [w for w in re.findall(r"[\w'’-]+", text.lower()) if not RESULT_WORDS.match(w) and w not in name_words]
    if len(content) < 2:
        return [Violation("headline", f"\"{text}\" only states the result: make it a verdict, saying what the result meant or why it happened (one of the verdict_candidates)")]
    return []


def check_hedging(section: str, text: str, sheet: dict) -> list[Violation]:
    if sheet.get("insufficient_data"):
        allowed = 1
    else:
        allowed = 0
    found = [h for h in HEDGES if h in text.lower()]
    if len(found) > allowed:
        return [Violation(section, f"cut the hedging (\"{found[0]}\"): state the computed verdicts; only {'one sentence about missing data is' if allowed else 'nothing here is'} allowed")]
    return []


def check_story(data: dict, sheet: dict, *, roster: dict[str, str], entrants: set[str], extra_numbers: set[float] | None = None,
                limits: dict[str, int] | None = None, style: bool = True) -> list[Violation]:
    """All checks over a structured story {headline, essential, key_numbers, glossary_terms} (a story from
    before prompt v4 also has expert and analysis, checked too). Arcs and head-to-heads pass their own
    `limits` (their sections and word counts).

    `style`: also hold the story to the style rules (no filler about what didn't happen). They apply when a
    story is written; a published story is re-checked for truth only, so a true but padded story isn't
    swapped for a template."""
    out: list[Violation] = []
    allowed = _allowed_numbers(sheet, extra_numbers or set())
    sheet_text = json.dumps(sheet, default=str)
    teammate = (sheet.get("driver") or {}).get("teammate")
    sections = limits or (LEGACY_LIMITS if data.get("expert") else LIMITS)
    for section, limit in sections.items():
        text = (data.get(section) or "").strip()
        if not text:
            if section != "analysis" or (sheet.get("result") or {}).get("status") != "did not start":
                out.append(Violation(section, "missing"))
            continue
        if LEAK.search(text):
            out.append(Violation(section, f"contains formatting or non-story text near \"{LEAK.search(text).group()}\": write plain prose only"))
        if _words(text) > limit * LIMIT_SLACK:
            out.append(Violation(section, f"{_words(text)} words; the limit is {limit}"))
        out += check_numbers(section, text, allowed)
        out += check_names(section, text, roster, entrants, sheet_text)
        out += check_teammate(section, text, teammate)
        out += check_arithmetic(section, text, sheet)
        out += check_status(section, text, sheet)
        out += check_neutralisation_logic(section, text, sheet)
        out += check_ordinals(section, text)
        out += check_out_of(section, text)
        out += check_points(section, text)
        out += check_stand_in(section, text, sheet)
        out += check_half(section, text, sheet, len(entrants))
        out += check_motives(section, text)
        out += check_sectors(section, text, sheet)
        out += check_segments(section, text, sheet)
        if section in ("headline", "essential", "arc_text"):  # Essential and arcs never talk about missing data
            out += check_missing_data(section, text)
    if limits is not None:
        text = " ".join(str(data.get(k) or "") for k in limits)
        if style and "comparison_text" in limits:  # head-to-heads (#65): Stroll vs Alonso R17 read out three pairs of sector times
            if TIMES_READ_OUT.search(text):
                out.append(Violation("comparison_text", f"don't read out times (\"{TIMES_READ_OUT.search(text).group()}\"): say who was quicker, with the sector rank or the gap"))
            if NON_EVENT.search(text):
                out.append(Violation("comparison_text", f"leave out what didn't happen (\"{NON_EVENT.search(text).group()}\"): every sentence should say something that did"))
        return out + check_hedging("story", text, sheet)
    essential = data.get("essential") or ""
    if LAP_TIME.search(essential):
        out.append(Violation("essential", "no lap times in essential: it is for a new fan"))
    if RAW.search(essential):
        out.append(Violation("essential", f"use plain words in essential, not data notation like \"{RAW.search(essential).group()}\" (that belongs in expert)"))
    if RE_ESSENTIAL_DATA.search(essential):
        out.append(Violation("essential", f"no sector ranks or pit-lane times in essential (\"{RE_ESSENTIAL_DATA.search(essential).group()}\"): they are in the Expert debrief"))
    if style and NON_EVENT.search(essential):
        out.append(Violation("essential", f"leave out what didn't happen (\"{NON_EVENT.search(essential).group()}\"): every sentence should say something that did"))
    if data.get("headline") and (sheet.get("result") or {}).get("status") != "did not start":
        out += check_headline(data["headline"], sheet)
        out += check_headline_reading(data["headline"], sheet)
        # R1 Russell: "A lap-27 pass on Hamilton" for a lead taken through the pit stops (prompt v5 pilot)
        win = next((c for c in sheet.get("verdict_candidates") or [] if c.get("kind") == "win"), None)
        if win and "through the pit stops" in win.get("verdict", "") and PASS_WORD.search(data["headline"]):
            out.append(Violation("headline", "he took the lead through the pit stops, not by passing on track: don't call it a pass"))
    if "analysis" in sections:
        out += check_hedging("analysis", data.get("analysis") or "", sheet)
        if sheet.get("verdicts") and data.get("analysis") and not _uses_a_verdict(data["analysis"], sheet["verdicts"]):
            out.append(Violation("analysis", "state at least one of the computed verdicts as a conclusion"))
    for k in data.get("key_numbers") or []:
        out += check_numbers("key_numbers", str(k.get("value", "")), allowed)
    return out


def _uses_a_verdict(analysis: str, verdicts: list[str]) -> bool:
    """Loose match: the analysis shares the verdict's key numbers or wording."""
    a = analysis.lower()
    for v in verdicts:
        nums = set(re.findall(r"\d+(?:\.\d+)?", v))
        if nums and sum(1 for n in nums if n in a) >= min(2, len(nums)):
            return True
        if any(k in a and k in v.lower() for k in ("undercut", "overcut", "unlucky", "under the", "missed", "cheap stop", "held steady", "fell away")):
            return True
    return False
