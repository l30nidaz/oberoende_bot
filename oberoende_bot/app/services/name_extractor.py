# oberoende_bot/app/services/name_extractor.py
import re
from typing import Optional

_PATTERNS = [
    r"\bme llamo\s+([A-Za-zÁÉÍÓÚÑáéíóúñ]+)\b",
    r"\bsoy\s+([A-Za-zÁÉÍÓÚÑáéíóúñ]+)\b",
    r"\bmi nombre es\s+([A-Za-zÁÉÍÓÚÑáéíóúñ]+)\b",
]

def extract_name(text: str) -> Optional[str]:
    t = text.strip()
    for p in _PATTERNS:
        m = re.search(p, t, flags=re.IGNORECASE)
        if m:
            name = m.group(1).strip()
            # Normaliza: "julio" -> "Julio"
            return name[:1].upper() + name[1:].lower()
    return None