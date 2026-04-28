from fastapi import APIRouter
from manch_backend.api.routes import health, tasks, sessions, agents, events, conversations, auth, pipeline, approvals, preview, skills, audit_log, repos, memory, webhooks


api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])
api_router.include_router(health.router, tags=["health"])
api_router.include_router(tasks.router, prefix="/tasks", tags=["tasks"])
api_router.include_router(conversations.router, prefix="/conversations", tags=["conversations"])
api_router.include_router(sessions.router, prefix="/sessions", tags=["sessions"])
api_router.include_router(agents.router, prefix="/agents", tags=["agents"])
api_router.include_router(events.router, prefix="/events", tags=["events"])
api_router.include_router(pipeline.router, prefix="/tasks", tags=["pipeline"])
api_router.include_router(approvals.router, prefix="/approvals", tags=["approvals"])
api_router.include_router(preview.router, prefix="/preview", tags=["preview"])
api_router.include_router(skills.router, prefix="/skills", tags=["skills"])
api_router.include_router(audit_log.router, prefix="/audit-log", tags=["audit-log"])
api_router.include_router(repos.router, prefix="/repos", tags=["repos"])
api_router.include_router(memory.router, prefix="/memory", tags=["memory"])
