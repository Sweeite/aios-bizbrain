import os
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from engine.spine.types import AutonomyTier, ParkedApprovalRequest, Scope, ScopeLevel, ToolMode, ToolSpec
from engine.tools.executor import ToolExecutor
from engine.tools.registry import ToolRegistry

router = APIRouter(prefix="/approvals", tags=["approvals"])

_executor: ToolExecutor | None = None


def get_executor() -> ToolExecutor:
    global _executor
    if _executor is None:
        _executor = ToolExecutor(ToolRegistry())
    return _executor


class ApproveRequest(BaseModel):
    body: str | None = None


class RejectRequest(BaseModel):
    reason: str


@router.get("")
def list_approvals(executor: ToolExecutor = Depends(get_executor)):
    return [r.model_dump() for r in executor.list_pending()]


@router.post("/{idempotency_key}/approve")
def approve(
    idempotency_key: str,
    req: ApproveRequest | None = None,
    executor: ToolExecutor = Depends(get_executor),
):
    try:
        override = req.body if req else None
        result = executor.approve(idempotency_key, override_body=override)
        return {"status": "approved", "result": result}
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Unknown key: {idempotency_key!r}")


@router.post("/seed")
def seed(executor: ToolExecutor = Depends(get_executor)):
    if not os.getenv("DEBUG"):
        raise HTTPException(status_code=404)

    spec = ToolSpec(
        name="gmail.draft_email",
        inputs={"to": "str", "subject": "str", "body": "str"},
        system="gmail",
        mode=ToolMode.write,
        tier=AutonomyTier.T3,
        scope_required=ScopeLevel.entity,
        reversible=False,
        side_effects=["creates_email_draft"],
    )
    registry = executor._registry
    if "gmail.draft_email" not in registry._tools:
        registry.register(spec, lambda inputs, dry_run=False: inputs.get("body", ""))

    key = f"seed-{uuid.uuid4().hex[:8]}"
    executor.execute(
        "gmail.draft_email",
        inputs={
            "to": "northpath@example.com",
            "subject": "Following up on the Q3 proposal",
            "body": "Dear Northpath,\n\nJust following up on the Q3 proposal we sent last week. Happy to jump on a call to walk through the scope and fees.\n\nBest,\nAustin",
        },
        scope=Scope(level=ScopeLevel.entity, entity_ref="client-northpath-001"),
        requesting_agent="account-agent",
        principal="client-northpath-001",
        rationale="Commitment language detected in last email — confirming scope and fees before proceeding.",
        idempotency_key=key,
    )
    return {"seeded": key}


@router.post("/{idempotency_key}/reject")
def reject(
    idempotency_key: str,
    req: RejectRequest,
    executor: ToolExecutor = Depends(get_executor),
):
    try:
        executor.reject(idempotency_key, reason=req.reason)
        return {"status": "rejected"}
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Unknown key: {idempotency_key!r}")
