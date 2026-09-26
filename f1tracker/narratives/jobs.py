"""A story job = one Claude call plus how to store its result.

Planning (DB reads, hashing) and saving (DB writes) happen on the caller's DB session; only the
Claude call in between is thread-safe, so the pipeline can run many of them in parallel.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from sqlalchemy.orm import Session as OrmSession

from .llm import generate_json


@dataclass
class StoryJob:
    label: str
    system: str
    user: str
    schema: dict[str, Any]
    save: Callable[[OrmSession, dict[str, Any], str], Any]  # (db, parsed output, model used) -> stored row

    def call(self) -> tuple[dict[str, Any], str]:
        return generate_json(self.system, self.user, self.schema)

    def run(self, db: OrmSession) -> Any:
        data, model_used = self.call()
        return self.save(db, data, model_used)
