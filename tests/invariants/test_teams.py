"""Team invariants: one team per driver per event, and constructor points that match the FIA's."""
from __future__ import annotations

import json
import os
import urllib.request
from collections import defaultdict
from functools import lru_cache
from pathlib import Path

import pytest

from .conftest import all_sessions, events, load, season_year

JOLPICA = "https://api.jolpi.ca/ergast/f1"
CACHE = Path(os.environ.get("INVARIANT_CACHE", Path(__file__).resolve().parent / ".cache"))


@lru_cache(maxsize=None)
def jolpica(path: str) -> dict:
    """Official data, cached on disk so repeated runs don't hammer the API."""
    CACHE.mkdir(exist_ok=True)
    f = CACHE / (path.replace("/", "_") + ".json")
    if f.exists():
        return json.loads(f.read_text())
    try:
        with urllib.request.urlopen(f"{JOLPICA}/{path}.json?limit=100", timeout=30) as r:
            data = json.load(r)
    except OSError as exc:
        pytest.skip(f"Jolpica unreachable: {exc}")
    f.write_text(json.dumps(data))
    return data


def test_one_team_per_driver_per_event():
    """#4: every session of a weekend agrees on each driver's team."""
    bad = []
    for e in events():
        teams: dict[int, set[str]] = defaultdict(set)
        for _, s in [(x, y) for x, y in all_sessions() if x["id"] == e["id"]]:
            h = load(f"sessions/{s['id']}/headline")
            for did, d in h["drivers"].items():
                teams[int(did)].add(d.get("team"))
        bad += [(e["round"], did, t) for did, t in teams.items() if len(t) != 1]
    assert not bad, f"drivers with several teams in one event: {bad[:10]}"


def test_team_cars_per_race():
    """#4: no team runs more than two cars in a race."""
    bad = []
    for e, s in all_sessions():
        if s["session_type"] != "R":
            continue
        h = load(f"sessions/{s['id']}/headline")
        count: dict[str, int] = defaultdict(int)
        for r in h["race"]:
            count[h["drivers"][str(r["driver_id"])]["team"]] += 1
        bad += [(e["round"], t, n) for t, n in count.items() if n > 2]
    assert not bad, f"teams with more than two cars: {bad}"


def _norm(name: str) -> str:
    return "".join(ch for ch in name.lower() if ch.isalnum())


def test_constructor_points_match_official_standings():
    """#4: our constructor table equals Jolpica's official standings after the latest round."""
    st = load(f"seasons/{season_year()}/standings")
    last = max(st["rounds"])
    official = jolpica(f"{season_year()}/{last}/constructorstandings")["MRData"]["StandingsTable"]["StandingsLists"][0]["ConstructorStandings"]
    ours = {t.get("constructor_id") or _norm(t["team"]): float(t["points"]) for t in st["teams"]}
    theirs = {c["Constructor"]["constructorId"]: float(c["points"]) for c in official}
    assert ours == theirs, f"ours {sorted(ours.items())} vs official {sorted(theirs.items())}"


def test_driver_points_match_official_standings():
    st = load(f"seasons/{season_year()}/standings")
    last = max(st["rounds"])
    official = jolpica(f"{season_year()}/{last}/driverstandings")["MRData"]["StandingsTable"]["StandingsLists"][0]["DriverStandings"]
    theirs = {d["Driver"]["code"]: float(d["points"]) for d in official}
    ours = {d["code"]: float(d["points"]) for d in st["drivers"]}
    diff = {k: (ours.get(k), v) for k, v in theirs.items() if ours.get(k, 0.0) != v}
    assert not diff, f"driver points differ (ours, official): {diff}"
