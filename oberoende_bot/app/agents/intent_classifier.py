from openai import OpenAI
import os
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def classify_intent(user_message: str) -> str:
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": """
Clasifica la intención del usuario en una de estas categorías:

- consulta_producto
- crear_pedido
- saludo
- otro

Responde solo con la etiqueta.
"""
            },
            {"role": "user", "content": user_message}
        ],
        temperature=0
    )

    return response.choices[0].message.content.strip()