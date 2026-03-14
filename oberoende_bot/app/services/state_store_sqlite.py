# oberoende_bot/app/services/state_store_sqlite.py
from __future__ import annotations
import sqlite3
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import Optional, Any, Dict

DB_PATH = "conversation_state.db"

# Si el usuario no escribe en X horas, se resetea el estado de conversación.
# Esto evita que alguien que vuelve días después se encuentre en medio de un
# lead flow o followup que ya no recuerda.
SESSION_TIMEOUT_HOURS = 4


@dataclass
class ConversationState:
    last_intent: Optional[str] = None
    last_topic: Optional[str] = None
    last_product: Optional[str] = None
    pending_followup: bool = False
    last_answer: Optional[str] = None
    last_question: Optional[str] = None
    turn_summary: Optional[str] = None
    lead_stage: Optional[str] = None          # await_model | await_district | await_payment
    lead_model: Optional[str] = None
    lead_district: Optional[str] = None
    lead_payment: Optional[str] = None
    last_activity: Optional[str] = None       # ISO timestamp del último mensaje


def init_state_db() -> None:
    conn = sqlite3.connect(DB_PATH, timeout=10)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS conversation_state (
            user_id          TEXT PRIMARY KEY,
            last_intent      TEXT,
            last_topic       TEXT,
            last_product     TEXT,
            pending_followup INTEGER,
            last_answer      TEXT,
            last_question    TEXT,
            turn_summary     TEXT,
            lead_stage       TEXT,
            lead_model       TEXT,
            lead_district    TEXT,
            lead_payment     TEXT,
            last_activity    TEXT
        )
        """
    )
    # Migración segura: agrega la columna si la tabla ya existía sin ella.
    # ALTER TABLE ignora el error si la columna ya existe (IGNORE).
    try:
        cur.execute(
            "ALTER TABLE conversation_state ADD COLUMN last_activity TEXT"
        )
    except sqlite3.OperationalError:
        pass  # columna ya existe, no hacer nada

    conn.commit()
    conn.close()


def _row_to_state(row) -> ConversationState:
    return ConversationState(
        last_intent=row[0],
        last_topic=row[1],
        last_product=row[2],
        pending_followup=bool(row[3]),
        last_answer=row[4],
        last_question=row[5],
        turn_summary=row[6],
        lead_stage=row[7],
        lead_model=row[8],
        lead_district=row[9],
        lead_payment=row[10],
        last_activity=row[11] if len(row) > 11 else None,
    )


def get_state(user_id: str) -> ConversationState:
    conn = sqlite3.connect(DB_PATH, timeout=10)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT last_intent, last_topic, last_product, pending_followup,
               last_answer, last_question, turn_summary,
               lead_stage, lead_model, lead_district, lead_payment,
               last_activity
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
            (user_id, last_intent, last_topic, last_product, pending_followup,
             last_answer, last_question, turn_summary,
             lead_stage, lead_model, lead_district, lead_payment, last_activity)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                st.last_intent,
                st.last_topic,
                st.last_product,
                int(st.pending_followup),
                st.last_answer,
                st.last_question,
                st.turn_summary,
                st.lead_stage,
                st.lead_model,
                st.lead_district,
                st.lead_payment,
                st.last_activity,
            ),
        )
        conn.commit()
        conn.close()
        return st

    conn.close()
    return _row_to_state(row)


def update_state(user_id: str, **kwargs: Any) -> ConversationState:
    """
    Actualiza solo campos conocidos del estado.
    Siempre actualiza last_activity al momento actual.
    """
    st = get_state(user_id)
    for k, v in kwargs.items():
        if hasattr(st, k):
            setattr(st, k, v)

    # Siempre pisamos last_activity con el timestamp actual
    st.last_activity = datetime.utcnow().isoformat()

    conn = sqlite3.connect(DB_PATH, timeout=10)
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE conversation_state
        SET last_intent      = ?,
            last_topic       = ?,
            last_product     = ?,
            pending_followup = ?,
            last_answer      = ?,
            last_question    = ?,
            turn_summary     = ?,
            lead_stage       = ?,
            lead_model       = ?,
            lead_district    = ?,
            lead_payment     = ?,
            last_activity    = ?
        WHERE user_id = ?
        """,
        (
            st.last_intent,
            st.last_topic,
            st.last_product,
            int(st.pending_followup),
            st.last_answer,
            st.last_question,
            st.turn_summary,
            st.lead_stage,
            st.lead_model,
            st.lead_district,
            st.lead_payment,
            st.last_activity,
            user_id,
        ),
    )
    conn.commit()
    conn.close()
    return st


def reset_if_expired(user_id: str) -> bool:
    """
    Comprueba si la sesión del usuario ha expirado (sin actividad por
    SESSION_TIMEOUT_HOURS horas). Si expiró, resetea todos los campos
    de contexto/followup/lead y devuelve True para que el nodo pueda
    informarlo o mostrar el menú de bienvenida.

    No toca last_intent ni last_topic para mantener algo de contexto
    histórico, pero sí limpia todo lo que podría dejar al usuario
    atascado en un flujo antiguo.
    """
    st = get_state(user_id)

    if not st.last_activity:
        return False  # usuario nuevo, no hay nada que resetear

    try:
        last = datetime.fromisoformat(st.last_activity)
    except ValueError:
        return False

    elapsed = datetime.utcnow() - last
    if elapsed < timedelta(hours=SESSION_TIMEOUT_HOURS):
        return False  # sesión todavía activa

    # Sesión expirada → limpiar estado de flujo
    print(f"⏱️ Sesión expirada para {user_id} (último mensaje hace {elapsed}). Reseteando.")
    update_state(
        user_id,
        pending_followup=False,
        lead_stage=None,
        lead_model=None,
        lead_district=None,
        lead_payment=None,
        last_answer=None,
        last_question=None,
        turn_summary=None,
    )
    return True


def state_dict(user_id: str) -> Dict[str, Any]:
    return asdict(get_state(user_id))