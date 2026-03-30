from fastapi import Request

from oberoende_bot.app.services.provider_config import get_whatsapp_provider


def send_whatsapp_text(to_number: str, body: str):
    provider = get_whatsapp_provider()
    if provider == "twilio":
        from oberoende_bot.app.services.twilio_whatsapp_service import send_whatsapp_text as impl
    else:
        from oberoende_bot.app.services.meta_whatsapp_service import send_whatsapp_text as impl
    return impl(to_number, body)


def send_whatsapp_image(to_number: str, image_url: str, caption: str | None = None):
    provider = get_whatsapp_provider()
    if provider == "twilio":
        from oberoende_bot.app.services.twilio_whatsapp_service import send_whatsapp_image as impl
    else:
        from oberoende_bot.app.services.meta_whatsapp_service import send_whatsapp_image as impl
    return impl(to_number, image_url, caption)


def send_whatsapp_document(
    to_number: str,
    document_url: str,
    filename: str = "catalogo.pdf",
    caption: str | None = None
):
    provider = get_whatsapp_provider()
    if provider == "twilio":
        from oberoende_bot.app.services.twilio_whatsapp_service import send_whatsapp_document as impl
    else:
        from oberoende_bot.app.services.meta_whatsapp_service import send_whatsapp_document as impl
    return impl(to_number, document_url, filename, caption)


def send_catalog_whatsapp(to_number: str, business_config: dict):
    provider = get_whatsapp_provider()
    if provider == "twilio":
        from oberoende_bot.app.services.twilio_whatsapp_service import send_catalog_whatsapp as impl
    else:
        from oberoende_bot.app.services.meta_whatsapp_service import send_catalog_whatsapp as impl
    return impl(to_number, business_config)


def send_whatsapp_buttons(to_number: str, body: str, buttons: list[str]):
    provider = get_whatsapp_provider()
    if provider == "twilio":
        from oberoende_bot.app.services.twilio_whatsapp_service import send_whatsapp_text as impl
        # Twilio no soporta botones interactivos nativos — fallback a texto
        options = "\n".join(f"{i+1}️⃣ {b}" for i, b in enumerate(buttons))
        return impl(to_number, f"{body}\n\n{options}")
    else:
        from oberoende_bot.app.services.meta_whatsapp_service import send_whatsapp_buttons as impl
    return impl(to_number, body, buttons)



    provider = get_whatsapp_provider()
    if provider == "twilio":
        from oberoende_bot.app.services.twilio_whatsapp_service import handle_incoming_whatsapp as impl
    else:
        from oberoende_bot.app.services.meta_whatsapp_service import handle_incoming_whatsapp as impl
    return await impl(request)