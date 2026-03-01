from oberoende_bot.app.agents.order_store import save_order

def create_order(user_id: str, user_message: str) -> str:
    # Versión simple inicial
    save_order(user_id, "Pedido detectado", user_message)
    return "Tu pedido ha sido registrado. Te contactaremos para coordinar el pago."