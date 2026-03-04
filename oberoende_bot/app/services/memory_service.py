# oberoende_bot/app/services/memory_service.py
import sqlite3
from datetime import datetime
from typing import List

from langchain_core.messages import HumanMessage, AIMessage, BaseMessage

DB_PATH = "memory.db"


def init_memory_db() -> None:
    conn = sqlite3.connect(DB_PATH, timeout=10)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            role TEXT,
            message TEXT,
            timestamp TEXT
        )
    """)
    conn.commit()
    conn.close()


def _save_message(user_id: str, role: str, message: str) -> None:
    conn = sqlite3.connect(DB_PATH, timeout=10)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO conversations (user_id, role, message, timestamp)
        VALUES (?, ?, ?, ?)
    """, (user_id, role, message, datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()


def add_user_message(user_id: str, message: str) -> None:
    _save_message(user_id, "user", message)


def add_ai_message(user_id: str, message: str) -> None:
    _save_message(user_id, "assistant", message)


def get_history(user_id: str, limit: int = 12) -> List[BaseMessage]:
    """
    Devuelve historial como mensajes LangChain, en orden cronológico.
    limit=12 suele ir bien (6 turnos ida/vuelta) para costos.
    """
    conn = sqlite3.connect(DB_PATH, timeout=10)
    cur = conn.cursor()
    cur.execute("""
        SELECT role, message
        FROM conversations
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT ?
    """, (user_id, limit))
    rows = cur.fetchall()
    conn.close()

    rows.reverse()

    out: List[BaseMessage] = []
    for role, msg in rows:
        if role in ("user", "human"):
            out.append(HumanMessage(content=msg))
        else:
            out.append(AIMessage(content=msg))
    return out