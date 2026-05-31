import os

from fastapi import FastAPI
from dotenv import load_dotenv

from app.approvals import router as approvals_router

load_dotenv()

app = FastAPI(title="AIOS BizBrain", version="0.1.0")
app.include_router(approvals_router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "supabase_url": bool(os.getenv("SUPABASE_URL"))}
