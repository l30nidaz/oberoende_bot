# obebot/app/services/state_store_sqlite.py
from __future__ import annotations
import sqlite3
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import Optional, Any, Dict

DB_PATH = "conversation_state.db"

# Si el usuario no escribe en X horas, se resetea el estado de conversación.
# Evita que alguien que vuelve días después quede atascado en un flujo antiguo.
SESSION_TIMEOUT_HOURS = 4


@dataclass
class ConversationState:
    last_intent:      Optional[str] = None
    last_topic:       Optional[str] = None
    pending_followup: bool          = False
    last_answer:      Optional[str] = None
    last_question:    Optional[str] = None
    last_activity:    Optional[str] = None   # ISO timestamp del último mensaje

    # ── Flujo de citas ────────────────────────────────────────────────────────
    # appt_stage:
    #   await_service  → esperando que el usuario diga qué servicio necesita
    #   await_date     → esperando fecha
    #   await_time     → esperando hora (tras mostrar slots disponibles)
    #   await_confirm  → esperando confirmación (sí/no)
    #   await_cancel   → esperando nombre/ID para cancelar
    appt_stage:    Optional[str] = None
    appt_service:  Optional[str] = None   # servicio elegido
    appt_date:     Optional[str] = None   # fecha en texto normalizado
    appt_time:     Optional[str] = None   # hora elegida "HH:MM"
    appt_event_id: Optional[str] = None   # ID del evento en Google Calendar


def init_state_db() -> None:
    conn = sqlite3.connect(DB_PATH, timeout=10)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS conversation_state (
            user_id          TEXT PRIMARY KEY,
            last_intent      TEXT,
            last_topic       TEXT,
            pending_followup INTEGER DEFAULT 0,
            last_answer      TEXT,
            last_question    TEXT,
            last_activity    TEXT,
            appt_stage       TEXT,
            appt_service     TEXT,
            appt_date        TEXT,
            appt_time        TEXT,
            appt_event_id    TEXT
        )
        """
    )

    # Migraciones seguras: añade columnas si la tabla ya existía sin ellas.
    _safe_add_columns(cur, "conversation_state", {
        "last_activity": "TEXT",
        "appt_stage":    "TEXT",
        "appt_service":  "TEXT",
        "appt_date":     "TEXT",
        "appt_time":     "TEXT",
        "appt_event_id": "TEXT",
    })

    conn.commit()
    conn.close()


def _safe_add_columns(cur, table: str, columns: dict[str, str]) -> None:
    """Añade columnas que no existen todavía. Ignora el error si ya existen."""
    for col, col_type in columns.items():
        try:
            cur.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}")
        except Exception:
            pass


def _row_to_state(row) -> ConversationState:
    return ConversationState(
        last_intent=row[0],
        last_topic=row[1],
        pending_followup=bool(row[2]),
        last_answer=row[3],
        last_question=row[4],
        last_activity=row[5],
        appt_stage=row[6],
        appt_service=row[7],
        appt_date=row[8],
        appt_time=row[9],
        appt_event_id=row[10],
    )


def get_state(user_id: str) -> ConversationState:
    conn = sqlite3.connect(DB_PATH, timeout=10)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT last_intent, last_topic, pending_followup,
               last_answer, last_question, last_activity,
               appt_stage, appt_service, appt_date, appt_time, appt_event_id
        FROM conversation_state
        WHERE user_id = ?
        """,
        (user_id,),
    )
    row = cur.fetchone()

    if row is None:
        st = ConversationState()
        cur.execute(
            """
            INSERT INTO conversation_state
            (user_id, last_intent, last_topic, pending_followup,
             last_answer, last_question, last_activity,
             appt_stage, appt_service, appt_date, appt_time, appt_event_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                st.last_intent, st.last_topic, int(st.pending_followup),
                st.last_answer, st.last_question, st.last_activity,
                st.appt_stage, st.appt_service, st.appt_date,
                st.appt_time, st.appt_event_id,
            ),
        )
        conn.commit()
        conn.close()
        return st

    conn.close()
    return _row_to_state(row)


def update_state(user_id: str, **kwargs: Any) -> ConversationState:
    """
    Actualiza solo los campos conocidos del estado.
    Siempre actualiza last_activity al momento actual.
    """
    st = get_state(user_id)
    for k, v in kwargs.items():
        if hasattr(st, k):
            setattr(st, k, v)

    st.last_activity = datetime.utcnow().isoformat()

    conn = sqlite3.connect(DB_PATH, timeout=10)
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE conversation_state
        SET last_intent      = ?,
            last_topic       = ?,
            pending_followup = ?,
            last_answer      = ?,
            last_question    = ?,
            last_activity    = ?,
            appt_stage       = ?,
            appt_service     = ?,
            appt_date        = ?,
            appt_time        = ?,
            appt_event_id    = ?
        WHERE user_id = ?
        """,
        (
            st.last_intent, st.last_topic, int(st.pending_followup),
            st.last_answer, st.last_question, st.last_activity,
            st.appt_stage, st.appt_service, st.appt_date,
            st.appt_time, st.appt_event_id,
            user_id,
        ),
    )
    conn.commit()
    conn.close()
    return st


def reset_if_expired(user_id: str) -> bool:
    """
    Si la sesión expiró (sin actividad por SESSION_TIMEOUT_HOURS horas),
    resetea todos los campos de flujo y devuelve True.
    """
    st = get_state(user_id)

    if not st.last_activity:
        return False

    try:
        last = datetime.fromisoformat(st.last_activity)
    except ValueError:
        return False

    elapsed = datetime.utcnow() - last
    if elapsed < timedelta(hours=SESSION_TIMEOUT_HOURS):
        return False

    print(f"⏱️ Sesión expirada para {user_id} (último mensaje hace {elapsed}). Reseteando.")
    update_state(
        user_id,
        pending_followup=False,
        appt_stage=None,
        appt_service=None,
        appt_date=None,
        appt_time=None,
        appt_event_id=None,
    )
    return True


def state_dict(user_id: str) -> Dict[str, Any]:
    return asdict(get_state(user_id))