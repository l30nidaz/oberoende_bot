import asyncio
import hashlib
import hmac
import os
import requests
from fastapi import Request
from fastapi.responses import JSONResponse


# ── Constantes de seguridad ──────────────────────────────────────────────────
MAX_MESSAGE_LENGTH = 250


def _verify_hmac_signature(body_bytes: bytes, signature_header: str | None, app_secret: str) -> bool:
    if not app_secret:
        return True

    if not signature_header or not signature_header.startswith("sha256="):
        print("⚠️ HMAC: header X-Hub-Signature-256 ausente o malformado")
        return False

    expected = "sha256=" + hmac.new(
        app_secret.encode("utf-8"),
        body_bytes,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature_header)


def _get_config(business_config: dict = None):
    token = os.getenv("WHATSAPP_TOKEN")
    graph_api_version = os.getenv("WHATSAPP_GRAPH_VERSION", "v25.0")

    default_bid = os.getenv("DEFAULT_BUSINESS_ID", "").strip().upper()
    phone_number_id = (
        os.getenv(f"{default_bid}_META_PHONE_NUMBER_ID", "").strip()
        or os.getenv("WHATSAPP_PHONE_NUMBER_ID", "").strip()
    )

    base_url = f"https://graph.facebook.com/{graph_api_version}/{phone_number_id}/messages"
    return token, phone_number_id, graph_api_version, base_url


def _headers(business_config: dict = None):
    token, _, _, _ = _get_config(business_config)
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def send_whatsapp_text(to_number: str, body: str, business_config: dict = None):
    _, _, _, base_url = _get_config(business_config)
    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "text",
        "text": {
            "preview_url": True,
            "body": body,
        },
    }
    response = requests.post(base_url, headers=_headers(business_config), json=payload, timeout=30)
    response.raise_for_status()
    return response.json()


def send_whatsapp_image(to_number: str, image_url: str, caption: str | None = None, business_config: dict = None):
    _, _, _, base_url = _get_config(business_config)

    image_obj = {"link": image_url}
    if caption:
        image_obj["caption"] = caption

    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "image",
        "image": image_obj,
    }

    response = requests.post(base_url, headers=_headers(), json=payload, timeout=30)
    response.raise_for_status()
    return response.json()


def send_whatsapp_document(
    to_number: str,
    document_url: str,
    filename: str = "catalogo.pdf",
    caption: str | None = None,
):
    _, _, _, base_url = _get_config()

    document_obj = {"link": document_url, "filename": filename}
    if caption:
        document_obj["caption"] = caption

    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "document",
        "document": document_obj,
    }

    response = requests.post(base_url, headers=_headers(), json=payload, timeout=30)
    response.raise_for_status()
    return response.json()


def send_whatsapp_buttons(to_number: str, body: str, buttons: list[str]):
    _, _, _, base_url = _get_config()

    if len(buttons) > 3:
        buttons = buttons[:3]

    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": body},
            "action": {
                "buttons": [
                    {
                        "type": "reply",
                        "reply": {
                            "id": f"btn_{i}",
                            "title": btn[:20],
                        },
                    }
                    for i, btn in enumerate(buttons)
                ]
            },
        },
    }

    response = requests.post(base_url, headers=_headers(), json=payload, timeout=30)
    response.raise_for_status()
    return response.json()


def send_catalog_whatsapp(to_number: str, business_config: dict):
    catalog_images = business_config.get("catalog_images", [])
    catalog_pdf_url = business_config.get("catalog_pdf_url", "")
    business_name = business_config.get("name", "la tienda")
    payment_methods = ", ".join(business_config.get("payment_methods", []))

    for idx, image_url in enumerate(catalog_images):
        caption = f"✨ Aquí tienes parte del catálogo de {business_name}" if idx == 0 else None
        send_whatsapp_image(to_number, image_url, caption=caption)

    if catalog_pdf_url:
        send_whatsapp_document(
            to_number,
            catalog_pdf_url,
            filename=f"catalogo_{business_name.lower().replace(' ', '_')}.pdf",
            caption=f"📄 Aquí tienes el catálogo completo de {business_name}",
        )

    cta_text = (
        f"📄 También puedes descargar el catálogo aquí:\n{catalog_pdf_url}\n\n"
        "✨ ¿Qué modelo te gustó?\n"
        "Escríbeme el nombre y te digo el precio, stock y tiempo de entrega.\n\n"
        "🚚 Hacemos envíos.\n"
        f"💳 Aceptamos {payment_methods}."
    )
    send_whatsapp_text(to_number, cta_text)


# ── Tipos de mensaje ──────────────────────────────────────────────────────────
_MEDIA_FALLBACK_MSG = (
    "Vi que enviaste {media_type} 📎\n"
    "Por ahora solo puedo leer texto. Escríbeme tu consulta y te ayudo. ✨"
)

_MEDIA_TYPE_LABELS = {
    "image":    "una imagen",
    "video":    "un video",
    "audio":    "un audio",
    "document": "un documento",
    "sticker":  "un sticker",
    "location": "una ubicación",
    "contacts": "un contacto",
}


