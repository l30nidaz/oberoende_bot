import hashlib
import hmac
import os
import requests
from fastapi import Request
from fastapi.responses import JSONResponse


# ── Constantes de seguridad ──────────────────────────────────────────────────
# Máximo de caracteres que se pasan al LLM. Mensajes más largos se truncan
# silenciosamente — el usuario recibe respuesta normal, solo se recorta el input.
MAX_MESSAGE_LENGTH = 250


def _verify_hmac_signature(body_bytes: bytes, signature_header: str | None, app_secret: str) -> bool:
    """
    Verifica que el webhook viene realmente de Meta usando HMAC-SHA256.
    Meta firma cada request con tu App Secret y lo envía en el header
    X-Hub-Signature-256 como 'sha256=<hex_digest>'.

    Si WHATSAPP_APP_SECRET no está configurado, se omite la verificación
    (útil en desarrollo local con ngrok). En producción siempre debe estar.
    """

    if not app_secret:
        # Sin secret configurado → modo dev, se omite la verificación
        return True

    if not signature_header or not signature_header.startswith("sha256="):
        print("⚠️ HMAC: header X-Hub-Signature-256 ausente o malformado")
        return False

    expected = "sha256=" + hmac.new(
        app_secret.encode("utf-8"),
        body_bytes,
        hashlib.sha256,
    ).hexdigest()
    print(f"🔐 HMAC esperado: {expected}")
    print(f"🔐 HMAC recibido: {signature_header}")
    # Comparación en tiempo constante para evitar timing attacks
    return hmac.compare_digest(expected, signature_header)


def _get_config():
    token = os.getenv("WHATSAPP_TOKEN")
    phone_number_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
    graph_api_version = os.getenv("WHATSAPP_GRAPH_VERSION", "v25.0")
    base_url = f"https://graph.facebook.com/{graph_api_version}/{phone_number_id}/messages"
    return token, phone_number_id, graph_api_version, base_url


def _headers():
    token, _, _, _ = _get_config()
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def send_whatsapp_text(to_number: str, body: str):
    _, _, _, base_url = _get_config()

    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "text",
        "text": {
            "preview_url": True,
            "body": body,
        },
    }

    response = requests.post(base_url, headers=_headers(), json=payload, timeout=30)
    response.raise_for_status()
    return response.json()


def send_whatsapp_image(to_number: str, image_url: str, caption: str | None = None):
    _, _, _, base_url = _get_config()

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
    """
    Envía un mensaje interactivo con botones de respuesta rápida (máx. 3).
    Cuando el usuario toca un botón, WhatsApp envía su título como mensaje de texto,
    que el bot recibe igual que cualquier otro mensaje.
    """
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
                            "title": btn[:20],  # API limit: 20 chars
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


