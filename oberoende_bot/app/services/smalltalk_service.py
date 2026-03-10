# oberoende_bot/app/services/smalltalk_service.py
import re

from oberoende_bot.app.services.state_store_sqlite import get_state, update_state
from oberoende_bot.app.services.user_profile_store_sqlite import get_name

def _normalize(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[^\w\sáéíóúñü]", "", text)
    return text

_GREETINGS = {
    "hola", "holi", "buenas", "buenos dias", "buen día", "buenos días",
    "buenas tardes", "buenas noches", "hey", "que tal", "qué tal", "hi",
    "menu", "menú", "inicio", "empezar", "start"
}

_THANKS = {"gracias", "muchas gracias", "genial gracias", "perfecto gracias"}

_MENU_TEXT = (
    "¡Hola! 👋 Bienvenido a Oberoende 💎\n\n"
    "¿En qué puedo ayudarte hoy?\n\n"
    "1️⃣ Ver catálogo\n"
    "2️⃣ Saber precios\n"
    "3️⃣ Comprar un modelo\n"
    "4️⃣ Hablar con asesor"
)

def sales_menu(name: str | None = None) -> str:
    if name:
        return (
            f"¡Hola, {name}! 👋 Bienvenido a Oberoende 💎\n\n"
            "¿En qué puedo ayudarte hoy?\n\n"
            "1️⃣ Ver catálogo\n"
            "2️⃣ Saber precios\n"
            "3️⃣ Comprar un modelo\n"
            "4️⃣ Hablar con asesor"
        )
    return _MENU_TEXT

def smalltalk_answer(user_id: str, user_message: str) -> str:
    st = get_state(user_id)
    norm = _normalize(user_message)
    name = get_name(user_id)

    # Si el usuario estaba en followup pendiente y responde "ok", mantenemos el flujo actual
    if st.pending_followup and norm in {"ok", "ya", "listo", "perfecto", "dale", "okey"}:
        prod = st.last_product or "el producto"
        return (
            f"Perfecto ✅ Sobre {prod}, ¿qué te gustaría ver ahora?\n"
            "1) Opciones de envío\n"
            "2) Materiales / detalles\n"
            "3) Disponibilidad\n"
            "Respóndeme con 1, 2 o 3."
        )

    # Menú principal
    if norm in _GREETINGS:
        return sales_menu(name)

    # Opción 2 del menú principal
    if norm in {"2", "2️⃣", "precio", "precios", "saber precios", "ver precios"}:
        return (
            "¡Claro! 💎\n"
            "Dime qué modelo te interesa y te ayudo con el precio.\n\n"
            "Puedes escribir el nombre del modelo o enviarme una foto/captura."
        )

    if norm in _THANKS:
        update_state(user_id, pending_followup=False)
        return "¡Con gusto! 😊 Si quieres, escribe *menú* para ver las opciones otra vez."

    return sales_menu(name)