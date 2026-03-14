# oberoende_bot/app/services/rate_limiter.py
"""
Rate limiting por usuario, sin Redis.

Usa una tabla SQLite con ventana deslizante de 60 segundos.
Si un usuario supera MAX_MESSAGES mensajes en esa ventana, el bot
ignora el mensaje sin procesar (no llama al LLM ni al grafo).

Valores por defecto conservadores para producción:
  - MAX_MESSAGES = 10 mensajes por ventana
  - WINDOW_SECONDS = 60 segundos

Ajusta según el volumen esperado de tus clientes.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta

DB_PATH = "rate_limit.db"
MAX_MESSAGES = 10       # máximo de mensajes permitidos en la ventana
WINDOW_SECONDS = 60     # tamaño de la ventana en segundos


def init_rate_limit_db() -> None:
    conn = sqlite3.connect(DB_PATH, timeout=10)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS rate_limit_events (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    TEXT    NOT NULL,
            created_at TEXT    NOT NULL
        )
    """)
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_rate_limit_user_id
        ON rate_limit_events (user_id)
    """)
    conn.commit()
    conn.close()


def is_rate_limited(user_id: str) -> bool:
    """
    Registra el evento del usuario y devuelve True si supera el límite.

    Flujo:
    1. Elimina eventos fuera de la ventana para ese usuario.
    2. Cuenta los eventos restantes dentro de la ventana.
    3. Si ya alcanzó el límite, devuelve True sin registrar el nuevo evento.
    4. Si no, registra el evento y devuelve False.
    """
    now = datetime.utcnow()
    window_start = (now - timedelta(seconds=WINDOW_SECONDS)).isoformat()
    now_iso = now.isoformat()

    conn = sqlite3.connect(DB_PATH, timeout=10)
    cur = conn.cursor()

    # Limpiar eventos viejos del usuario para mantener la tabla pequeña
    cur.execute(
        "DELETE FROM rate_limit_events WHERE user_id = ? AND created_at < ?",
        (user_id, window_start),
    )

    # Contar eventos actuales en la ventana
    cur.execute(
        "SELECT COUNT(*) FROM rate_limit_events WHERE user_id = ? AND created_at >= ?",
        (user_id, window_start),
    )
    count = cur.fetchone()[0]

    if count >= MAX_MESSAGES:
        conn.commit()
        conn.close()
        print(f"🚦 Rate limit alcanzado para usuario {user_id} ({count} msgs en {WINDOW_SECONDS}s)")
        return True

    # Registrar el nuevo evento
    cur.execute(
        "INSERT INTO rate_limit_events (user_id, created_at) VALUES (?, ?)",
        (user_id, now_iso),
    )
    conn.commit()
    conn.close()
    return False