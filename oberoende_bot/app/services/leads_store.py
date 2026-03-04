# oberoende_bot/app/services/leads_store.py
import sqlite3
from datetime import datetime
from typing import Optional

DB_PATH = "leads.db"


def init_leads_db() -> None:
    conn = sqlite3.connect(DB_PATH, timeout=10)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            channel TEXT NOT NULL,               -- whatsapp / instagram (futuro)
            name TEXT,
            product TEXT,
            district TEXT,
            payment_method TEXT,
            raw_message TEXT,
            status TEXT DEFAULT 'nuevo',
            created_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


def save_lead(
    *,
    user_id: str,
    channel: str,
    name: Optional[str] = None,
    product: Optional[str] = None,
    district: Optional[str] = None,
    payment_method: Optional[str] = None,
    raw_message: str,
) -> None:
    """
    Guarda un lead estructurado.

    NOTA: usar kwargs con * evita errores por posición y hace más claro el llamado.
    """
    conn = sqlite3.connect(DB_PATH, timeout=10)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO leads (
            user_id, channel, name, product, district, payment_method, raw_message, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            channel,
            (name or "").strip() or None,
            (product or "").strip() or None,
            (district or "").strip() or None,
            (payment_method or "").strip() or None,
            raw_message,
            datetime.utcnow().isoformat(),
        ),
    )
    conn.commit()
    conn.close()