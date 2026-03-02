from typing import TypedDict, Optional

class BotState(TypedDict):
    user_id: str
    user_message: str
    response: str
    # estado persistente externo