"""Two-driver comparison for one session: data bundle + cached comparative narrative."""
from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session as OrmSession

from ..models import ComparisonNarrative, DetailPositionByLap, DetailStintTimeline, Driver, Lap, Session
from ..util import fmt_ms, utcnow
from .inputs import build_driver_session_input
from .jobs import StoryJob
from .llm import stable_hash
from .prompts import SCHEMA_COMPARISON, SYSTEM_COMPARISON

log = logging.getLogger(__name__)


def _position_series(db: OrmSession, session_id: int, driver_id: int) -> list[dict]:
    rows = db.scalars(select(DetailPositionByLap).where(DetailPositionByLap.session_id == session_id, DetailPositionByLap.driver_id == driver_id).order_by(DetailPositionByLap.lap_number)).all()
    return [{"lap": r.lap_number, "position": r.position} for r in rows]


def _stints(db: OrmSession, session_id: int, driver_id: int) -> list[dict]:
    rows = db.scalars(select(DetailStintTimeline).where(DetailStintTimeline.session_id == session_id, DetailStintTimeline.driver_id == driver_id).order_by(DetailStintTimeline.stint_number)).all()
    return [{"stint": r.stint_number, "compound": r.compound, "lap_start": r.lap_start, "lap_end": r.lap_end} for r in rows]


def gap_over_time(db: OrmSession, session_id: int, driver_a: int, driver_b: int) -> list[dict]:
    """Cumulative race-time difference (A minus B) by lap, from lap times. Positive = A behind."""
    def times(d: int) -> dict[int, int]:
        return {l.lap_number: l.lap_time_ms for l in db.scalars(select(Lap).where(Lap.session_id == session_id, Lap.driver_id == d)).all() if l.lap_time_ms}

    ta, tb = times(driver_a), times(driver_b)
    common = sorted(set(ta) & set(tb))
    out, cum = [], 0
    for lap in common:
        cum += ta[lap] - tb[lap]
        out.append({"lap": lap, "gap_ms": cum, "gap_formatted": ("+" if cum >= 0 else "") + fmt_ms(cum) + "s"})
    return out


def build_comparison(db: OrmSession, session_id: int, driver_a: int, driver_b: int) -> dict[str, Any]:
    session = db.get(Session, session_id)
    if session is None:
        raise ValueError(f"session {session_id} not found")
    da, dbv = db.get(Driver, driver_a), db.get(Driver, driver_b)
    if da is None or dbv is None:
        raise ValueError("driver not found")
    return {
        "session_id": session_id,
        "session_type": session.session_type,
        "driver_a": {"id": da.id, "name": da.full_name, "team": da.team, "position_by_lap": _position_series(db, session_id, da.id), "stints": _stints(db, session_id, da.id)},
        "driver_b": {"id": dbv.id, "name": dbv.full_name, "team": dbv.team, "position_by_lap": _position_series(db, session_id, dbv.id), "stints": _stints(db, session_id, dbv.id)},
        "gap_over_time": gap_over_time(db, session_id, da.id, dbv.id),
    }


def _existing(db: OrmSession, session_id: int, a: int, b: int) -> ComparisonNarrative | None:
    return db.scalar(select(ComparisonNarrative).where(ComparisonNarrative.session_id == session_id, ComparisonNarrative.driver_a_id == a, ComparisonNarrative.driver_b_id == b))


def plan_comparison_narrative(db: OrmSession, session_id: int, driver_a: int, driver_b: int, *, force: bool = False) -> tuple[ComparisonNarrative | None, StoryJob | None]:
    a, b = sorted((driver_a, driver_b))
    in_a = build_driver_session_input(db, session_id, a)
    in_b = build_driver_session_input(db, session_id, b)
    # trim the per-driver docs to what matters for a comparison
    for doc in (in_a, in_b):
        doc.pop("pivotal_moments_session", None)
        doc.pop("nearby_rivals_strategy", None)
        doc.pop("race_control", None)
    gap = gap_over_time(db, session_id, a, b)
    sampled = gap[:: max(1, len(gap) // 15)] + ([gap[-1]] if gap and gap[-1] not in gap[:: max(1, len(gap) // 15)] else [])
    payload = {"meta": in_a["meta"], "driver_a": in_a, "driver_b": in_b, "cumulative_gap_a_minus_b_by_lap": sampled}
    h = stable_hash(payload)
    existing = _existing(db, session_id, a, b)
    if existing and existing.input_hash == h and not force:
        return existing, None

    def save(db: OrmSession, data: dict, model_used: str) -> ComparisonNarrative:
        row = _existing(db, session_id, a, b)
        if row is None:
            row = ComparisonNarrative(session_id=session_id, driver_a_id=a, driver_b_id=b, comparison_text="", generated_at=utcnow(), model_used=model_used, input_hash=h)
            db.add(row)
        row.comparison_text = data["comparison_text"].strip()
        row.generated_at = utcnow()
        row.model_used = model_used
        row.input_hash = h
        db.flush()
        return row

    user = "Comparison data (JSON):\n" + json.dumps(payload, indent=1, default=str)
    return existing, StoryJob(f"comparison session={session_id} {a} vs {b}", SYSTEM_COMPARISON, user, SCHEMA_COMPARISON, save)


def get_or_generate_comparison_narrative(db: OrmSession, session_id: int, driver_a: int, driver_b: int, *, force: bool = False) -> ComparisonNarrative:
    existing, job = plan_comparison_narrative(db, session_id, driver_a, driver_b, force=force)
    return existing if job is None else job.run(db)
