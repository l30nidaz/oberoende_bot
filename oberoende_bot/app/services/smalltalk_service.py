# oberoende_bot/app/services/smalltalk_service.py
import re

from oberoende_bot.app.services.state_store_sqlite import update_state
from oberoende_bot.app.services.user_profile_store_sqlite import get_name


def _normalize(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[^\w\sáéíóúñü]", "", text)
    return text


_GREETINGS = {
    "hola", "holi", "buenas", "buenos dias", "buen día", "buenos días",
    "buenas tardes", "buenas noches", "hey", "que tal", "qué tal", "hi",
    "menu", "menú", "inicio", "empezar", "start",
}

_THANKS = {
    "gracias", "muchas gracias", "genial gracias", "perfecto gracias",
    "ok gracias", "listo gracias",
}


def main_menu(config: dict, name: str | None = None) -> str:
    """Genera el mensaje de menú principal, personalizando el saludo si hay nombre."""
    title   = config["menu_title"]
    options = "\n".join(config["menu_options"])

    if name:
        # Quita el saludo genérico del título para no duplicarlo
        clean_title = title.replace("¡Hola! 👋 ", "").replace("¡Hola! 👋", "")
        return (
            f"¡Hola, {name}! 👋\n\n"
            f"{clean_title}\n\n"
            "¿En qué puedo ayudarte hoy?\n\n"
            f"{options}"
        )

    return (
        f"{title}\n\n"
        "¿En qué puedo ayudarte hoy?\n\n"
        f"{options}"
    )


def smalltalk_answer(conversation_id: str, user_message: str, business_config: dict) -> str:
    """
    Maneja saludos, agradecimientos y mensajes cortos que no requieren
    RAG ni flujo de cita. Siempre devuelve el menú como anclaje.
    """
    norm = _normalize(user_message)
    name = get_name(conversation_id)

    if norm in _THANKS:
        update_state(conversation_id, pending_followup=False)
        return "¡Con gusto! 😊 Escribe *menú* cuando quieras ver las opciones."

    if norm in _GREETINGS or True:
        # Fallback seguro: ante cualquier smalltalk no reconocido, mostrar menú
        return main_menu(business_config, name)