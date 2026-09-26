#!/usr/bin/env python
"""Run the API + built web UI. Port from PORT env (default 8000)."""
import os

import _common  # noqa: F401
import uvicorn

if __name__ == "__main__":
    uvicorn.run("f1tracker.api.main:app", host="127.0.0.1", port=int(os.environ.get("PORT", "8000")))
