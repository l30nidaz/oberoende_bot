import os
from typing import Dict, Any

BUSINESSES: Dict[str, Dict[str, Any]] = {
    "soldeoro": {
        "business_id": "soldeoro",
        "name": "Soldeoro",
        "app_name": "Oberoende",
        "emoji": "💎",
        "industry": "joyería",
        "assistant_role": "Eres un asistente profesional de una joyería.",
        "router_role": "Eres un router de conversación para una joyería.",
        "menu_title": "¡Hola! 👋 Bienvenido a Soldeoro 💎",
        "menu_options": [
            "1️⃣ Ver catálogo",
            "2️⃣ Saber precios",
            "3️⃣ Comprar un modelo",
            "4️⃣ Hablar con asesor",
        ],
        "product_keywords": ["anillo", "collar", "arete", "pulsera", "cadena", "dije", "aro"],
        "product_examples": "anillos, collares, pulseras o aretes",
        "payment_methods": ["Yape", "Plin", "transferencia"],
        "lead_questions": {
            "model": "1️⃣ ¿Qué modelo te interesa? (puedes escribir el nombre)",
            "district": "Perfecto 👍 ¿En qué distrito estás?",
            "payment": "Gracias ✅ ¿Cómo prefieres pagar: Yape, Plin o transferencia?"
        },
        "catalog_images": [
            "https://catalogo-oberoende-s3.s3.us-east-1.amazonaws.com/catalogo3.jpg",
            "https://catalogo-oberoende-s3.s3.us-east-1.amazonaws.com/catalogo1.jpg",
            "https://catalogo-oberoende-s3.s3.us-east-1.amazonaws.com/catalogo2.png",
        ],
        "catalog_pdf_url": "https://catalogo-oberoende-s3.s3.us-east-1.amazonaws.com/catalogo.pdf",
        "documents_path": "oberoende_bot/app/data/businesses/soldeoro/documentos",
        "vectorstore_path": "oberoende_bot/app/data/businesses/soldeoro/vectorstore",
        "channel_ids": [
            os.getenv("SOLDEORO_META_PHONE_NUMBER_ID", "").strip(),
            os.getenv("SOLDEORO_TWILIO_NUMBER", "").strip(),
        ],
        "lead_email_subject": "Nuevo lead (joyería) - Soldeoro",
    },

    "difios": {
        "business_id": "difios",
        "name": "Difios",
        "app_name": "Oberoende",
        "emoji": "💍",
        "industry": "joyería",
        "assistant_role": "Eres un asistente profesional de una joyería.",
        "router_role": "Eres un router de conversación para una joyería.",
        "menu_title": "¡Hola! 👋 Bienvenido a Difios 💍",
        "menu_options": [
            "1️⃣ Ver catálogo",
            "2️⃣ Saber precios",
            "3️⃣ Comprar un modelo",
            "4️⃣ Hablar con asesor",
        ],
        "product_keywords": ["anillo", "collar", "arete", "pulsera", "cadena", "dije", "aro"],
        "product_examples": "anillos, collares, pulseras o aretes",
        "payment_methods": ["Yape", "Plin", "transferencia"],
        "lead_questions": {
            "model": "1️⃣ ¿Qué modelo te interesa? (puedes escribir el nombre)",
            "district": "Perfecto 👍 ¿En qué distrito estás?",
            "payment": "Gracias ✅ ¿Cómo prefieres pagar: Yape, Plin o transferencia?"
        },
        "catalog_images": [
            "https://catalogo-oberoende-s3.s3.us-east-1.amazonaws.com/catalogo3.jpg",
            "https://catalogo-oberoende-s3.s3.us-east-1.amazonaws.com/catalogo1.jpg",
            "https://catalogo-oberoende-s3.s3.us-east-1.amazonaws.com/catalogo2.png",
        ],
        "catalog_pdf_url": "https://catalogo-oberoende-s3.s3.us-east-1.amazonaws.com/catalogo.pdf",
        "documents_path": "oberoende_bot/app/data/businesses/difios/documentos",
        "vectorstore_path": "oberoende_bot/app/data/businesses/difios/vectorstore",
        "channel_ids": [
            os.getenv("DIFIOS_META_PHONE_NUMBER_ID", "").strip(),
            os.getenv("DIFIOS_TWILIO_NUMBER", "").strip(),
        ],
        "lead_email_subject": "Nuevo lead (joyería) - Difios",
    },

    "casa_hogar": {
        "business_id": "casa_hogar",
        "name": "Casa Hogar",
        "app_name": "Oberoende",
        "emoji": "🛏️",
        "industry": "tienda de ropa de cama y textiles para el hogar",
        "assistant_role": "Eres un asistente profesional de una tienda de cobertores, sábanas, toallas y textiles para el hogar.",
        "router_role": "Eres un router de conversación para una tienda de cobertores, sábanas, toallas y textiles para el hogar.",
        "menu_title": "¡Hola! 👋 Bienvenido a Casa Hogar 🛏️",
        "menu_options": [
            "1️⃣ Ver catálogo",
            "2️⃣ Consultar precios",
            "3️⃣ Hacer pedido",
            "4️⃣ Hablar con asesor",
        ],
        "product_keywords": [
            "sábana", "sabana", "cobertor", "cobertores", "toalla", "toallas",
            "frazada", "edredón", "edredon", "acolchado", "ropa de cama"
        ],
        "product_examples": "sábanas, cobertores, frazadas, edredones o toallas",
        "payment_methods": ["Yape", "Plin", "transferencia"],
        "lead_questions": {
            "model": "1️⃣ ¿Qué producto te interesa? (puedes escribir el nombre)",
            "district": "Perfecto 👍 ¿A qué distrito sería el envío?",
            "payment": "Gracias ✅ ¿Cómo prefieres pagar?"
        },
        "catalog_images": [
            "https://ejemplo.com/casa_hogar_1.jpg",
            "https://ejemplo.com/casa_hogar_2.jpg",
        ],
        "catalog_pdf_url": "https://ejemplo.com/casa_hogar_catalogo.pdf",
        "documents_path": "oberoende_bot/app/data/businesses/casa_hogar/documentos",
        "vectorstore_path": "oberoende_bot/app/data/businesses/casa_hogar/vectorstore",
        "channel_ids": [
            os.getenv("CASA_HOGAR_META_PHONE_NUMBER_ID", "").strip(),
            os.getenv("CASA_HOGAR_TWILIO_NUMBER", "").strip(),
        ],
        "lead_email_subject": "Nuevo lead (textiles) - Casa Hogar",
    },
}

DEFAULT_BUSINESS_ID = os.getenv("DEFAULT_BUSINESS_ID", "soldeoro").strip() or "soldeoro"


def get_business_config(business_id: str | None = None) -> Dict[str, Any]:
    bid = business_id or DEFAULT_BUSINESS_ID
    return BUSINESSES.get(bid, BUSINESSES[DEFAULT_BUSINESS_ID])


def resolve_business_by_channel(channel_id: str | None) -> Dict[str, Any]:
    normalized = (channel_id or "").strip()

    if normalized:
        for business in BUSINESSES.values():
            channel_ids = [x for x in business.get("channel_ids", []) if x]
            if normalized in channel_ids:
                return business

    return get_business_config(DEFAULT_BUSINESS_ID)