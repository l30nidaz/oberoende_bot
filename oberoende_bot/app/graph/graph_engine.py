# oberoende_bot/app/graph/graph_engine.py
from langgraph.graph import StateGraph, END
from typing import TypedDict, Optional, Any
import re

from oberoende_bot.app.config.businesses import resolve_business_by_channel
from oberoende_bot.app.services.brain_router import interpret_message
from oberoende_bot.app.services.smalltalk_service import smalltalk_answer, main_menu
from oberoende_bot.app.services.rag_answer_service import ask_rag_answer
from oberoende_bot.app.services.memory_service import add_user_message, add_ai_message
from oberoende_bot.app.services.state_store_sqlite import (
    get_state, update_state, state_dict, reset_if_expired,
)
from oberoende_bot.app.services.name_extractor import extract_name
from oberoende_bot.app.services.user_profile_store_sqlite import set_name, get_name


# =============================================================================
# Estado del grafo
# =============================================================================

class BotState(TypedDict):
    user_id:         str             # teléfono del cliente
    channel_id:      str             # phone_number_id de Meta o número Twilio
    conversation_id: str             # "{business_id}:{user_id}"
    business_id:     str
    business_config: dict[str, Any]
    user_message:    str
    response:        str
    decision:        Optional[str]


# =============================================================================
# Helpers internos
# =============================================================================

def _normalize(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[^\w\sáéíóúñü]", "", text)
    return text


def _ensure_business_context(s: BotState) -> tuple[str, dict]:
    """Rellena business_config y conversation_id si aún están vacíos."""
    business_config = s.get("business_config") or resolve_business_by_channel(s.get("channel_id"))
    business_id     = business_config["business_id"]
    conversation_id = s.get("conversation_id") or f"{business_id}:{s['user_id']}"

    s["business_id"]     = business_id
    s["business_config"] = business_config
    s["conversation_id"] = conversation_id
    return conversation_id, business_config


def _is_appt_response(msg: str, stage: str) -> bool:
    """
    Pregunta al LLM si el mensaje es una respuesta genuina a la pregunta
    del flujo de cita (servicio / fecha / hora / confirmación) o si es
    una pregunta/desvío. Devuelve True si ES una respuesta al flujo.
    Evita que "¿dónde están?" avance el appt_stage.
    """
    from langchain_openai import ChatOpenAI
    import os

    stage_labels = {
        "await_service": "qué servicio o tipo de consulta necesita",
        "await_date":    "qué día quiere la cita",
        "await_time":    "qué hora prefiere",
        "await_confirm": "si confirma o cancela la cita (sí/no)",
        "await_cancel":  "su nombre o número de confirmación para cancelar",
    }
    expected = stage_labels.get(stage, "una pregunta del proceso de cita")

    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0,
        api_key=os.getenv("OPENAI_API_KEY"),
    )

    prompt = (
        f"Estás en un chatbot de citas. Se le preguntó al usuario: '{expected}'.\n"
        f"El usuario respondió: '{msg}'\n\n"
        "¿Es esto una respuesta directa a la pregunta o es una pregunta/comentario diferente?\n"
        "Responde SOLO con: RESPUESTA o PREGUNTA"
    )

    result = llm.invoke(prompt).content.strip().upper()
    print(f"[APPT_GATE] stage={stage} msg='{msg}' → {result}")
    return result == "RESPUESTA"


# =============================================================================
# Nodos del grafo
# =============================================================================

