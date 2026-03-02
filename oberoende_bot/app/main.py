from fastapi import FastAPI, Request
from contextlib import asynccontextmanager

from oberoende_bot.app.services.whatsapp_service import handle_whatsapp
from oberoende_bot.app.services.rag_service import initialize_vectorstore
from oberoende_bot.app.services.state_store_sqlite import init_state_db
import os
from fastapi import HTTPException
from oberoende_bot.app.services.user_profile_store_sqlite import init_user_profile_db

ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "admin-token-123")

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 Inicializando aplicación...")
    init_state_db()
    init_user_profile_db()
    initialize_vectorstore(force_rebuild=False)
    yield
    print("🛑 Cerrando aplicación...")

app = FastAPI(lifespan=lifespan)

@app.post("/whatsapp_webhook")
async def whatsapp_webhook(request: Request):
    print("📩 Recibida solicitud en /whatsapp_webhook")
    return await handle_whatsapp(request)

@app.post("/admin/reindex")
async def reindex(token: str):
    if token != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")
    initialize_vectorstore(force_rebuild=False)
    return {"status": "vectorstore rebuilt"}
