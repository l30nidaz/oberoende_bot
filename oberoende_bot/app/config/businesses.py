import os
from typing import Dict, Any

# =============================================================================
# BUSINESSES — Configuración por negocio cliente de Obebot
# =============================================================================
#
# Obebot está orientado a negocios de servicios que gestionan citas:
# médicos, dentistas, psicólogos, peluquerías, spas, consultorías, etc.
#
# Para agregar un nuevo cliente:
#   1. Copia el bloque "demo" al final del diccionario
#   2. Reemplaza todos los valores
#   3. Agrega las variables de entorno correspondientes en .env
#   4. Coloca el JSON de credenciales de Google Calendar en secrets/
#   5. Crea la carpeta de documentos y sube los archivos de info del negocio
# =============================================================================

BUSINESSES: Dict[str, Dict[str, Any]] = {

    # ─────────────────────────────────────────────────────────────────────────
    # DEMO — Plantilla base y fallback.
    # No asignar a ningún número real de WhatsApp.
    # ─────────────────────────────────────────────────────────────────────────
    "demo": {
        # ── Identidad ─────────────────────────────────────────────────────────
        "business_id": "demo",
        "name":        "Demo Negocio",
        "emoji":       "🤖",
        "industry":    "servicios generales",

        # ── Roles del asistente ───────────────────────────────────────────────
        # Estos textos se inyectan como system prompt al LLM.
        # Personaliza según la voz y tono del negocio cliente.
        "assistant_role": (
            "Eres un asistente virtual profesional y amable. "
            "Ayudas a los clientes a obtener información sobre los servicios "
            "y a gestionar sus citas de forma sencilla."
        ),
        "router_role": (
            "Eres un router de conversación para un negocio de servicios. "
            "Tu trabajo es clasificar la intención del usuario y dirigirlo "
            "al flujo correcto: agendar cita, consultar info, cancelar o asesor."
        ),

        # ── Menú principal ────────────────────────────────────────────────────
        "menu_title": "¡Hola! 👋 Bienvenido a Demo Negocio 🤖",
        "menu_options": [
            "1️⃣ Agendar una cita",
            "2️⃣ Información y servicios",
            "3️⃣ Cancelar o modificar cita",
            "4️⃣ Hablar con un asesor",
        ],

        # ── Canales WhatsApp ──────────────────────────────────────────────────
        # Phone Number ID de Meta y/o número Twilio del negocio.
        # Dejar vacío ("") si no aplica.
        "channel_ids": [
            os.getenv("DEMO_META_PHONE_NUMBER_ID", "").strip(),
            os.getenv("DEMO_TWILIO_NUMBER", "").strip(),
        ],

        # ── Notificaciones por email ──────────────────────────────────────────
        "lead_email_subject": "Nueva cita agendada - Demo Negocio",

        # ── RAG / base de conocimiento ────────────────────────────────────────
        # Coloca aquí archivos .txt / .pdf / .docx con información del negocio:
        # servicios ofrecidos, precios, ubicación, preguntas frecuentes, etc.
        "documents_path":   "oberoende_bot/data/businesses/demo/documentos",
        "vectorstore_path": "oberoende_bot/data/businesses/demo/vectorstore",

        # ── Google Calendar ───────────────────────────────────────────────────
        # calendar_id: correo del Google Calendar del negocio.
        #   El cliente debe compartir su calendario con la Service Account de Obebot.
        # credentials_path: ruta al JSON de la Service Account (nunca en el repo).
        # appointment_duration_minutes: duración de cada cita en minutos.
        # appointment_hours: horarios ofrecidos cada día (formato "HH:MM", 24h).
        # appointment_days: días disponibles (0=lunes, 1=martes, …, 6=domingo).
        "calendar_id":                   "",
        "calendar_credentials_path":     "secrets/demo_calendar.json",
        "appointment_duration_minutes":  30,
        "appointment_hours": [
            "09:00", "10:00", "11:00",
            "14:00", "15:00", "16:00", "17:00",
        ],
        "appointment_days": [0, 1, 2, 3, 4],  # lunes a viernes

        # ── Textos del flujo de cita ──────────────────────────────────────────
        # Personaliza el lenguaje según el negocio.
        # Placeholders disponibles:
        #   {slots}   → lista de horarios disponibles
        #   {date}    → fecha elegida por el usuario
        #   {time}    → hora elegida
        #   {service} → servicio elegido
        "appointment_questions": {
            "service": (
                "¿Para qué tipo de servicio deseas la cita?\n"
                "Escríbeme el nombre o descríbelo brevemente."
            ),
            "date": (
                "¿Qué día te viene bien? 📅\n"
                "Puedes escribir algo como: *lunes 14*, *el martes*, o *14/04*."
            ),
            "time": (
                "Estos horarios están disponibles el {date}:\n\n"
                "{slots}\n\n"
                "¿Cuál prefieres?"
            ),
            "confirm": (
                "Confirmando tu cita ✅\n\n"
                "📅 {date} a las {time}\n"
                "📋 Servicio: {service}\n\n"
                "¿Confirmas? Responde *sí* o *no*."
            ),
            "success": (
                "¡Listo! 🎉 Tu cita ha sido agendada.\n\n"
                "📅 {date} a las {time}\n"
                "📋 {service}\n\n"
                "Te esperamos. Si necesitas cancelar o cambiar la fecha, "
                "escríbeme aquí mismo."
            ),
            "cancel_ask": (
                "Para cancelar tu cita, dime tu nombre completo o el número "
                "de confirmación que te enviamos."
            ),
            "cancel_success": (
                "✅ Tu cita ha sido cancelada sin problema.\n"
                "Cuando quieras agendar una nueva, escríbeme."
            ),
            "no_slots": (
                "Lo siento 😔 No hay horarios disponibles el {date}.\n"
                "¿Te gustaría intentar con otro día?"
            ),
        },
    },
    "oberoende": {
    "business_id": "oberoende",
    "name": "Oberoende",
    "app_name": "Oberoende",
    "emoji": "🤖",
    "industry": "software de chatbots",
    "assistant_role": "Eres un asistente profesional de Oberoende, una plataforma de chatbots para WhatsApp.",
    "router_role": "Eres un router de conversación para una empresa de software.",
    "menu_title": "¡Hola! 👋 Bienvenido a Oberoende 🤖",
    "menu_options": [
        "1️⃣ ¿Qué es Oberoende?",
        "2️⃣ Ver planes y precios",
        "3️⃣ Quiero una demo",
        "4️⃣ Hablar con un asesor",
    ],
    "product_keywords": ["chatbot", "bot", "whatsapp", "automatización", "plan"],
    "product_examples": "chatbots, planes o integraciones",
    "payment_methods": ["Yape", "Plin", "transferencia"],
    "lead_questions": {
        "model": "1️⃣ ¿Para qué tipo de negocio quieres el chatbot?",
        "district": "Perfecto 👍 ¿En qué ciudad o país estás?",
        "payment": "Gracias ✅ ¿Cómo prefieres coordinar el pago?"
    },
    "catalog_images": [],
    "catalog_pdf_url": "",
    "documents_path": "oberoende_bot/app/data/businesses/oberoende/documentos",
    "vectorstore_path": "oberoende_bot/app/data/businesses/oberoende/vectorstore",
    "channel_ids": [
        os.getenv("OBEROENDE_META_PHONE_NUMBER_ID", "").strip(),
    ],
    "lead_email_subject": "Nuevo lead - Oberoende",
},

    # ─────────────────────────────────────────────────────────────────────────
    # AGREGA AQUÍ TUS CLIENTES REALES
    #
    # "nombre_cliente": {
    #     "business_id": "nombre_cliente",
    #     "name":        "Nombre Visible",
    #     "emoji":       "🏥",
    #     "industry":    "medicina general",
    #     "assistant_role": "Eres el asistente virtual de...",
    #     "router_role":    "Eres un router de conversación para...",
    #     "menu_title":  "¡Hola! 👋 Bienvenido a Nombre Visible 🏥",
    #     "menu_options": [
    #         "1️⃣ Agendar una cita",
    #         "2️⃣ Información y servicios",
    #         "3️⃣ Cancelar o modificar cita",
    #         "4️⃣ Hablar con recepción",
    #     ],
    #     "channel_ids": [
    #         os.getenv("NOMBRE_CLIENTE_META_PHONE_NUMBER_ID", "").strip(),
    #         "",
    #     ],
    #     "lead_email_subject": "Nueva cita - Nombre Visible",
    #     "documents_path":   "oberoende_bot/data/businesses/nombre_cliente/documentos",
    #     "vectorstore_path": "oberoende_bot/data/businesses/nombre_cliente/vectorstore",
    #     "calendar_id":                  "cliente@gmail.com",
    #     "calendar_credentials_path":    "secrets/nombre_cliente_calendar.json",
    #     "appointment_duration_minutes": 30,
    #     "appointment_hours": ["09:00", "10:00", "11:00", "15:00", "16:00"],
    #     "appointment_days":  [0, 1, 2, 3, 4],
    #     "appointment_questions": {
    #         "service":        "¿Qué tipo de consulta necesitas?",
    #         "date":           "¿Qué día te viene bien?",
    #         "time":           "Horarios disponibles el {date}:\n{slots}\n¿Cuál prefieres?",
    #         "confirm":        "Confirmando:\n📅 {date} a las {time}\n📋 {service}\n¿Confirmas?",
    #         "success":        "¡Cita agendada! 🎉 Te esperamos el {date} a las {time}.",
    #         "cancel_ask":     "¿Me das tu nombre o número de confirmación?",
    #         "cancel_success": "✅ Cita cancelada. ¡Hasta pronto!",
    #         "no_slots":       "No hay horarios el {date}. ¿Pruebas otro día?",
    #     },
    # },
    # ─────────────────────────────────────────────────────────────────────────
}

# =============================================================================
# DEFAULT_BUSINESS_ID
# Negocio usado cuando el channel_id del webhook no coincide con ninguno.
# Configura en .env: DEFAULT_BUSINESS_ID=demo
# =============================================================================
DEFAULT_BUSINESS_ID = os.getenv("DEFAULT_BUSINESS_ID", "demo").strip() or "demo"


def get_business_config(business_id: str | None = None) -> Dict[str, Any]:
    """Devuelve la config de un negocio por su ID, o el default si no existe."""
    bid = business_id or DEFAULT_BUSINESS_ID
    return BUSINESSES.get(bid, BUSINESSES[DEFAULT_BUSINESS_ID])


def resolve_business_by_channel(channel_id: str | None) -> Dict[str, Any]:
    """
    Busca el negocio que tiene ese channel_id (Meta phone_number_id o Twilio).
    Si no encuentra coincidencia, devuelve el negocio default.
    """
    normalized = (channel_id or "").strip()

    if normalized:
        for business in BUSINESSES.values():
            channel_ids = [x for x in business.get("channel_ids", []) if x]
            if normalized in channel_ids:
                return business

    return get_business_config(DEFAULT_BUSINESS_ID)