def decide_node(s: BotState) -> BotState:
    """
    Nodo de entrada. Registra el mensaje, verifica sesión expirada,
    extrae el nombre si viene en el mensaje y delega al router LLM
    para obtener la decisión de routing.
    """
    msg = s["user_message"]
    conversation_id, business_config = _ensure_business_context(s)
    add_user_message(conversation_id, msg)

    # ── 1. Timeout de sesión ──────────────────────────────────────────────────
    # Si el usuario vuelve tras varias horas, reseteamos el flujo y mostramos
    # el menú de bienvenida para que no quede atascado en una cita a medias.
    if reset_if_expired(conversation_id):
        name = get_name(conversation_id)
        resp = main_menu(business_config, name)
        s["response"] = resp
        s["decision"] = "smalltalk"
        add_ai_message(conversation_id, resp)
        return s

    current_state = get_state(conversation_id)
    print(f"[DECIDE] msg='{msg}' | last_intent={current_state.last_intent} | appt_stage={current_state.appt_stage} | pending_followup={current_state.pending_followup}")

    # ── 2. Si hay un flujo de cita en curso, ir directo sin pasar por LLM ────
    # El usuario está en medio de agendar o cancelar. Cualquier mensaje suyo
    # (incluso "el martes", "10am", "sí") debe ir al appointment_flow_node.
    if current_state.appt_stage:
        s["decision"] = None  # router() lo enviará a appointment_flow
        return s

    # ── 3. Extracción de nombre ───────────────────────────────────────────────
    name = extract_name(msg)
    if name:
        set_name(conversation_id, name)
        resp = main_menu(business_config, name)
        s["response"] = resp
        s["decision"] = "smalltalk"
        add_ai_message(conversation_id, resp)
        update_state(conversation_id, pending_followup=False)
        return s

    # ── 4. Opciones numéricas del menú principal ──────────────────────────────
    norm = _normalize(msg)
    if not current_state.pending_followup:
        menu_routing = business_config.get("menu_routing", {})
        if norm.replace("️⃣","").strip() in menu_routing:
            s["decision"] = menu_routing[norm.replace("️⃣","").strip()]
            return s

    # ── 5. Router LLM para todo lo demás ─────────────────────────────────────
    state_for_router = state_dict(conversation_id)
    decision = interpret_message(msg, state_for_router, business_config)
    print(f"[ROUTER LLM] msg='{msg}' → decision='{decision}'")
    s["decision"] = decision
    return s


