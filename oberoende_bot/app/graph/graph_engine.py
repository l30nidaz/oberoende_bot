from langgraph.graph import StateGraph, END
from typing import TypedDict, Optional, Any
import re

from oberoende_bot.app.config.businesses import resolve_business_by_channel
from oberoende_bot.app.services.brain_router import interpret_message
from oberoende_bot.app.services.smalltalk_service import smalltalk_answer, sales_menu
from oberoende_bot.app.services.rag_answer_service import ask_rag_answer
from oberoende_bot.app.services.memory_service import add_user_message, add_ai_message
from oberoende_bot.app.services.state_store_sqlite import (
    get_state, update_state, state_dict, reset_if_expired,
)
from oberoende_bot.app.services.name_extractor import extract_name
from oberoende_bot.app.services.user_profile_store_sqlite import set_name


class BotState(TypedDict):
    user_id: str                   # teléfono del cliente
    channel_id: str                # número/phone_number_id del negocio
    conversation_id: str           # business_id:user_id
    business_id: str
    business_config: dict[str, Any]
    user_message: str
    response: str
    decision: Optional[str]


def _normalize(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[^\w\sáéíóúñü]", "", text)
    return text


def _ensure_business_context(s: BotState) -> tuple[str, dict]:
    business_config = s.get("business_config") or resolve_business_by_channel(s.get("channel_id"))
    business_id = business_config["business_id"]
    conversation_id = s.get("conversation_id") or f"{business_id}:{s['user_id']}"

    s["business_id"] = business_id
    s["business_config"] = business_config
    s["conversation_id"] = conversation_id
    return conversation_id, business_config


def catalog_node(s: BotState) -> BotState:
    uid = s["user_id"]
    _, business_config = _ensure_business_context(s)
    conversation_id = s["conversation_id"]

    try:
        from oberoende_bot.app.services.whatsapp_service import send_catalog_whatsapp

        send_catalog_whatsapp(uid, business_config)
        response_text = (
            f"Te acabo de enviar el catálogo de {business_config['name']} por WhatsApp 📚\n"
            "Revísalo y dime qué modelo te gustó."
        )

        update_state(
            conversation_id,
            last_intent="catalog",
            pending_followup=True,
            last_topic="catalog",
        )
    except Exception as e:
        print(f"Error enviando catálogo: {e}")
        pdf_url = business_config.get("catalog_pdf_url", "")

        response_text = (
            "No pude enviar el catálogo en este momento 😥\n"
            f"Pero aquí tienes el PDF:\n{pdf_url}\n\n"
            "✨ Envíame el nombre o una captura del modelo que te gustó y te ayudo con el precio."
        )
        update_state(
            conversation_id,
            last_intent="catalog",
            pending_followup=True,
            last_topic="catalog",
        )

    add_ai_message(conversation_id, response_text)
    s["response"] = response_text
    return s


def decide_node(s: BotState) -> BotState:
    msg = s["user_message"]

    conversation_id, business_config = _ensure_business_context(s)
    add_user_message(conversation_id, msg)

    # ── MEJORA 1: Timeout de sesión ───────────────────────────────────────────
    # Si el usuario no escribió en SESSION_TIMEOUT_HOURS horas, reseteamos el
    # estado de flujo/lead y mostramos el menú de bienvenida. Así alguien que
    # vuelve 2 días después no queda atascado en un lead flow que ya olvidó.
    session_expired = reset_if_expired(conversation_id)
    if session_expired:
        resp = sales_menu(business_config)
        s["response"] = resp
        s["decision"] = "smalltalk"
        add_ai_message(conversation_id, resp)
        return s

    current_state = get_state(conversation_id)
    norm = _normalize(msg)
    msg_lower = msg.lower().strip()

    # ── 1. Si hay un lead en curso, saltar TODA la lógica de keywords ────────
    # El usuario está respondiendo preguntas del lead flow (modelo, distrito,
    # pago). Cualquier keyword de producto en su respuesta ("anillo de oro",
    # "collar de plata") NO debe disparar el submenú — debe ir directo al nodo
    # lead_flow. El router() ya sabe redirigirlo ahí.
    if current_state.last_intent == "handoff" and current_state.lead_stage:
        s["decision"] = None  # router() lo enviará a lead_flow
        return s

    # ── 2. Números de menú estando en follow-up pendiente ────────────────────
    if norm in {"1", "2", "3", "1️⃣", "2️⃣", "3️⃣"} and current_state.pending_followup:
        s["decision"] = "continue_followup"
        return s

    # ── 3. Keyword de producto ────────────────────────────────────────────────
    product_keywords = [p.lower() for p in business_config.get("product_keywords", [])]

    # MEJORA 2: extraemos el keyword real que disparó la detección en vez de
    # guardar el literal "producto". Así followup_node puede decir
    # "Sobre el precio del anillo..." en vez de "Sobre el precio de producto..."
    matched_product = next(
        (p for p in product_keywords if p in msg_lower), None
    )

    if matched_product:
        resp = (
            "¡Excelente elección! ✨\n\n"
            "¿Qué te gustaría saber sobre ese modelo?\n\n"
            "1️⃣ Precio\n"
            "2️⃣ Material / detalles\n"
            "3️⃣ Comprar\n"
        )
        s["response"] = resp
        s["decision"] = "smalltalk"
        add_ai_message(conversation_id, resp)
        update_state(
            conversation_id,
            last_product=matched_product,   # ← keyword real, no "producto"
            pending_followup=True,
            last_intent="product_interest",
        )
        return s

    # ── 4. Extracción de nombre ───────────────────────────────────────────────
    name = extract_name(msg)
    if name:
        set_name(conversation_id, name)
        resp = sales_menu(business_config, name)
        s["response"] = resp
        s["decision"] = "smalltalk"
        add_ai_message(conversation_id, resp)
        update_state(conversation_id, pending_followup=False)
        return s

    # ── 5. Opciones numéricas del menú principal (SOLO sin followup activo) ───
    # Se verifica explícitamente que NO hay followup para evitar que un "1" o "2"
    # fuera de contexto active el catálogo o precio cuando el usuario está en
    # medio de otra conversación.
    if not current_state.pending_followup:
        if norm in {"1", "1️⃣"}:
            s["decision"] = "catalog"
            return s

        if norm in {"2", "2️⃣"}:
            resp = (
                "¡Claro! ✨\n"
                f"Dime qué {business_config['product_examples']} te interesa "
                "y te ayudo con el precio.\n\n"
                "Puedes escribir el nombre del modelo o enviarme una foto/captura."
            )
            s["response"] = resp
            s["decision"] = "smalltalk"
            add_ai_message(conversation_id, resp)
            update_state(
                conversation_id,
                last_intent="price_prompt",
                pending_followup=False,
                last_topic="precio",
            )
            return s

    if norm in {"3", "3️⃣", "comprar", "comprar un modelo", "hacer pedido"}:
        s["decision"] = "handoff"
        return s

    if norm in {"4", "4️⃣", "asesor", "hablar con asesor"}:
        s["decision"] = "handoff"
        return s

    # ── 6. Router LLM para todo lo demás ─────────────────────────────────────
    state_for_router = state_dict(conversation_id)
    decision = interpret_message(msg, state_for_router, business_config)
    s["decision"] = decision
    return s


def followup_node(s: BotState) -> BotState:
    conversation_id, _ = _ensure_business_context(s)
    msg = s["user_message"]

    choice = msg.strip()
    st = get_state(conversation_id)
    prod = st.last_product or "el producto"

    if choice == "1":
        resp = (
            f"Claro ✨ Sobre el precio de {prod}:\n"
            "envíame el nombre exacto del modelo o una foto/captura del catálogo "
            "y te digo el precio exacto."
        )
        update_state(conversation_id, pending_followup=False, last_topic="precio")

    elif choice == "2":
        resp = (
            f"Genial ✨ Sobre el material o detalles de {prod}:\n"
            "¿quieres saber medidas, material, colores o disponibilidad?"
        )
        update_state(conversation_id, pending_followup=False, last_topic="material")

    elif choice == "3":
        lead_q = s["business_config"]["lead_questions"]["model"]
        resp = f"¡Perfecto! ✨ Para ayudarte con la compra:\n\n{lead_q}"
        update_state(
            conversation_id,
            last_intent="handoff",
            pending_followup=True,
            lead_stage="await_model",
            lead_model=None,
            lead_district=None,
            lead_payment=None,
        )

    else:
        resp = smalltalk_answer(conversation_id, msg, s["business_config"])
        update_state(conversation_id, pending_followup=False)

    s["response"] = resp
    add_ai_message(conversation_id, resp)
    return s


def rag_node(s: BotState) -> BotState:
    conversation_id, business_config = _ensure_business_context(s)
    q = s["user_message"]

    answer, signals = ask_rag_answer(q, conversation_id, business_config)
    s["response"] = answer
    add_ai_message(conversation_id, answer)

    update_state(
        conversation_id,
        last_intent="faq_rag",
        last_topic=signals.get("topic"),
        last_product=signals.get("product"),
        pending_followup=bool(signals.get("pending_followup")),
        last_answer=answer,
        last_question=q,
    )
    return s


def smalltalk_node(s: BotState) -> BotState:
    conversation_id, business_config = _ensure_business_context(s)
    msg = s["user_message"]

    resp = s.get("response") or smalltalk_answer(conversation_id, msg, business_config)

    s["response"] = resp
    add_ai_message(conversation_id, resp)
    update_state(conversation_id, last_intent="smalltalk")
    return s


def handoff_node(s: BotState) -> BotState:
    conversation_id, business_config = _ensure_business_context(s)
    lead_q = business_config["lead_questions"]["model"]

    response = f"¡Genial! ✨ Para ayudarte mejor:\n\n{lead_q}"

    s["response"] = response
    add_ai_message(conversation_id, response)

    update_state(
        conversation_id,
        last_intent="handoff",
        pending_followup=True,
        lead_stage="await_model",
        lead_model=None,
        lead_district=None,
        lead_payment=None,
    )
    return s


def lead_flow_node(s: BotState) -> BotState:
    user_phone = s["user_id"]
    conversation_id, business_config = _ensure_business_context(s)
    msg = (s["user_message"] or "").strip()

    from oberoende_bot.app.services.user_profile_store_sqlite import get_name
    from oberoende_bot.app.services.leads_store import save_lead
    from oberoende_bot.app.services.email_service import notify_owner_lead

    # ── Leer estado UNA sola vez al inicio del nodo ───────────────────────────
    st = get_state(conversation_id)
    profile_name = get_name(conversation_id) or "Cliente"
    stage = st.lead_stage or "await_model"

    # ── Cancelación ──────────────────────────────────────────────────────────
    if msg.lower() in {"cancelar", "salir", "no"}:
        resp = "Entendido ✅ Si deseas retomar la compra, escríbeme nuevamente."
        s["response"] = resp
        add_ai_message(conversation_id, resp)
        update_state(
            conversation_id,
            pending_followup=False,
            lead_stage=None,
            lead_model=None,
            lead_district=None,
            lead_payment=None,
        )
        return s

    # ── Etapa 1: recibir modelo ───────────────────────────────────────────────
    if stage == "await_model":
        update_state(conversation_id, lead_model=msg, lead_stage="await_district")
        resp = business_config["lead_questions"]["district"]
        s["response"] = resp
        add_ai_message(conversation_id, resp)
        return s

    # ── Etapa 2: recibir distrito ─────────────────────────────────────────────
    if stage == "await_district":
        update_state(conversation_id, lead_district=msg, lead_stage="await_payment")
        resp = business_config["lead_questions"]["payment"]
        s["response"] = resp
        add_ai_message(conversation_id, resp)
        return s

    # ── Etapa 3: recibir pago y guardar lead ──────────────────────────────────
    if stage == "await_payment":
        update_state(conversation_id, lead_payment=msg)
        st_final = get_state(conversation_id)  # lectura única después del write

        product  = st_final.lead_model    or ""
        district = st_final.lead_district or ""
        payment  = st_final.lead_payment  or ""

        save_lead(
            user_id=user_phone,
            channel="whatsapp",
            name=profile_name,
            product=product,
            district=district,
            payment_method=payment,
            raw_message=(
                f"Negocio: {business_config['name']}\n"
                f"Modelo: {product}\n"
                f"Distrito: {district}\n"
                f"Pago: {payment}"
            ),
        )

        lead_text_email = (
            "NUEVO LEAD\n\n"
            f"Negocio: {business_config['name']}\n"
            f"Cliente (WhatsApp): {user_phone}\n"
            f"Nombre: {profile_name}\n"
            f"Modelo: {product}\n"
            f"Distrito: {district}\n"
            f"Pago: {payment}\n"
        )
        try:
            notify_owner_lead(
                user_id=user_phone,
                channel="whatsapp",
                lead_text=lead_text_email,
                subject=business_config.get("lead_email_subject"),
            )
        except Exception as e:
            print("⚠️ Error enviando email:", repr(e))

        resp = (
            "¡Listo! ✅ Ya registré tus datos.\n"
            "Un asesor te contactará en breve para ayudarte con tu compra."
        )
        s["response"] = resp
        add_ai_message(conversation_id, resp)

        update_state(
            conversation_id,
            pending_followup=False,
            lead_stage=None,
            lead_model=None,
            lead_district=None,
            lead_payment=None,
        )
        return s

    # ── Fallback: estado inesperado, reiniciar flujo ──────────────────────────
    resp = f"Vamos de nuevo 🙂 {business_config['lead_questions']['model']}"
    s["response"] = resp
    add_ai_message(conversation_id, resp)
    update_state(conversation_id, lead_stage="await_model")
    return s


def router(s: BotState) -> str:
    conversation_id, _ = _ensure_business_context(s)
    decision = s.get("decision")
    st = get_state(conversation_id)

    if st.last_intent == "handoff" and st.pending_followup and st.lead_stage:
        return "lead_flow"

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
    g.add_node("lead_flow", lead_flow_node)

    g.set_entry_point("decide")

    g.add_conditional_edges("decide", router, {
        "lead_flow": "lead_flow",
        "followup": "followup",
        "rag": "rag",
        "smalltalk": "smalltalk",
        "handoff": "handoff",
        "catalog": "catalog",
    })

    g.add_edge("followup", END)
    g.add_edge("rag", END)
    g.add_edge("smalltalk", END)
    g.add_edge("handoff", END)
    g.add_edge("catalog", END)
    g.add_edge("lead_flow", END)

    return g.compile()


graph = build_graph()