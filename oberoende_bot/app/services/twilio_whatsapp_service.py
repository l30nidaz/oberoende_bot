import os
from fastapi import Request, Response
from fastapi.responses import PlainTextResponse
from twilio.rest import Client


def _get_client():
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    return Client(account_sid, auth_token)


def _from_number():
    return os.getenv("TWILIO_WHATSAPP_FROM")


def _normalize_to_whatsapp(number: str) -> str:
    number = number.strip()
    if number.startswith("whatsapp:"):
        return number
    return f"whatsapp:{number}"


def send_whatsapp_text(to_number: str, body: str):
    client = _get_client()
    msg = client.messages.create(
        from_=_from_number(),
        to=_normalize_to_whatsapp(to_number),
        body=body,
    )
    return {"sid": msg.sid}


def send_whatsapp_image(to_number: str, image_url: str, caption: str | None = None):
    client = _get_client()
    msg = client.messages.create(
        from_=_from_number(),
        to=_normalize_to_whatsapp(to_number),
        body=caption or "",
        media_url=[image_url],
    )
    return {"sid": msg.sid}


def send_whatsapp_document(
    to_number: str,
    document_url: str,
    filename: str = "catalogo.pdf",
    caption: str | None = None,
):
    client = _get_client()
    msg = client.messages.create(
        from_=_from_number(),
        to=_normalize_to_whatsapp(to_number),
        body=caption or f"Adjunto: {filename}",
        media_url=[document_url],
    )
    return {"sid": msg.sid}


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
        "Envíame el nombre y te digo el precio, stock y tiempo de entrega.\n\n"
        "🚚 Hacemos envíos.\n"
        f"💳 Aceptamos {payment_methods}."
    )
    send_whatsapp_text(to_number, cta_text)


# ── Tipos multimedia con sus etiquetas en español ────────────────────────────
_MEDIA_FALLBACK_MSG = (
    "Vi que enviaste {media_type} 📎\n"
    "Por ahora solo puedo leer texto. Escríbeme el nombre del modelo "
    "que te interesa y te ayudo con precio, stock y detalles. ✨"
)

# Twilio indica el tipo mediante NumMedia > 0 y MediaContentType0
# Para mensajes de voz llega como audio/ogg o audio/mpeg
_CONTENT_TYPE_LABELS = {
    "image":    "una imagen",
    "video":    "un video",
    "audio":    "un audio",
    "document": "un documento",
}

# ── Constantes para mensajes de rate limit ────────────────────────────────────
_RATE_LIMIT_MSG = (
    "Estás enviando mensajes muy rápido 😅 "
    "Dame un momento y escríbeme de nuevo."
)


async def handle_incoming_whatsapp(request: Request):
    form = await request.form()

    from oberoende_bot.app.services.rate_limiter import is_rate_limited

    from_number_raw = form.get("From", "")
    to_number = form.get("To")
    message_body: str | None = form.get("Body") or None

    if not from_number_raw:
        return PlainTextResponse("ignored", status_code=200)

    user_id = str(from_number_raw).replace("whatsapp:", "").strip()
    channel_id = str(to_number or "").replace("whatsapp:", "").strip()

    # ── Punto 3: Rate limiting por usuario ────────────────────────────────────
    if is_rate_limited(user_id):
        try:
            send_whatsapp_text(user_id, _RATE_LIMIT_MSG)
        except Exception as e:
            print("⚠️ Error enviando aviso de rate limit (Twilio):", repr(e))
        return PlainTextResponse("rate_limited", status_code=200)

    # ── Punto 2: Fallback para mensajes multimedia ─────────────────────────────
    # Twilio indica adjuntos con NumMedia > 0.
    # Si el Body está vacío pero hay media, respondemos con texto explicativo.
    num_media = int(form.get("NumMedia", "0") or "0")
    if not message_body and num_media > 0:
        # Intentamos detectar el tipo para dar un mensaje más preciso
        content_type: str = form.get("MediaContentType0", "") or ""
        media_category = content_type.split("/")[0] if content_type else "unknown"
        label = _CONTENT_TYPE_LABELS.get(media_category, "un archivo multimedia")
        message_body = _MEDIA_FALLBACK_MSG.format(media_type=label)

    # Si sigue sin haber mensaje procesable, ignorar
    if not message_body:
        return PlainTextResponse("ignored", status_code=200)

    from oberoende_bot.app.graph.graph_engine import graph

    result = graph.invoke({
        "user_id": user_id,
        "channel_id": channel_id,
        "conversation_id": "",
        "business_id": "",
        "business_config": {},
        "user_message": message_body,
        "response": "",
        "decision": None,
    })

    response_text = result["response"]

    try:
        if response_text:
            send_whatsapp_text(user_id, response_text)
    except Exception as e:
        print("⚠️ Error enviando respuesta a WhatsApp Twilio:", repr(e))

    return Response(status_code=200)