def appointment_flow_node(s: BotState) -> BotState:
    """
    Maneja el flujo conversacional de agendamiento paso a paso:
      await_service → await_date → await_time → await_confirm → (cita creada)

    También maneja el flujo de cancelación:
      await_cancel → (cita cancelada)

    El gate semántico (_is_appt_response) detecta si el usuario hizo una
    pregunta fuera de contexto y la responde sin perder el flujo.
    """
    user_phone = s["user_id"]
    conversation_id, business_config = _ensure_business_context(s)
    msg = (s["user_message"] or "").strip()
    msg_lower = msg.lower()

    from oberoende_bot.app.services.email_service import notify_owner_lead

    st           = get_state(conversation_id)
    profile_name = get_name(conversation_id) or "Cliente"
    stage        = st.appt_stage or "await_service"
    questions    = business_config["appointment_questions"]

    # ── Cancelación explícita del flujo ──────────────────────────────────────
    if msg_lower in {"cancelar", "salir", "no quiero", "olvidalo", "olvídalo"}:
        resp = "Entendido ✅ Cuando quieras, escríbeme para agendar una cita."
        s["response"] = resp
        add_ai_message(conversation_id, resp)
        update_state(
            conversation_id,
            pending_followup=False,
            appt_stage=None, appt_service=None,
            appt_date=None, appt_time=None, appt_event_id=None,
        )
        return s

    # ── Gate semántico ────────────────────────────────────────────────────────
    # Si el usuario desvía la conversación con una pregunta, la respondemos
    # con RAG y recordamos en qué etapa estábamos.
    if not _is_appt_response(msg, stage):
        answer, _ = ask_rag_answer(msg, conversation_id, business_config)
        stage_reminders = {
            "await_service": questions["service"],
            "await_date":    questions["date"],
            "await_time":    "¿Qué hora prefieres?",
            "await_confirm": questions["confirm"].format(
                date=st.appt_date or "?",
                time=st.appt_time or "?",
                service=st.appt_service or "?",
            ),
            "await_cancel":  questions["cancel_ask"],
        }
        reminder = stage_reminders.get(stage, "")
        resp = f"{answer}\n\n---\n📋 Cuando quieras continuar:\n{reminder}"
        s["response"] = answer
        add_ai_message(conversation_id, resp)
        return s

    # ── Flujo de cancelación ──────────────────────────────────────────────────
    if stage == "await_cancel":
        # Por ahora guardamos el identificador que dio el usuario.
        # Cuando integremos Google Calendar, aquí buscaremos y eliminaremos el evento.
        resp = questions["cancel_success"]
        s["response"] = resp
        add_ai_message(conversation_id, resp)
        update_state(
            conversation_id,
            pending_followup=False, last_intent="cancel_appointment",
            appt_stage=None, appt_service=None,
            appt_date=None, appt_time=None, appt_event_id=None,
        )
        return s

    # ── Flujo de agendamiento ─────────────────────────────────────────────────

    # Etapa 1: recibir servicio
    if stage == "await_service":
        update_state(conversation_id, appt_service=msg, appt_stage="await_date")
        resp = questions["date"]
        s["response"] = resp
        add_ai_message(conversation_id, resp)
        return s

    # Etapa 2: recibir fecha y mostrar slots disponibles
    if stage == "await_date":
        # TODO: cuando integremos calendar_service, aquí consultaremos
        # los slots reales de Google Calendar para la fecha dada.
        # Por ahora mostramos los horarios configurados en businesses.py.
        hours = business_config.get("appointment_hours", [])
        slots = "\n".join(f"{i+1}️⃣ {h}" for i, h in enumerate(hours)) if hours else "No hay horarios configurados."
        resp = questions["time"].format(date=msg, slots=slots)
        update_state(conversation_id, appt_date=msg, appt_stage="await_time")
        s["response"] = resp
        add_ai_message(conversation_id, resp)
        return s

    # Etapa 3: recibir hora y pedir confirmación
    if stage == "await_time":
        # El usuario puede responder con un número ("2") o con la hora ("14:00").
        # Intentamos resolver el número al horario correspondiente.
        hours = business_config.get("appointment_hours", [])
        chosen_time = msg
        if msg.strip().isdigit():
            idx = int(msg.strip()) - 1
            if 0 <= idx < len(hours):
                chosen_time = hours[idx]

        update_state(conversation_id, appt_time=chosen_time, appt_stage="await_confirm")
        resp = questions["confirm"].format(
            date=st.appt_date or msg,
            time=chosen_time,
            service=st.appt_service or "",
        )
        s["response"] = resp
        add_ai_message(conversation_id, resp)
        return s

    # Etapa 4: confirmación final → crear la cita
    if stage == "await_confirm":
        norm = _normalize(msg)

        if norm in {"no", "nop", "nope", "nel"}:
            resp = "Sin problema ✅ Escríbeme cuando quieras intentar con otra fecha u hora."
            s["response"] = resp
            add_ai_message(conversation_id, resp)
            update_state(
                conversation_id,
                pending_followup=False,
                appt_stage=None, appt_service=None,
                appt_date=None, appt_time=None,
            )
            return s

        # Confirmado: guardar cita
        # TODO: aquí llamaremos a calendar_service.create_event() cuando esté listo.
        st_final = get_state(conversation_id)
        service  = st_final.appt_service or ""
        date     = st_final.appt_date    or ""
        time     = st_final.appt_time    or ""

        # Notificación por email al dueño del negocio
        email_text = (
            "NUEVA CITA AGENDADA\n\n"
            f"Negocio:  {business_config['name']}\n"
            f"Cliente:  {user_phone}\n"
            f"Nombre:   {profile_name}\n"
            f"Servicio: {service}\n"
            f"Fecha:    {date}\n"
            f"Hora:     {time}\n"
        )
        try:
            notify_owner_lead(
                user_id=user_phone,
                channel="whatsapp",
                lead_text=email_text,
                subject=business_config.get("lead_email_subject"),
            )
        except Exception as e:
            print("⚠️ Error enviando email de cita:", repr(e))

        resp = questions["success"].format(date=date, time=time, service=service)
        s["response"] = resp
        add_ai_message(conversation_id, resp)
        update_state(
            conversation_id,
            last_intent="appointment",
            pending_followup=False,
            appt_stage=None, appt_service=None,
            appt_date=None, appt_time=None,
        )
        return s

    # ── Fallback: estado inesperado, reiniciar flujo ──────────────────────────
    resp = f"Vamos de nuevo 🙂\n\n{questions['service']}"
    s["response"] = resp
    add_ai_message(conversation_id, resp)
    update_state(conversation_id, appt_stage="await_service")
    return s


