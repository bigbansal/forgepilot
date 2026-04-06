"""Skill registry — discovers, loads, and manages skill lifecycle.

Discovery sources (in order):
1. Built-in skills under ``skills/builtins/``
2. Local skills from a configurable directory
3. pip-installed entry-points in the ``manch.skills`` group

The registry is the single authority for which skills are active.
It integrates with the DB ``SkillRecord`` to persist enable/disable
state and per-skill configuration.
"""
from __future__ import annotations

import importlib
import logging
from pathlib import Path
from typing import Any
from uuid import uuid4

from manch_backend.skills import BaseSkill, SkillManifest

logger = logging.getLogger(__name__)


class SkillRegistry:
    """Global singleton that owns every known skill instance."""

    def __init__(self) -> None:
        self._skills: dict[str, BaseSkill] = {}
        self._disabled: set[str] = set()

    # ── Query ────────────────────────────────────────

    def get(self, name: str) -> BaseSkill | None:
        return self._skills.get(name)

    def list_all(self) -> list[BaseSkill]:
        return list(self._skills.values())

    def list_enabled(self) -> list[BaseSkill]:
        return [s for s in self._skills.values() if s.name not in self._disabled]

    def is_enabled(self, name: str) -> bool:
        return name in self._skills and name not in self._disabled

    # ── Lifecycle ────────────────────────────────────

    def load_skill(self, skill: BaseSkill, config: dict[str, Any] | None = None) -> list[str]:
        """Run a skill through its full lifecycle.

        Returns a list of errors (empty = success).
        """
        if config:
            skill.config.update(config)

        errors: list[str] = []

        # init
        try:
            skill.init()
        except Exception as exc:  # noqa: BLE001
            logger.exception("Skill %s init() failed", skill.name)
            errors.append(f"init failed: {exc}")
            return errors

        # validate
        try:
            validation_errors = skill.validate()
            if validation_errors:
                errors.extend(validation_errors)
                return errors
        except Exception as exc:  # noqa: BLE001
            logger.exception("Skill %s validate() failed", skill.name)
            errors.append(f"validate failed: {exc}")
            return errors

        # register
        try:
            skill.register()
        except Exception as exc:  # noqa: BLE001
            logger.exception("Skill %s register() failed", skill.name)
            errors.append(f"register failed: {exc}")
            return errors

        self._skills[skill.name] = skill
        logger.info("Loaded skill: %s v%s", skill.name, skill.manifest.version)
        # Write SKILL.md to both local CLI skill directories immediately.
        self.sync_local_skill_files(skill)
        return []

    def unload_skill(self, name: str) -> None:
        """Teardown and remove a skill."""
        skill = self._skills.pop(name, None)
        if skill:
            try:
                skill.teardown()
            except Exception:  # noqa: BLE001
                logger.exception("Skill %s teardown() failed", name)
        self._disabled.discard(name)
        # Remove SKILL.md from both local CLI skill directories.
        self._remove_local_skill_files(name)

    def enable(self, name: str) -> bool:
        """Enable a previously disabled skill (re-registers it)."""
        skill = self._skills.get(name)
        if not skill:
            return False
        self._disabled.discard(name)
        try:
            skill.register()
        except Exception:  # noqa: BLE001
            logger.exception("Skill %s re-register on enable failed", name)
            return False
        self._persist_state(name, enabled=True)
        # Write SKILL.md to local CLI skill directories on re-enable.
        self.sync_local_skill_files(skill)
        return True

    def disable(self, name: str) -> bool:
        """Disable a loaded skill (calls teardown)."""
        skill = self._skills.get(name)
        if not skill:
            return False
        self._disabled.add(name)
        try:
            skill.teardown()
        except Exception:  # noqa: BLE001
            logger.exception("Skill %s teardown on disable failed", name)
        self._persist_state(name, enabled=False)
        # Remove SKILL.md from local CLI skill directories when disabled.
        self._remove_local_skill_files(name)
        return True

    # ── Discovery ────────────────────────────────────

    def discover_builtins(self) -> None:
        """Import all modules in ``skills/builtins/`` so built-in skills
        self-register via their module-level code.
        """
        builtins_dir = Path(__file__).parent / "builtins"
        if not builtins_dir.exists():
            return
        for py_file in sorted(builtins_dir.glob("*.py")):
            if py_file.name.startswith("_"):
                continue
            module_name = f"manch_backend.skills.builtins.{py_file.stem}"
            try:
                mod = importlib.import_module(module_name)
                # Convention: module exposes a ``skill`` instance
                skill_instance: BaseSkill | None = getattr(mod, "skill", None)
                if skill_instance:
                    self.load_skill(skill_instance)
            except Exception:  # noqa: BLE001
                logger.exception("Failed to import built-in skill module %s", module_name)

    def discover_entrypoints(self) -> None:
        """Discover pip-installed skills via ``manch.skills`` entry-points."""
        try:
            from importlib.metadata import entry_points
        except ImportError:
            return

        eps = entry_points()
        # Python ≥ 3.12 returns a SelectableGroups; earlier returns dict
        skill_eps = eps.select(group="manch.skills") if hasattr(eps, "select") else eps.get("manch.skills", [])

        for ep in skill_eps:
            try:
                skill_cls_or_instance = ep.load()
                if isinstance(skill_cls_or_instance, type) and issubclass(skill_cls_or_instance, BaseSkill):
                    instance = skill_cls_or_instance()
                elif isinstance(skill_cls_or_instance, BaseSkill):
                    instance = skill_cls_or_instance
                else:
                    logger.warning("Entry-point %s did not resolve to a BaseSkill", ep.name)
                    continue

                # Load config from DB
                config = self._load_config(instance.name)
                self.load_skill(instance, config=config)
            except Exception:  # noqa: BLE001
                logger.exception("Failed to load entry-point skill %s", ep.name)

    def discover_all(self) -> None:
        """Run all discovery sources and sync state with DB."""
        self.discover_builtins()
        self.discover_custom()
        self.discover_entrypoints()
        self._sync_db()

    def discover_custom(self) -> None:
        """Import all modules in ``skills/custom/`` so user-created skills
        self-register via their module-level ``skill`` instance.
        """
        custom_dir = Path(__file__).parent / "custom"
        if not custom_dir.exists():
            return
        for py_file in sorted(custom_dir.glob("*.py")):
            if py_file.name.startswith("_"):
                continue
            module_name = f"manch_backend.skills.custom.{py_file.stem}"
            try:
                mod = importlib.import_module(module_name)
                skill_instance: BaseSkill | None = getattr(mod, "skill", None)
                if skill_instance:
                    self.load_skill(skill_instance)
            except Exception:  # noqa: BLE001
                logger.exception("Failed to import custom skill module %s", module_name)

    # ── DB persistence helpers ───────────────────────

    @staticmethod
    def _load_config(name: str) -> dict[str, Any]:
        """Read per-skill config from the ``skills`` table."""
        import json
        try:
            from manch_backend.db.models import SkillRecord
            from manch_backend.db.session import SessionLocal
            with SessionLocal() as db:
                from sqlalchemy import select
                rec = db.execute(
                    select(SkillRecord).where(SkillRecord.name == name)
                ).scalars().first()
                if rec and rec.config_json:
                    return json.loads(rec.config_json)
        except Exception:  # noqa: BLE001
            pass
        return {}

    @staticmethod
    def _persist_state(name: str, enabled: bool) -> None:
        """Update the ``enabled`` flag in the ``skills`` table."""
        try:
            from manch_backend.db.models import SkillRecord
            from manch_backend.db.session import SessionLocal
            from sqlalchemy import select
            with SessionLocal() as db:
                rec = db.execute(
                    select(SkillRecord).where(SkillRecord.name == name)
                ).scalars().first()
                if rec:
                    rec.enabled = enabled
                    db.commit()
        except Exception:  # noqa: BLE001
            logger.exception("Failed to persist skill state for %s", name)

    def _sync_db(self) -> None:
        """Ensure every loaded skill has a row in ``skills``, and respect
        previously-disabled state.
        """
        import json
        try:
            from manch_backend.db.models import SkillRecord
            from manch_backend.db.session import SessionLocal
            from sqlalchemy import select
            with SessionLocal() as db:
                for skill in self._skills.values():
                    rec = db.execute(
                        select(SkillRecord).where(SkillRecord.name == skill.name)
                    ).scalars().first()
                    if not rec:
                        rec = SkillRecord(
                            id=str(uuid4()),
                            name=skill.name,
                            version=skill.manifest.version,
                            description=skill.manifest.description,
                            kind=skill.manifest.kind.value,
                            risk_level=skill.manifest.risk_level.value,
                            author=skill.manifest.author,
                            tags_json=json.dumps(skill.manifest.tags),
                            config_json=json.dumps(skill.config) if skill.config else None,
                            enabled=True,
                        )
                        db.add(rec)
                    else:
                        # Respect DB disable state
                        if not rec.enabled:
                            self._disabled.add(skill.name)
                            try:
                                skill.teardown()
                            except Exception:  # noqa: BLE001
                                pass
                        # Update version if changed
                        rec.version = skill.manifest.version
                        rec.description = skill.manifest.description
                db.commit()
        except Exception:  # noqa: BLE001
            logger.exception("Failed to sync skill DB state")

    # ── Local skill file sync ────────────────────────

    # Directories (inside the container) that are bind-mounted from the host's
    # ~/.codex/skills and ~/.gemini/skills via docker-compose.
    _LOCAL_SKILL_DIRS: tuple[str, ...] = (
        "/root/.codex/skills",
        "/root/.gemini/skills",
    )

    def sync_local_skill_files(self, skill: "BaseSkill") -> None:
        """Write a SKILL.md for *skill* into every local CLI skill directory.

        These directories are bind-mounted from the developer's host machine
        (``~/.codex/skills`` and ``~/.gemini/skills``) so the file appears
        immediately on the local filesystem without any extra step.
        """
        import os

        try:
            content = skill.to_skill_md()
        except Exception:  # noqa: BLE001
            logger.warning("Skill %s to_skill_md() failed; skipping local sync", skill.name)
            return

        for base in self._LOCAL_SKILL_DIRS:
            skill_dir = os.path.join(base, skill.name)
            try:
                os.makedirs(skill_dir, exist_ok=True)
                skill_md_path = os.path.join(skill_dir, "SKILL.md")
                with open(skill_md_path, "w", encoding="utf-8") as fh:
                    fh.write(content)
                logger.debug("Wrote %s", skill_md_path)
            except OSError as exc:
                # Non-fatal: the directory may not be writable (e.g. during
                # unit tests or when the volume is not mounted).
                logger.debug("Could not write SKILL.md to %s: %s", skill_dir, exc)

    def sync_all_local_skill_files(self) -> int:
        """Write SKILL.md for every *enabled* skill to local CLI directories.

        Returns the count of skills successfully synced.
        """
        count = 0
        for skill in self.list_enabled():
            self.sync_local_skill_files(skill)
            count += 1
        return count

    def _remove_local_skill_files(self, name: str) -> None:
        """Remove the SKILL.md (and skill directory if empty) for *name* from
        every local CLI skill directory.
        """
        import os
        import shutil

        for base in self._LOCAL_SKILL_DIRS:
            skill_dir = os.path.join(base, name)
            try:
                if os.path.isdir(skill_dir):
                    shutil.rmtree(skill_dir)
                    logger.debug("Removed local skill dir %s", skill_dir)
            except OSError as exc:
                logger.debug("Could not remove %s: %s", skill_dir, exc)

    # ── CLI skill injection ──────────────────────────

    def build_skill_injection_cmd(self, runner: str) -> str:
        """Return a shell command (or empty string) that writes SKILL.md files
        for every enabled skill into the discovery directory used by the given
        CLI runner (``"codex-cli"`` or ``"gemini-cli"``).

        The content is base64-encoded before embedding in the command so that
        special characters in skill descriptions never break shell quoting.

        The returned string always ends with `` && `` so callers can simply
        prepend it to the main CLI invocation::

            cmd = skill_registry.build_skill_injection_cmd("codex-cli") + main_cmd
        """
        import base64

        runner = runner.lower()
        if runner == "codex-cli":
            skills_dir = "/root/.codex/skills"
        elif runner in ("gemini-cli", "opensandbox"):
            skills_dir = "/root/.gemini/skills"
        else:
            return ""

        enabled = self.list_enabled()
        if not enabled:
            return ""

        parts: list[str] = [f"mkdir -p {skills_dir}"]
        for skill in enabled:
            try:
                content = skill.to_skill_md()
            except Exception:  # noqa: BLE001
                logger.warning("Skill %s to_skill_md() failed; skipping injection", skill.name)
                continue
            encoded = base64.b64encode(content.encode()).decode()
            skill_dir = f"{skills_dir}/{skill.name}"
            parts.append(
                f"mkdir -p {skill_dir} && "
                f"echo '{encoded}' | base64 -d > {skill_dir}/SKILL.md"
            )

        if len(parts) <= 1:
            # Only the mkdir, no skills — nothing useful to prepend
            return ""

        return " && ".join(parts) + " && "


# Module-level singleton
skill_registry = SkillRegistry()
