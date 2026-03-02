# oberoende_bot/app/services/user_profile_store_sqlite.py
from __future__ import annotations
import sqlite3
from typing import Optional

DB_PATH = "user_profiles.db"

def init_user_profile_db() -> None:
    conn = sqlite3.connect(DB_PATH, timeout=10)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS user_profile (
            user_id TEXT PRIMARY KEY,
            name TEXT
        )
    """)
    conn.commit()
    conn.close()

def get_name(user_id: str) -> Optional[str]:
    conn = sqlite3.connect(DB_PATH, timeout=10)
    cur = conn.cursor()
    cur.execute("SELECT name FROM user_profile WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None

def set_name(user_id: str, name: str) -> None:
    name = name.strip()
    if not name:
        return
    conn = sqlite3.connect(DB_PATH, timeout=10)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO user_profile (user_id, name)
        VALUES (?, ?)
        ON CONFLICT(user_id) DO UPDATE SET name=excluded.name
    """, (user_id, name))
    conn.commit()
    conn.close()