# ── Tipos de mensaje que el usuario puede mandar y que no son texto ───────────
_MEDIA_FALLBACK_MSG = (
    "Vi que enviaste {media_type} 📎\n"
    "Por ahora solo puedo leer texto. Escríbeme el nombre del modelo "
    "que te interesa y te ayudo con precio, stock y detalles. ✨"
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
    """
    Parsea el webhook de Meta y devuelve:
        (from_number, message_body, channel_id, message_id)

    - message_body es None si el tipo no es procesable como texto.
    - Si el mensaje es de tipo multimedia, message_body toma un texto de
      fallback para que el usuario reciba una respuesta explicativa en vez
      de silencio.
    - message_id se devuelve siempre que esté disponible para deduplicación.
    """
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
        message_id = msg.get("id")  # ← usado para deduplicación

        # Texto plano
        if msg_type == "text":
            body = msg["text"]["body"]
            return from_number, body, phone_number_id, message_id

        # Botones / listas interactivas
        if msg_type == "interactive":
            interactive = msg.get("interactive", {})
            if interactive.get("type") == "button_reply":
                return from_number, interactive["button_reply"]["title"], phone_number_id, message_id
            if interactive.get("type") == "list_reply":
                return from_number, interactive["list_reply"]["title"], phone_number_id, message_id

        # Multimedia u otro tipo: responde con mensaje explicativo
        # en vez de ignorar al usuario por completo.
        if msg_type in _MEDIA_TYPE_LABELS:
            label = _MEDIA_TYPE_LABELS[msg_type]
            fallback = _MEDIA_FALLBACK_MSG.format(media_type=label)
            return from_number, fallback, phone_number_id, message_id

        # Tipo completamente desconocido → ignorar
        return from_number, None, phone_number_id, message_id

    except Exception as e:
        print("⚠️ Error parseando webhook de Meta:", repr(e))
        return None, None, None, None


# ── Constantes para mensajes de rate limit ───────────────────────────────────
_RATE_LIMIT_MSG = (
    "Estás enviando mensajes muy rápido 😅 "
    "Dame un momento y escríbeme de nuevo."
)


async def handle_incoming_whatsapp(request: Request):
    # ── Verificación HMAC ─────────────────────────────────────────────────────
    # Leemos el body como bytes ANTES de parsearlo como JSON para poder
    # calcular el HMAC sobre los bytes crudos, tal como lo hace Meta.
    body_bytes = await request.body()

    
    # 1. Parsear payload primero
    import json
    try:
        payload = json.loads(body_bytes)
    except Exception:
        return JSONResponse({"status": "ignored"}, status_code=200)
    
    # 2. Extraer phone_number_id para identificar el negocio
    try:
        phone_number_id = payload["entry"][0]["changes"][0]["value"]["metadata"]["phone_number_id"]
    except Exception:
        phone_number_id = None
    
    # 3. Resolver negocio por channel_id
    from oberoende_bot.app.config.businesses import resolve_business_by_channel
    business_config = resolve_business_by_channel(phone_number_id)
    
    # 4. Verificar HMAC con el secret del negocio correspondiente
    app_secret = business_config.get("whatsapp_app_secret", "").strip()
    signature = request.headers.get("X-Hub-Signature-256")
    

    print(f"📱 phone_number_id recibido: {phone_number_id}")
    print(f"🏢 negocio resuelto: {business_config['business_id']}")
    print(f"🔑 secret usado: {app_secret[:8]}...")

    if app_secret and not _verify_hmac_signature(body_bytes, signature, app_secret):
        print(f"🚨 HMAC inválido para negocio {business_config['business_id']}")
        return JSONResponse({"status": "forbidden"}, status_code=403)
    

    from oberoende_bot.app.services.message_id_store import is_duplicate
    from oberoende_bot.app.services.rate_limiter import is_rate_limited

    from_number, message_body, channel_id, message_id = _extract_message(payload)

    # ── Descartar si no hay remitente ─────────────────────────────────────────
    if not from_number:
        return JSONResponse({"status": "ignored"}, status_code=200)

    # ── Punto 1: Deduplicación por message_id ─────────────────────────────────
    if message_id and is_duplicate(message_id):
        print(f"⚠️ Mensaje duplicado ignorado: {message_id}")
        return JSONResponse({"status": "duplicate"}, status_code=200)

    # ── Punto 3: Rate limiting por usuario ────────────────────────────────────
    if is_rate_limited(from_number):
        try:
            send_whatsapp_text(from_number, _RATE_LIMIT_MSG)
        except Exception as e:
            print("⚠️ Error enviando aviso de rate limit:", repr(e))
        return JSONResponse({"status": "rate_limited"}, status_code=200)

    # ── Punto 2: Si no hay cuerpo de mensaje procesable, ya viene el fallback ─
    # _extract_message ya rellenó message_body con texto explicativo para
    # mensajes multimedia. Si sigue siendo None es un tipo completamente
    # desconocido → ignorar silenciosamente.
    if not message_body:
        return JSONResponse({"status": "ignored"}, status_code=200)

    # ── Límite de tamaño de mensaje ──────────────────────────────────────────
    # Trunca mensajes excesivamente largos antes de pasarlos al LLM.
    # Protege contra payload bombing y reduce costos de tokens.
    if message_body and len(message_body) > MAX_MESSAGE_LENGTH:
        print(f"⚠️ Mensaje truncado: {len(message_body)} → {MAX_MESSAGE_LENGTH} chars")
        message_body = message_body[:MAX_MESSAGE_LENGTH]

    from oberoende_bot.app.graph.graph_engine import graph

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
    config={
        "metadata": {
            "conversation_id": from_number,
        }
    }
    )
    response_text = result["response"]

    try:
        if response_text:
            send_whatsapp_text(from_number, response_text)
    except Exception as e:
        print("⚠️ Error enviando respuesta a WhatsApp Meta:", repr(e))

    return JSONResponse({"status": "ok"}, status_code=200)