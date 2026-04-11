# oberoende_bot/app/services/calendar_service.py
"""
Integración con Google Calendar usando una Service Account.

Funciones principales:
  - get_available_slots(calendar_id, credentials_path, date_str, duration_min, allowed_hours, allowed_days)
      → lista de horas libres ["09:00", "10:00", ...]

  - create_event(calendar_id, credentials_path, date_str, time_str, duration_min,
                 service, client_name, client_phone)
      → event_id (str) o None si falla

  - cancel_event(calendar_id, credentials_path, event_id)
      → True/False

  - find_event_by_phone(calendar_id, credentials_path, client_phone, days_ahead)
      → list[dict] con {event_id, summary, start}

Requisitos:
  pip install google-api-python-client google-auth

Configuración en el .env / businesses.py del negocio:
  calendar_id                  → correo del Google Calendar (ej. "negocio@gmail.com")
  calendar_credentials_path    → ruta al JSON de la Service Account
  appointment_duration_minutes → duración de cada cita en minutos
  appointment_hours            → ["09:00", "10:00", ...]  horarios ofrecidos
  appointment_days             → [0,1,2,3,4]  días permitidos (0=lunes…6=domingo)
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, date, time
from typing import Optional
from zoneinfo import ZoneInfo

# ── Zona horaria por defecto ──────────────────────────────────────────────────
# Cámbiala si tu negocio está en otra zona.
DEFAULT_TZ = os.getenv("CALENDAR_TIMEZONE", "America/Lima")


# =============================================================================
# Helpers de fecha
# =============================================================================

def _parse_date(date_str: str) -> Optional[date]:
    """
    Intenta parsear la cadena de fecha que escribió el usuario.
    Acepta varios formatos comunes:
      - "lunes 14", "el martes", "mañana", "14/04", "14-04", "2025-04-14"
    Devuelve un objeto date o None si no puede parsearlo.
    """
    import re
    from dateutil import parser as dateparser

    now = datetime.now(ZoneInfo(DEFAULT_TZ))
    text = date_str.strip().lower()

    # Palabras clave simples
    if text in {"hoy", "today"}:
        return now.date()
    if text in {"mañana", "tomorrow"}:
        return (now + timedelta(days=1)).date()
    if text in {"pasado mañana"}:
        return (now + timedelta(days=2)).date()

    # "el lunes", "lunes", etc.
    _DAYS_ES = {
        "lunes": 0, "martes": 1, "miércoles": 2, "miercoles": 2,
        "jueves": 3, "viernes": 4, "sábado": 5, "sabado": 5, "domingo": 6,
    }
    for name, wd in _DAYS_ES.items():
        if name in text:
            days_ahead = (wd - now.weekday()) % 7
            if days_ahead == 0:
                days_ahead = 7  # mismo día de la semana → próxima semana
            return (now + timedelta(days=days_ahead)).date()

    # Formatos numéricos: "14/04", "14-04", "14/04/2025"
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%d/%m", "%d-%m", "%Y-%m-%d"):
        try:
            parsed = datetime.strptime(text, fmt)
            # Si no tiene año, usar el actual (o siguiente si ya pasó)
            if fmt in ("%d/%m", "%d-%m"):
                parsed = parsed.replace(year=now.year)
                if parsed.date() < now.date():
                    parsed = parsed.replace(year=now.year + 1)
            return parsed.date()
        except ValueError:
            continue

    # Fallback: dateutil
    try:
        return dateparser.parse(date_str, dayfirst=True).date()
    except Exception:
        return None


def _parse_time(time_str: str) -> Optional[time]:
    """Parsea "09:00", "9am", "9 am", "14:30" → time object."""
    import re
    text = time_str.strip().lower()
    # HH:MM
    m = re.match(r"^(\d{1,2}):(\d{2})$", text)
    if m:
        return time(int(m.group(1)), int(m.group(2)))
    # 9am / 9 am / 9pm
    m = re.match(r"^(\d{1,2})\s*(am|pm)$", text)
    if m:
        h = int(m.group(1))
        if m.group(2) == "pm" and h != 12:
            h += 12
        if m.group(2) == "am" and h == 12:
            h = 0
        return time(h, 0)
    return None


# =============================================================================
# Cliente de Google Calendar
# =============================================================================

def _build_service(credentials_path: str):
    """
    Construye el cliente de Google Calendar autenticado con Service Account.
    Lanza FileNotFoundError si el JSON no existe.
    """
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    SCOPES = ["https://www.googleapis.com/auth/calendar"]

    if not os.path.exists(credentials_path):
        raise FileNotFoundError(
            f"No se encontró el archivo de credenciales: {credentials_path}\n"
            "Asegúrate de colocar el JSON de la Service Account en esa ruta "
            "y de compartir el Google Calendar con el email de la cuenta."
        )

    creds = service_account.Credentials.from_service_account_file(
        credentials_path, scopes=SCOPES
    )
    return build("calendar", "v3", credentials=creds, cache_discovery=False)


# =============================================================================
# Función principal: slots disponibles
# =============================================================================

def get_available_slots(
    calendar_id: str,
    credentials_path: str,
    date_str: str,
    duration_min: int = 30,
    allowed_hours: list[str] | None = None,
    allowed_days: list[int] | None = None,
) -> list[str]:
    """
    Devuelve los horarios libres para la fecha dada.

    Parámetros:
      date_str      → fecha en texto natural ("lunes 14", "14/04", "mañana", …)
      duration_min  → duración de cada cita en minutos
      allowed_hours → ["09:00", "10:00", …]  horarios configurados por el negocio
      allowed_days  → [0,1,2,3,4]  días de la semana disponibles (0=lunes)

    Retorna lista de strings "HH:MM" con los slots libres.
    Retorna [] si la fecha no es válida, es un día no laborable, o no hay slots.
    """
    tz = ZoneInfo(DEFAULT_TZ)
    parsed = _parse_date(date_str)

    if parsed is None:
        print(f"[Calendar] No pude parsear la fecha: '{date_str}'")
        return []

    # Verificar que el día está entre los permitidos
    if allowed_days is not None and parsed.weekday() not in allowed_days:
        print(f"[Calendar] Día no laborable: {parsed} (weekday={parsed.weekday()})")
        return []

    if not allowed_hours:
        print("[Calendar] No hay horarios configurados para este negocio.")
        return []

    # Definir rango de consulta: todo el día seleccionado
    day_start = datetime(parsed.year, parsed.month, parsed.day, 0, 0, 0, tzinfo=tz)
    day_end   = day_start + timedelta(days=1)

    try:
        service = _build_service(credentials_path)

        # Obtener eventos existentes en ese día
        events_result = service.events().list(
            calendarId=calendar_id,
            timeMin=day_start.isoformat(),
            timeMax=day_end.isoformat(),
            singleEvents=True,
            orderBy="startTime",
        ).execute()

        existing_events = events_result.get("items", [])
    except FileNotFoundError as e:
        print(f"⚠️ [Calendar] {e}")
        return allowed_hours  # fallback: devolver todos los horarios configurados
    except Exception as e:
        print(f"⚠️ [Calendar] Error consultando eventos: {repr(e)}")
        return allowed_hours  # fallback seguro

    # Construir intervalos ocupados
    busy_intervals: list[tuple[datetime, datetime]] = []
    for ev in existing_events:
        start_raw = ev.get("start", {})
        end_raw   = ev.get("end", {})
        try:
            ev_start = datetime.fromisoformat(start_raw.get("dateTime", "")).astimezone(tz)
            ev_end   = datetime.fromisoformat(end_raw.get("dateTime", "")).astimezone(tz)
            busy_intervals.append((ev_start, ev_end))
        except Exception:
            continue

    # Filtrar los horarios configurados que no choquen con ningún evento
    free_slots: list[str] = []
    for hour_str in allowed_hours:
        t = _parse_time(hour_str)
        if t is None:
            continue
        slot_start = datetime(parsed.year, parsed.month, parsed.day, t.hour, t.minute, tzinfo=tz)
        slot_end   = slot_start + timedelta(minutes=duration_min)

        occupied = any(
            slot_start < busy_end and slot_end > busy_start
            for busy_start, busy_end in busy_intervals
        )
        if not occupied:
            free_slots.append(hour_str)

    return free_slots


# =============================================================================
# Crear evento
# =============================================================================

def create_event(
    calendar_id: str,
    credentials_path: str,
    date_str: str,
    time_str: str,
    duration_min: int = 30,
    service_name: str = "Cita",
    client_name: str = "Cliente",
    client_phone: str = "",
) -> Optional[str]:
    """
    Crea un evento en Google Calendar.

    Retorna el event_id (str) si tiene éxito, o None si falla.

    El título del evento será: "{service_name} — {client_name}"
    La descripción incluye el número de teléfono del cliente.
    """
    tz = ZoneInfo(DEFAULT_TZ)
    parsed_date = _parse_date(date_str)
    parsed_time = _parse_time(time_str)

    if parsed_date is None or parsed_time is None:
        print(f"[Calendar] No pude parsear fecha='{date_str}' o hora='{time_str}'")
        return None

    start_dt = datetime(
        parsed_date.year, parsed_date.month, parsed_date.day,
        parsed_time.hour, parsed_time.minute,
    )
    end_dt = start_dt + timedelta(minutes=duration_min)

    event_body = {
        "summary": f"{service_name} — {client_name}",
        "description": (
            f"📱 WhatsApp: {client_phone}\n"
            f"🗓️ Agendado por el bot de Oberoende"
        ),
        "start": {
            "dateTime": start_dt.isoformat(),
            "timeZone": "America/Lima",
        },
        "end": {
            "dateTime": end_dt.isoformat(),
            "timeZone": "America/Lima",
        },
        "reminders": {
            "useDefault": False,
            "overrides": [
                {"method": "email",  "minutes": 60},
                {"method": "popup",  "minutes": 30},
            ],
        },
    }

    try:
        svc = _build_service(credentials_path)
        created = svc.events().insert(calendarId=calendar_id, body=event_body).execute()
        event_id = created.get("id")
        print(f"✅ [Calendar] Evento creado: {event_id} — {start_dt}")
        return event_id
    except FileNotFoundError as e:
        print(f"⚠️ [Calendar] {e}")
        return None
    except Exception as e:
        print(f"⚠️ [Calendar] Error creando evento: {repr(e)}")
        return None


# =============================================================================
# Cancelar evento por ID
# =============================================================================

def cancel_event(
    calendar_id: str,
    credentials_path: str,
    event_id: str,
) -> bool:
    """
    Elimina un evento de Google Calendar por su ID.
    Retorna True si se eliminó, False si hubo error.
    """
    try:
        svc = _build_service(credentials_path)
        svc.events().delete(calendarId=calendar_id, eventId=event_id).execute()
        print(f"✅ [Calendar] Evento cancelado: {event_id}")
        return True
    except FileNotFoundError as e:
        print(f"⚠️ [Calendar] {e}")
        return False
    except Exception as e:
        print(f"⚠️ [Calendar] Error cancelando evento: {repr(e)}")
        return False


# =============================================================================
# Buscar eventos del cliente por teléfono
# =============================================================================

def find_event_by_phone(
    calendar_id: str,
    credentials_path: str,
    client_phone: str,
    days_ahead: int = 30,
) -> list[dict]:
    """
    Busca eventos futuros cuya descripción contenga el número de teléfono.

    Retorna lista de dicts: [{event_id, summary, start_str}, ...]
    Útil para el flujo de cancelación: el usuario da su número y
    encontramos sus citas activas.
    """
    tz = ZoneInfo(DEFAULT_TZ)
    now     = datetime.now(tz)
    future  = now + timedelta(days=days_ahead)

    try:
        svc = _build_service(credentials_path)
        result = svc.events().list(
            calendarId=calendar_id,
            timeMin=now.isoformat(),
            timeMax=future.isoformat(),
            singleEvents=True,
            orderBy="startTime",
            q=client_phone,          # búsqueda de texto libre en la descripción
        ).execute()

        events = result.get("items", [])
        found = []
        for ev in events:
            desc = ev.get("description", "")
            if client_phone in desc:
                start_raw = ev.get("start", {}).get("dateTime", "")
                try:
                    start_dt = datetime.fromisoformat(start_raw).astimezone(tz)
                    start_str = start_dt.strftime("%d/%m/%Y a las %H:%M")
                except Exception:
                    start_str = start_raw
                found.append({
                    "event_id": ev["id"],
                    "summary":  ev.get("summary", "Cita"),
                    "start_str": start_str,
                })
        return found

    except FileNotFoundError as e:
        print(f"⚠️ [Calendar] {e}")
        return []
    except Exception as e:
        print(f"⚠️ [Calendar] Error buscando eventos: {repr(e)}")
        return []