def rag_node(s: BotState) -> BotState:
    """Responde preguntas informativas usando el vectorstore del negocio."""
    conversation_id, business_config = _ensure_business_context(s)
    q = s["user_message"]

    answer, signals = ask_rag_answer(q, conversation_id, business_config)
    s["response"] = answer
    add_ai_message(conversation_id, answer)

    update_state(
        conversation_id,
        last_intent="faq_rag",
        last_topic=signals.get("topic"),
        last_answer=answer,
        last_question=q,
        pending_followup=bool(signals.get("pending_followup")),
    )
    return s


def smalltalk_node(s: BotState) -> BotState:
    """Maneja saludos, agradecimientos y charla casual."""
    conversation_id, business_config = _ensure_business_context(s)
    msg = s["user_message"]

    resp = s.get("response") or smalltalk_answer(conversation_id, msg, business_config)
    s["response"] = resp
    add_ai_message(conversation_id, resp)
    update_state(conversation_id, last_intent="smalltalk", pending_followup=False)
    return s


def handoff_node(s: BotState) -> BotState:
    """Informa al usuario que será atendido por una persona."""
    conversation_id, business_config = _ensure_business_context(s)

    resp = (
        f"Entendido 👋 En breve un miembro del equipo de {business_config['name']} "
        "te atenderá personalmente.\n\n"
        "Si prefieres, también puedo ayudarte a *agendar una cita* ahora mismo. "
        "¿Te gustaría hacerlo?"
    )
    s["response"] = resp
    add_ai_message(conversation_id, resp)
    update_state(conversation_id, last_intent="handoff", pending_followup=False)
    return s


def cancel_appointment_node(s: BotState) -> BotState:
    """Inicia el flujo de cancelación de cita."""
    conversation_id, business_config = _ensure_business_context(s)
    questions = business_config["appointment_questions"]

    resp = questions["cancel_ask"]
    s["response"] = resp
    add_ai_message(conversation_id, resp)
    update_state(
        conversation_id,
        last_intent="cancel_appointment",
        pending_followup=True,
        appt_stage="await_cancel",
    )
    return s


# =============================================================================
# Router — decide a qué nodo va después de decide_node
# =============================================================================

def router(s: BotState) -> str:
    conversation_id, _ = _ensure_business_context(s)
    decision  = s.get("decision")
    st        = get_state(conversation_id)

    print(f"[ROUTER] decision={decision} | last_intent={st.last_intent} | appt_stage={st.appt_stage}")

    # Si hay un flujo de cita activo (agendando o cancelando), prioridad absoluta
    if st.appt_stage:
        print("[ROUTER] → appointment_flow (stage activo)")
        return "appointment_flow"

    if decision == "appointment":
        return "appointment_flow"

    if decision == "cancel_appointment":
        return "cancel_appointment"

    if decision == "handoff":
        return "handoff"

    if decision == "faq_rag":
        return "rag"

    if decision == "smalltalk":
        return "smalltalk"

    # Fallback seguro
    print("[ROUTER] → rag (fallback)")
    return "rag"


# =============================================================================
# Construcción del grafo
# =============================================================================

def build_graph():
    g = StateGraph(BotState)

    g.add_node("decide",             decide_node)
    g.add_node("appointment_flow",   appointment_flow_node)
    g.add_node("cancel_appointment", cancel_appointment_node)
    g.add_node("rag",                rag_node)
    g.add_node("smalltalk",          smalltalk_node)
    g.add_node("handoff",            handoff_node)

    g.set_entry_point("decide")

    g.add_conditional_edges("decide", router, {
        "appointment_flow":   "appointment_flow",
        "cancel_appointment": "cancel_appointment",
        "rag":                "rag",
        "smalltalk":          "smalltalk",
        "handoff":            "handoff",
    })

    g.add_edge("appointment_flow",   END)
    g.add_edge("cancel_appointment", END)
    g.add_edge("rag",                END)
    g.add_edge("smalltalk",          END)
    g.add_edge("handoff",            END)

    return g.compile()


graph = build_graph()