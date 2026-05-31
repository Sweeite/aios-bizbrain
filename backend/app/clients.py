from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.deps import get_client_profile_service
from engine.clients.profile_service import ClientProfileService, ScopeViolationError
from engine.spine.types import Scope, ScopeLevel

router = APIRouter(prefix="/clients", tags=["clients"])


def _parse_scope(scope: str | None) -> Scope:
    if scope:
        return Scope(level=ScopeLevel.entity, entity_ref=scope)
    return Scope(level=ScopeLevel.org)


@router.get("")
def list_clients(
    scope: str | None = Query(default=None),
    svc: ClientProfileService = Depends(get_client_profile_service),
):
    return svc.list_clients(_parse_scope(scope))


@router.get("/{client_id}")
def get_client(
    client_id: str,
    scope: str | None = Query(default=None),
    svc: ClientProfileService = Depends(get_client_profile_service),
):
    try:
        profile = svc.get_profile(client_id, _parse_scope(scope))
    except ScopeViolationError:
        raise HTTPException(status_code=403, detail="scope does not permit access to this client")
    if profile is None:
        raise HTTPException(status_code=404, detail="client not found")
    return profile
