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
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id   TEXT    NOT NULL,
            role      TEXT    NOT NULL,
            message   TEXT    NOT NULL,
            timestamp TEXT    NOT NULL
        )
    """)
    # Índice en user_id: hace que SELECT … WHERE user_id = ? sea O(log n)
    # en vez de un full-table-scan que crece con cada mensaje.
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_conversations_user_id
        ON conversations (user_id)
    """)
    conn.commit()
    conn.close()


def _save_message(user_id: str, role: str, message: str) -> None:
    conn = sqlite3.connect(DB_PATH, timeout=10)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO conversations (user_id, role, message, timestamp)
        VALUES (?, ?, ?, ?)
        """,
        (user_id, role, message, datetime.utcnow().isoformat()),
    )
    conn.commit()
    conn.close()


def add_user_message(user_id: str, message: str) -> None:
    _save_message(user_id, "user", message)


def add_ai_message(user_id: str, message: str) -> None:
    _save_message(user_id, "assistant", message)


def get_history(user_id: str, limit: int = 12) -> List[BaseMessage]:
    """
    Devuelve el historial como mensajes LangChain en orden cronológico.
    limit=12 cubre 6 turnos ida/vuelta, buen equilibrio entre contexto y costo.
    """
    conn = sqlite3.connect(DB_PATH, timeout=10)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT role, message
        FROM conversations
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT ?
        """,
        (user_id, limit),
    )
    rows = cur.fetchall()
    conn.close()

    rows.reverse()  # cronológico ascendente

    out: List[BaseMessage] = []
    for role, msg in rows:
        if role in ("user", "human"):
            out.append(HumanMessage(content=msg))
        else:
            out.append(AIMessage(content=msg))
    return out