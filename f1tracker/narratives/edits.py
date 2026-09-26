"""Human edits layered over AI stories.

AI first: every story is written by Claude and stored in its own table. A human correction is a
Markdown file at ``stories/<story_key>.md``; it is synced into ``story_edits`` and shown *instead of*
the AI text, without touching the AI row. Deleting the file reverts to the AI version.

File format (front matter optional; headings pick the part being replaced)::

    ---
    ai_generated_at: 2026-03-08T10:12:44
    note: Wrong pit lap - he stopped on lap 21, not 23
    ---

    ## Recap

    Corrected recap text...

    ## Analysis

    Corrected strategy analysis (driver session stories only)...

If the AI story is regenerated later (its data changed), an edit whose ``ai_generated_at`` is older
than the new AI version is flagged ``edit_stale`` so it can be reviewed.
"""
from __future__ import annotations

import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session as OrmSession

from ..config import STORIES_DIR
from ..models import ComparisonNarrative, Driver, DriverSessionNarrative, DriverWeekendArc, Event, Season, SeasonArc, Session, StoryEdit
from ..util import utcnow

log = logging.getLogger(__name__)

SESSION_DIRS = {"FP1": "fp1", "FP2": "fp2", "FP3": "fp3", "SQ": "sprint-quali", "S": "sprint", "Q": "qualifying", "R": "race"}


def slug(text: str) -> str:
    """'Red Bull Racing' -> 'red-bull-racing'. Mirrored in frontend/src/lib/stories.ts."""
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


# ---------------------------------------------------------------------------
# Story keys: stable, human-readable paths under stories/ (without the .md)
# ---------------------------------------------------------------------------
def _event_dir(db: OrmSession, event: Event) -> str:
    season = db.get(Season, event.season_id)
    return f"{season.year}/{event.round:02d}-{slug(event.name)}"


def driver_session_key(db: OrmSession, session_id: int, driver_id: int) -> str:
    session = db.get(Session, session_id)
    event = db.get(Event, session.event_id)
    driver = db.get(Driver, driver_id)
    return f"{_event_dir(db, event)}/{SESSION_DIRS[session.session_type]}/{driver.driver_ref}"


def weekend_arc_key(db: OrmSession, event_id: int, driver_id: int) -> str:
    event = db.get(Event, event_id)
    driver = db.get(Driver, driver_id)
    return f"{_event_dir(db, event)}/weekend/{driver.driver_ref}"


def comparison_key(db: OrmSession, session_id: int, driver_a: int, driver_b: int) -> str:
    session = db.get(Session, session_id)
    event = db.get(Event, session.event_id)
    a, b = (db.get(Driver, d) for d in sorted((driver_a, driver_b)))
    return f"{_event_dir(db, event)}/{SESSION_DIRS[session.session_type]}/compare-{a.driver_ref}-vs-{b.driver_ref}"


def season_arc_key(db: OrmSession, season_id: int, subject_type: str, subject_id: str) -> str:
    season = db.get(Season, season_id)
    if subject_type == "driver":
        driver = db.get(Driver, int(subject_id))
        return f"{season.year}/season/driver-{driver.driver_ref}"
    return f"{season.year}/season/team-{slug(subject_id)}"


# ---------------------------------------------------------------------------
# Parsing + syncing edit files
# ---------------------------------------------------------------------------
def parse_edit_file(text: str) -> dict[str, Any]:
    """-> {text, analysis_text, note, based_on_generated_at}. Raises ValueError if there is no story text."""
    meta: dict[str, str] = {}
    body = text.replace("\r\n", "\n")
    if body.startswith("---\n"):
        end = body.find("\n---", 4)
        if end != -1:
            for line in body[4:end].splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    meta[k.strip().lower()] = v.strip().strip('"').strip("'")
            body = body[end + 4 :]
    body = re.sub(r"<!--.*?-->", "", body, flags=re.S)  # instructions left in the template

    main: list[str] = []
    analysis: list[str] | None = None
    current = main
    for line in body.split("\n"):
        m = re.match(r"^#{1,3}\s+(.*)$", line)
        if m:
            if m.group(1).strip().lower().startswith("analysis"):
                analysis = analysis if analysis is not None else []
                current = analysis
            else:
                current = main
            continue
        current.append(line)

    def clean(lines: list[str] | None) -> str | None:
        if lines is None:
            return None
        t = re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()
        return t or None

    main_text = clean(main)
    if not main_text:
        raise ValueError("edit file has no story text")
    based_on = None
    if meta.get("ai_generated_at"):
        try:
            based_on = datetime.fromisoformat(meta["ai_generated_at"].replace("Z", ""))
        except ValueError:
            based_on = None
    return {"text": main_text, "analysis_text": clean(analysis), "note": meta.get("note") or None, "based_on_generated_at": based_on}


