from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session as OrmSession

from f1tracker.models import Base, Driver, DriverSessionNarrative, Event, Season, Session
from f1tracker.narratives.edits import driver_session_key, parse_edit_file, present_driver_session, slug, sync_story_edits


def test_parse_edit_file_sections_front_matter_and_comments():
    parsed = parse_edit_file(
        "---\nai_generated_at: 2026-03-08T10:00:00\nnote: fixed pit lap\n---\n\n<!-- instructions\n spanning lines -->\n"
        "## Recap\n\nLine one.\n\n\n\nLine two.\n\n## Analysis\n\nHedged take.\n"
    )
    assert parsed["text"] == "Line one.\n\nLine two."
    assert parsed["analysis_text"] == "Hedged take."
    assert parsed["note"] == "fixed pit lap"
    assert parsed["based_on_generated_at"] == datetime(2026, 3, 8, 10)


def test_parse_edit_file_plain_body_and_empty():
    parsed = parse_edit_file("Just a corrected arc.\n")
    assert parsed == {"text": "Just a corrected arc.", "analysis_text": None, "note": None, "based_on_generated_at": None}
    with pytest.raises(ValueError):
        parse_edit_file("---\nnote: x\n---\n## Recap\n\n")


def test_slug():
    assert slug("Red Bull Racing") == "red-bull-racing"
    assert slug("Haas F1 Team") == "haas-f1-team"


@pytest.fixture()
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with OrmSession(engine) as s:
        s.add_all([
            Season(id=1, year=2026),
            Event(id=1, season_id=1, round=1, name="Australian Grand Prix", circuit_name="Albert Park", country="Australia"),
            Session(id=5, event_id=1, session_type="R", status="completed"),
            Driver(id=1, driver_ref="leclerc", full_name="Charles Leclerc", team="Ferrari"),
        ])
        s.add(DriverSessionNarrative(id=1, session_id=5, driver_id=1, session_type="R", narrative_text="AI recap", strategy_analysis_text="AI analysis",
                                     generated_at=datetime(2026, 3, 8, 12), model_used="m", input_hash="h"))
        s.flush()
        yield s


def test_edit_overrides_ai_story_and_revert(db, tmp_path):
    n = db.get(DriverSessionNarrative, 1)
    key = driver_session_key(db, 5, 1)
    assert key == "2026/01-australian-grand-prix/race/leclerc"
    assert present_driver_session(db, n)["edited"] is False

    f = tmp_path / f"{key}.md"
    f.parent.mkdir(parents=True)
    f.write_text("---\nai_generated_at: 2026-03-08T11:00:00\n---\n## Recap\n\nHuman recap.\n")
    (tmp_path / "README.md").write_text("not a story")
    assert sync_story_edits(db, tmp_path) == {"edits": 1, "removed": 0, "invalid": 0}

    shown = present_driver_session(db, n)
    assert shown["narrative_text"] == "Human recap." and shown["ai_narrative_text"] == "AI recap"
    assert shown["strategy_analysis_text"] == "AI analysis"  # no Analysis section -> AI's kept
    assert shown["edited"] and shown["edit_stale"]  # AI version (12:00) is newer than the one corrected (11:00)
    assert n.narrative_text == "AI recap"  # the AI row itself is untouched

    f.unlink()
    assert sync_story_edits(db, tmp_path)["removed"] == 1
    assert present_driver_session(db, n)["narrative_text"] == "AI recap"
