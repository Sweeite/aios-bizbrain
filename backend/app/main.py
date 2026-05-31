import os
import sys
from pathlib import Path

# packs/ and config/ live one level above backend/
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from fastapi import FastAPI
from dotenv import load_dotenv

from app.activity import router as activity_router
from app.approvals import router as approvals_router
from app.chat import router as chat_router
from app.clients import router as clients_router
from app.home import router as home_router
from app.traces import router as traces_router

load_dotenv()

app = FastAPI(title="AIOS BizBrain", version="0.1.0")
app.include_router(activity_router)
app.include_router(approvals_router)
app.include_router(chat_router)
app.include_router(clients_router)
app.include_router(home_router)
app.include_router(traces_router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "supabase_url": bool(os.getenv("SUPABASE_URL"))}
