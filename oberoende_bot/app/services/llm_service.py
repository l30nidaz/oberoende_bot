import os
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


def ask_llm(question: str, user_id: str) -> str:
    """
    RAG informativo (sin LangGraph), optimizado:
    - Usa vectorstore cacheado en RAM (initialize_vectorstore en startup)
    - Retriever MMR con fetch_k para mejor recall
    - Fallback pre-LLM si no hay contexto (ahorra tokens y evita alucinación)
    - Incluye {context} explícitamente en el prompt
    - Memoria por usuario (historial en RAM)
    """

    # 1) Modelo
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0.2,
        api_key=os.getenv("OPENAI_API_KEY")
    )

    # 2) Vectorstore (ya inicializado en startup)
    vectorstore = get_vectorstore()
    if vectorstore is None:
        # Si por algún motivo el startup no corrió
        return FALLBACK_MESSAGE

    # 3) Retriever (MMR mejora diversidad; fetch_k aumenta candidatos)
    retriever = vectorstore.as_retriever(
        search_type="mmr",
        search_kwargs={
            "k": 4,
            "fetch_k": 15,
            "lambda_mult": 0.5
        }
    )

    # 4) Historial del usuario
    chat_history = get_history(user_id)

    # 5) Recuperar docs primero (para fallback pre-LLM)
    try:
        docs = retriever.invoke(question)
    except Exception:
        return FALLBACK_MESSAGE

    context = "\n\n".join(d.page_content for d in docs) if docs else ""
    if not context.strip():
        # No hay evidencia => no gastamos tokens del LLM
        add_user_message(user_id, question)
        add_ai_message(user_id, FALLBACK_MESSAGE)
        return FALLBACK_MESSAGE

    # 6) Prompt: incluye contexto de forma explícita
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

    # 7) Ejecutar LLM con inputs completos
    answer = chain.invoke({
        "context": context,
        "chat_history": chat_history,
        "question": question
    })

    # 8) Guardar memoria
    add_user_message(user_id, question)
    add_ai_message(user_id, answer)

    return answer