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


def sales_menu(config: dict, name: str | None = None) -> str:
    title = config["menu_title"]
    options = "\n".join(config["menu_options"])

    if name:
        return (
            f"¡Hola, {name}! 👋\n\n"
            f"{title.replace('¡Hola! 👋 ', '')}\n\n"
            "¿En qué puedo ayudarte hoy?\n\n"
            f"{options}"
        )

    return (
        f"{title}\n\n"
        "¿En qué puedo ayudarte hoy?\n\n"
        f"{options}"
    )


def smalltalk_answer(conversation_id: str, user_message: str, business_config: dict) -> str:
    st = get_state(conversation_id)
    norm = _normalize(user_message)
    name = get_name(conversation_id)

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
        return sales_menu(business_config, name)

    if norm in {"2", "2️⃣", "precio", "precios", "saber precios", "ver precios", "consultar precios"}:
        return (
            "¡Claro! ✨\n"
            f"Dime qué {business_config['product_examples']} te interesa y te ayudo con el precio.\n\n"
            "Puedes escribir el nombre del modelo"
        )

    if norm in _THANKS:
        update_state(conversation_id, pending_followup=False)
        return "¡Con gusto! 😊 Si quieres, escribe *menú* para ver las opciones otra vez."

    return sales_menu(business_config, name)