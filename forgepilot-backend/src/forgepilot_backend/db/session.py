from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from forgepilot_backend.config import settings
from forgepilot_backend.db.base import Base

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db() -> None:
    from forgepilot_backend.db import models  # noqa: F401

    Base.metadata.create_all(bind=engine)


def get_db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
