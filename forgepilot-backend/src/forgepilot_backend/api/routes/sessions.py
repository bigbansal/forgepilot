from fastapi import APIRouter
from forgepilot_backend.services.orchestrator import orchestrator

router = APIRouter()


@router.get("")
def list_sessions():
    return orchestrator.list_sessions()
