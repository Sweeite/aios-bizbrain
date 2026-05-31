from fastapi import APIRouter, Depends, HTTPException

from app.deps import get_connector_health_service
from engine.connectors.health_service import ConnectorHealthService
from engine.spine.types import ConnectorHealthRecord

router = APIRouter(prefix="/integrations", tags=["integrations"])


@router.get("/health", response_model=list[ConnectorHealthRecord])
def get_health(svc: ConnectorHealthService = Depends(get_connector_health_service)):
    return svc.get_all()


@router.post("/{source_system}/reconnect", response_model=ConnectorHealthRecord)
def reconnect(
    source_system: str,
    svc: ConnectorHealthService = Depends(get_connector_health_service),
):
    record = svc.reconnect(source_system)
    if record is None:
        raise HTTPException(status_code=404, detail=f"unknown connector: {source_system}")
    return record
