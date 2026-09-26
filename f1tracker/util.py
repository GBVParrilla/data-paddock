from __future__ import annotations

import re
from datetime import datetime, timezone


def parse_iso_utc(text: str | None) -> datetime | None:
    """ISO-8601 (with offset) -> naive UTC datetime."""
    if not text:
        return None
    dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def fmt_ms(ms: int | None) -> str:
    """78518 -> '1:18.518'; 812 -> '0.812'."""
    if ms is None:
        return "n/a"
    sign = "-" if ms < 0 else ""
    ms = abs(ms)
    minutes, rem = divmod(ms, 60_000)
    seconds, millis = divmod(rem, 1000)
    if minutes:
        return f"{sign}{minutes}:{seconds:02d}.{millis:03d}"
    return f"{sign}{seconds}.{millis:03d}"
