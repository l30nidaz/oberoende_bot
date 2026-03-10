from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import PlainTextResponse
from contextlib import asynccontextmanager
from pathlib import Path
from dotenv import load_dotenv
import os

from oberoende_bot.app.services.memory_service import init_memory_db
from oberoende_bot.app.services.whatsapp_service import handle_whatsapp
from oberoende_bot.app.services.rag_service import initialize_vectorstore
from oberoende_bot.app.services.state_store_sqlite import init_state_db
from oberoende_bot.app.services.user_profile_store_sqlite import init_user_profile_db
from oberoende_bot.app.services.leads_store import init_leads_db

load_dotenv()
ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(dotenv_path=ENV_PATH)
print("✅ .env cargado desde:", ENV_PATH)

ADMIN_TOKEN = os.getenv("ADMIN_TOKEN")
WHATSAPP_VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN")
print("✅ Variables de entorno cargadas:")
print("   - ADMIN_TOKEN:", "✅" if ADMIN_TOKEN else "❌")
print("   - WHATSAPP_VERIFY_TOKEN:", "✅" if WHATSAPP_VERIFY_TOKEN else "❌")

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 Inicializando aplicación...")
    init_state_db()
    init_user_profile_db()
    init_leads_db()
    init_memory_db()
    initialize_vectorstore(force_rebuild=False)
    yield
    print("🛑 Cerrando aplicación...")


app = FastAPI(lifespan=lifespan)


@app.get("/whatsapp_webhook")
async def verify_whatsapp_webhook(request: Request):
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    if mode == "subscribe" and token == WHATSAPP_VERIFY_TOKEN:
        return PlainTextResponse(content=challenge or "", status_code=200)

    return PlainTextResponse(content="Verification failed", status_code=403)


@app.post("/whatsapp_webhook")
async def whatsapp_webhook(request: Request):
    print("📩 Recibida solicitud en /whatsapp_webhook")
    return await handle_whatsapp(request)


@app.post("/admin/reindex")
async def reindex(token: str):
    if token != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorizedddd")
    initialize_vectorstore(force_rebuild=False)
    return {"status": "vectorstore rebuilt"}