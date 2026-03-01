from fastapi import FastAPI, Request
from contextlib import asynccontextmanager

from oberoende_bot.app.services.whatsapp_service import handle_whatsapp
from oberoende_bot.app.services.rag_service import initialize_vectorstore


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 Inicializando aplicación...")
    initialize_vectorstore(force_rebuild=True)  # 👈 forzar
    yield
    print("🛑 Cerrando aplicación...")

app = FastAPI(lifespan=lifespan)


@app.post("/whatsapp_webhook")
async def whatsapp_webhook(request: Request):
    return await handle_whatsapp(request)