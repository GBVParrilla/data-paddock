"""SQLAlchemy models: raw tables, derived analytics, narratives, pivotal moments."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

SESSION_TYPES = ("FP1", "FP2", "FP3", "SQ", "S", "Q", "R")
SESSION_STATUSES = ("upcoming", "live", "completed")
RACE_LIKE = ("R", "S")
QUALI_LIKE = ("Q", "SQ")
PRACTICE_LIKE = ("FP1", "FP2", "FP3")


class Base(DeclarativeBase):
    pass


# --------------------------------------------------------------------------
# Core / raw
# --------------------------------------------------------------------------
class Season(Base):
    __tablename__ = "seasons"
    id: Mapped[int] = mapped_column(primary_key=True)
    year: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (UniqueConstraint("season_id", "round"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    season_id: Mapped[int] = mapped_column(ForeignKey("seasons.id"), nullable=False)
    round: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    circuit_name: Mapped[str] = mapped_column(String(120))
    country: Mapped[str] = mapped_column(String(80))
    event_date: Mapped[datetime | None] = mapped_column(DateTime)  # race day (UTC)
    has_sprint: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    openf1_meeting_key: Mapped[int | None] = mapped_column(Integer, index=True)
    lat: Mapped[float | None] = mapped_column(Float)  # circuit reference point, from Jolpica
    lon: Mapped[float | None] = mapped_column(Float)


class Session(Base):
    __tablename__ = "sessions"
    __table_args__ = (UniqueConstraint("event_id", "session_type"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), nullable=False, index=True)
    session_type: Mapped[str] = mapped_column(String(4), nullable=False)  # FP1|FP2|FP3|SQ|S|Q|R
    start_time: Mapped[datetime | None] = mapped_column(DateTime)
    end_time: Mapped[datetime | None] = mapped_column(DateTime)
    # upcoming|live|completed. Only "completed" is used today; the others are
    # the seam for a future live-ingestion mode.
    status: Mapped[str] = mapped_column(String(12), default="upcoming", nullable=False)
    openf1_session_key: Mapped[int | None] = mapped_column(Integer, index=True)


class Driver(Base):
    __tablename__ = "drivers"
    id: Mapped[int] = mapped_column(primary_key=True)
    driver_ref: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)  # Jolpica driverId
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    code: Mapped[str | None] = mapped_column(String(3))
    team: Mapped[str | None] = mapped_column(String(80))
    number: Mapped[int | None] = mapped_column(Integer, index=True)


class Lap(Base):
    __tablename__ = "laps"
    __table_args__ = (UniqueConstraint("session_id", "driver_id", "lap_number"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"), nullable=False, index=True)
    driver_id: Mapped[int] = mapped_column(ForeignKey("drivers.id"), nullable=False, index=True)
    lap_number: Mapped[int] = mapped_column(Integer, nullable=False)
    lap_time_ms: Mapped[int | None] = mapped_column(Integer)
    sector_1_ms: Mapped[int | None] = mapped_column(Integer)
    sector_2_ms: Mapped[int | None] = mapped_column(Integer)
    sector_3_ms: Mapped[int | None] = mapped_column(Integer)
    top_speed_kph: Mapped[int | None] = mapped_column(Integer)
    compound: Mapped[str | None] = mapped_column(String(16))
    tyre_life: Mapped[int | None] = mapped_column(Integer)
    is_pit_lap: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    position: Mapped[int | None] = mapped_column(Integer)
    lap_start_time: Mapped[datetime | None] = mapped_column(DateTime)


class Stint(Base):
    __tablename__ = "stints"
    __table_args__ = (UniqueConstraint("session_id", "driver_id", "stint_number"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"), nullable=False, index=True)
    driver_id: Mapped[int] = mapped_column(ForeignKey("drivers.id"), nullable=False)
    stint_number: Mapped[int] = mapped_column(Integer, nullable=False)
    compound: Mapped[str | None] = mapped_column(String(16))
    lap_start: Mapped[int | None] = mapped_column(Integer)
    lap_end: Mapped[int | None] = mapped_column(Integer)
    tyre_life_start: Mapped[int | None] = mapped_column(Integer)


class PitStop(Base):
    __tablename__ = "pit_stops"
    __table_args__ = (UniqueConstraint("session_id", "driver_id", "lap_number"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"), nullable=False, index=True)
    driver_id: Mapped[int] = mapped_column(ForeignKey("drivers.id"), nullable=False)
    lap_number: Mapped[int] = mapped_column(Integer, nullable=False)  # in-lap: "pitted at end of lap N"
    duration_ms: Mapped[int | None] = mapped_column(Integer)  # stationary time
    lane_duration_ms: Mapped[int | None] = mapped_column(Integer)  # pit-lane entry to exit


class RaceControl(Base):
    __tablename__ = "race_control"
    __table_args__ = (UniqueConstraint("session_id", "timestamp", "message"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"), nullable=False, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    lap_number: Mapped[int | None] = mapped_column(Integer)
    driver_id: Mapped[int | None] = mapped_column(ForeignKey("drivers.id"))
    category: Mapped[str | None] = mapped_column(String(32))
    message: Mapped[str] = mapped_column(Text, nullable=False)
    flag: Mapped[str | None] = mapped_column(String(32))
    scope: Mapped[str | None] = mapped_column(String(32))


class Weather(Base):
    __tablename__ = "weather"
    __table_args__ = (UniqueConstraint("session_id", "timestamp"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"), nullable=False, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    air_temp: Mapped[float | None] = mapped_column(Float)
    track_temp: Mapped[float | None] = mapped_column(Float)
    humidity: Mapped[float | None] = mapped_column(Float)
    wind_speed: Mapped[float | None] = mapped_column(Float)
    rainfall: Mapped[float | None] = mapped_column(Float)


class Result(Base):
    __tablename__ = "results"
    __table_args__ = (UniqueConstraint("session_id", "driver_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"), nullable=False, index=True)
    driver_id: Mapped[int] = mapped_column(ForeignKey("drivers.id"), nullable=False)
    position: Mapped[int | None] = mapped_column(Integer)  # classification order
    points: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str | None] = mapped_column(String(40))  # Finished / Retired / +1 Lap / Q1 ...
    grid_position: Mapped[int | None] = mapped_column(Integer)
    gap_to_leader_ms: Mapped[int | None] = mapped_column(Integer)
    laps_completed: Mapped[int | None] = mapped_column(Integer)
    # qualifying-type sessions only: best time per segment
    q1_ms: Mapped[int | None] = mapped_column(Integer)
    q2_ms: Mapped[int | None] = mapped_column(Integer)
    q3_ms: Mapped[int | None] = mapped_column(Integer)


class SessionIngestionState(Base):
    """Per-session bookkeeping so full-season runs are resumable."""

    __tablename__ = "session_ingestion_state"
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"), primary_key=True)
    results_done: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    details_done: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    transforms_done: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    results_at: Mapped[datetime | None] = mapped_column(DateTime)
    details_at: Mapped[datetime | None] = mapped_column(DateTime)
    transforms_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_error: Mapped[str | None] = mapped_column(Text)


# --------------------------------------------------------------------------
# Headline (casual fan)
# --------------------------------------------------------------------------
class HeadlinePractice(Base):
    __tablename__ = "headline_practice"
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"), primary_key=True)
    driver_id: Mapped[int] = mapped_column(ForeignKey("drivers.id"), primary_key=True)
    fastest_lap_ms: Mapped[int | None] = mapped_column(Integer)
    gap_to_fastest_ms: Mapped[int | None] = mapped_column(Integer)
    rank: Mapped[int | None] = mapped_column(Integer)


class HeadlineQualifying(Base):
    __tablename__ = "headline_qualifying"
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"), primary_key=True)
    driver_id: Mapped[int] = mapped_column(ForeignKey("drivers.id"), primary_key=True)
    position: Mapped[int | None] = mapped_column(Integer)
    gap_to_pole_ms: Mapped[int | None] = mapped_column(Integer)
    eliminated_in: Mapped[str | None] = mapped_column(String(2))  # Q1|Q2|Q3|None


class HeadlineRace(Base):
    __tablename__ = "headline_race"
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"), primary_key=True)
    driver_id: Mapped[int] = mapped_column(ForeignKey("drivers.id"), primary_key=True)
    finish_position: Mapped[int | None] = mapped_column(Integer)
    grid_position: Mapped[int | None] = mapped_column(Integer)
    positions_gained: Mapped[int | None] = mapped_column(Integer)
    points: Mapped[float] = mapped_column(Float, default=0.0)
    pit_stop_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str | None] = mapped_column(String(40))


class HeadlineSessionSummary(Base):
    __tablename__ = "headline_session_summary"
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"), primary_key=True)
    summary_text: Mapped[str] = mapped_column(Text, nullable=False)


# --------------------------------------------------------------------------
# Detail (avid fan)
# --------------------------------------------------------------------------
class DetailLongRunPace(Base):
    __tablename__ = "detail_long_run_pace"
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"), primary_key=True)
    driver_id: Mapped[int] = mapped_column(ForeignKey("drivers.id"), primary_key=True)
    compound: Mapped[str] = mapped_column(String(16), primary_key=True)
    avg_lap_time_ms: Mapped[int | None] = mapped_column(Integer)
    lap_count: Mapped[int] = mapped_column(Integer, default=0)


class DetailQualifyingSegment(Base):
    __tablename__ = "detail_qualifying_segments"
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"), primary_key=True)
    driver_id: Mapped[int] = mapped_column(ForeignKey("drivers.id"), primary_key=True)
    segment: Mapped[str] = mapped_column(String(2), primary_key=True)  # Q1|Q2|Q3
    best_lap_ms: Mapped[int | None] = mapped_column(Integer)
    gap_to_segment_leader_ms: Mapped[int | None] = mapped_column(Integer)


class DetailStintTimeline(Base):
    __tablename__ = "detail_stint_timeline"
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"), primary_key=True)
    driver_id: Mapped[int] = mapped_column(ForeignKey("drivers.id"), primary_key=True)
    stint_number: Mapped[int] = mapped_column(Integer, primary_key=True)
    compound: Mapped[str | None] = mapped_column(String(16))
    lap_start: Mapped[int | None] = mapped_column(Integer)
    lap_end: Mapped[int | None] = mapped_column(Integer)


class DetailDegradation(Base):
    __tablename__ = "detail_degradation"
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"), primary_key=True)
    driver_id: Mapped[int] = mapped_column(ForeignKey("drivers.id"), primary_key=True)
    stint_number: Mapped[int] = mapped_column(Integer, primary_key=True)
    lap_number_in_stint: Mapped[int] = mapped_column(Integer, primary_key=True)
    lap_time_ms: Mapped[int | None] = mapped_column(Integer)


class DetailPositionByLap(Base):
    __tablename__ = "detail_position_by_lap"
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"), primary_key=True)
    driver_id: Mapped[int] = mapped_column(ForeignKey("drivers.id"), primary_key=True)
    lap_number: Mapped[int] = mapped_column(Integer, primary_key=True)
    position: Mapped[int | None] = mapped_column(Integer)


class DetailSectorDelta(Base):
    __tablename__ = "detail_sector_deltas"
    __table_args__ = (
        UniqueConstraint("session_id", "driver_id", "lap_number", "sector"),
        Index("ix_sector_deltas_session_driver", "session_id", "driver_id"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"), nullable=False)
    driver_id: Mapped[int] = mapped_column(ForeignKey("drivers.id"), nullable=False)
    lap_number: Mapped[int] = mapped_column(Integer, nullable=False)
    sector: Mapped[int] = mapped_column(Integer, nullable=False)  # 1|2|3
    driver_sector_ms: Mapped[int | None] = mapped_column(Integer)
    session_best_sector_ms: Mapped[int | None] = mapped_column(Integer)
    delta_ms: Mapped[int | None] = mapped_column(Integer)


# --------------------------------------------------------------------------
# Narratives (LLM) and pivotal moments (pure data)
# --------------------------------------------------------------------------
class DriverSessionNarrative(Base):
    __tablename__ = "driver_session_narratives"
    __table_args__ = (UniqueConstraint("session_id", "driver_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"), nullable=False, index=True)
    driver_id: Mapped[int] = mapped_column(ForeignKey("drivers.id"), nullable=False)
    session_type: Mapped[str] = mapped_column(String(4), nullable=False)
    narrative_text: Mapped[str] = mapped_column(Text, nullable=False)
    strategy_analysis_text: Mapped[str] = mapped_column(Text, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    model_used: Mapped[str] = mapped_column(String(60), nullable=False)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)


class DriverWeekendArc(Base):
    __tablename__ = "driver_weekend_arcs"
    __table_args__ = (UniqueConstraint("event_id", "driver_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), nullable=False, index=True)
    driver_id: Mapped[int] = mapped_column(ForeignKey("drivers.id"), nullable=False)
    arc_text: Mapped[str] = mapped_column(Text, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    model_used: Mapped[str] = mapped_column(String(60), nullable=False)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)


class SeasonArc(Base):
    __tablename__ = "season_arcs"
    __table_args__ = (UniqueConstraint("season_id", "subject_type", "subject_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    season_id: Mapped[int] = mapped_column(ForeignKey("seasons.id"), nullable=False, index=True)
    subject_type: Mapped[str] = mapped_column(String(8), nullable=False)  # driver|team
    subject_id: Mapped[str] = mapped_column(String(80), nullable=False)  # driver id (str) or team name
    through_round: Mapped[int] = mapped_column(Integer, nullable=False)
    arc_text: Mapped[str] = mapped_column(Text, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    model_used: Mapped[str] = mapped_column(String(60), nullable=False)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)


class ComparisonNarrative(Base):
    __tablename__ = "comparison_narratives"
    __table_args__ = (UniqueConstraint("session_id", "driver_a_id", "driver_b_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"), nullable=False, index=True)
    driver_a_id: Mapped[int] = mapped_column(ForeignKey("drivers.id"), nullable=False)
    driver_b_id: Mapped[int] = mapped_column(ForeignKey("drivers.id"), nullable=False)
    comparison_text: Mapped[str] = mapped_column(Text, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    model_used: Mapped[str] = mapped_column(String(60), nullable=False)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)


class PivotalMoment(Base):
    __tablename__ = "pivotal_moments"
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"), nullable=False, index=True)
    lap_number: Mapped[int | None] = mapped_column(Integer)
    driver_id: Mapped[int | None] = mapped_column(ForeignKey("drivers.id"))
    moment_type: Mapped[str] = mapped_column(String(20), nullable=False)
    magnitude_score: Mapped[float] = mapped_column(Float, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)


class TrackOutline(Base):
    """Normalized track outline derived from one clean lap of OpenF1 location telemetry."""

    __tablename__ = "track_outlines"
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), primary_key=True)
    points_json: Mapped[str] = mapped_column(Text, nullable=False)  # [[x, y], ...] in a 0-1000 box
    sector_1_end_index: Mapped[int] = mapped_column(Integer, nullable=False)
    sector_2_end_index: Mapped[int] = mapped_column(Integer, nullable=False)
    source_session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"), nullable=False)
    source_driver_id: Mapped[int] = mapped_column(ForeignKey("drivers.id"), nullable=False)
    source_lap_number: Mapped[int] = mapped_column(Integer, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    # Geo-projected version for the satellite overlay (nullable until the event's lat/lon is backfilled).
    geo_points_json: Mapped[str | None] = mapped_column(Text)
    geo_bbox_json: Mapped[str | None] = mapped_column(Text)  # {south, west, north, east}
    drs_zones_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")  # [[start_idx, end_idx], ...]
    drs_zone_source: Mapped[str] = mapped_column(String(20), nullable=False, default="none")  # telemetry | estimated_throttle | none
    # Reference-lap geometry, used on demand to compute another driver's turn-by-turn time deltas.
    ref_distance_m_json: Mapped[str | None] = mapped_column(Text)  # cumulative meters, parallel to points/geo_points
    ref_elapsed_ms_json: Mapped[str | None] = mapped_column(Text)  # ms since lap start, parallel to points/geo_points
    turns_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")  # [{number, index, distance_m, apex_speed_kph}, ...]


class TurnDeltaCache(Base):
    """Precomputed turn-by-turn deltas (they need OpenF1 telemetry, so they're fetched once, not per request)."""

    __tablename__ = "turn_delta_cache"
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"), primary_key=True)
    driver_id: Mapped[int] = mapped_column(ForeignKey("drivers.id"), primary_key=True)
    payload_json: Mapped[str | None] = mapped_column(Text)  # compute_turn_deltas() output; null when it failed
    error: Mapped[str | None] = mapped_column(Text)  # why it couldn't be computed (not retried unless forced)
    computed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class StoryEdit(Base):
    """A human correction of an AI story, synced from stories/<story_key>.md (the file is the source of truth).

    The AI text stays untouched in its own table; the edit is layered on top when the story is shown.
    """

    __tablename__ = "story_edits"
    story_key: Mapped[str] = mapped_column(String(200), primary_key=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)  # replaces narrative/arc/comparison text
    analysis_text: Mapped[str | None] = mapped_column(Text)  # replaces strategy analysis (driver session stories only)
    note: Mapped[str | None] = mapped_column(Text)  # optional "why this was changed"
    based_on_generated_at: Mapped[datetime | None] = mapped_column(DateTime)  # AI version the edit corrected
    synced_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
