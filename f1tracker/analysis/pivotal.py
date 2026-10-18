"""Key moments: the handful of things that decided a session, as scored candidates (no LLM).

Each candidate type answers "would a fan who missed this session want to know?":
  race:  a top-10 starter who didn't start or retired, recovery drives and big drops, grid drops,
         every SC/VSC/red flag (with who pitted under it), penalties, lead changes, undercuts and
         overcuts between cars running together, slow stops, big net swings through the stops,
         stewards' cases between two cars, the fastest lap (as filler only)
  quali: pole margin, favourites knocked out early, drivers who set no time, close escapes at the
         cut lines, midfield cars into the final segment, red flags
  practice: red flags, the session topper, standout midfield results

impact = base x championship weight x visibility (+ a midfield bonus), so a routine pit stop
never outranks a retirement from P3, and every race keeps at least one non-podium story.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session as OrmSession

from ..ingest.entries import event_drivers
from ..models import (
    PRACTICE_LIKE,
    QUALI_LIKE,
    RACE_LIKE,
    DetailPositionByLap,
    Event,
    HeadlineQualifying,
    HeadlineRace,
    Lap,
    PitStop,
    PivotalMoment,
    RaceControl,
    Session,
    Stint,
)
from ..util import fmt_ms
from .race_control import Incident, cases, neutral_periods, parse_messages
from .strategy import analyse_stops, pit_battles

log = logging.getLogger(__name__)

LIMITS = {"race": (5, 8), "quali": (3, 5), "practice": (2, 4)}
MIDFIELD_BONUS = 0.6
PERIOD_LABEL = {"SC": "Safety Car", "VSC": "Virtual Safety Car", "RED": "Red flag"}


@dataclass
class Moment:
    moment_type: str
    score: float
    headline: str
    detail: str | None = None
    lap: int | None = None
    driver_id: int | None = None
    related_driver_id: int | None = None
    end_lap: int | None = None
    must_include: bool = False

    @property
    def description(self) -> str:
        return self.headline + (f" {self.detail}" if self.detail else "")


@dataclass
class Context:
    session_type: str
    drivers: dict[int, dict]  # id -> {name, code, team}
    race: list[dict] = field(default_factory=list)  # headline_race rows
    quali: list[dict] = field(default_factory=list)  # headline_qualifying rows
    event_quali: dict[int, dict] = field(default_factory=dict)  # this weekend's Q result per driver
    positions: dict[int, dict[int, int]] = field(default_factory=dict)
    pits: list[dict] = field(default_factory=list)
    stints: list[dict] = field(default_factory=list)
    lap_starts: dict[int, dict[int, datetime]] = field(default_factory=dict)
    incidents: list[Incident] = field(default_factory=list)
    fastest: dict | None = None  # {driver_id, lap, ms, compound}
    practice: list[dict] = field(default_factory=list)  # headline_practice rows
    championship: dict[int, int] = field(default_factory=dict)  # driver -> standing before this event
    top_teams: set[str] = field(default_factory=set)  # top four constructors before this event
    session_start: datetime | None = None


class _Names:
    def __init__(self, ctx: Context):
        self.ctx = ctx

    def __call__(self, did: int | None) -> str:
        d = self.ctx.drivers.get(did) if did is not None else None
        return d["name"] if d else "a driver"

    def last(self, did: int | None) -> str:
        return self(did).split(" ")[-1]

    def team(self, did: int | None) -> str | None:
        d = self.ctx.drivers.get(did) if did is not None else None
        return d.get("team") if d else None


def _weights(ctx: Context, did: int | None, position: int | None) -> float:
    champ = ctx.championship.get(did) if did is not None else None
    w = 1.5 if champ and champ <= 3 else 1.25 if champ and champ <= 6 else 1.0
    w *= 1.5 if position and position <= 3 else 1.2 if position and position <= 10 else 1.0
    return w


def _midfield(ctx: Context, did: int | None) -> bool:
    team = ctx.drivers.get(did, {}).get("team") if did is not None else None
    return bool(team and ctx.top_teams and team not in ctx.top_teams)


def _score(ctx: Context, base: float, did: int | None, position: int | None) -> float:
    return round(base * _weights(ctx, did, position) + (MIDFIELD_BONUS if _midfield(ctx, did) else 0.0), 2)


def _minutes_in(ctx: Context, t: datetime | None) -> str | None:
    if t is None or ctx.session_start is None:
        return None
    mins = int((t - ctx.session_start).total_seconds() // 60)
    return f"{mins} minutes in" if 0 <= mins <= 200 else None


# ---------------------------------------------------------------------------- race
def _race_moments(ctx: Context) -> list[Moment]:
    name = _Names(ctx)
    out: list[Moment] = []
    periods = neutral_periods(ctx.incidents)
    stops = analyse_stops(ctx.pits, ctx.stints, ctx.positions, periods)
    stops_by_driver = defaultdict(list)
    for v in stops:
        stops_by_driver[v.driver_id].append(v)
    rows = {r["driver_id"]: r for r in ctx.race}
    distance = max((r.get("laps_completed") or 0 for r in ctx.race), default=0)

    # did not start / retired
    for r in ctx.race:
        did, code = r["driver_id"], r.get("status_code")
        if code == "DNS":
            grid = r.get("grid_position")
            m = Moment("dns", _score(ctx, 3 + max(0, 11 - (grid or 11)) * 0.5, did, grid), f"{name(did)} did not start" + (f" from P{grid}" if grid else "") + ".", driver_id=did, lap=0)
            out.append(m)
        elif code in ("DNF", "NC"):
            lap = r.get("laps_completed")
            mine = ctx.positions.get(did, {})
            pos = mine.get(lap) or (mine[max(mine)] if mine else None)
            reason = (r.get("status") or "").strip()
            reason_txt = f" ({reason.lower()})" if reason and reason.lower() not in ("retired", "lapped", "finished") else ""
            where = f" from P{pos}" if pos else ""
            when = f" on lap {lap + 1}" if lap is not None and lap < distance else ""
            grid = r.get("grid_position")
            started = f", having started P{grid}" if grid and pos and grid != pos and grid <= 10 else ""
            if r.get("finish_position"):
                headline = f"{name(did)} stopped{when}{where} but was still classified P{r['finish_position']}."
            else:
                headline = f"{name(did)} retired{where}{when}{reason_txt}{started}."
            near = [i for i in ctx.incidents if did in i.driver_ids and i.kind in ("investigation", "penalty") and lap is not None and i.lap is not None and abs(i.lap - lap) <= 2]
            detail = f"Race control noted an incident involving him on lap {near[0].lap}." if near else None
            ref = min(p for p in (pos, grid) if p) if (pos or grid) else None
            base = 3 + max(0, 11 - ref) * 0.5 if ref and ref <= 10 else 2.0
            out.append(Moment("dnf", _score(ctx, base, did, pos), headline, detail, lap=(lap + 1) if lap is not None else None, driver_id=did))

    # recovery drives, big drops, grid drops
    for r in ctx.race:
        did, grid, fin = r["driver_id"], r.get("grid_position"), r.get("finish_position")
        q = ctx.event_quali.get(did)
        grid_note = None
        if q is not None and grid:
            if q.get("status_code") == "NO_TIME":
                grid_note = "He set no time in qualifying."
            elif q.get("position") and grid - q["position"] >= 3:
                grid_note = f"He qualified P{q['position']} but started P{grid}."
        if r.get("status_code") in ("FIN", "LAP") and grid and fin:
            gained = grid - fin
            passes = _on_track_gains(ctx, did)
            if gained >= 5:
                detail = " ".join(x for x in (grid_note, f"He made {passes} places on track, away from the pit stops." if passes >= 3 else None) if x)
                out.append(Moment("recovery", _score(ctx, 1.5 + gained * 0.45, did, fin), f"{name(did)} climbed from P{grid} to P{fin}.", detail or None, driver_id=did))
                continue
            if gained <= -5:
                out.append(Moment("drop", _score(ctx, 1.0 + -gained * 0.35, did, grid), f"{name(did)} fell from P{grid} to P{fin}.", driver_id=did))
                continue
        if grid_note and grid and grid <= 22 and q is not None and (q.get("position") or 0) <= 10:
            out.append(Moment("grid", _score(ctx, 2.5, did, q.get("position")), f"{name(did)} started P{grid}.", grid_note, driver_id=did, lap=0))

    # neutralisations: every one is a key moment (REVIEW #14)
    for p in periods:
        start, end = p.get("start_lap"), p.get("end_lap")
        under = [v for v in stops if v.neutralisation == "during" and v.neutralisation_laps == (start, end)]
        label = PERIOD_LABEL[p["kind"]]
        if p["kind"] == "RED":
            when = f"on lap {start}" if start else _minutes_in(ctx, p.get("time"))
            headline = f"Red flag{' ' + when if when else ''}: the session was stopped."
        else:
            span = f"laps {start}–{end}" if end and end != start else f"lap {start}"
            headline = f"{label} on {span}."
        detail = None
        if under:
            gainers = sorted((v for v in under if (v.net_places or 0) >= 2), key=lambda v: -(v.net_places or 0))
            names = ", ".join(name.last(v.driver_id) for v in sorted(under, key=lambda v: v.position_before or 99)[:6])
            detail = f"{len(under)} car{'s' if len(under) != 1 else ''} pitted under it ({names}{', ...' if len(under) > 6 else ''})."
            if gainers:
                g = gainers[0]
                detail += f" {name(g.driver_id)} gained {g.net_places} places from the cheaper stop."
        base = {"RED": 6.0, "SC": 4.5, "VSC": 3.5}[p["kind"]] + 0.3 * len(under)
        out.append(Moment("red_flag" if p["kind"] == "RED" else "safety_car" if p["kind"] == "SC" else "vsc", round(base, 2), headline, detail, lap=start, end_lap=end, must_include=True))

    # penalties
    for inc in ctx.incidents:
        if inc.kind != "penalty" or not inc.driver_ids:
            continue
        did = inc.driver_ids[0]
        outcome = (inc.outcome or "a penalty").replace("penalty", "penalty").strip()
        why = f" for {inc.reason.lower()}" if inc.reason else ""
        heavy = any(w in outcome for w in ("stop-and-go", "stop/go", "drive through", "drive-through"))
        fin = rows.get(did, {}).get("finish_position")
        out.append(Moment("penalty", _score(ctx, 4.5 if heavy else 3.0, did, fin), f"{name(did)} was given a {outcome}{why}.", lap=inc.lap, driver_id=did))

    # lead changes on track or through the stops
    leader = {}
    for did, by_lap in ctx.positions.items():
        for lap, pos in by_lap.items():
            if pos == 1:
                leader[lap] = did
    laps = sorted(leader)
    pit_laps = {(p["driver_id"], p["lap_number"]) for p in ctx.pits}
    changes = []
    for a, b in zip(laps, laps[1:]):
        if b == a + 1 and leader[a] != leader[b] and a > 1:
            new, old = leader[b], leader[a]
            via_pits = any((d, l) in pit_laps for d in (new, old) for l in (a - 1, a, b))
            changes.append((b, new, old, via_pits))
    for lap, new, old, via_pits in changes[:3]:
        how = "through the pit stops" if via_pits else "on track"
        final = rows.get(new, {}).get("finish_position") == 1
        out.append(Moment("lead_change", _score(ctx, 4.5 if final else 3.0, new, 1), f"{name(new)} took the lead from {name.last(old)} {how} on lap {lap}.", lap=lap, driver_id=new, related_driver_id=old))

    # undercuts / overcuts between cars running together
    for b in pit_battles(ctx.pits, ctx.positions, ctx.lap_starts, periods):
        if b.under_neutralisation or b.verdict not in ("undercut_worked", "overcut_worked"):
            continue
        winner, loser = (b.attacker_id, b.defender_id) if b.verdict == "undercut_worked" else (b.defender_id, b.attacker_id)
        pos = ctx.positions.get(winner, {}).get(b.decided_lap)
        kind = "undercut" if b.verdict == "undercut_worked" else "overcut"
        gap = f" from {abs(b.gap_before_ms) / 1000:.1f}s behind" if (b.gap_before_ms is not None and b.verdict == "undercut_worked") else ""
        detail = f"{name.last(b.attacker_id)} pitted on lap {b.attacker_lap}, {name.last(b.defender_id)} on lap {b.defender_lap}; after both stops {name.last(winner)} was ahead{(' in P' + str(pos)) if pos else ''}."
        out.append(Moment(kind, _score(ctx, 3.0, winner, pos), f"{name(winner)} {'undercut' if kind == 'undercut' else 'overcut'} {name.last(loser)}{gap}.", detail, lap=b.defender_lap, driver_id=winner, related_driver_id=loser))

    # slow stops and big swings through the stops
    for v in stops:
        fin = rows.get(v.driver_id, {}).get("finish_position")
        if v.slow:
            what = f"{v.stationary_ms / 1000:.1f}s stationary" if v.stationary_ms and v.stationary_ms >= 4000 else (f"{v.lane_vs_median_ms / 1000:.1f}s longer in the pit lane than the typical stop" if v.lane_vs_median_ms else "a slow stop")
            lost = f" and dropped {-v.net_places} places" if v.net_places and v.net_places < 0 else ""
            out.append(Moment("slow_stop", _score(ctx, 2.5 + max(0, -(v.net_places or 0)) * 0.5, v.driver_id, fin), f"{name(v.driver_id)} lost time in the pits on lap {v.in_lap}{lost}.", f"The stop took {what}.", lap=v.in_lap, driver_id=v.driver_id))
        elif v.net_places is not None and abs(v.net_places) >= 3 and v.neutralisation != "during":
            verb = "gained" if v.net_places > 0 else "lost"
            when = " just before the " + PERIOD_LABEL.get(v.neutralisation_kind or "", "neutralisation") if v.neutralisation == "just_before" else ""
            out.append(Moment("pit_cycle", _score(ctx, 2.0 + abs(v.net_places) * 0.4, v.driver_id, fin), f"{name(v.driver_id)} {verb} {abs(v.net_places)} places through his stop on lap {v.in_lap}{when}.", f"P{v.position_before} before the stop, P{v.position_after_cycle} once the cars around him had stopped too.", lap=v.in_lap, driver_id=v.driver_id))

    # stewards' cases between two cars (both drivers' stories share these)
    for c in cases(ctx.incidents):
        if len(c["driver_ids"]) < 2 or c["outcome"] == "stop-and-go penalty":
            continue
        a, b = c["driver_ids"][:2]
        where = f" at Turn {c['turn']}" if c.get("turn") else ""
        what = f" ({c['reason']})" if c.get("reason") else ""
        result = "no further action" if c["outcome"] == "no further action" else (c["outcome"] or ("investigated after the race" if c["after_race"] else "under investigation"))
        fin = min((rows.get(d, {}).get("finish_position") or 99) for d in (a, b))
        out.append(Moment("incident", _score(ctx, 1.8, a, fin), f"{name(a)} and {name(b)} were investigated for an incident{where}{what}.", f"Stewards' decision: {result}.", lap=c["opened_lap"], driver_id=a, related_driver_id=b))

    if ctx.fastest:
        f = ctx.fastest
        out.append(Moment("fastest_lap", 1.2, f"Fastest lap: {name(f['driver_id'])}, {fmt_ms(f['ms'])} on lap {f['lap']}.", lap=f["lap"], driver_id=f["driver_id"]))
    return out


def _on_track_gains(ctx: Context, did: int) -> int:
    """Places gained on laps without a pit stop by this driver (or a neutralisation restart)."""
    mine = ctx.positions.get(did, {})
    pits = {p["lap_number"] for p in ctx.pits if p["driver_id"] == did}
    gained = 0
    for lap in sorted(mine):
        prev = mine.get(lap - 1)
        if prev is None or lap <= 1:
            continue
        if any(l in pits for l in (lap - 1, lap, lap + 1)):
            continue
        if prev > mine[lap]:
            gained += prev - mine[lap]
    return gained


# ---------------------------------------------------------------------------- qualifying
def _quali_moments(ctx: Context) -> list[Moment]:
    name = _Names(ctx)
    out: list[Moment] = []
    rows = sorted([r for r in ctx.quali if r.get("position")], key=lambda r: r["position"])
    seg = "SQ" if ctx.session_type == "SQ" else "Q"
    if len(rows) >= 2 and rows[1].get("gap_to_pole_ms") is not None:
        pole, p2 = rows[0], rows[1]
        margin = p2["gap_to_pole_ms"]
        out.append(Moment("pole", 4.0 + (1.0 if margin >= 300 or margin <= 30 else 0), f"{name(pole['driver_id'])} took pole by {fmt_ms(margin)}s from {name.last(p2['driver_id'])}.", driver_id=pole["driver_id"], related_driver_id=p2["driver_id"]))
    # favourites knocked out early
    for r in rows:
        did = r["driver_id"]
        fav = (ctx.championship.get(did) or 99) <= 8 or name.team(did) in ctx.top_teams
        if fav and r.get("eliminated_in") in ("Q1", "Q2") and r.get("status_code") != "NO_TIME":
            out.append(Moment("knocked_out", _score(ctx, 3.0 if r["eliminated_in"] == "Q2" else 4.0, did, None), f"{name(did)} was knocked out in {seg}{r['eliminated_in'][1]} and starts P{r['position']}.", driver_id=did))
    for r in ctx.quali:
        if r.get("status_code") == "NO_TIME" or (r.get("q1_ms") is None and r.get("q2_ms") is None and r.get("q3_ms") is None):
            did = r["driver_id"]
            dels = [i for i in ctx.incidents if did in i.driver_ids and i.kind == "track_limits"]
            detail = "His laps were deleted for track limits." if dels else None
            out.append(Moment("no_time", _score(ctx, 3.5, did, None), f"{name(did)} set no time.", detail, driver_id=did))
    # close escapes at the cut lines
    for cut_seg, key in (("Q1", "q1_ms"), ("Q2", "q2_ms")):
        times = sorted((r[key], r["driver_id"]) for r in ctx.quali if r.get(key))
        if not times:
            continue
        survivors = sum(1 for r in ctx.quali if r.get(key) and r.get("eliminated_in") != cut_seg)
        if 0 < survivors < len(times):
            (t_in, d_in), (t_out, d_out) = times[survivors - 1], times[survivors]
            if t_out - t_in <= 100:
                out.append(Moment("cut_line", _score(ctx, 2.5, d_in, survivors), f"{name(d_in)} escaped {seg}{cut_seg[1]} by {fmt_ms(t_out - t_in)}s, at the expense of {name.last(d_out)}.", driver_id=d_in, related_driver_id=d_out))
    # midfield cars into the final segment
    into_q3 = [r for r in rows if r.get("eliminated_in") is None and _midfield(ctx, r["driver_id"])]
    for r in into_q3[:2]:
        out.append(Moment("midfield_q3", _score(ctx, 2.2, r["driver_id"], r["position"]), f"{name(r['driver_id'])} reached the final segment and qualified P{r['position']} for {name.team(r['driver_id'])}.", driver_id=r["driver_id"]))
    out += _red_flags(ctx)
    return out


def _red_flags(ctx: Context) -> list[Moment]:
    out = []
    for p in neutral_periods(ctx.incidents):
        if p["kind"] != "RED":
            continue
        when = f"on lap {p['start_lap']}" if (p.get("start_lap") and ctx.session_type in RACE_LIKE) else _minutes_in(ctx, p.get("time"))
        out.append(Moment("red_flag", 4.0, f"Red flag{' ' + when if when else ''}: the session was stopped.", must_include=True))
    return out


# ---------------------------------------------------------------------------- practice
def _practice_moments(ctx: Context) -> list[Moment]:
    name = _Names(ctx)
    out = _red_flags(ctx)
    for p in neutral_periods(ctx.incidents):
        if p["kind"] in ("SC", "VSC"):
            out.append(Moment("vsc", 1.5, f"{PERIOD_LABEL[p['kind']]} period during the session."))
    rows = sorted((r for r in ctx.practice if r.get("rank")), key=lambda r: r["rank"])
    if len(rows) >= 2:
        top, second = rows[0], rows[1]
        out.append(Moment("fastest", 3.0, f"{name(top['driver_id'])} set the pace with a {fmt_ms(top['fastest_lap_ms'])}, {fmt_ms(second['gap_to_fastest_ms'])}s clear of {name.last(second['driver_id'])}.", driver_id=top["driver_id"]))
    for r in rows[1:6]:
        if _midfield(ctx, r["driver_id"]):
            out.append(Moment("midfield_pace", _score(ctx, 1.8, r["driver_id"], r["rank"]), f"{name(r['driver_id'])} was P{r['rank']} for {name.team(r['driver_id'])}.", driver_id=r["driver_id"]))
            break
    return out


# ---------------------------------------------------------------------------- selection
def select_moments(candidates: list[Moment], session_type: str, race_rows: list[dict] | None = None, ctx: Context | None = None) -> list[Moment]:
    kind = "race" if session_type in RACE_LIKE else "quali" if session_type in QUALI_LIKE else "practice"
    lo, hi = LIMITS[kind]
    seen: set[tuple] = set()
    unique = []
    for m in sorted(candidates, key=lambda m: (-m.score, m.lap or 0)):
        key = (m.moment_type, m.driver_id, m.lap if m.driver_id is None else None)
        if key in seen:
            continue
        seen.add(key)
        unique.append(m)
    chosen = [m for m in unique if m.must_include]
    for m in unique:
        if len(chosen) >= hi:
            break
        if m not in chosen:
            chosen.append(m)
    # every race keeps at least one story from beyond the podium
    if kind == "race" and race_rows:
        podium = {r["driver_id"] for r in race_rows if r.get("finish_position") in (1, 2, 3)}
        if not any(m.driver_id is not None and m.driver_id not in podium for m in chosen):
            extra = next((m for m in unique if m.driver_id is not None and m.driver_id not in podium), None)
            if extra is not None:
                droppable = [m for m in chosen if not m.must_include]
                if len(chosen) >= hi and droppable:
                    chosen.remove(droppable[-1])
                chosen.append(extra)
    del lo  # the minimum is whatever the session offers; fillers keep thin sessions above it
    return sorted(chosen, key=lambda m: (m.lap if m.lap is not None else 999, -m.score))


def compute_moments(ctx: Context) -> list[Moment]:
    if ctx.session_type in RACE_LIKE:
        candidates = _race_moments(ctx)
    elif ctx.session_type in QUALI_LIKE:
        candidates = _quali_moments(ctx)
    else:
        candidates = _practice_moments(ctx)
    return select_moments(candidates, ctx.session_type, ctx.race, ctx)


# ---------------------------------------------------------------------------- DB
def _row(obj) -> dict:
    return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}


def championship_before(db: OrmSession, event: Event) -> tuple[dict[int, int], set[str]]:
    """Driver standings and the top four constructors from the rounds before this event."""
    from ..ingest.entries import entry_map

    q = (
        select(HeadlineRace.driver_id, HeadlineRace.points, Event.id)
        .join(Session, Session.id == HeadlineRace.session_id)
        .join(Event, Event.id == Session.event_id)
        .where(Event.season_id == event.season_id, Event.round < event.round)
    )
    pts: dict[int, float] = defaultdict(float)
    team_pts: dict[str, float] = defaultdict(float)
    entries: dict[int, dict] = {}
    for did, p, eid in db.execute(q).all():
        pts[did] += p or 0
        e = entries.setdefault(eid, entry_map(db, eid)).get(did)
        if e:
            team_pts[e.team] += p or 0
    ranked = sorted(pts.items(), key=lambda kv: -kv[1])
    standing = {did: i + 1 for i, (did, p) in enumerate(ranked) if p > 0}
    top = {t for t, _ in sorted(team_pts.items(), key=lambda kv: -kv[1])[:4]}
    return standing, top


def build_context(db: OrmSession, session_id: int) -> Context:
    session = db.get(Session, session_id)
    event = db.get(Event, session.event_id)
    standing, top = championship_before(db, event)
    ctx = Context(session_type=session.session_type, drivers=event_drivers(db, event.id), championship=standing, top_teams=top, session_start=session.start_time)
    numbers = {d["number"]: did for did, d in ctx.drivers.items() if d.get("number") is not None}
    ctx.incidents = parse_messages(db.scalars(select(RaceControl).where(RaceControl.session_id == session_id)).all(), numbers)
    if session.session_type in RACE_LIKE:
        ctx.race = [_row(r) for r in sorted(db.scalars(select(HeadlineRace).where(HeadlineRace.session_id == session_id)).all(), key=lambda r: r.classification_order or 99)]
        for r in db.scalars(select(DetailPositionByLap).where(DetailPositionByLap.session_id == session_id)).all():
            if r.position is not None:
                ctx.positions.setdefault(r.driver_id, {})[r.lap_number] = r.position
        ctx.pits = [_row(p) for p in db.scalars(select(PitStop).where(PitStop.session_id == session_id)).all()]
        ctx.stints = [_row(s) for s in db.scalars(select(Stint).where(Stint.session_id == session_id)).all()]
        for lap in db.scalars(select(Lap).where(Lap.session_id == session_id, Lap.lap_start_time.is_not(None))).all():
            ctx.lap_starts.setdefault(lap.driver_id, {})[lap.lap_number] = lap.lap_start_time
        if session.session_type == "R":
            q = db.scalar(select(Session).where(Session.event_id == event.id, Session.session_type == "Q"))
            if q is not None:
                ctx.event_quali = {r.driver_id: _row(r) for r in db.scalars(select(HeadlineQualifying).where(HeadlineQualifying.session_id == q.id)).all()}
    elif session.session_type in QUALI_LIKE:
        ctx.quali = [_row(r) for r in db.scalars(select(HeadlineQualifying).where(HeadlineQualifying.session_id == session_id)).all()]
    elif session.session_type in PRACTICE_LIKE:
        from ..models import HeadlinePractice

        ctx.practice = [_row(r) for r in db.scalars(select(HeadlinePractice).where(HeadlinePractice.session_id == session_id)).all()]
    clean = db.scalars(select(Lap).where(Lap.session_id == session_id, Lap.lap_time_ms.is_not(None), Lap.is_pit_lap.is_(False)).order_by(Lap.lap_time_ms).limit(1)).first()
    if clean is not None:
        ctx.fastest = {"driver_id": clean.driver_id, "lap": clean.lap_number, "ms": clean.lap_time_ms, "compound": clean.compound}
    return ctx


def detect_pivotal_moments(db: OrmSession, session_id: int) -> int:
    moments = compute_moments(build_context(db, session_id))
    db.execute(delete(PivotalMoment).where(PivotalMoment.session_id == session_id))
    for m in moments:
        db.add(
            PivotalMoment(
                session_id=session_id, lap_number=m.lap, driver_id=m.driver_id, related_driver_id=m.related_driver_id, end_lap=m.end_lap,
                moment_type=m.moment_type, magnitude_score=m.score, description=m.description, headline=m.headline, detail=m.detail,
            )
        )
    return len(moments)
