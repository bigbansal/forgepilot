"""Skill management API endpoints."""
from __future__ import annotations

import importlib
import json
import logging
import re
import textwrap
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from manch_backend.core.deps import get_current_user
from manch_backend.db.models import UserRecord
from manch_backend.skills.registry import skill_registry
from manch_backend.skills.marketplace import (
    list_marketplace,
    get_marketplace_categories,
    install_marketplace_skill,
    uninstall_marketplace_skill,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Response schemas ─────────────────────────────────


class SkillSummary(BaseModel):
    name: str
    version: str
    description: str
    kind: str
    risk_level: str
    author: str
    tags: list[str]
    enabled: bool


class SkillDetail(SkillSummary):
    config: dict[str, Any]
    config_schema: dict[str, Any]
    dependencies: list[str]


class SkillConfigUpdate(BaseModel):
    config: dict[str, Any]


class MarketplaceItem(BaseModel):
    name: str
    version: str
    description: str
    kind: str
    risk_level: str
    author: str
    tags: list[str]
    dependencies: list[str]
    category: str
    downloads: int
    icon: str
    installed: bool


class MarketplaceCategory(BaseModel):
    name: str
    count: int


class InstallRequest(BaseModel):
    name: str


class SkillCreateRequest(BaseModel):
    """Payload for creating a new custom skill (from UI or chat /create-skill)."""
    name: str
    description: str
    tags: list[str] = []
    author: str = "Custom"
    risk_level: str = "LOW"


# ── Endpoints ────────────────────────────────────────


@router.get("", response_model=list[SkillSummary])
def list_skills(_user: UserRecord = Depends(get_current_user)):
    """Return all registered skills with their enabled/disabled state."""
    results: list[SkillSummary] = []
    for skill in skill_registry.list_all():
        m = skill.manifest
        results.append(
            SkillSummary(
                name=m.name,
                version=m.version,
                description=m.description,
                kind=m.kind.value,
                risk_level=m.risk_level.value,
                author=m.author,
                tags=list(m.tags),
                enabled=skill_registry.is_enabled(m.name),
            )
        )
    return results


# ── Marketplace Endpoints (must come before /{name}) ─


@router.get("/marketplace", response_model=list[MarketplaceItem])
def marketplace_list(
    category: str | None = Query(None, description="Filter by category"),
    search: str | None = Query(None, description="Search in name/description/tags"),
    _user: UserRecord = Depends(get_current_user),
):
    """List skills available in the marketplace (not yet installed)."""
    return list_marketplace(category=category, search=search)


@router.get("/marketplace/categories", response_model=list[MarketplaceCategory])
def marketplace_categories(_user: UserRecord = Depends(get_current_user)):
    """Return marketplace categories with available skill counts."""
    return get_marketplace_categories()


@router.post("/marketplace/install")
def marketplace_install(body: InstallRequest, _user: UserRecord = Depends(get_current_user)):
    """Install a skill from the marketplace catalogue."""
    try:
        result = install_marketplace_skill(body.name)
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/marketplace/uninstall")
def marketplace_uninstall(body: InstallRequest, _user: UserRecord = Depends(get_current_user)):
    """Uninstall a marketplace-installed skill (builtins cannot be removed)."""
    try:
        result = uninstall_marketplace_skill(body.name)
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ── Per-skill Endpoints ──────────────────────────────


@router.get("/{name}", response_model=SkillDetail)
def get_skill(name: str, _user: UserRecord = Depends(get_current_user)):
    """Get full detail of a specific skill."""
    skill = skill_registry.get(name)
    if not skill:
        raise HTTPException(status_code=404, detail=f"Skill '{name}' not found")
    m = skill.manifest
    return SkillDetail(
        name=m.name,
        version=m.version,
        description=m.description,
        kind=m.kind.value,
        risk_level=m.risk_level.value,
        author=m.author,
        tags=list(m.tags),
        enabled=skill_registry.is_enabled(m.name),
        config=skill.config,
        config_schema=m.config_schema,
        dependencies=list(m.dependencies),
    )


@router.post("/{name}/enable")
def enable_skill(name: str, _user: UserRecord = Depends(get_current_user)):
    """Enable a disabled skill."""
    if not skill_registry.get(name):
        raise HTTPException(status_code=404, detail=f"Skill '{name}' not found")
    ok = skill_registry.enable(name)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to enable skill")
    return {"status": "enabled", "name": name}


@router.post("/{name}/disable")
def disable_skill(name: str, _user: UserRecord = Depends(get_current_user)):
    """Disable a skill (calls teardown)."""
    if not skill_registry.get(name):
        raise HTTPException(status_code=404, detail=f"Skill '{name}' not found")
    ok = skill_registry.disable(name)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to disable skill")
    return {"status": "disabled", "name": name}


@router.put("/{name}/config")
def update_skill_config(name: str, body: SkillConfigUpdate, _user: UserRecord = Depends(get_current_user)):
    """Update per-skill configuration (persisted to DB)."""
    skill = skill_registry.get(name)
    if not skill:
        raise HTTPException(status_code=404, detail=f"Skill '{name}' not found")

    skill.config.update(body.config)

    # Persist to DB
    try:
        from manch_backend.db.models import SkillRecord
        from manch_backend.db.session import SessionLocal
        from sqlalchemy import select

        with SessionLocal() as db:
            rec = db.execute(
                select(SkillRecord).where(SkillRecord.name == name)
            ).scalars().first()
            if rec:
                rec.config_json = json.dumps(skill.config)
                db.commit()
    except Exception:
        logger.exception("Failed to persist config for skill %s", name)

    return {"status": "updated", "name": name, "config": skill.config}


# ── Local sync endpoints ──────────────────────────────


@router.get("/{name}/skill-md", response_class=PlainTextResponse)
def get_skill_md(name: str, _user: UserRecord = Depends(get_current_user)):
    """Return the SKILL.md content for the given skill (for preview or download)."""
    skill = skill_registry.get(name)
    if not skill:
        raise HTTPException(status_code=404, detail=f"Skill '{name}' not found")
    return skill.to_skill_md()


@router.post("/{name}/sync-local")
def sync_skill_local(name: str, _user: UserRecord = Depends(get_current_user)):
    """Write this skill's SKILL.md to ~/.codex/skills and ~/.gemini/skills on the host.

    The backend container must have those directories bind-mounted (see docker-compose.yml).
    """
    skill = skill_registry.get(name)
    if not skill:
        raise HTTPException(status_code=404, detail=f"Skill '{name}' not found")
    if not skill_registry.is_enabled(name):
        raise HTTPException(status_code=400, detail=f"Skill '{name}' is disabled; enable it first")
    skill_registry.sync_local_skill_files(skill)
    return {
        "status": "synced",
        "name": name,
        "paths": [f"{d}/{name}/SKILL.md" for d in skill_registry._LOCAL_SKILL_DIRS],
    }


@router.post("/sync-all-local")
def sync_all_skills_local(_user: UserRecord = Depends(get_current_user)):
    """Sync SKILL.md for every enabled skill to local CLI directories."""
    count = skill_registry.sync_all_local_skill_files()
    return {
        "status": "synced",
        "count": count,
        "paths": list(skill_registry._LOCAL_SKILL_DIRS),
    }


# ── Skill creation endpoint ───────────────────────────


def _slugify(name: str) -> str:
    """Convert an arbitrary string into a valid Python identifier and slug."""
    name = name.lower().strip()
    name = re.sub(r"[^a-z0-9]+", "-", name).strip("-")
    return name


_CUSTOM_SKILL_TEMPLATE = '''\
"""Custom skill: {name}

Auto-generated by Manch skill creator.
"""
from __future__ import annotations

from manch_backend.models import RiskLevel
from manch_backend.skills import BaseSkill, SkillKind, SkillManifest


class {class_name}(BaseSkill):
    manifest = SkillManifest(
        name={name_repr},
        version="1.0.0",
        description={description_repr},
        kind=SkillKind.TOOL,
        risk_level=RiskLevel.{risk_level},
        author={author_repr},
        tags={tags_repr},
    )

    def register(self) -> None:
        # Add ToolSpec objects here to expose tools to agents.
        # Example:
        #   from manch_backend.agents.tools import ToolSpec, register_tool
        #   register_tool(ToolSpec(name="my_tool", description="...", handler=self._my_tool))
        pass


skill = {class_name}()
'''


@router.post("/create", status_code=201)
def create_skill(body: SkillCreateRequest, _user: UserRecord = Depends(get_current_user)):
    """Create a new custom skill from the UI or a chat /create-skill command.

    The skill is:
    1. Saved as a Python file in ``skills/custom/`` (persists across restarts).
    2. Loaded into the registry immediately.
    3. Synced to ``~/.codex/skills`` and ``~/.gemini/skills`` on the host.

    Chat usage: type ``/create-skill <name>: <description>`` in the chat window.
    """
    slug = _slugify(body.name)
    if not slug:
        raise HTTPException(status_code=400, detail="Invalid skill name — use letters, digits, and hyphens only")

    if skill_registry.get(slug):
        raise HTTPException(status_code=409, detail=f"Skill '{slug}' already exists")

    # Build the Python source file
    class_name = "".join(part.capitalize() for part in slug.split("-")) + "Skill"
    risk = body.risk_level.upper() if body.risk_level.upper() in ("LOW", "MEDIUM", "HIGH", "CRITICAL") else "LOW"
    source = _CUSTOM_SKILL_TEMPLATE.format(
        name=slug,
        name_repr=repr(slug),
        class_name=class_name,
        description_repr=repr(body.description),
        author_repr=repr(body.author),
        tags_repr=repr(["custom"] + [t.lower() for t in body.tags if t]),
        risk_level=risk,
    )

    # Persist to skills/custom/ directory (auto-discovered on next startup)
    custom_dir = Path(__file__).parent.parent.parent / "skills" / "custom"
    custom_dir.mkdir(parents=True, exist_ok=True)
    # Ensure the package has an __init__.py
    init_file = custom_dir / "__init__.py"
    if not init_file.exists():
        init_file.write_text("")

    skill_file = custom_dir / f"{slug.replace('-', '_')}.py"
    skill_file.write_text(source, encoding="utf-8")

    # Dynamically import and load the skill right now (no restart needed)
    module_name = f"manch_backend.skills.custom.{slug.replace('-', '_')}"
    try:
        mod = importlib.import_module(module_name)
    except Exception:
        # Re-try after invalidating import caches
        import importlib.util
        spec = importlib.util.spec_from_file_location(module_name, skill_file)
        mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
        spec.loader.exec_module(mod)  # type: ignore[union-attr]

    skill_instance = getattr(mod, "skill", None)
    if not skill_instance:
        raise HTTPException(status_code=500, detail="Skill module did not export a 'skill' instance")

    errors = skill_registry.load_skill(skill_instance)
    if errors:
        raise HTTPException(status_code=500, detail=f"Skill load errors: {'; '.join(errors)}")

    # Sync to local CLI directories immediately so it's visible right away
    skill_registry.sync_local_skill_files(skill_instance)

    # Persist state to DB
    skill_registry._sync_db()

    return {
        "status": "created",
        "name": slug,
        "description": body.description,
        "file": str(skill_file),
        "local_paths": [f"{d}/{slug}/SKILL.md" for d in skill_registry._LOCAL_SKILL_DIRS],
    }
