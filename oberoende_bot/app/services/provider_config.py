import os
from dotenv import load_dotenv

load_dotenv()

def get_whatsapp_provider() -> str:
    provider = os.getenv("WHATSAPP_PROVIDER", "meta").strip().lower()
    if provider not in {"meta", "twilio"}:
        return "meta"
    return provider