import os
from fastapi import Request, Response
from fastapi.responses import PlainTextResponse
from twilio.rest import Client

CATALOG_IMAGES = [
    "https://catalogo-oberoende-s3.s3.us-east-1.amazonaws.com/catalogo3.jpg",
    "https://catalogo-oberoende-s3.s3.us-east-1.amazonaws.com/catalogo1.jpg",
    "https://catalogo-oberoende-s3.s3.us-east-1.amazonaws.com/catalogo2.png",
]

CATALOG_PDF_URL = "https://catalogo-oberoende-s3.s3.us-east-1.amazonaws.com/catalogo.pdf"


def _get_client():
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    return Client(account_sid, auth_token)


def _from_number():
    # Ejemplo: whatsapp:+14155238886
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
    caption: str | None = None
):
    client = _get_client()
    msg = client.messages.create(
        from_=_from_number(),
        to=_normalize_to_whatsapp(to_number),
        body=caption or f"Adjunto: {filename}",
        media_url=[document_url],
    )
    return {"sid": msg.sid}


def send_catalog_whatsapp(to_number: str):
    for idx, image_url in enumerate(CATALOG_IMAGES):
        caption = "✨ Aquí tienes parte de nuestro catálogo" if idx == 0 else None
        send_whatsapp_image(to_number, image_url, caption=caption)

    send_whatsapp_document(
        to_number,
        CATALOG_PDF_URL,
        filename="catalogo_oberoende.pdf",
        caption="📄 Aquí tienes el catálogo completo en PDF"
    )

    cta_text = (
        f"📄 También puedes descargar el catálogo aquí:\n{CATALOG_PDF_URL}\n\n"
        "✨ ¿Qué modelo te gustó?\n"
        "Envíame el nombre o una captura y te digo el precio, stock y tiempo de entrega.\n\n"
        "🚚 Hacemos envíos.\n"
        "💳 Aceptamos Yape, Plin y transferencia."
    )
    send_whatsapp_text(to_number, cta_text)


async def handle_incoming_whatsapp(request: Request):
    form = await request.form()

    from_number = form.get("From")
    message_body = form.get("Body")

    if not from_number or not message_body:
        return PlainTextResponse("ignored", status_code=200)

    # Twilio envía "whatsapp:+51999..."
    user_id = str(from_number).replace("whatsapp:", "").strip()

    from oberoende_bot.app.graph.graph_engine import graph

    result = graph.invoke({
        "user_id": user_id,
        "user_message": message_body,
        "response": "",
        "decision": None
    })

    response_text = result["response"]

    try:
        if response_text:
            send_whatsapp_text(user_id, response_text)
    except Exception as e:
        print("⚠️ Error enviando respuesta a WhatsApp Twilio:", repr(e))

    return Response(status_code=200)