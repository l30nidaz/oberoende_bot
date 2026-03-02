# oberoende_bot/app/services/rag_answer_service.py
import os
from typing import Tuple, Dict, Any

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser

from oberoende_bot.app.services.rag_service import get_vectorstore
from oberoende_bot.app.services.memory_service import get_history

FALLBACK_MESSAGE = "Déjame consultar esa información con un asesor."

def _extract_signals(question: str, answer: str) -> Dict[str, Any]:
    """
    Heurística ligera (no sólo palabras), para marcar followup.
    Luego lo hacemos con LLM si quieres.
    """
    q = question.lower()
    signals: Dict[str, Any] = {"topic": None, "product": None, "pending_followup": False}

    if any(x in q for x in ["cuanto", "cuánto", "precio", "costo", "vale"]):
        signals["topic"] = "precio"
        signals["pending_followup"] = True

    # producto simple: busca menciones típicas
    for p in ["anillo", "collar", "pulsera", "aretes", "aro", "cadena"]:
        if p in q:
            signals["product"] = p
            break

    return signals

def ask_rag_answer(question: str, user_id: str) -> Tuple[str, Dict[str, Any]]:
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0.2,
        api_key=os.getenv("OPENAI_API_KEY")
    )

    vectorstore = get_vectorstore()
    if vectorstore is None:
        return FALLBACK_MESSAGE, {"pending_followup": False}

    retriever = vectorstore.as_retriever(
        search_type="mmr",
        search_kwargs={"k": 4, "fetch_k": 15, "lambda_mult": 0.5}
    )

    # Traer evidencia primero
    try:
        docs = retriever.invoke(question)
    except Exception:
        return FALLBACK_MESSAGE, {"pending_followup": False}

    context = "\n\n".join(d.page_content for d in docs) if docs else ""
    if not context.strip():
        return FALLBACK_MESSAGE, {"pending_followup": False}

    chat_history = get_history(user_id)

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

    signals = _extract_signals(question, answer)
    return answer, signals