import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from manch_backend.config import settings
from manch_backend.api.router import api_router
from manch_backend.db.session import init_db

logger = logging.getLogger("manch")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # ── Startup ──
    from manch_backend.services.events import event_broker
    event_broker.set_main_loop(asyncio.get_running_loop())
    init_db()

    # Discover and load all skills (builtins + pip entry-points)
    from manch_backend.skills.registry import skill_registry
    skill_registry.discover_all()

    # Warn if secret_key is the default
    if settings.secret_key == "change-me-in-production-use-openssl-rand-hex-32":
        logger.warning(
            "⚠️  Using default secret_key — set MANCH_SECRET_KEY for production!"
        )

    yield
    # ── Shutdown (nothing to do currently) ──


app = FastAPI(title="Manch Backend", version="0.1.0", lifespan=lifespan)


# ── Global exception handler ──
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


# ── CORS ──
_origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.api_prefix)


@app.get("/")
def root():
    return {"name": "Manch", "version": "0.1.0", "docs": "/docs"}
