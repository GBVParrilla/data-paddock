"""Rate-limited HTTP GET with retry/backoff. Shared by both API clients."""
from __future__ import annotations

import logging
import random
import threading
import time
from typing import Any

import requests

from ..config import HTTP_MAX_RETRIES, HTTP_TIMEOUT_S

log = logging.getLogger(__name__)

RETRY_STATUSES = {429, 500, 502, 503, 504}


class RateLimitedClient:
    def __init__(self, base_url: str, min_interval_s: float, name: str = "http"):
        self.base_url = base_url.rstrip("/")
        self.min_interval_s = min_interval_s
        self.name = name
        self._last_request_at = 0.0
        self._lock = threading.Lock()
        self._session = requests.Session()
        self._session.headers["User-Agent"] = "f1-tracker/0.1 (+historical ingestion)"

    def _throttle(self) -> None:
        with self._lock:
            wait = self.min_interval_s - (time.monotonic() - self._last_request_at)
            if wait > 0:
                time.sleep(wait)
            self._last_request_at = time.monotonic()

    def get_json(self, path: str, params: dict[str, Any] | None = None, *, empty_on_404: bool = False) -> Any:
        url = f"{self.base_url}/{path.lstrip('/')}"
        attempt = 0
        while True:
            attempt += 1
            self._throttle()
            try:
                resp = self._session.get(url, params=params, timeout=HTTP_TIMEOUT_S)
            except requests.RequestException as exc:
                if attempt >= HTTP_MAX_RETRIES:
                    raise
                delay = self._backoff(attempt)
                log.warning("%s: %s on %s (attempt %d) - retrying in %.1fs", self.name, exc, url, attempt, delay)
                time.sleep(delay)
                continue

            if resp.status_code == 404 and empty_on_404:
                return []
            if resp.status_code in RETRY_STATUSES:
                if attempt >= HTTP_MAX_RETRIES:
                    resp.raise_for_status()
                retry_after = resp.headers.get("Retry-After")
                delay = float(retry_after) if retry_after and retry_after.isdigit() else self._backoff(attempt)
                log.warning("%s: HTTP %s on %s (attempt %d) - retrying in %.1fs", self.name, resp.status_code, resp.url, attempt, delay)
                time.sleep(delay)
                continue
            resp.raise_for_status()
            return resp.json()

    @staticmethod
    def _backoff(attempt: int) -> float:
        return min(60.0, (2 ** attempt) + random.uniform(0, 1))
