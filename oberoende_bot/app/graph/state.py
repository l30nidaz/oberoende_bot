from typing import TypedDict

class AgentState(TypedDict):
    user_id: str
    user_message: str
    intent: str
    response: str