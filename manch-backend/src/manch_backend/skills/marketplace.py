"""Skill marketplace — catalog of installable community / third-party skills.

In production this would fetch from a remote skill registry.  For the POC
we maintain a static in-memory catalogue that represents "available" skills
which are not yet loaded as builtins.  The install flow dynamically
creates a thin skill wrapper and loads it into the registry.
"""
from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from typing import Any

from manch_backend.models import RiskLevel
from manch_backend.skills import BaseSkill, SkillKind, SkillManifest
from manch_backend.skills.registry import skill_registry

logger = logging.getLogger(__name__)


# ── Catalog entry ────────────────────────────────────


@dataclass
class MarketplaceEntry:
    """Metadata for a skill available in the marketplace."""

    name: str
    version: str
    description: str
    kind: str = "tool"
    risk_level: str = "low"
    author: str = "Community"
    tags: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    category: str = "general"
    downloads: int = 0
    icon: str = ""  # optional icon identifier


# ── Static catalogue ─────────────────────────────────

MARKETPLACE_CATALOG: list[MarketplaceEntry] = [
    MarketplaceEntry(
        name="react-developer",
        version="1.0.0",
        description="React 18+ development tools — component scaffolding, hooks generator, Redux Toolkit setup, Vite build integration.",
        kind="tool",
        risk_level="MEDIUM",
        author="Community",
        tags=["react", "frontend", "javascript", "typescript"],
        category="frontend",
        downloads=2340,
        icon="react",
    ),
    MarketplaceEntry(
        name="vue-developer",
        version="1.0.0",
        description="Vue 3 Composition API tools — component scaffolding, Pinia store generator, Vitest integration, Nuxt support.",
        kind="tool",
        risk_level="MEDIUM",
        author="Community",
        tags=["vue", "frontend", "javascript", "typescript"],
        category="frontend",
        downloads=1870,
        icon="vue",
    ),
    MarketplaceEntry(
        name="python-developer",
        version="1.0.0",
        description="Python development tools — project scaffolding (Poetry/PDM), pytest runner, type-checking, linting (Ruff), virtual-env management.",
        kind="tool",
        risk_level="MEDIUM",
        author="Community",
        tags=["python", "backend", "pytest", "ruff"],
        category="backend",
        downloads=3100,
        icon="python",
    ),
    MarketplaceEntry(
        name="go-developer",
        version="1.0.0",
        description="Go development tools — project init, go test runner, benchmarking, linting (golangci-lint), module management.",
        kind="tool",
        risk_level="MEDIUM",
        author="Community",
        tags=["go", "golang", "backend"],
        category="backend",
        downloads=1450,
        icon="go",
    ),
    MarketplaceEntry(
        name="database-tools",
        version="1.0.0",
        description="Database management tools — schema diffing, migration generation (Alembic/Flyway/Prisma), seed data generator, query analysis.",
        kind="tool",
        risk_level="MEDIUM",
        author="Community",
        tags=["database", "sql", "migration", "postgres", "mysql"],
        category="data",
        downloads=2780,
        icon="database",
    ),
    MarketplaceEntry(
        name="devops-tools",
        version="1.0.0",
        description="DevOps & CI/CD tools — GitHub Actions generator, Terraform scaffolding, Helm chart linting, Kubernetes manifest validation.",
        kind="tool",
        risk_level="HIGH",
        author="Community",
        tags=["devops", "cicd", "terraform", "kubernetes", "docker"],
        category="infrastructure",
        downloads=1920,
        icon="devops",
    ),
    MarketplaceEntry(
        name="testing-tools",
        version="1.0.0",
        description="Testing framework tools — test generator (unit/integration/e2e), coverage reporter, mocking helpers, fixtures scaffolding.",
        kind="tool",
        risk_level="LOW",
        author="Community",
        tags=["testing", "jest", "pytest", "cypress", "playwright"],
        category="quality",
        downloads=2560,
        icon="testing",
    ),
    MarketplaceEntry(
        name="documentation-tools",
        version="1.0.0",
        description="Documentation tools — API doc generator (OpenAPI/Swagger), README scaffolding, JSDoc/docstring writer, changelog generator.",
        kind="tool",
        risk_level="LOW",
        author="Community",
        tags=["documentation", "openapi", "swagger", "markdown"],
        category="quality",
        downloads=1680,
        icon="docs",
    ),
    MarketplaceEntry(
        name="rust-developer",
        version="1.0.0",
        description="Rust development tools — Cargo build/test/bench, crate scaffolding, clippy linting, unsafe code auditing.",
        kind="tool",
        risk_level="MEDIUM",
        author="Community",
        tags=["rust", "cargo", "backend", "systems"],
        category="backend",
        downloads=980,
        icon="rust",
    ),
    MarketplaceEntry(
        name="performance-tools",
        version="1.0.0",
        description="Performance analysis tools — Lighthouse audit, bundle size tracker, load testing (k6), profiling, Core Web Vitals checker.",
        kind="tool",
        risk_level="LOW",
        author="Community",
        tags=["performance", "lighthouse", "bundle", "profiling"],
        category="quality",
        downloads=1340,
        icon="performance",
    ),
]


