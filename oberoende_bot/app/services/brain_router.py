# oberoende_bot/app/services/brain_router.py
import os
from typing import Literal, Dict, Any

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

Decision = Literal["continue_followup", "smalltalk", "faq_rag", "handoff", "catalog"]


def interpret_message(user_message: str, state: Dict[str, Any]) -> Decision:
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0,
        api_key=os.getenv("OPENAI_API_KEY")
    )

    prompt = ChatPromptTemplate.from_messages([
        ("system",
         "Eres un router de conversación para una joyería.\n"
         "Debes elegir UNA acción entre:\n"
         "- continue_followup: si el mensaje confirma/acepta/continúa algo pendiente.\n"
         "- faq_rag: si es una consulta informativa que requiere buscar en documentos (precios, envíos, horarios, materiales, personalización, etc.).\n"
         "- smalltalk: si es saludo, agradecimiento, charla casual o pide menú/inicio.\n"
         "- catalog: si pide catálogo, ver catálogo, ver imágenes, ver modelos, lista visual de productos o catálogo PDF.\n"
         "- handoff: si quiere comprar, pagar, hacer pedido, separar producto, hablar con asesor o atención humana.\n\n"
         "Ejemplos:\n"
         "- 'hola' => smalltalk\n"
         "- 'menú' => smalltalk\n"
         "- 'quiero ver catálogo' => catalog\n"
         "- 'quiero comprar' => handoff\n"
         "- 'quiero hablar con asesor' => handoff\n"
         "- 'cuánto cuesta el anillo x' => faq_rag\n\n"
         "Responde SOLO con la etiqueta.\n"
         "Usa el estado para interpretar mensajes cortos como 'ok'."),
        ("human",
         "Estado actual:\n{state}\n\nMensaje usuario:\n{msg}\n\nEtiqueta:")
    ])

    chain = prompt | llm | StrOutputParser()
    out = chain.invoke({"state": str(state), "msg": user_message}).strip()

    if out not in {"continue_followup", "faq_rag", "smalltalk", "handoff", "catalog"}:
        return "faq_rag"
    return out  # type: ignore