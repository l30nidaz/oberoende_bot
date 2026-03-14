# oberoende_bot/app/services/message_id_store.py
"""
Deduplicación de mensajes entrantes.

Meta puede reenviar el mismo webhook más de una vez (reintentos por timeout,
errores de red, etc.). Este módulo guarda los message_id ya procesados y
permite descartar duplicados antes de invocar el grafo.

Los IDs se guardan con un TTL de 24 horas: pasado ese tiempo se limpian
automáticamente en cada llamada a init, para que la tabla no crezca
indefinidamente.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta

DB_PATH = "message_ids.db"
TTL_HOURS = 24


def init_message_id_db() -> None:
    conn = sqlite3.connect(DB_PATH, timeout=10)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS processed_message_ids (
            message_id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL
        )
    """)
    # Limpia registros vencidos para que la tabla no crezca sin límite
    cutoff = (datetime.utcnow() - timedelta(hours=TTL_HOURS)).isoformat()
    cur.execute(
        "DELETE FROM processed_message_ids WHERE created_at < ?",
        (cutoff,),
    )
    conn.commit()
    conn.close()


def is_duplicate(message_id: str) -> bool:
    """
    Devuelve True si el message_id ya fue procesado.
    Si no existe, lo registra y devuelve False.
    Operación atómica con INSERT OR IGNORE para evitar race conditions.
    """
    conn = sqlite3.connect(DB_PATH, timeout=10)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT OR IGNORE INTO processed_message_ids (message_id, created_at)
        VALUES (?, ?)
        """,
        (message_id, datetime.utcnow().isoformat()),
    )
    inserted = cur.rowcount  # 1 = nuevo, 0 = ya existía (duplicado)
    conn.commit()
    conn.close()
    return inserted == 0