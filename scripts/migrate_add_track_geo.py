#!/usr/bin/env python
"""One-off additive migration: add lat/lon (events) and geo/DRS columns (track_outlines).

Safe to re-run - only adds columns that are missing. Does not touch existing data.
"""
import sqlite3

import _common  # noqa: F401

from f1tracker.config import DATABASE_URL

assert DATABASE_URL.startswith("sqlite"), "this migration script is SQLite-only; Postgres users should ALTER TABLE by hand"
path = DATABASE_URL.split("sqlite:///")[1]

ADDS = {
    "events": [("lat", "FLOAT"), ("lon", "FLOAT")],
    "track_outlines": [("geo_points_json", "TEXT"), ("geo_bbox_json", "TEXT"), ("drs_zones_json", "TEXT NOT NULL DEFAULT '[]'")],
}

conn = sqlite3.connect(path)
cur = conn.cursor()
for table, cols in ADDS.items():
    existing = {row[1] for row in cur.execute(f"PRAGMA table_info({table})")}
    for name, decl in cols:
        if name in existing:
            print(f"{table}.{name} already present - skipping")
            continue
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {name} {decl}")
        print(f"added {table}.{name}")
conn.commit()
conn.close()

conn = sqlite3.connect(path)
cur = conn.cursor()
existing = {row[1] for row in cur.execute("PRAGMA table_info(track_outlines)")}
if "drs_zone_source" not in existing:
    cur.execute("ALTER TABLE track_outlines ADD COLUMN drs_zone_source TEXT NOT NULL DEFAULT 'none'")
    print("added track_outlines.drs_zone_source")
else:
    print("track_outlines.drs_zone_source already present - skipping")
conn.commit()
conn.close()

conn = sqlite3.connect(path)
cur = conn.cursor()
existing = {row[1] for row in cur.execute("PRAGMA table_info(track_outlines)")}
for name, decl in [("ref_distance_m_json", "TEXT"), ("ref_elapsed_ms_json", "TEXT"), ("turns_json", "TEXT NOT NULL DEFAULT '[]'")]:
    if name not in existing:
        cur.execute(f"ALTER TABLE track_outlines ADD COLUMN {name} {decl}")
        print(f"added track_outlines.{name}")
    else:
        print(f"track_outlines.{name} already present - skipping")
conn.commit()
conn.close()
