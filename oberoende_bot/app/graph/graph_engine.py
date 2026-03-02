# oberoende_bot/app/graph/graph_engine.py
from langgraph.graph import StateGraph, END
from typing import TypedDict, Optional, Dict, Any

from oberoende_bot.app.services.brain_router import interpret_message
from oberoende_bot.app.services.smalltalk_service import smalltalk_answer
from oberoende_bot.app.services.rag_answer_service import ask_rag_answer
from oberoende_bot.app.services.memory_service import add_user_message, add_ai_message
from oberoende_bot.app.services.state_store_sqlite import get_state, update_state, state_dict
from oberoende_bot.app.services.name_extractor import extract_name
from oberoende_bot.app.services.user_profile_store_sqlite import set_name

HANDOFF_MESSAGE = (
    "¡Claro! Para ayudarte mejor, déjame derivar tu solicitud a un asesor.\n"
    "¿Qué producto te interesa y en qué ciudad estás para el envío?"
)

class BotState(TypedDict):
    user_id: str
    user_message: str
    response: str
    decision: Optional[str]

def decide_node(s: BotState) -> BotState:
    uid = s["user_id"]
    msg = s["user_message"]

    # guardar mensaje en memoria conversacional
    add_user_message(uid, msg)

    name = extract_name(msg)
    if name:
        set_name(uid, name)
        resp = f"¡Encantado, {name}! 😊 ¿En qué te puedo ayudar sobre nuestras joyas (precios, materiales, envíos, horarios)?"
        s["response"] = resp
        s["decision"] = "smalltalk"  # o una decisión especial
        add_ai_message(uid, resp)
        # opcional: actualizar estado
        update_state(uid, pending_followup=False)
        return s
    
    st = state_dict(uid)
    decision = interpret_message(msg, st)
    s["decision"] = decision

    return s

def followup_node(s: BotState) -> BotState:
    uid = s["user_id"]
    msg = s["user_message"]

    # Si responde 1/2/3 (flujo informativo)
    choice = msg.strip()
    st = get_state(uid)
    prod = st.last_product or "el producto"

    if choice == "1":
        resp = f"Perfecto 📦 Sobre envíos de {prod}: ¿a qué ciudad/distrito sería el envío?"
    elif choice == "2":
        resp = f"Genial ✨ Sobre materiales/detalles de {prod}: ¿prefieres plata 925 u oro 18k (si aplica)?"
    elif choice == "3":
        resp = f"Listo ✅ Sobre disponibilidad de {prod}: ¿lo buscas para hoy, esta semana o para una fecha específica?"
    else:
        # si solo dijo "ok" u otro confirmatorio
        resp = smalltalk_answer(uid, msg)

    s["response"] = resp
    add_ai_message(uid, resp)
    update_state(uid, pending_followup=False)
    return s

def rag_node(s: BotState) -> BotState:
    uid = s["user_id"]
    q = s["user_message"]

    answer, signals = ask_rag_answer(q, uid)
    s["response"] = answer
    add_ai_message(uid, answer)

    # actualizar estado estructurado
    update_state(
        uid,
        last_intent="faq_rag",
        last_topic=signals.get("topic"),
        last_product=signals.get("product"),
        pending_followup=bool(signals.get("pending_followup")),
        last_answer=answer,
        last_question=q
    )
    return s

def smalltalk_node(s: BotState) -> BotState:
    uid = s["user_id"]
    msg = s["user_message"]
    resp = smalltalk_answer(uid, msg)
    s["response"] = resp
    add_ai_message(uid, resp)
    update_state(uid, last_intent="smalltalk")
    return s

def handoff_node(s: BotState) -> BotState:
    uid = s["user_id"]
    s["response"] = HANDOFF_MESSAGE
    add_ai_message(uid, HANDOFF_MESSAGE)
    update_state(uid, last_intent="handoff", pending_followup=False)
    return s

def router(s: BotState) -> str:
    uid = s["user_id"]
    decision = s.get("decision")

    # Si el router dice continuar followup y realmente hay followup pendiente
    if decision == "continue_followup" and get_state(uid).pending_followup:
        return "followup"
    if decision == "smalltalk":
        return "smalltalk"
    if decision == "handoff":
        return "handoff"
    return "rag"  # default

def build_graph():
    g = StateGraph(BotState)
    g.add_node("decide", decide_node)
    g.add_node("followup", followup_node)
    g.add_node("rag", rag_node)
    g.add_node("smalltalk", smalltalk_node)
    g.add_node("handoff", handoff_node)

    g.set_entry_point("decide")
    g.add_conditional_edges("decide", router, {
        "followup": "followup",
        "rag": "rag",
        "smalltalk": "smalltalk",
        "handoff": "handoff"
    })

    g.add_edge("followup", END)
    g.add_edge("rag", END)
    g.add_edge("smalltalk", END)
    g.add_edge("handoff", END)

    return g.compile()

graph = build_graph()