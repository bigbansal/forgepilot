"""Built-in Angular Developer skill.

Provides Angular-specific tools for component generation, module scaffolding,
NgRx store creation, and Angular CLI command execution inside the sandbox.
"""
from __future__ import annotations

from typing import Any

from manch_backend.models import RiskLevel
from manch_backend.skills import BaseSkill, SkillKind, SkillManifest


class AngularDeveloperSkill(BaseSkill):
    manifest = SkillManifest(
        name="angular-developer",
        version="1.0.0",
        description=(
            "Angular 17+ development tools — component/service/pipe generation, "
            "NgRx signal-store scaffolding, Angular CLI wrappers, and best-practice "
            "linting helpers."
        ),
        kind=SkillKind.TOOL,
        risk_level=RiskLevel.MEDIUM,
        author="Manch",
        tags=["builtin", "angular", "frontend", "typescript"],
        dependencies=["sandbox-tools"],
        config_schema={
            "angular_version": {"type": "string", "default": "19", "description": "Target Angular major version"},
            "style_format": {"type": "string", "default": "scss", "description": "Default stylesheet format"},
            "standalone": {"type": "boolean", "default": True, "description": "Generate standalone components by default"},
        },
    )

    def register(self) -> None:
        from manch_backend.agents.tools import ToolSpec, register_tool, get_tool

        tools = [
            ToolSpec(
                name="ng_generate_component",
                description=(
                    "Generate an Angular standalone component with template, styles, and spec. "
                    "Usage: provide component name (e.g. 'user-profile') and optional path."
                ),
                risk_level=RiskLevel.MEDIUM,
                handler=self._generate_component,
            ),
            ToolSpec(
                name="ng_generate_service",
                description="Generate an Angular injectable service with spec file.",
                risk_level=RiskLevel.MEDIUM,
                handler=self._generate_service,
            ),
            ToolSpec(
                name="ng_generate_pipe",
                description="Generate an Angular standalone pipe with spec.",
                risk_level=RiskLevel.LOW,
                handler=self._generate_pipe,
            ),
            ToolSpec(
                name="ng_generate_guard",
                description="Generate an Angular functional route guard.",
                risk_level=RiskLevel.LOW,
                handler=self._generate_guard,
            ),
            ToolSpec(
                name="ng_generate_store",
                description="Scaffold an NgRx SignalStore with entity adapter and CRUD methods.",
                risk_level=RiskLevel.MEDIUM,
                handler=self._generate_store,
            ),
            ToolSpec(
                name="ng_cli",
                description=(
                    "Run any Angular CLI command (ng build, ng test, ng lint, ng serve, etc.) "
                    "inside the sandbox."
                ),
                risk_level=RiskLevel.MEDIUM,
                handler=self._ng_cli,
            ),
            ToolSpec(
                name="ng_analyze_bundle",
                description="Analyze Angular build bundle size and output a summary.",
                risk_level=RiskLevel.LOW,
                handler=self._analyze_bundle,
            ),
        ]

        for spec in tools:
            if not get_tool(spec.name):
                register_tool(spec)

    # ── Tool handlers ────────────────────────────────

    @staticmethod
    def _generate_component(sandbox_session_id: str, name: str, path: str = "src/app", **_: Any):
        from manch_backend.agents.tools import _run_sandbox_command
        return _run_sandbox_command(
            sandbox_session_id,
            f"cd /workspace && npx ng generate component {name} --path={path} "
            f"--standalone --style=scss --skip-tests=false 2>&1",
        )

    @staticmethod
    def _generate_service(sandbox_session_id: str, name: str, path: str = "src/app/core/services", **_: Any):
        from manch_backend.agents.tools import _run_sandbox_command
        return _run_sandbox_command(
            sandbox_session_id,
            f"cd /workspace && npx ng generate service {name} --path={path} 2>&1",
        )

    @staticmethod
    def _generate_pipe(sandbox_session_id: str, name: str, path: str = "src/app/shared/pipes", **_: Any):
        from manch_backend.agents.tools import _run_sandbox_command
        return _run_sandbox_command(
            sandbox_session_id,
            f"cd /workspace && npx ng generate pipe {name} --path={path} --standalone 2>&1",
        )

    @staticmethod
    def _generate_guard(sandbox_session_id: str, name: str, path: str = "src/app/core/guards", **_: Any):
        from manch_backend.agents.tools import _run_sandbox_command
        return _run_sandbox_command(
            sandbox_session_id,
            f"cd /workspace && npx ng generate guard {name} --path={path} --functional 2>&1",
        )

    @staticmethod
    def _generate_store(sandbox_session_id: str, name: str, path: str = "src/app/core/store", **_: Any):
        from manch_backend.agents.tools import _run_sandbox_command, _write_file
        import shlex

        store_content = f"""import {{ computed }} from '@angular/core';
import {{ signalStore, withState, withComputed, withMethods, patchState }} from '@ngrx/signals';

export interface {name.title().replace('-', '')}State {{
  items: any[];
  loading: boolean;
  error: string | null;
}}

const initialState: {name.title().replace('-', '')}State = {{
  items: [],
  loading: false,
  error: null,
}};

export const {name.title().replace('-', '')}Store = signalStore(
  {{ providedIn: 'root' }},
  withState(initialState),
  withComputed((state) => ({{
    itemCount: computed(() => state.items().length),
    hasError: computed(() => state.error() !== null),
  }})),
  withMethods((store) => ({{
    setLoading(loading: boolean) {{
      patchState(store, {{ loading }});
    }},
    setItems(items: any[]) {{
      patchState(store, {{ items, loading: false, error: null }});
    }},
    setError(error: string) {{
      patchState(store, {{ error, loading: false }});
    }},
    reset() {{
      patchState(store, initialState);
    }},
  }})),
);
"""
        return _write_file(sandbox_session_id, f"{path}/{name}.store.ts", store_content)

    @staticmethod
    def _ng_cli(sandbox_session_id: str, command: str, **_: Any):
        from manch_backend.agents.tools import _run_sandbox_command
        import shlex
        safe_cmd = shlex.quote(command)
        return _run_sandbox_command(
            sandbox_session_id,
            f"cd /workspace && npx ng {safe_cmd} 2>&1 | tail -100",
        )

    @staticmethod
    def _analyze_bundle(sandbox_session_id: str, **_: Any):
        from manch_backend.agents.tools import _run_sandbox_command
        return _run_sandbox_command(
            sandbox_session_id,
            "cd /workspace && npx ng build --configuration=production --stats-json 2>&1 | tail -30"
            " && echo '---' && cat dist/*/stats.json 2>/dev/null | python3 -c '"
            "import sys,json; d=json.load(sys.stdin); "
            "assets=d.get(\"assets\",[]); "
            "[print(f\"{a[\"name\"]:50s} {a[\"size\"]/1024:.1f} KB\") for a in sorted(assets, key=lambda x:-x[\"size\"])[:20]]"
            "' 2>/dev/null || echo 'Bundle analysis complete'",
        )


# Module-level instance for auto-discovery
skill = AngularDeveloperSkill()
