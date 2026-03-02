# oberoende_bot/app/services/brain_router.py
import os
from typing import Literal, Dict, Any

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

Decision = Literal["continue_followup", "smalltalk", "faq_rag", "handoff"]

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
         "- faq_rag: si es una consulta informativa que requiere buscar en documentos (precios, envíos, horarios, etc.).\n"
         "- smalltalk: si es saludo, agradecimiento o charla casual.\n"
         "- handoff: si quiere comprar/pagar/pedido urgente (por ahora derivar).\n\n"
         "Responde SOLO con la etiqueta.\n"
         "Usa el estado para interpretar mensajes cortos como 'ok'."),
        ("human",
         "Estado actual:\n{state}\n\nMensaje usuario:\n{msg}\n\nEtiqueta:")
    ])

    chain = prompt | llm | StrOutputParser()
    out = chain.invoke({"state": str(state), "msg": user_message}).strip()

    if out not in {"continue_followup", "faq_rag", "smalltalk", "handoff"}:
        return "faq_rag"
    return out  # type: ignore