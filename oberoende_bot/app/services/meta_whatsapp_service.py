import os
import requests
from fastapi import Request
from fastapi.responses import JSONResponse

CATALOG_IMAGES = [
    "https://catalogo-oberoende-s3.s3.us-east-1.amazonaws.com/catalogo3.jpg",
    "https://catalogo-oberoende-s3.s3.us-east-1.amazonaws.com/catalogo1.jpg",
    "https://catalogo-oberoende-s3.s3.us-east-1.amazonaws.com/catalogo2.png",
]

CATALOG_PDF_URL = "https://catalogo-oberoende-s3.s3.us-east-1.amazonaws.com/catalogo.pdf"


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
            "body": body
        }
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
        "image": image_obj
    }

    response = requests.post(base_url, headers=_headers(), json=payload, timeout=30)
    response.raise_for_status()
    return response.json()


def send_whatsapp_document(
    to_number: str,
    document_url: str,
    filename: str = "catalogo.pdf",
    caption: str | None = None
):
    _, _, _, base_url = _get_config()

    document_obj = {
        "link": document_url,
        "filename": filename
    }
    if caption:
        document_obj["caption"] = caption

    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "document",
        "document": document_obj
    }

    response = requests.post(base_url, headers=_headers(), json=payload, timeout=30)
    response.raise_for_status()
    return response.json()


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


def _extract_text_message(payload: dict) -> tuple[str | None, str | None]:
    try:
        entry = payload["entry"][0]
        changes = entry["changes"][0]
        value = changes["value"]

        messages = value.get("messages")
        if not messages:
            return None, None

        msg = messages[0]
        from_number = msg.get("from")
        msg_type = msg.get("type")

        if msg_type == "text":
            body = msg["text"]["body"]
            return from_number, body

        if msg_type == "interactive":
            interactive = msg.get("interactive", {})
            if interactive.get("type") == "button_reply":
                return from_number, interactive["button_reply"]["title"]
            if interactive.get("type") == "list_reply":
                return from_number, interactive["list_reply"]["title"]

        return from_number, None
    except Exception as e:
        print("⚠️ Error parseando webhook de Meta:", repr(e))
        return None, None


async def handle_incoming_whatsapp(request: Request):
    payload = await request.json()
    print("📩 Webhook Meta recibido:", payload)

    from_number, message_body = _extract_text_message(payload)

    if not from_number or not message_body:
        return JSONResponse({"status": "ignored"}, status_code=200)

    from oberoende_bot.app.graph.graph_engine import graph

    result = graph.invoke({
        "user_id": from_number,
        "user_message": message_body,
        "response": "",
        "decision": None
    })

    response_text = result["response"]

    try:
        if response_text:
            send_whatsapp_text(from_number, response_text)
    except Exception as e:
        print("⚠️ Error enviando respuesta a WhatsApp Meta:", repr(e))

    return JSONResponse({"status": "ok"}, status_code=200)