def _edit_files(root: Path) -> dict[str, Path]:
    if not root.is_dir():
        return {}
    out = {}
    for p in root.rglob("*.md"):
        if p.name.lower() == "readme.md":
            continue
        out[p.relative_to(root).with_suffix("").as_posix()] = p
    return out


def sync_story_edits(db: OrmSession, root: Path = STORIES_DIR) -> dict[str, int]:
    """Make story_edits mirror the files in `root` exactly. Safe to run any time."""
    files = _edit_files(root)
    stats = {"edits": 0, "removed": 0, "invalid": 0}
    for key, path in files.items():
        try:
            parsed = parse_edit_file(path.read_text(encoding="utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            log.warning("ignoring story edit %s: %s", path, exc)
            stats["invalid"] += 1
            continue
        row = db.get(StoryEdit, key) or StoryEdit(story_key=key, text="", synced_at=utcnow())
        db.add(row)
        row.text = parsed["text"]
        row.analysis_text = parsed["analysis_text"]
        row.note = parsed["note"]
        row.based_on_generated_at = parsed["based_on_generated_at"]
        row.synced_at = utcnow()
        stats["edits"] += 1
    valid = set(files)
    stale = [k for k in db.scalars(select(StoryEdit.story_key)).all() if k not in valid]
    if stale:
        db.execute(delete(StoryEdit).where(StoryEdit.story_key.in_(stale)))
        stats["removed"] = len(stale)
    db.flush()
    return stats


_last_sync_stamp: tuple[int, float] | None = None


def sync_if_changed(db: OrmSession, root: Path = STORIES_DIR) -> None:
    """Cheap check for the local API: re-sync only when files were added/removed/modified."""
    global _last_sync_stamp
    files = _edit_files(root)
    stamp = (len(files), max((os.path.getmtime(p) for p in files.values()), default=0.0))
    if stamp != _last_sync_stamp:
        sync_story_edits(db, root)
        _last_sync_stamp = stamp


# ---------------------------------------------------------------------------
# Presenting a story = AI row + (optional) edit on top
# ---------------------------------------------------------------------------
def _row(obj: Any) -> dict[str, Any]:
    return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}


def edited_text(db: OrmSession, key: str, ai_text: str) -> str:
    edit = db.get(StoryEdit, key)
    return edit.text if edit else ai_text


def _present(db: OrmSession, row: Any, key: str, text_field: str, analysis_field: str | None = None) -> dict[str, Any]:
    out = _row(row)
    out["story_key"] = key
    out["edited"] = False
    edit = db.get(StoryEdit, key)
    if edit is not None:
        out["edited"] = True
        out["edit_note"] = edit.note
        out["edit_stale"] = bool(edit.based_on_generated_at and row.generated_at and row.generated_at > edit.based_on_generated_at)
        out["ai_" + text_field] = out[text_field]
        out[text_field] = edit.text
        if analysis_field and edit.analysis_text:
            out["ai_" + analysis_field] = out[analysis_field]
            out[analysis_field] = edit.analysis_text
    return out


def present_driver_session(db: OrmSession, n: DriverSessionNarrative) -> dict[str, Any]:
    return _present(db, n, driver_session_key(db, n.session_id, n.driver_id), "narrative_text", "strategy_analysis_text")


def present_weekend_arc(db: OrmSession, a: DriverWeekendArc) -> dict[str, Any]:
    return _present(db, a, weekend_arc_key(db, a.event_id, a.driver_id), "arc_text")


def present_season_arc(db: OrmSession, a: SeasonArc) -> dict[str, Any]:
    return _present(db, a, season_arc_key(db, a.season_id, a.subject_type, a.subject_id), "arc_text")


def present_comparison(db: OrmSession, c: ComparisonNarrative) -> dict[str, Any]:
    return _present(db, c, comparison_key(db, c.session_id, c.driver_a_id, c.driver_b_id), "comparison_text")
