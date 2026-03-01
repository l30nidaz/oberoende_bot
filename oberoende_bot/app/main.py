from fastapi import FastAPI, Request
from contextlib import asynccontextmanager

from oberoende_bot.app.services.whatsapp_service import handle_whatsapp
from oberoende_bot.app.services.rag_service import initialize_vectorstore
import os
from fastapi import HTTPException

ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "admin-token-123")

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 Inicializando aplicación...")
    initialize_vectorstore(force_rebuild=False)  # 👈 forzar
    yield
    print("🛑 Cerrando aplicación...")

app = FastAPI(lifespan=lifespan)

@app.post("/whatsapp_webhook")
async def whatsapp_webhook(request: Request):
    return await handle_whatsapp(request)

@app.post("/admin/reindex")
async def reindex(token: str):
    if token != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")
    initialize_vectorstore(force_rebuild=True)
    return {"status": "vectorstore rebuilt"}
