"""
migrate_is_active.py — Add is_active to executives, companies,
trip_templates, and categories.

Run once with the app stopped:
    python migrate_is_active.py
"""

import os
import shutil
import sqlite3
import sys
from datetime import datetime

DB_PATH = "travel_planner.db"


def backup():
    if not os.path.exists(DB_PATH):
        print(f"No database at {DB_PATH}.")
        sys.exit(0)
    bak = f"{DB_PATH}.bak_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    shutil.copy2(DB_PATH, bak)
    print(f"💾 Backup: {bak}")


def has_col(c, table, col):
    c.execute(f"PRAGMA table_info({table})")
    return col in [r[1] for r in c.fetchall()]


def migrate():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    c = conn.cursor()

    additions = [
        ("executives", "is_active", "INTEGER DEFAULT 1"),
        ("companies", "is_active", "INTEGER DEFAULT 1"),
        ("trip_templates", "is_active", "INTEGER DEFAULT 1"),
        ("categories", "is_active", "INTEGER DEFAULT 1"),
    ]
    for table, col, decl in additions:
        if not has_col(c, table, col):
            c.execute(f"ALTER TABLE {table} ADD COLUMN {col} {decl}")
            print(f"✅ {table}.{col} added")
        else:
            print(f"•  {table}.{col} already exists")

    conn.commit()
    conn.close()
    print("Done. Restart Streamlit.")


if __name__ == "__main__":
    backup()
    migrate()
