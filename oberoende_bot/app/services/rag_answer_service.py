import os
from typing import Tuple, Dict, Any

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser

from oberoende_bot.app.services.rag_service import get_vectorstore
from oberoende_bot.app.services.memory_service import get_history

FALLBACK_MESSAGE = "Déjame consultar esa información con un asesor."


def _extract_signals(question: str, business_config: Dict[str, Any]) -> Dict[str, Any]:
    q = question.lower()
    signals: Dict[str, Any] = {
        "topic": None,
        "product": None,
        "pending_followup": False
    }

    if any(x in q for x in ["cuanto", "cuánto", "precio", "costo", "vale"]):
        signals["topic"] = "precio"
        signals["pending_followup"] = True

    for p in business_config.get("product_keywords", []):
        if p.lower() in q:
            signals["product"] = p
            break

    return signals


def ask_rag_answer(
    question: str,
    conversation_id: str,
    business_config: Dict[str, Any]
) -> Tuple[str, Dict[str, Any]]:
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0.2,
        api_key=os.getenv("OPENAI_API_KEY")
    )

    business_id = business_config["business_id"]
    vectorstore = get_vectorstore(business_id)

    if vectorstore is None:
        return FALLBACK_MESSAGE, {"pending_followup": False}

    retriever = vectorstore.as_retriever(
        search_type="mmr",
        search_kwargs={"k": 4, "fetch_k": 15, "lambda_mult": 0.5}
    )

    try:
        docs = retriever.invoke(question)
        print(f"[RAG] query='{question}' → docs encontrados: {len(docs)}")
        for i, d in enumerate(docs):
            print(f"[RAG] doc[{i}] preview: {d.page_content[:80]}")
    except Exception:
        return FALLBACK_MESSAGE, {"pending_followup": False}

    context = "\n\n".join(d.page_content for d in docs) if docs else ""
    if not context.strip():
        return FALLBACK_MESSAGE, {"pending_followup": False}

    chat_history = get_history(conversation_id)

    prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            f"{business_config['assistant_role']}\n"
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

    signals = _extract_signals(question, business_config)
    return answer, signals