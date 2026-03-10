from fastapi import Request

from oberoende_bot.app.services.provider_config import get_whatsapp_provider

# URLs de catálogo compartidas
CATALOG_IMAGES = [
    "https://catalogo-oberoende-s3.s3.us-east-1.amazonaws.com/catalogo3.jpg",
    "https://catalogo-oberoende-s3.s3.us-east-1.amazonaws.com/catalogo1.jpg",
    "https://catalogo-oberoende-s3.s3.us-east-1.amazonaws.com/catalogo2.png",
]

CATALOG_PDF_URL = "https://catalogo-oberoende-s3.s3.us-east-1.amazonaws.com/catalogo.pdf"


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


def send_catalog_whatsapp(to_number: str):
    provider = get_whatsapp_provider()
    if provider == "twilio":
        from oberoende_bot.app.services.twilio_whatsapp_service import send_catalog_whatsapp as impl
    else:
        from oberoende_bot.app.services.meta_whatsapp_service import send_catalog_whatsapp as impl
    return impl(to_number)


async def handle_whatsapp(request: Request):
    provider = get_whatsapp_provider()
    if provider == "twilio":
        from oberoende_bot.app.services.twilio_whatsapp_service import handle_incoming_whatsapp as impl
    else:
        from oberoende_bot.app.services.meta_whatsapp_service import handle_incoming_whatsapp as impl
    return await impl(request)