# ── Marketplace helper functions ─────────────────────


def list_marketplace(
    category: str | None = None,
    search: str | None = None,
) -> list[dict[str, Any]]:
    """Return marketplace entries not already installed, with optional filters."""
    installed_names = {s.name for s in skill_registry.list_all()}

    results: list[dict[str, Any]] = []
    for entry in MARKETPLACE_CATALOG:
        if entry.name in installed_names:
            continue
        if category and entry.category != category:
            continue
        if search:
            haystack = f"{entry.name} {entry.description} {' '.join(entry.tags)}".lower()
            if search.lower() not in haystack:
                continue
        d = asdict(entry)
        d["installed"] = False
        results.append(d)

    return results


def get_marketplace_categories() -> list[dict[str, Any]]:
    """Return a list of categories with counts."""
    installed_names = {s.name for s in skill_registry.list_all()}
    cats: dict[str, int] = {}
    for entry in MARKETPLACE_CATALOG:
        if entry.name not in installed_names:
            cats[entry.category] = cats.get(entry.category, 0) + 1
    return [{"name": c, "count": n} for c, n in sorted(cats.items())]


class _DynamicSkill(BaseSkill):
    """Lightweight wrapper that creates a skill from a marketplace entry.

    Community skills in the real product would be pip-installable packages;
    for the POC this placeholder skill simply exists in the registry and
    advertises its metadata so the UI can track install state.
    """

    def __init__(self, entry: MarketplaceEntry) -> None:
        self.manifest = SkillManifest(
            name=entry.name,
            version=entry.version,
            description=entry.description,
            kind=SkillKind(entry.kind),
            risk_level=RiskLevel(entry.risk_level),
            author=entry.author,
            tags=list(entry.tags),
            dependencies=list(entry.dependencies),
        )
        super().__init__()

    def register(self) -> None:
        # Placeholder — real plugins would register actual tools here.
        logger.info("Marketplace skill %s installed (placeholder tools)", self.name)


def install_marketplace_skill(name: str) -> dict[str, Any]:
    """Install a skill from the marketplace catalogue into the registry.

    Returns a dict with status and the skill metadata.
    Raises ``ValueError`` if the skill is not in the catalogue or is
    already installed.
    """
    # Check not already installed
    if skill_registry.get(name):
        raise ValueError(f"Skill '{name}' is already installed")

    # Find in catalogue
    entry: MarketplaceEntry | None = None
    for e in MARKETPLACE_CATALOG:
        if e.name == name:
            entry = e
            break
    if not entry:
        raise ValueError(f"Skill '{name}' not found in the marketplace")

    # Create and load
    skill_instance = _DynamicSkill(entry)
    errors = skill_registry.load_skill(skill_instance)

    if errors:
        raise RuntimeError(f"Failed to install skill: {'; '.join(errors)}")

    # Persist to DB
    skill_registry._sync_db()

    return {
        "status": "installed",
        "name": entry.name,
        "version": entry.version,
        "description": entry.description,
    }


def uninstall_marketplace_skill(name: str) -> dict[str, str]:
    """Uninstall a marketplace-installed skill.

    Built-in skills cannot be uninstalled via this function.
    Raises ``ValueError`` if the skill cannot be uninstalled.
    """
    skill = skill_registry.get(name)
    if not skill:
        raise ValueError(f"Skill '{name}' not found")

    # Prevent uninstalling builtins
    if "builtin" in skill.manifest.tags:
        raise ValueError(f"Cannot uninstall built-in skill '{name}'")

    skill_registry.unload_skill(name)

    # Remove from DB
    try:
        from manch_backend.db.models import SkillRecord
        from manch_backend.db.session import SessionLocal
        from sqlalchemy import select

        with SessionLocal() as db:
            rec = db.execute(
                select(SkillRecord).where(SkillRecord.name == name)
            ).scalars().first()
            if rec:
                db.delete(rec)
                db.commit()
    except Exception:  # noqa: BLE001
        logger.exception("Failed to remove skill %s from DB", name)

    return {"status": "uninstalled", "name": name}
