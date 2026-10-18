"""Data invariants over the exported site JSON (DATA_DIR, default frontend/dist/data).

Each check names the REVIEW.md issue it guards. They read only what the site reads, so a
number that passes here is a number a visitor sees.
"""
from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path

import pytest

DATA_DIR = Path(os.environ.get("DATA_DIR", Path(__file__).resolve().parents[2] / "frontend" / "dist" / "data"))


def load(rel: str):
    p = DATA_DIR / f"{rel}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


@lru_cache(maxsize=1)
def season_year() -> int:
    seasons = load("seasons") or []
    return max(s["year"] for s in seasons)


@lru_cache(maxsize=1)
def events() -> list[dict]:
    return [e for e in (load(f"seasons/{season_year()}/events") or []) if e.get("completed")]


@lru_cache(maxsize=None)
def sessions(event_id: int) -> list[dict]:
    return [s for s in (load(f"events/{event_id}/sessions") or []) if s["ingestion"]["transforms"]]


def all_sessions() -> list[tuple[dict, dict]]:
    return [(e, s) for e in events() for s in sessions(e["id"])]


def session_ids(*types: str) -> list[tuple[int, str]]:
    return [(s["id"], f"R{e['round']:02d}-{s['session_type']}") for e, s in all_sessions() if not types or s["session_type"] in types]


def params(*types: str):
    ids = session_ids(*types)
    return pytest.mark.parametrize("sid", [i for i, _ in ids], ids=[label for _, label in ids])


def pytest_configure(config):
    if not DATA_DIR.exists():
        raise pytest.UsageError(f"no exported data at {DATA_DIR} - run `make build` (or set DATA_DIR)")
