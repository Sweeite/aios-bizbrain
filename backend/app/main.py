import os

from fastapi import FastAPI
from dotenv import load_dotenv

from app.approvals import router as approvals_router
from app.chat import router as chat_router
from app.traces import router as traces_router

load_dotenv()

app = FastAPI(title="AIOS BizBrain", version="0.1.0")
app.include_router(approvals_router)
app.include_router(chat_router)
app.include_router(traces_router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "supabase_url": bool(os.getenv("SUPABASE_URL"))}
