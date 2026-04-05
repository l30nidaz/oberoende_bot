# obebot/app/services/brain_router.py
import os
from typing import Literal, Dict, Any

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

Decision = Literal["appointment", "cancel_appointment", "faq_rag", "smalltalk", "handoff"]

# ── Singleton del LLM ─────────────────────────────────────────────────────────
# Se instancia una sola vez al importar el módulo para evitar el overhead
# de construir el objeto en cada mensaje entrante.
_llm: ChatOpenAI | None = None


def _get_llm() -> ChatOpenAI:
    global _llm
    if _llm is None:
        _llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0,
            api_key=os.getenv("OPENAI_API_KEY"),
        )
    return _llm


def interpret_message(
    user_message: str,
    state: Dict[str, Any],
    business_config: Dict[str, Any],
) -> Decision:
    llm = _get_llm()

    prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            f"{business_config['router_role']}\n\n"
            "Clasifica el mensaje del usuario en UNA de estas etiquetas:\n\n"
            "- appointment        → quiere agendar, reservar, pedir o programar una cita.\n"
            "- cancel_appointment → quiere cancelar, anular, mover o modificar una cita existente.\n"
            "- faq_rag            → pregunta informativa sobre servicios, precios, ubicación,\n"
            "                       horarios, requisitos u otro tema que requiere buscar en docs.\n"
            "- smalltalk          → saludo, agradecimiento, despedida, charla casual, pide menú.\n"
            "- handoff            → quiere hablar con una persona, asesor o recepcionista.\n\n"
            "Reglas:\n"
            "- Responde SOLO con la etiqueta, sin explicación.\n"
            "- Si el mensaje es ambiguo, usa el estado actual para decidir.\n"
            "- Mensajes cortos como 'sí', 'ok', 'dale' en contexto de cita → appointment.\n\n"
            "Ejemplos:\n"
            "- 'hola'                          => smalltalk\n"
            "- 'quiero una cita'               => appointment\n"
            "- 'necesito agendar para mañana'  => appointment\n"
            "- 'quiero cancelar mi cita'       => cancel_appointment\n"
            "- 'cuánto cuesta la consulta'     => faq_rag\n"
            "- 'dónde están ubicados'          => faq_rag\n"
            "- 'quiero hablar con alguien'     => handoff\n"
        ),
        (
            "human",
            "Estado actual:\n{state}\n\nMensaje del usuario:\n{msg}\n\nEtiqueta:",
        ),
    ])

    chain = prompt | llm | StrOutputParser()
    out = chain.invoke({"state": str(state), "msg": user_message}).strip().lower()

    valid = {"appointment", "cancel_appointment", "faq_rag", "smalltalk", "handoff"}
    if out not in valid:
        return "faq_rag"
    return out  # type: ignore