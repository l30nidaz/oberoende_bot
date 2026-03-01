from langgraph.graph import StateGraph, END
from oberoende_bot.app.graph.state import AgentState
from oberoende_bot.app.agents.intent_classifier import classify_intent
from oberoende_bot.app.agents.tools import create_order
from oberoende_bot.app.services.llm_service import ask_llm

# -------------------------
# NODO 1: Clasificación
# -------------------------

def classify_node(state: AgentState) -> AgentState:
    intent = classify_intent(state["user_message"])
    state["intent"] = intent
    return state

# -------------------------
# NODO 2: Consulta RAG
# -------------------------

def rag_node(state: AgentState) -> AgentState:
    reply = ask_llm(state["user_id"], state["user_message"])
    state["response"] = reply
    return state

# -------------------------
# NODO 3: Crear Pedido
# -------------------------

def order_node(state: AgentState) -> AgentState:
    reply = create_order(state["user_id"], state["user_message"])
    state["response"] = reply
    return state

# -------------------------
# Router dinámico
# -------------------------

def route_intent(state: AgentState):
    if state["intent"] == "crear_pedido":
        return "order_node"
    else:
        return "rag_node"

# -------------------------
# Construcción del grafo
# -------------------------

def build_graph():

    workflow = StateGraph(AgentState)

    workflow.add_node("classify_node", classify_node)
    workflow.add_node("rag_node", rag_node)
    workflow.add_node("order_node", order_node)

    workflow.set_entry_point("classify_node")

    workflow.add_conditional_edges(
        "classify_node",
        route_intent,
        {
            "order_node": "order_node",
            "rag_node": "rag_node"
        }
    )

    workflow.add_edge("rag_node", END)
    workflow.add_edge("order_node", END)

    return workflow.compile()

graph = build_graph()