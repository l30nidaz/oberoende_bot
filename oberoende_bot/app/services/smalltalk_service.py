# oberoende_bot/app/services/smalltalk_service.py
import re
from oberoende_bot.app.services.state_store_sqlite import get_state

def _normalize(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[^\w\sáéíóúñü]", "", text)
    return text

_GREETINGS = {
    "hola", "holi", "buenas", "buenos dias", "buen día", "buenos días",
    "buenas tardes", "buenas noches", "hey", "que tal", "qué tal", "hi"
}
_THANKS = {"gracias", "muchas gracias", "genial gracias", "perfecto gracias"}

def smalltalk_answer(user_id: str, user_message: str) -> str:
    st = get_state(user_id)
    norm = _normalize(user_message)

    # Si estábamos esperando followup, NO respondemos genérico
    if st.pending_followup and norm in {"ok", "ya", "listo", "perfecto", "dale", "okey"}:
        prod = st.last_product or "el producto"
        return (
            f"Perfecto ✅ Sobre {prod}, ¿qué te gustaría ver ahora?\n"
            "1) Opciones de envío\n"
            "2) Materiales / detalles\n"
            "3) Disponibilidad\n"
            "Respóndeme con 1, 2 o 3."
        )

    if norm in _GREETINGS:
        return (
            "¡Hola! 👋 Soy el asistente virtual de la joyería.\n"
            "Puedo ayudarte con precios, materiales, envíos, horarios y personalización.\n"
            "¿Qué estás buscando: anillos, collares, pulseras o aretes?"
        )

    if norm in _THANKS:
        return "¡Con gusto! 😊 ¿Te ayudo con algo más de la joyería?"

    return "Entendido ✅ ¿Qué consulta tienes sobre nuestros productos o envíos?"