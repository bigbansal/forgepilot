from fastapi import APIRouter, Depends
from manch_backend.core.deps import get_current_user, AuthContext
from manch_backend.services.orchestrator import orchestrator

router = APIRouter()


@router.get("")
def list_sessions(auth: AuthContext = Depends(get_current_user)):
    return orchestrator.list_sessions(user_id=auth.user.id, team_id=auth.team_id)
