"""
database.py — SQLite connection factory.
Uses /tmp/evrs.db on Render, project-local database/ otherwise.
"""

import sqlite3
import os

IS_RENDER = os.getenv("RENDER", "") == "true"

if IS_RENDER:
    DB_PATH = "/tmp/evrs.db"
else:
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    DB_PATH  = os.path.join(BASE_DIR, "database", "database.db")

# Ensure directory exists
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)


def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")   # Better concurrent read performance
    return conn