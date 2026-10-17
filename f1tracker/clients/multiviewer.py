"""MultiViewer circuit API: the circuit metadata F1's own live timing map uses.

/circuits/{circuit_key}/{year} -> {rotation, corners[{number, trackPosition{x,y}}], x[], y[], ...}
x/y share OpenF1's location frame (decimeters), so `rotation` orients our own telemetry
outline exactly the way F1 draws the track, and `corners` are the official turn numbers.
"""
from __future__ import annotations

import functools
import logging
from typing import Any

from .http import RateLimitedClient

log = logging.getLogger(__name__)

_client = RateLimitedClient("https://api.multiviewer.app/api/v1", 0.5, name="multiviewer")


@functools.lru_cache(maxsize=64)
def fetch_circuit(circuit_key: int, year: int) -> dict[str, Any] | None:
    try:
        data = _client.get_json(f"circuits/{circuit_key}/{year}", empty_on_404=True)
    except Exception as exc:  # optional enrichment - never fail outline generation over it
        log.warning("multiviewer circuit %s/%s unavailable: %s", circuit_key, year, exc)
        return None
    return data if isinstance(data, dict) and "rotation" in data else None
