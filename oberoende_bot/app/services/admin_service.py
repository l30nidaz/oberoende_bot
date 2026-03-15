# oberoende_bot/app/services/admin_service.py
"""
Servicio de datos para el panel de administración.
Extrae métricas de las bases de datos SQLite existentes.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import sqlite3
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional


# ── Credenciales de admin por negocio ────────────────────────────────────────
# Se configuran en el .env como:
#   ADMIN_USER_SOLDEORO=admin
#   ADMIN_PASS_SOLDEORO=mipassword
# Si no están configuradas, el acceso queda bloqueado.

def get_admin_credentials(business_id: str) -> tuple[str | None, str | None]:
    key = business_id.upper()
    user = os.getenv(f"ADMIN_USER_{key}", "").strip() or None
    pwd  = os.getenv(f"ADMIN_PASS_{key}", "").strip() or None
    return user, pwd


def verify_admin_credentials(business_id: str, username: str, password: str) -> bool:
    expected_user, expected_pass = get_admin_credentials(business_id)
    if not expected_user or not expected_pass:
        return False
    # Comparación en tiempo constante para evitar timing attacks
    user_ok = hmac.compare_digest(expected_user.lower(), username.strip().lower())
    pass_ok  = hmac.compare_digest(expected_pass, password.strip())
    return user_ok and pass_ok


# ── Consultas de métricas ─────────────────────────────────────────────────────

def get_total_messages(business_id: str) -> Dict[str, int]:
    """
    Total de mensajes de usuario y del bot para el negocio.
    user_id en memory.db tiene formato 'business_id:phone' o solo 'phone'.
    """
    try:
        conn = sqlite3.connect("memory.db", timeout=10)
        cur = conn.cursor()
        # Mensajes del usuario
        cur.execute(
            """
            SELECT COUNT(*) FROM conversations
            WHERE role = 'user'
            AND (user_id LIKE ? OR user_id LIKE ?)
            """,
            (f"{business_id}:%", f"%:{business_id}:%"),
        )
        user_msgs = cur.fetchone()[0]

        # Mensajes del bot
        cur.execute(
            """
            SELECT COUNT(*) FROM conversations
            WHERE role = 'assistant'
            AND (user_id LIKE ? OR user_id LIKE ?)
            """,
            (f"{business_id}:%", f"%:{business_id}:%"),
        )
        bot_msgs = cur.fetchone()[0]
        conn.close()
        return {"user": user_msgs, "bot": bot_msgs, "total": user_msgs + bot_msgs}
    except Exception as e:
        print(f"⚠️ get_total_messages error: {e}")
        return {"user": 0, "bot": 0, "total": 0}


def get_unique_users(business_id: str) -> List[Dict[str, Any]]:
    """
    Lista de números únicos que han interactuado con el negocio,
    con el total de mensajes y la fecha del último mensaje.
    """
    try:
        conn = sqlite3.connect("memory.db", timeout=10)
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                user_id,
                COUNT(*) as total_msgs,
                MAX(timestamp) as last_seen
            FROM conversations
            WHERE role = 'user'
            AND (user_id LIKE ? OR user_id LIKE ?)
            GROUP BY user_id
            ORDER BY last_seen DESC
            """,
            (f"{business_id}:%", f"%:{business_id}:%"),
        )
        rows = cur.fetchall()
        conn.close()

        users = []
        for user_id, total_msgs, last_seen in rows:
            # Extraer solo el número del formato "business_id:phone"
            phone = user_id.split(":")[-1] if ":" in user_id else user_id
            # Formatear timestamp
            try:
                dt = datetime.fromisoformat(last_seen)
                last_seen_fmt = dt.strftime("%d/%m/%Y %H:%M")
            except Exception:
                last_seen_fmt = last_seen or "—"

            users.append({
                "phone": phone,
                "total_msgs": total_msgs,
                "last_seen": last_seen_fmt,
            })
        return users
    except Exception as e:
        print(f"⚠️ get_unique_users error: {e}")
        return []


def get_activity_by_day(business_id: str, days: int = 14) -> List[Dict[str, Any]]:
    """
    Mensajes de usuario agrupados por día para los últimos N días.
    Devuelve lista de {date, count} ordenada cronológicamente.
    """
    try:
        conn = sqlite3.connect("memory.db", timeout=10)
        cur = conn.cursor()
        since = (datetime.utcnow() - timedelta(days=days)).isoformat()
        cur.execute(
            """
            SELECT
                DATE(timestamp) as day,
                COUNT(*) as count
            FROM conversations
            WHERE role = 'user'
            AND timestamp >= ?
            AND (user_id LIKE ? OR user_id LIKE ?)
            GROUP BY day
            ORDER BY day ASC
            """,
            (since, f"{business_id}:%", f"%:{business_id}:%"),
        )
        rows = cur.fetchall()
        conn.close()

        # Rellenar días sin actividad con 0
        result = {}
        for i in range(days):
            d = (datetime.utcnow() - timedelta(days=days - 1 - i)).strftime("%Y-%m-%d")
            result[d] = 0
        for day, count in rows:
            if day in result:
                result[day] = count

        return [
            {"date": d, "label": datetime.strptime(d, "%Y-%m-%d").strftime("%d %b"), "count": c}
            for d, c in result.items()
        ]
    except Exception as e:
        print(f"⚠️ get_activity_by_day error: {e}")
        return []


def get_leads_count(business_id: str) -> int:
    """Total de leads capturados para el negocio."""
    try:
        conn = sqlite3.connect("leads.db", timeout=10)
        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM leads WHERE raw_message LIKE ?",
            (f"%{business_id}%",),
        )
        count = cur.fetchone()[0]
        conn.close()
        return count
    except Exception as e:
        print(f"⚠️ get_leads_count error: {e}")
        return 0


def get_dashboard_data(business_id: str) -> Dict[str, Any]:
    """Agrega todos los datos del dashboard en un solo dict."""
    from oberoende_bot.app.config.businesses import BUSINESSES
    config = BUSINESSES.get(business_id, {})

    return {
        "business_id": business_id,
        "business_name": config.get("name", business_id),
        "business_emoji": config.get("emoji", "🏢"),
        "messages": get_total_messages(business_id),
        "users": get_unique_users(business_id),
        "activity": get_activity_by_day(business_id, days=14),
        "leads_count": get_leads_count(business_id),
        "generated_at": datetime.utcnow().strftime("%d/%m/%Y %H:%M UTC"),
    }