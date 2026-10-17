"""Central configuration. Secrets are read from the environment only."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# --- Storage -----------------------------------------------------------------
# Swap to Postgres by setting F1_DATABASE_URL=postgresql+psycopg://user:pw@host/db
DATABASE_URL = os.environ.get("F1_DATABASE_URL", f"sqlite:///{PROJECT_ROOT / 'data' / 'f1.db'}")

# --- Data sources ------------------------------------------------------------
JOLPICA_BASE_URL = "https://api.jolpi.ca/ergast/f1"
OPENF1_BASE_URL = "https://api.openf1.org/v1"

# Minimum seconds between requests to each API (basic politeness rate limiting).
JOLPICA_MIN_INTERVAL_S = 0.35
OPENF1_MIN_INTERVAL_S = 0.55
HTTP_MAX_RETRIES = 6
HTTP_TIMEOUT_S = 60

# --- Narrative generation ----------------------------------------------------
# One-line change to move models later.
NARRATIVE_MODEL = "claude-fable-5-1"
NARRATIVE_EFFORT = os.environ.get("F1_NARRATIVE_EFFORT", "high")
NARRATIVE_MAX_TOKENS = 4096
# Bump when prompts change so cached narratives regenerate.
PROMPT_VERSION = "1"

# --- Story pipeline + human edits ----------------------------------------------
# Stories are written by the pipeline right after a session is processed, stored in the DB,
# and only displayed afterwards. Human corrections live as Markdown files in STORIES_DIR.
STORIES_DIR = Path(os.environ.get("F1_STORIES_DIR", PROJECT_ROOT / "stories"))
# Which sessions get a per-driver story (practice included by default - the site shows every session).
STORY_SESSION_TYPES = tuple(os.environ.get("F1_STORY_SESSION_TYPES", "FP1,FP2,FP3,SQ,S,Q,R").split(","))
# Teammate head-to-heads are written for these session types.
COMPARISON_SESSION_TYPES = tuple(os.environ.get("F1_COMPARISON_SESSION_TYPES", "SQ,S,Q,R").split(","))
STORY_WORKERS = int(os.environ.get("F1_STORY_WORKERS", "4"))  # parallel Claude calls


def anthropic_api_key_present() -> bool:
    """True if ANTHROPIC_API_KEY is set. Never returns the key itself."""
    return bool(os.environ.get("ANTHROPIC_API_KEY"))
