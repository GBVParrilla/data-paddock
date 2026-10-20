"""Headline variety within a session (REVIEW_ROUND3 #53).

In the round 2 pilot, 10 drivers in one practice session got "X's long-run pace beat his
single-lap place", and Gasly and Ocon both got "Pitting just before the VSC was unlucky for X".
Two things fix that:

- `mark_shared` ranks each driver's verdict candidates by how distinctive they are: a situation
  much of the field shared (a VSC everyone stopped under, a long run that beat a single-lap place)
  counts for half its weight against what was true of this driver alone.
- `SessionHeadlines` remembers the headlines written for a session. A new one with the same shape
  as another driver's is rejected (and retried), and the template fallback picks a candidate whose
  shape is still free.

A headline's shape is its words with names, teams and numbers taken out: "Pitting just before the
VSC was unlucky for Gasly" and "... for Ocon" have the same shape.
"""
from __future__ import annotations

import re
import threading
from typing import Any

STOP = {"a", "an", "the", "his", "him", "he", "of", "to", "for", "in", "on", "at", "by", "and", "with", "from", "was", "is", "s"}
SHARED_SHARE = 0.25  # a candidate shape true of a quarter of the field or more is the session's story, not his
SHARED_WEIGHT = 0.5  # ...so it counts for half: it still leads when nothing else about him is as telling


def shape(headline: str, names: set[str]) -> tuple[str, ...]:
    """The construction of a headline, with who and how many taken out."""
    words = re.findall(r"[a-z]+|\d+", headline.lower().replace("’", "'"))
    out = []
    for w in words:
        if w.isdigit():
            out.append("#")
        elif w in names:
            out.append("@")
        elif w not in STOP:
            out.append(w)
    return tuple(out)


def same_shape(a: tuple[str, ...], b: tuple[str, ...]) -> bool:
    """The same construction: identical, or sharing at least 70% of their words (word order aside)."""
    if a == b:
        return True
    sa, sb = set(a) - {"@", "#"}, set(b) - {"@", "#"}
    if not sa or not sb:
        return False
    return len(sa & sb) / len(sa | sb) >= 0.7


def name_words(names) -> set[str]:
    return {w for n in names if n for w in re.findall(r"[a-z]+", n.lower())}


def mark_shared(sheets: dict[int, dict[str, Any]], names: set[str]) -> None:
    """Re-order each sheet's verdict candidates so the most distinctive comes first; a candidate shape
    that a quarter or more of the session's drivers also have gets `shared_with_other_drivers`."""
    shapes: dict[int, list[tuple[str, ...]]] = {d: [shape(c["headline"], names) for c in s.get("verdict_candidates") or []] for d, s in sheets.items()}
    n = len(sheets)
    for d, s in sheets.items():
        cands = s.get("verdict_candidates") or []
        if not cands:
            continue
        for c, sh in zip(cands, shapes[d]):
            others = sum(1 for o, osh in shapes.items() if o != d and any(same_shape(sh, x) for x in osh))
            if others and (others + 1) / max(n, 1) >= SHARED_SHARE:
                c["shared_with_other_drivers"] = others
            else:
                c.pop("shared_with_other_drivers", None)
        s["verdict_candidates"] = sorted(cands, key=lambda c: -(c.get("weight", 1.0) * (SHARED_WEIGHT if "shared_with_other_drivers" in c else 1.0)))


class SessionHeadlines:
    """The headlines written for one session so far, shared by the jobs writing it (thread-safe)."""

    def __init__(self, names: set[str]):
        self.names = names
        self._lock = threading.Lock()
        self._by_driver: dict[int, tuple[str, tuple[str, ...]]] = {}

    def seed(self, driver_id: int, headline: str) -> None:
        with self._lock:
            self._by_driver[driver_id] = (headline, shape(headline, self.names))

    def written(self, except_driver: int) -> list[str]:
        with self._lock:
            return [h for d, (h, _) in self._by_driver.items() if d != except_driver]

    def clash(self, driver_id: int, headline: str) -> str | None:
        """Another driver's headline with the same shape, if any."""
        mine = shape(headline, self.names)
        with self._lock:
            return next((h for d, (h, sh) in self._by_driver.items() if d != driver_id and same_shape(mine, sh)), None)

    def claim(self, driver_id: int, headline: str) -> str | None:
        """Record this headline unless its shape is taken; returns the clashing headline, or None when claimed."""
        mine = shape(headline, self.names)
        with self._lock:
            other = next((h for d, (h, sh) in self._by_driver.items() if d != driver_id and same_shape(mine, sh)), None)
            if other is None:
                self._by_driver[driver_id] = (headline, mine)
            return other
