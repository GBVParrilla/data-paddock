#!/usr/bin/env python
"""Write the site's data as static JSON (for GitHub Pages). No Claude calls, no network.

  python scripts/export_static.py --out frontend/dist/data
"""
import argparse
from pathlib import Path

import _common  # noqa: F401

from f1tracker.db import db_session, init_db
from f1tracker.export import export_site_data
from f1tracker.logging_setup import setup_logging


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    setup_logging()
    init_db()
    with db_session() as db:
        export_site_data(db, args.out)


if __name__ == "__main__":
    main()
