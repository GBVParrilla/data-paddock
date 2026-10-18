"""A story job = Claude calls plus how to check and store the result.

Planning (DB reads, hashing) and saving (DB writes) happen on the caller's DB session; only
`call` (the Claude calls and the pure checks between them) runs in worker threads.

`call` generates, runs `check` on the output, and on violations asks again with the list of
problems, up to `attempts` times. If every attempt fails it returns `fallback()` (a story built by
code from the facts), so unverified model text is never what gets stored as publishable.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable

from sqlalchemy.orm import Session as OrmSession

from .llm import NarrativeGenerationError, NarrativeStopError, generate_json
from .prompts import RETRY_NOTE

log = logging.getLogger(__name__)


@dataclass
class Outcome:
    data: dict[str, Any]
    model: str
    attempts: int = 1
    fallback: bool = False
    violations: list[str] = field(default_factory=list)  # the last rejected attempt's problems (empty when it passed)


@dataclass
class StoryJob:
    label: str
    system: str
    user: str
    schema: dict[str, Any]
    save: Callable[[OrmSession, Outcome], Any]
    check: Callable[[dict[str, Any]], list[Any]] = lambda data: []
    fallback: Callable[[], dict[str, Any]] | None = None
    attempts: int = 3

    def call(self) -> Outcome:
        user = self.user
        problems: list[str] = []
        model = "template"
        for attempt in range(1, self.attempts + 1):
            try:
                data, model = generate_json(self.system, user, self.schema)
            except NarrativeStopError:
                raise
            except NarrativeGenerationError as exc:
                problems = [f"generation failed: {exc}"]
                log.warning("%s attempt %d: %s", self.label, attempt, exc)
                continue
            problems = [str(v) for v in self.check(data)]
            if not problems:
                return Outcome(data, model, attempt)
            log.info("%s attempt %d rejected: %s", self.label, attempt, "; ".join(problems[:4]))
            user = self.user + "\n\n" + RETRY_NOTE.format(violations="\n".join(f"- {p}" for p in problems[:12]))
        if self.fallback is None:
            raise NarrativeGenerationError(f"{self.label}: no attempt passed the checks ({'; '.join(problems[:3])})")
        log.warning("%s: published the fact-sheet template after %d rejected attempts", self.label, self.attempts)
        return Outcome(self.fallback(), model, self.attempts, fallback=True, violations=problems)

    def run(self, db: OrmSession) -> Any:
        return self.save(db, self.call())
