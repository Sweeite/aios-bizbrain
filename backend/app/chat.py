import json
import os

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from engine.agent.chat_handler import ChatHandler
from engine.agent.live import LiveQuery
from engine.ingestion.memory_writer import MemoryWriter
from engine.spine.types import Scope, ScopeLevel

router = APIRouter(tags=["chat"])

_memory_writer = MemoryWriter()
_live = LiveQuery()


def get_anthropic_client():
    import anthropic
    return anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


class ChatRequest(BaseModel):
    message: str
    client_id: str = "client-northpath-001"


@router.post("/chat")
def chat(req: ChatRequest, anthropic_client=Depends(get_anthropic_client)):
    scope = Scope(level=ScopeLevel.entity, entity_ref=req.client_id)
    memory_records = _memory_writer.recall(req.client_id, scope)
    live_context = _live.query(req.client_id)

    def generate():
        handler = ChatHandler()
        for chunk in handler.stream(
            message=req.message,
            entity_ref=req.client_id,
            memory_records=memory_records,
            live_context=live_context,
            anthropic_client=anthropic_client,
        ):
            yield f"data: {json.dumps({'text': chunk})}\n\n"
        yield f"data: {json.dumps({'done': True})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
