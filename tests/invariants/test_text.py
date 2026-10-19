"""No machine text in anything a visitor reads (#2, #10)."""
from __future__ import annotations

import json
import re

from .conftest import DATA_DIR

# "None" only mid-sentence ("lap None"); "None of his sectors..." is English. Code tokens are
# case-sensitive; the model's leaked self-talk ("Note to reviewer") is matched in any case.
FORBIDDEN = re.compile(
    r"(?<![.!?:]\s)(?<!^)\bNone\b|\bnull\b|\bundefined\b|\bNaN\b|\[object|BAD_FORMAT|\{\}|```|\{\""
    r"|(?i:</?br\s*/?>|</?[a-z_]+_text>|note to reviewer|invalid trailing)"
)
# Keys holding text shown on the page (stories, moment descriptions, labels, reasons, names).
USER_FACING = re.compile(r"(text|description|label|reason|summary|headline|story|analysis|name|note|title)$", re.I)


def _walk(obj, path=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _walk(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _walk(v, f"{path}[{i}]")
    elif isinstance(obj, str):
        yield path, obj


def test_no_machine_text_in_user_facing_strings():
    bad = []
    for f in DATA_DIR.rglob("*.json"):
        data = json.loads(f.read_text(encoding="utf-8"))
        for path, s in _walk(data):
            key = path.rsplit(".", 1)[-1].split("[")[0]
            if USER_FACING.search(key) and FORBIDDEN.search(s):
                m = FORBIDDEN.search(s)
                bad.append(f"{f.relative_to(DATA_DIR)}{path}: ...{s[max(0, m.start() - 50): m.end() + 30]}...")
    assert not bad, f"{len(bad)} leaks, e.g.\n" + "\n".join(bad[:8])


def _driver_stories():
    for f in DATA_DIR.glob("sessions/*/drivers/*/narrative.json"):
        story = json.loads(f.read_text(encoding="utf-8"))
        if story.get("edited") or story.get("headline", "").startswith("Did not start"):
            continue  # an editor's correction is theirs; a DNS has nothing to judge
        yield f, story


def test_every_published_headline_is_a_verdict():
    """REVIEW_ROUND2 B2: a headline says what the result meant or why, not only "P10 from P14"."""
    from f1tracker.narratives.factcheck import check_headline

    bad = [f"{f.relative_to(DATA_DIR)}: {s['headline']}" for f, s in _driver_stories() if check_headline(s["headline"], {})]
    assert not bad, f"{len(bad)} result-only headlines, e.g.\n" + "\n".join(bad[:8])


def test_essential_stories_use_plain_words():
    """REVIEW_ROUND2 #40: no lap times and no "(-0.06s per lap)" notation for a new fan."""
    from f1tracker.narratives.factcheck import LAP_TIME, RAW

    bad = [f"{f.relative_to(DATA_DIR)}: {s['summary'][:90]}" for f, s in _driver_stories() if LAP_TIME.search(s.get("summary") or "") or RAW.search(s.get("summary") or "")]
    assert not bad, f"{len(bad)} essential stories with data notation, e.g.\n" + "\n".join(bad[:8])