def _extract_message(payload: dict) -> tuple[str | None, str | None, str | None, str | None]:
    try:
        entry = payload["entry"][0]
        changes = entry["changes"][0]
        value = changes["value"]

        metadata = value.get("metadata", {})
        phone_number_id = metadata.get("phone_number_id")

        messages = value.get("messages")
        if not messages:
            return None, None, phone_number_id, None

        msg = messages[0]
        from_number = msg.get("from")
        msg_type = msg.get("type")
        message_id = msg.get("id")

        if msg_type == "text":
            body = msg["text"]["body"]
            return from_number, body, phone_number_id, message_id

        if msg_type == "interactive":
            interactive = msg.get("interactive", {})
            if interactive.get("type") == "button_reply":
                return from_number, interactive["button_reply"]["title"], phone_number_id, message_id
            if interactive.get("type") == "list_reply":
                return from_number, interactive["list_reply"]["title"], phone_number_id, message_id

        if msg_type in _MEDIA_TYPE_LABELS:
            label = _MEDIA_TYPE_LABELS[msg_type]
            fallback = _MEDIA_FALLBACK_MSG.format(media_type=label)
            return from_number, fallback, phone_number_id, message_id

        return from_number, None, phone_number_id, message_id

    except Exception as e:
        print("⚠️ Error parseando webhook de Meta:", repr(e))
        return None, None, None, None


_RATE_LIMIT_MSG = (
    "Estás enviando mensajes muy rápido 😅 "
    "Dame un momento y escríbeme de nuevo."
)


# ── Procesamiento en background ───────────────────────────────────────────────

async def _process_message(
    from_number: str,
    channel_id: str,
    message_body: str,
    business_config: dict,
):
    """
    Ejecuta el grafo y envía la respuesta al usuario.
    Se llama como background task para que Meta reciba el 200 OK
    antes de los 5 segundos y no reintente el webhook.
    """
    from oberoende_bot.app.graph.graph_engine import graph

    try:
        result = graph.invoke(
            {
                "user_id": from_number,
                "channel_id": channel_id or "",
                "conversation_id": "",
                "business_id": "",
                "business_config": {},
                "user_message": message_body,
                "response": "",
                "decision": None,
            },
            config={"metadata": {"conversation_id": from_number}},
        )
        response_text = result["response"]

        if response_text:
            send_whatsapp_text(from_number, response_text, business_config=business_config)

    except Exception as e:
        print("⚠️ Error en _process_message:", repr(e))


# ── Handler principal ─────────────────────────────────────────────────────────

async def handle_incoming_whatsapp(request: Request):
    # 1. Leer body como bytes para HMAC
    body_bytes = await request.body()

    # 2. Parsear JSON
    import json
    try:
        payload = json.loads(body_bytes)
    except Exception:
        return JSONResponse({"status": "ignored"}, status_code=200)

    # 3. Extraer phone_number_id y resolver negocio
    try:
        phone_number_id = payload["entry"][0]["changes"][0]["value"]["metadata"]["phone_number_id"]
    except Exception:
        phone_number_id = None

    from oberoende_bot.app.config.businesses import resolve_business_by_channel
    business_config = resolve_business_by_channel(phone_number_id)

    # 4. Verificar HMAC
    app_secret = os.getenv("WHATSAPP_APP_SECRET", "").strip()
    signature = request.headers.get("X-Hub-Signature-256")

    print(f"📱 phone_number_id recibido: {phone_number_id}")
    print(f"🏢 negocio resuelto: {business_config['business_id']}")
    print(f"🔑 secret usado: {app_secret[:8]}...")

    if app_secret and not _verify_hmac_signature(body_bytes, signature, app_secret):
        print(f"🚨 HMAC inválido para negocio {business_config['business_id']}")
        return JSONResponse({"status": "forbidden"}, status_code=403)

    # 5. Extraer datos del mensaje
    from oberoende_bot.app.services.message_id_store import is_duplicate
    from oberoende_bot.app.services.rate_limiter import is_rate_limited

    from_number, message_body, channel_id, message_id = _extract_message(payload)

    if not from_number:
        return JSONResponse({"status": "ignored"}, status_code=200)

    # 6. Deduplicación
    if message_id and is_duplicate(message_id):
        print(f"⚠️ Mensaje duplicado ignorado: {message_id}")
        return JSONResponse({"status": "duplicate"}, status_code=200)

    # 7. Rate limiting
    if is_rate_limited(from_number):
        try:
            send_whatsapp_text(from_number, _RATE_LIMIT_MSG)
        except Exception as e:
            print("⚠️ Error enviando aviso de rate limit:", repr(e))
        return JSONResponse({"status": "rate_limited"}, status_code=200)

    # 8. Ignorar si no hay mensaje procesable
    if not message_body:
        return JSONResponse({"status": "ignored"}, status_code=200)

    # 9. Truncar mensajes muy largos
    if len(message_body) > MAX_MESSAGE_LENGTH:
        print(f"⚠️ Mensaje truncado: {len(message_body)} → {MAX_MESSAGE_LENGTH} chars")
        message_body = message_body[:MAX_MESSAGE_LENGTH]

    # 10. Lanzar procesamiento en background y responder 200 inmediatamente
    # Meta exige respuesta en < 5 segundos o reintenta el webhook.
    # El grafo (LLM + SQLite) puede tardar 2-8 segundos, por eso lo desacoplamos.
    asyncio.create_task(
        _process_message(from_number, channel_id, message_body, business_config)
    )

    return JSONResponse({"status": "ok"}, status_code=200)