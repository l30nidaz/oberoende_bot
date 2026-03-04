# oberoende_bot/app/services/state_store_sqlite.py
from __future__ import annotations
import sqlite3
from dataclasses import dataclass, asdict
from typing import Optional, Any, Dict

DB_PATH = "conversation_state.db"


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

def init_state_db() -> None:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS conversation_state (
            user_id TEXT PRIMARY KEY,
            last_intent TEXT,
            last_topic TEXT,
            last_product TEXT,
            pending_followup INTEGER,
            last_answer TEXT,
            last_question TEXT,
            turn_summary TEXT,
            lead_stage TEXT,
            lead_model TEXT,
            lead_district TEXT,
            lead_payment TEXT
        )
        """
    )
    conn.commit()
    conn.close()


def _row_to_state(row) -> ConversationState:
    # row: (last_intent, last_topic, last_product, pending_followup, last_answer, last_question, turn_summary)
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
    )


def get_state(user_id: str) -> ConversationState:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT last_intent, last_topic, last_product, pending_followup, last_answer, last_question, turn_summary, lead_stage, lead_model, lead_district, lead_payment
        FROM conversation_state
        WHERE user_id = ?
        """,
        (user_id,),
    )
    row = cur.fetchone()

    if row is None:
        # Insert default state
        st = ConversationState()
        cur.execute(
            """
            INSERT INTO conversation_state
            (user_id, last_intent, last_topic, last_product, pending_followup, last_answer, last_question, turn_summary, lead_stage, lead_model, lead_district, lead_payment)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
    """
    st = get_state(user_id)
    for k, v in kwargs.items():
        if hasattr(st, k):
            setattr(st, k, v)

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE conversation_state
        SET last_intent = ?,
            last_topic = ?,
            last_product = ?,
            pending_followup = ?,
            last_answer = ?,
            last_question = ?,
            turn_summary = ?,
            lead_stage = ?,
            lead_model = ?,
            lead_district = ?,
            lead_payment = ?
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
            user_id,
        ),
    )
    conn.commit()
    conn.close()
    return st


def state_dict(user_id: str) -> Dict[str, Any]:
    return asdict(get_state(user_id))