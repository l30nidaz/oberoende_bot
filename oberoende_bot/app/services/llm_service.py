import os
import re
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser

from oberoende_bot.app.services.rag_service import get_vectorstore
from oberoende_bot.app.services.memory_service import (
    get_history,
    add_user_message,
    add_ai_message
)

FALLBACK_MESSAGE = "Déjame consultar esa información con un asesor."

# Saluditos típicos en WhatsApp (puedes ampliar)
_GREETINGS = {
    "hola", "holi", "buenas", "buenos dias", "buen día", "buenos días",
    "buenas tardes", "buenas noches", "hey", "que tal", "qué tal",
    "ola", "hi"
}

_THANKS = {"gracias", "muchas gracias", "ok gracias", "genial gracias", "perfecto gracias"}


def _normalize(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[^\w\sáéíóúñü]", "", text)  # quita signos, mantiene letras latinas
    return text


def _is_short_chitchat(norm: str) -> bool:
    # Mensajes muy cortos tipo: "ok", "👍", "ya", etc. (si quieres incluir emojis, ajusta regex)
    return len(norm) <= 3 or norm in {"ok", "ya", "listo", "dale", "bien"}


def _handle_smalltalk(norm: str) -> str | None:
    if norm in _GREETINGS:
        return (
            "¡Hola! 👋 Soy el asistente virtual de la joyería.\n"
            "Puedo ayudarte con precios, materiales, envíos, horarios y personalización.\n"
            "¿Qué estás buscando: anillos, collares, pulseras o aretes?"
        )
    if norm in _THANKS:
        return "¡Con gusto! 😊 ¿Te ayudo con algo más de la joyería?"
    if _is_short_chitchat(norm):
        return "Perfecto ✅ ¿Qué consulta tienes sobre nuestros productos o envíos?"
    return None


def ask_llm(question: str, user_id: str) -> str:
    """
    RAG informativo (sin LangGraph), optimizado:
    - Vectorstore cacheado en RAM
    - Retriever MMR con fetch_k
    - Fallback pre-LLM si no hay contexto
    - Manejo de saludos/smalltalk antes del RAG
    - Memoria por usuario
    """
    norm = _normalize(question)

    # 0) Smalltalk / saludos antes de RAG
    smalltalk = _handle_smalltalk(norm)
    if smalltalk:
        #add_user_message(user_id, question)
        add_ai_message(user_id, smalltalk)
        return smalltalk

    # 1) Modelo
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0.2,
        api_key=os.getenv("OPENAI_API_KEY")
    )

    # 2) Vectorstore (ya inicializado en startup)
    vectorstore = get_vectorstore()
    if vectorstore is None:
        #add_user_message(user_id, question)
        add_ai_message(user_id, FALLBACK_MESSAGE)
        return FALLBACK_MESSAGE

    # 3) Retriever MMR
    retriever = vectorstore.as_retriever(
        search_type="mmr",
        search_kwargs={"k": 4, "fetch_k": 15, "lambda_mult": 0.5}
    )

    # 4) Historial
    chat_history = get_history(user_id)

    # 5) Recuperar docs primero (fallback pre-LLM)
    try:
        docs = retriever.invoke(question)
    except Exception:
        #add_user_message(user_id, question)
        add_ai_message(user_id, FALLBACK_MESSAGE)
        return FALLBACK_MESSAGE

    context = "\n\n".join(d.page_content for d in docs) if docs else ""
    if not context.strip():
        #add_user_message(user_id, question)
        add_ai_message(user_id, FALLBACK_MESSAGE)
        return FALLBACK_MESSAGE

    # 6) Prompt con contexto explícito
    prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            "Eres un asistente profesional de una joyería.\n"
            "Responde únicamente usando la información del CONTEXTO proporcionado.\n"
            "Si la respuesta no se encuentra en el contexto, responde exactamente:\n"
            f"'{FALLBACK_MESSAGE}'\n\n"
            "CONTEXTO:\n{context}"
        ),
        MessagesPlaceholder("chat_history"),
        ("human", "{question}")
    ])

    chain = prompt | llm | StrOutputParser()

    answer = chain.invoke({
        "context": context,
        "chat_history": chat_history,
        "question": question
    })

    #add_user_message(user_id, question)
    add_ai_message(user_id, answer)
    return answer