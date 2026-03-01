import os
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough

from oberoende_bot.app.services.rag_service import get_vectorstore
from oberoende_bot.app.services.memory_service import (
    get_history,
    add_user_message,
    add_ai_message
)


def ask_llm(question: str, user_id: str) -> str:
    """
    Ejecuta RAG con memoria usando LangChain 1.x (LCEL puro).
    """

    # 1️⃣ Modelo
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0.2,  # más bajo = menos alucinación
        api_key=os.getenv("OPENAI_API_KEY")
    )

    # 2️⃣ Vectorstore ya cargado en memoria (NO se recrea)
    vectorstore = get_vectorstore()

    # 3️⃣ Retriever optimizado con MMR
    retriever = vectorstore.as_retriever(
        search_type="mmr",
        search_kwargs={
            "k": 4,              # número de chunks
            "lambda_mult": 0.5   # balance relevancia/diversidad
        }
    )

    # 4️⃣ Historial del usuario
    chat_history = get_history(user_id)

    # 5️⃣ Prompt restrictivo
    prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        "Eres un asistente profesional de una joyería.\n\n"
        "Usa únicamente la información del siguiente contexto para responder.\n"
        "Si la respuesta no se encuentra en el contexto, responde exactamente:\n"
        "'Déjame consultar esa información con un asesor.'\n\n"
        "Contexto:\n{context}"
    ),
    MessagesPlaceholder("chat_history"),
    ("human", "{question}")
    ])

    # 6️⃣ Formateador de documentos recuperados
    def format_docs(docs):
        return "\n\n".join(doc.page_content for doc in docs)

    # 7️⃣ Pipeline LCEL completo
    rag_chain = (
        {
            "context": retriever | format_docs,
            "question": RunnablePassthrough(),
            "chat_history": lambda _: chat_history
        }
        | prompt
        | llm
        | StrOutputParser()
    )

    # 8️⃣ Ejecutar chain
    answer = rag_chain.invoke(question)

    # 9️⃣ Guardar en memoria
    add_user_message(user_id, question)
    add_ai_message(user_id, answer)

    return answer