from langchain_core.messages import HumanMessage, AIMessage

user_histories = {}

def get_history(user_id: str):
    if user_id not in user_histories:
        user_histories[user_id] = []
    return user_histories[user_id]

def add_user_message(user_id: str, message: str):
    user_histories.setdefault(user_id, []).append(
        HumanMessage(content=message)
    )

def add_ai_message(user_id: str, message: str):
    user_histories.setdefault(user_id, []).append(
        AIMessage(content=message)
    )