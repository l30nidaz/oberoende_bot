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
    "¡Genial! 💎 Para ayudarte mejor:\n\n"
    "1️⃣ ¿Qué modelo te interesa? (puedes escribir el nombre o enviar foto)\n"
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

    update_state(
        uid,
        last_intent="handoff",
        pending_followup=True,
        lead_stage="await_model",
        lead_model=None,
        lead_district=None,
        lead_payment=None
    )
    return s

def lead_capture_node(s: BotState) -> BotState:
    uid = s["user_id"]
    msg = s["user_message"]

    from oberoende_bot.app.services.leads_store import save_lead
    from oberoende_bot.app.services.user_profile_store_sqlite import get_name
    from oberoende_bot.app.services.email_service import notify_owner_lead

    profile_name = get_name(uid) or "Cliente"

    product, district, payment = extract_lead_fields(msg)

    # 1) Guardar lead estructurado
    save_lead(
        user_id=uid,
        channel="whatsapp",
        name=profile_name,
        product=product,
        district=district,
        payment_method=payment,
        raw_message=msg
    )

    # 2) Enviar email con info accionable (sin cambiar tu firma actual)
    lead_text_email = (
        f"NUEVO LEAD 💎\n\n"
        f"Cliente (WhatsApp): {uid}\n"
        f"Nombre: {profile_name}\n"
        f"Producto/Interés: {product or '(no especificado)'}\n"
        f"Distrito: {district or '(no especificado)'}\n\n"
        f"Mensaje completo:\n{msg}\n"
    )
    try:
        notify_owner_lead(user_id=uid, channel="whatsapp", lead_text=lead_text_email)
    except Exception as e:
        print(f"⚠️ Error al enviar email de lead: {e}")

    resp = (
        "¡Gracias! ✅ Ya registré tus datos.\n"
        "Un asesor te contactará en breve para ayudarte con tu compra. 💎"
    )

    s["response"] = resp
    add_ai_message(uid, resp)
    update_state(uid, pending_followup=False)  # cerramos captura
    return s

def lead_flow_node(s: BotState) -> BotState:
    uid = s["user_id"]
    msg = (s["user_message"] or "").strip()

    from oberoende_bot.app.services.state_store_sqlite import get_state, update_state
    from oberoende_bot.app.services.user_profile_store_sqlite import get_name
    from oberoende_bot.app.services.leads_store import save_lead
    from oberoende_bot.app.services.email_service import notify_owner_lead

    st = get_state(uid)
    profile_name = get_name(uid) or "Cliente"

    # Seguridad: si no hay etapa, reinicia a modelo
    stage = st.lead_stage or "await_model"

    # Permitir cancelar
    if msg.lower() in {"cancelar", "salir", "no"}:
        resp = "Entendido ✅ Si deseas retomar la compra, escríbeme nuevamente."
        s["response"] = resp
        add_ai_message(uid, resp)
        update_state(uid, pending_followup=False, lead_stage=None, lead_model=None, lead_district=None, lead_payment=None)
        return s

    if stage == "await_model":
        update_state(uid, lead_model=msg, lead_stage="await_district")
        resp = "Perfecto 👍 ¿En qué distrito estás?"
        s["response"] = resp
        add_ai_message(uid, resp)
        return s

    if stage == "await_district":
        update_state(uid, lead_district=msg, lead_stage="await_payment")
        resp = "Gracias ✅ ¿Cómo prefieres pagar: Yape, Plin o transferencia?"
        s["response"] = resp
        add_ai_message(uid, resp)
        return s

    # await_payment → guardamos todo
    if stage == "await_payment":
        # actualiza payment
        st = update_state(uid, lead_payment=msg)

        product = st.lead_model or ""
        district = st.lead_district or ""
        payment = st.lead_payment or ""

        # Guardar lead
        save_lead(
            user_id=uid,
            channel="whatsapp",
            name=profile_name,
            product=product,
            district=district,
            payment_method=payment,
            raw_message=f"Modelo: {product}\nDistrito: {district}\nPago: {payment}"
        )

        # Enviar email (NO tumbar el webhook si falla)
        lead_text_email = (
            f"NUEVO LEAD 💎\n\n"
            f"Cliente (WhatsApp): {uid}\n"
            f"Nombre: {profile_name}\n"
            f"Modelo: {product}\n"
            f"Distrito: {district}\n"
            f"Pago: {payment}\n"
        )
        try:
            notify_owner_lead(user_id=uid, channel="whatsapp", lead_text=lead_text_email)
        except Exception as e:
            print("⚠️ Error enviando email:", repr(e))

        resp = (
            "¡Listo! ✅ Ya registré tus datos.\n"
            "Un asesor te contactará en breve para ayudarte con tu compra. 💎"
        )
        s["response"] = resp
        add_ai_message(uid, resp)

        # Cerrar flujo
        update_state(uid, pending_followup=False, lead_stage=None, lead_model=None, lead_district=None, lead_payment=None)
        return s

    # fallback
    resp = "Vamos de nuevo 🙂 ¿Qué modelo te interesa?"
    s["response"] = resp
    add_ai_message(uid, resp)
    update_state(uid, lead_stage="await_model")
    return s

import re

def extract_lead_fields(text: str):
    product = ""
    district = ""
    payment = ""

    # Buscar con etiquetas
    m_product = re.search(r"modelo\s*:\s*(.+)", text, re.IGNORECASE)
    if m_product:
        product = m_product.group(1).strip()

    m_district = re.search(r"distrito\s*:\s*(.+)", text, re.IGNORECASE)
    if m_district:
        district = m_district.group(1).strip()

    m_payment = re.search(r"pago\s*:\s*(.+)", text, re.IGNORECASE)
    if m_payment:
        payment = m_payment.group(1).strip()

    # Fallback simple si no usaron etiquetas
    if not product or not district:
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        if not product and len(lines) >= 1:
            product = lines[0]
        if not district and len(lines) >= 2:
            district = lines[1]
        if not payment and len(lines) >= 3:
            payment = lines[2]

    return product, district, payment

def router(s: BotState) -> str:
    uid = s["user_id"]
    decision = s.get("decision")
    st = get_state(uid)
    # ✅ Si estamos en handoff guiado, seguimos el flujo
    if st.last_intent == "handoff" and st.pending_followup and st.lead_stage:
        return "lead_flow"
    # Si estamos en handoff y está pendiente, capturamos lead
    if st.last_intent == "handoff" and st.pending_followup:
        return "lead_capture"
    
    if decision == "continue_followup" and st.pending_followup:
        return "followup"
    if decision == "smalltalk":
        return "smalltalk"
    if decision == "handoff":
        return "handoff"
    return "rag"

def build_graph():
    g = StateGraph(BotState)
    g.add_node("decide", decide_node)
    g.add_node("followup", followup_node)
    g.add_node("rag", rag_node)
    g.add_node("smalltalk", smalltalk_node)
    g.add_node("handoff", handoff_node)
    g.add_node("lead_capture", lead_capture_node)
    g.add_node("lead_flow", lead_flow_node)
    g.set_entry_point("decide")
    g.add_conditional_edges("decide", router, {
        "lead_flow": "lead_flow",
        "followup": "followup",
        "rag": "rag",
        "smalltalk": "smalltalk",
        "handoff": "handoff",
        "lead_capture": "lead_capture"
    })

    g.add_edge("followup", END)
    g.add_edge("rag", END)
    g.add_edge("smalltalk", END)
    g.add_edge("handoff", END)
    g.add_edge("lead_capture", END)
    g.add_edge("lead_flow", END)
    return g.compile()


graph = build_graph()