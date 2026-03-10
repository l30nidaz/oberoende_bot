# oberoende_bot/app/graph/graph_engine.py
from langgraph.graph import StateGraph, END
from typing import TypedDict, Optional
import re

from oberoende_bot.app.services.brain_router import interpret_message
from oberoende_bot.app.services.smalltalk_service import smalltalk_answer, sales_menu
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


def _normalize(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[^\w\sáéíóúñü]", "", text)
    return text


def catalog_node(s: BotState) -> BotState:
    uid = s["user_id"]

    try:
        from oberoende_bot.app.services.whatsapp_service import (
            send_catalog_whatsapp,
            CATALOG_PDF_URL,
        )

        send_catalog_whatsapp(uid)
        response_text = (
            "Te acabo de enviar el catálogo por WhatsApp 📚\n"
            "Revísalo y dime qué modelo te gustó."
        )

        update_state(
            uid,
            last_intent="catalog",
            pending_followup=True,
            last_topic="catalog",
        )
    except Exception as e:
        print(f"Error enviando catálogo: {e}")
        from oberoende_bot.app.services.whatsapp_service import CATALOG_PDF_URL

        response_text = (
            "No pude enviar el catálogo en este momento 😥\n"
            f"Pero aquí tienes el PDF:\n{CATALOG_PDF_URL}\n\n"
            "✨ Envíame el nombre o una captura del modelo que te gustó y te ayudo con el precio."
        )
        add_ai_message(uid, response_text)

        update_state(
            uid,
            last_intent="catalog",
            pending_followup=True,
            last_topic="catalog",
        )

    s["response"] = response_text
    return s


def decide_node(s: BotState) -> BotState:
    uid = s["user_id"]
    msg = s["user_message"]

    add_user_message(uid, msg)

    # estado actual
    current_state = get_state(uid)
    norm = _normalize(msg)
    msg_lower = msg.lower().strip()

    # 1) Interceptar respuestas numéricas cuando hay followup pendiente
    if norm in {"1", "2", "3", "1️⃣", "2️⃣", "3️⃣"} and current_state.pending_followup:
        s["decision"] = "continue_followup"
        return s

    # 2) Detectar interés en producto
    PRODUCT_KEYWORDS = ["anillo", "collar", "arete", "pulsera", "cadena", "dije"]

    if any(p in msg_lower for p in PRODUCT_KEYWORDS):
        resp = (
            "¡Excelente elección! 💎\n\n"
            "¿Qué te gustaría saber sobre ese modelo?\n\n"
            "1️⃣ Precio\n"
            "2️⃣ Material\n"
            "3️⃣ Comprar\n"
        )

        s["response"] = resp
        s["decision"] = "smalltalk"
        add_ai_message(uid, resp)

        update_state(
            uid,
            last_product="producto",
            pending_followup=True,
            last_intent="product_interest"
        )
        return s

    # 3) Guardar nombre si el usuario se presenta
    name = extract_name(msg)
    if name:
        set_name(uid, name)
        resp = sales_menu(name)
        s["response"] = resp
        s["decision"] = "smalltalk"
        add_ai_message(uid, resp)
        update_state(uid, pending_followup=False)
        return s

    # 4) Menú principal
    if norm in {"1", "1️⃣"}:
        s["decision"] = "catalog"
        return s

    if norm in {"2", "2️⃣"}:
        resp = (
            "¡Claro! 💎\n"
            "Dime qué modelo te interesa y te ayudo con el precio.\n\n"
            "Puedes escribir el nombre del modelo o enviarme una foto/captura."
        )
        s["response"] = resp
        s["decision"] = "smalltalk"
        add_ai_message(uid, resp)
        update_state(
            uid,
            last_intent="price_prompt",
            pending_followup=False,
            last_topic="precio"
        )
        return s

    if norm in {"3", "3️⃣", "comprar", "comprar un modelo"}:
        s["decision"] = "handoff"
        return s

    if norm in {"4", "4️⃣", "asesor", "hablar con asesor"}:
        s["decision"] = "handoff"
        return s

    # 5) Router LLM
    state_for_router = state_dict(uid)
    decision = interpret_message(msg, state_for_router)
    s["decision"] = decision
    return s


def followup_node(s: BotState) -> BotState:
    uid = s["user_id"]
    msg = s["user_message"]

    choice = msg.strip()
    st = get_state(uid)
    prod = st.last_product or "el producto"

    if choice == "1":
        resp = (
            f"Claro 💎 Sobre el precio de {prod}:\n"
            "envíame el nombre exacto del modelo o una foto/captura del catálogo "
            "y te digo el precio exacto."
        )
        update_state(uid, pending_followup=False, last_topic="precio")

    elif choice == "2":
        resp = (
            f"Genial ✨ Sobre el material de {prod}:\n"
            "¿quieres saber si es plata 925, acero, baño de oro u otro material?"
        )
        update_state(uid, pending_followup=False, last_topic="material")

    elif choice == "3":
        resp = (
            "¡Perfecto! 💎 Para ayudarte con la compra:\n\n"
            "1️⃣ ¿Qué modelo te interesa? (puedes escribir el nombre o enviar foto)"
        )
        update_state(
            uid,
            last_intent="handoff",
            pending_followup=True,
            lead_stage="await_model",
            lead_model=None,
            lead_district=None,
            lead_payment=None
        )

    else:
        resp = smalltalk_answer(uid, msg)
        update_state(uid, pending_followup=False)

    s["response"] = resp
    add_ai_message(uid, resp)
    return s


def rag_node(s: BotState) -> BotState:
    uid = s["user_id"]
    q = s["user_message"]

    answer, signals = ask_rag_answer(q, uid)
    s["response"] = answer
    add_ai_message(uid, answer)

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

    # Si decide_node ya armó la respuesta, no la sobrescribimos
    resp = s.get("response") or smalltalk_answer(uid, msg)

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

    save_lead(
        user_id=uid,
        channel="whatsapp",
        name=profile_name,
        product=product,
        district=district,
        payment_method=payment,
        raw_message=msg
    )

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
    update_state(uid, pending_followup=False)
    return s


def lead_flow_node(s: BotState) -> BotState:
    uid = s["user_id"]
    msg = (s["user_message"] or "").strip()

    from oberoende_bot.app.services.user_profile_store_sqlite import get_name
    from oberoende_bot.app.services.leads_store import save_lead
    from oberoende_bot.app.services.email_service import notify_owner_lead

    st = get_state(uid)
    profile_name = get_name(uid) or "Cliente"

    stage = st.lead_stage or "await_model"

    if msg.lower() in {"cancelar", "salir", "no"}:
        resp = "Entendido ✅ Si deseas retomar la compra, escríbeme nuevamente."
        s["response"] = resp
        add_ai_message(uid, resp)
        update_state(
            uid,
            pending_followup=False,
            lead_stage=None,
            lead_model=None,
            lead_district=None,
            lead_payment=None
        )
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

    if stage == "await_payment":
        st = update_state(uid, lead_payment=msg)

        product = st.lead_model or ""
        district = st.lead_district or ""
        payment = st.lead_payment or ""

        save_lead(
            user_id=uid,
            channel="whatsapp",
            name=profile_name,
            product=product,
            district=district,
            payment_method=payment,
            raw_message=f"Modelo: {product}\nDistrito: {district}\nPago: {payment}"
        )

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

        update_state(
            uid,
            pending_followup=False,
            lead_stage=None,
            lead_model=None,
            lead_district=None,
            lead_payment=None
        )
        return s

    resp = "Vamos de nuevo 🙂 ¿Qué modelo te interesa?"
    s["response"] = resp
    add_ai_message(uid, resp)
    update_state(uid, lead_stage="await_model")
    return s


def extract_lead_fields(text: str):
    product = ""
    district = ""
    payment = ""

    m_product = re.search(r"modelo\s*:\s*(.+)", text, re.IGNORECASE)
    if m_product:
        product = m_product.group(1).strip()

    m_district = re.search(r"distrito\s*:\s*(.+)", text, re.IGNORECASE)
    if m_district:
        district = m_district.group(1).strip()

    m_payment = re.search(r"(yape|plin|transferencia)", text, re.IGNORECASE)
    if m_payment:
        payment = m_payment.group(1).strip()

    return product, district, payment


def router(s: BotState) -> str:
    uid = s["user_id"]
    decision = s.get("decision")
    st = get_state(uid)

    if st.last_intent == "handoff" and st.pending_followup and st.lead_stage:
        return "lead_flow"

    if st.last_intent == "handoff" and st.pending_followup:
        return "lead_capture"

    if decision == "continue_followup" and st.pending_followup:
        return "followup"

    if decision == "smalltalk":
        return "smalltalk"

    if decision == "handoff":
        return "handoff"

    if decision == "catalog":
        return "catalog"

    return "rag"


def build_graph():
    g = StateGraph(BotState)
    g.add_node("decide", decide_node)
    g.add_node("followup", followup_node)
    g.add_node("rag", rag_node)
    g.add_node("smalltalk", smalltalk_node)
    g.add_node("handoff", handoff_node)
    g.add_node("catalog", catalog_node)
    g.add_node("lead_capture", lead_capture_node)
    g.add_node("lead_flow", lead_flow_node)

    g.set_entry_point("decide")

    g.add_conditional_edges("decide", router, {
        "lead_flow": "lead_flow",
        "followup": "followup",
        "rag": "rag",
        "smalltalk": "smalltalk",
        "handoff": "handoff",
        "catalog": "catalog",
        "lead_capture": "lead_capture",
    })

    g.add_edge("followup", END)
    g.add_edge("rag", END)
    g.add_edge("smalltalk", END)
    g.add_edge("handoff", END)
    g.add_edge("catalog", END)
    g.add_edge("lead_capture", END)
    g.add_edge("lead_flow", END)

    return g.compile()


graph = build_graph()