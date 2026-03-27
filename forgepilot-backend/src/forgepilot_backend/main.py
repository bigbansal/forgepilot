from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from forgepilot_backend.config import settings
from forgepilot_backend.api.router import api_router
from forgepilot_backend.db.session import init_db

app = FastAPI(title="ForgePilot Backend", version="0.1.0")


@app.on_event("startup")
async def on_startup() -> None:
    import asyncio
    from forgepilot_backend.services.events import event_broker
    event_broker.set_main_loop(asyncio.get_running_loop())
    init_db()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.api_prefix)


@app.get("/")
def root():
    return {"name": "ForgePilot", "version": "0.1.0", "docs": "/docs"}
