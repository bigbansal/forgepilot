from fastapi import APIRouter
from forgepilot_backend.api.routes import health, tasks, sessions, agents, events, conversations, auth, pipeline


api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(health.router, tags=["health"])
api_router.include_router(tasks.router, prefix="/tasks", tags=["tasks"])
api_router.include_router(conversations.router, prefix="/conversations", tags=["conversations"])
api_router.include_router(sessions.router, prefix="/sessions", tags=["sessions"])
api_router.include_router(agents.router, prefix="/agents", tags=["agents"])
api_router.include_router(events.router, prefix="/events", tags=["events"])
api_router.include_router(pipeline.router, prefix="/tasks", tags=["pipeline"])
