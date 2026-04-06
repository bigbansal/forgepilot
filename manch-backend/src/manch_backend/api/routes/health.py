import logging

from fastapi import APIRouter
from sqlalchemy import text

from manch_backend.db.session import SessionLocal

router = APIRouter()
logger = logging.getLogger("manch.health")


@router.get("/health")
def health() -> dict[str, str]:
    """Liveness + readiness probe. Checks database connectivity."""
    db_ok = False
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
            db_ok = True
    except Exception as exc:
        logger.warning("Health check DB probe failed: %s", exc)

    status = "ok" if db_ok else "degraded"
    return {"status": status, "service": "manch-backend", "database": "ok" if db_ok else "unreachable"}
