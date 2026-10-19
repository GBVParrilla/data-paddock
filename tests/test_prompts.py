"""The worked examples in the story prompt must pass the same fact-check every story does."""
import re

from f1tracker.narratives.examples import EXAMPLES
from f1tracker.narratives.factcheck import LIMITS, check_story
from f1tracker.narratives.prompts import SCHEMA_DRIVER_STORY, SYSTEM_DRIVER_STORY


def _names(obj) -> set[str]:
    found = set()
    for m in re.finditer(r"\b([A-Z][a-z]+(?: [A-Z][a-z]+)+)\b", str(obj)):
        found.add(m.group(1))
    return found


def test_worked_examples_pass_the_fact_check_and_stay_well_under_the_limits():
    for ex in EXAMPLES:
        sheet = {"meta": {"season": 2026, "session_type": "R"}, **ex["facts_excerpt"]}
        entrants = _names(ex["facts_excerpt"]) | {"Lewis Hamilton"}
        roster = {n.split(" ")[-1]: n for n in entrants}
        assert [str(v) for v in check_story(ex["story"], sheet, roster=roster, entrants=entrants)] == [], ex["who"]
        for section, limit in LIMITS.items():
            words = len(re.findall(r"[\w'’.-]+", ex["story"][section]))
            assert words <= limit * 0.8, f"{ex['who']} {section}: {words} words is too close to {limit}"


def test_schema_and_prompt_agree_on_the_sections():
    assert set(SCHEMA_DRIVER_STORY["required"]) >= set(LIMITS)
    for section in LIMITS:
        assert f"- {section}:" in SYSTEM_DRIVER_STORY
