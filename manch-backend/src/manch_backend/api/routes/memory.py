"""Memory knowledge-base API endpoints — view and search captured knowledge."""
from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from manch_backend.core.deps import get_current_user, AuthContext
from manch_backend.db.models import MemoryEntryRecord
from manch_backend.db.session import SessionLocal
from sqlalchemy import select, func

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Schemas ──────────────────────────────────────────


class MemoryEntry(BaseModel):
    id: str
    key: str
    category: str
    content: str
    tags: list[str]
    confidence: float
    retention_value: str
    source_task_id: str | None = None
    created_at: str


class MemoryListResponse(BaseModel):
    items: list[MemoryEntry]
    total: int
    page: int
    page_size: int


class MemoryStats(BaseModel):
    total_entries: int
    categories: dict[str, int]
    avg_confidence: float


# ── Endpoints ────────────────────────────────────────


@router.get("", response_model=MemoryListResponse)
def list_memories(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    category: str | None = Query(None),
    tag: str | None = Query(None),
    min_confidence: float = Query(0.0, ge=0.0, le=1.0),
    auth: AuthContext = Depends(get_current_user),
):
    """List memory entries scoped by team."""
    with SessionLocal() as db:
        stmt = select(MemoryEntryRecord).order_by(MemoryEntryRecord.created_at.desc())
        count_stmt = select(func.count(MemoryEntryRecord.id))

        if auth.team_id:
            stmt = stmt.where(MemoryEntryRecord.team_id == auth.team_id)
            count_stmt = count_stmt.where(MemoryEntryRecord.team_id == auth.team_id)

        if category:
            stmt = stmt.where(MemoryEntryRecord.category == category)
            count_stmt = count_stmt.where(MemoryEntryRecord.category == category)
        if min_confidence > 0:
            stmt = stmt.where(MemoryEntryRecord.confidence >= min_confidence)
            count_stmt = count_stmt.where(MemoryEntryRecord.confidence >= min_confidence)

        total = db.execute(count_stmt).scalar() or 0
        records = db.execute(stmt.offset((page - 1) * page_size).limit(page_size)).scalars().all()

        items = []
        for r in records:
            entry_tags = json.loads(r.tags_json) if r.tags_json else []
            if tag and tag not in entry_tags:
                continue
            items.append(
                MemoryEntry(
                    id=r.id,
                    key=r.key,
                    category=r.category,
                    content=r.content,
                    tags=entry_tags,
                    confidence=r.confidence,
                    retention_value=r.retention_value,
                    source_task_id=r.source_task_id,
                    created_at=r.created_at.isoformat(),
                )
            )

    return MemoryListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/stats", response_model=MemoryStats)
def memory_stats(
    auth: AuthContext = Depends(get_current_user),
):
    """Return aggregate stats about the memory knowledge base."""
    with SessionLocal() as db:
        total = db.execute(select(func.count(MemoryEntryRecord.id))).scalar() or 0
        avg_conf = db.execute(select(func.avg(MemoryEntryRecord.confidence))).scalar() or 0.0

        cat_rows = db.execute(
            select(MemoryEntryRecord.category, func.count(MemoryEntryRecord.id))
            .group_by(MemoryEntryRecord.category)
            .order_by(MemoryEntryRecord.category)
        ).all()

    return MemoryStats(
        total_entries=total,
        categories={row[0]: row[1] for row in cat_rows},
        avg_confidence=round(float(avg_conf), 3),
    )


@router.get("/categories", response_model=list[str])
def list_categories(
    auth: AuthContext = Depends(get_current_user),
):
    """Return distinct memory categories for filter dropdowns."""
    with SessionLocal() as db:
        rows = db.execute(
            select(MemoryEntryRecord.category).distinct().order_by(MemoryEntryRecord.category)
        ).scalars().all()
    return list(rows)


@router.delete("/{entry_id}", status_code=204)
def delete_memory_entry(
    entry_id: str,
    auth: AuthContext = Depends(get_current_user),
):
    """Delete a single memory entry."""
    with SessionLocal() as db:
        record = db.get(MemoryEntryRecord, entry_id)
        if not record:
            raise HTTPException(status_code=404, detail="Memory entry not found")
        db.delete(record)
        db.commit()
