"""Deterministic checks on a generated story before it can be published.

A story passes only if:
  - it is clean text (no markup, JSON, self-talk or code tokens),
  - each section is within its word limit, and the summary has no lap times,
  - every number it quotes (times, gaps, positions, laps, counts) is in the fact sheet,
  - arithmetic claims ("97 points behind", "gained 4 places") match the computed values,
  - every driver it names took part in the session, and "teammate X" is the real teammate,
  - it doesn't contradict the result (a car that lost places never "climbed"),
  - stop-timing claims about a Safety Car or VSC agree with the computed verdicts, and
  - the analysis hedges only where the sheet lists insufficient data.
Each failure is a Violation with a message the model can act on when it retries.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .facts import numbers_in

LIMITS = {"headline": 12, "summary": 60, "story": 220, "analysis": 150}
LIMIT_SLACK = 1.15  # a sentence's worth over is tolerated; the gate is the prompt's limit + 15%

LEAK = re.compile(r"</?[a-z_]+>|<br\s*/?>|```|\{\s*\"|\"\s*\}|\}\s*$|^\s*\{|BAD_FORMAT|\bnull\b|\bundefined\b|\bNaN\b|\[object|"
                  r"note to (the )?reviewer|invalid (trailing|json)|let me (correct|fix|redo)|corrected below|as an ai\b|i (cannot|can't) (produce|generate)|^answer:|\(unlikely\)", re.I | re.M)
LAP_TIME = re.compile(r"\b\d:\d{2}\.\d{3}\b")
HEDGES = [
    "it is hard to say", "it's hard to say", "hard to know", "difficult to say", "the evidence does not support a strong conclusion",
    "does not support a strong conclusion", "cannot be confirmed", "can't be confirmed", "it is not possible to judge", "it's not possible to judge",
    "impossible to say", "not possible to say", "speculative", "it is unclear whether", "it's unclear whether",
]
CLIMB = re.compile(r"\b(climbed|gained|made up|moved up)\b")
# numbers as prose writes them: P10, +0.810s, 10th, 55%, 1.2 - not identifiers like Q2, FP1, T3
NUMBER = re.compile(r"(?<![\w.:])P?[+-]?\d+(?:\.\d+)?(?:s|%|st|nd|rd|th)?(?![\w:])")


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
        raw = re.sub(r"^P|[+-]|(s|%|st|nd|rd|th)$", "", m.group())
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
    if section in ("headline", "summary") and gained is not None and gained < 0 and CLIMB.search(first) and "place" in first:
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
                limits: dict[str, int] | None = None) -> list[Violation]:
    """All checks over a structured story {headline, summary, story, analysis, key_numbers, glossary_terms}.
    Arcs and head-to-heads pass their own `limits` (their sections and word counts)."""
    out: list[Violation] = []
    allowed = _allowed_numbers(sheet, extra_numbers or set())
    import json

    sheet_text = json.dumps(sheet, default=str)
    teammate = (sheet.get("driver") or {}).get("teammate")
    for section, limit in (limits or LIMITS).items():
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
    if limits is not None:
        return out + check_hedging("story", " ".join(str(data.get(k) or "") for k in limits), sheet)
    if LAP_TIME.search(data.get("summary") or ""):
        out.append(Violation("summary", "no lap times in the summary: it is for a new fan"))
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
