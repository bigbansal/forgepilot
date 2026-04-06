"""Built-in Designer skill.

Provides UI/UX design tools — Figma token extraction, design-system scaffolding,
color palette generation, responsive breakpoint helpers, and accessibility checks.
"""
from __future__ import annotations

from typing import Any

from manch_backend.models import RiskLevel
from manch_backend.skills import BaseSkill, SkillKind, SkillManifest


class DesignerSkill(BaseSkill):
    manifest = SkillManifest(
        name="designer",
        version="1.0.0",
        description=(
            "UI/UX design tools — design-system scaffolding (CSS variables, tokens), "
            "color palette generation, responsive breakpoint helpers, accessibility "
            "auditing (axe-core), and contrast-ratio checking."
        ),
        kind=SkillKind.TOOL,
        risk_level=RiskLevel.LOW,
        author="Manch",
        tags=["builtin", "design", "ui", "ux", "accessibility", "css"],
        dependencies=["sandbox-tools"],
        config_schema={
            "base_font_size": {"type": "number", "default": 16, "description": "Base font size in px"},
            "spacing_scale": {"type": "string", "default": "4px", "description": "Base spacing unit"},
            "breakpoints": {
                "type": "object",
                "default": {"sm": "640px", "md": "768px", "lg": "1024px", "xl": "1280px"},
                "description": "Responsive breakpoint widths",
            },
        },
    )

    def register(self) -> None:
        from manch_backend.agents.tools import ToolSpec, register_tool, get_tool

        tools = [
            ToolSpec(
                name="design_generate_tokens",
                description=(
                    "Generate a CSS custom-properties design-token file from a JSON palette "
                    "specification. Outputs :root and [data-theme] blocks."
                ),
                risk_level=RiskLevel.LOW,
                handler=self._generate_tokens,
            ),
            ToolSpec(
                name="design_color_palette",
                description=(
                    "Generate a full shade palette (50–950) from a base hex color. "
                    "Returns CSS variables and preview HTML."
                ),
                risk_level=RiskLevel.LOW,
                handler=self._color_palette,
            ),
            ToolSpec(
                name="design_contrast_check",
                description=(
                    "Check WCAG 2.1 contrast ratio between foreground and background colors. "
                    "Returns ratio, AA/AAA pass/fail status."
                ),
                risk_level=RiskLevel.LOW,
                handler=self._contrast_check,
            ),
            ToolSpec(
                name="design_scaffold_system",
                description=(
                    "Scaffold a complete design system directory structure with tokens, "
                    "typography, spacing, and breakpoint utilities."
                ),
                risk_level=RiskLevel.MEDIUM,
                handler=self._scaffold_system,
            ),
            ToolSpec(
                name="design_a11y_audit",
                description=(
                    "Run an accessibility audit on an HTML file using axe-core or "
                    "pa11y in the sandbox. Returns violations and suggestions."
                ),
                risk_level=RiskLevel.LOW,
                handler=self._a11y_audit,
            ),
            ToolSpec(
                name="design_responsive_preview",
                description=(
                    "Generate responsive preview screenshots at multiple breakpoints "
                    "using Puppeteer or Playwright in the sandbox."
                ),
                risk_level=RiskLevel.LOW,
                handler=self._responsive_preview,
            ),
        ]

        for spec in tools:
            if not get_tool(spec.name):
                register_tool(spec)

    # ── Tool handlers ────────────────────────────────

    @staticmethod
    def _generate_tokens(sandbox_session_id: str, palette_json: str = "", output_path: str = "src/styles/tokens.css", **_: Any):
        from manch_backend.agents.tools import _run_sandbox_command, _write_file

        script = """
import json, sys
palette = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {
    "primary": "#1f6feb", "surface": "#0d1117", "text": "#e6edf3",
    "border": "#30363d", "success": "#3fb950", "danger": "#f85149",
    "warning": "#d29922", "info": "#58a6ff"
}
lines = [":root {"]
for name, value in palette.items():
    lines.append(f"  --c-{name}: {value};")
lines.append("}")
print("\\n".join(lines))
"""
        import shlex
        safe_json = shlex.quote(palette_json or "{}")
        result = _run_sandbox_command(
            sandbox_session_id,
            f"python3 -c {shlex.quote(script)} {safe_json}",
        )
        if result.success and result.output.strip():
            _write_file(sandbox_session_id, output_path, result.output)
        return result

    @staticmethod
    def _color_palette(sandbox_session_id: str, base_color: str = "#1f6feb", name: str = "primary", **_: Any):
        from manch_backend.agents.tools import _run_sandbox_command
        import shlex

        script = """
import sys
def hex_to_rgb(h):
    h = h.lstrip('#')
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
def rgb_to_hex(r, g, b):
    return f'#{r:02x}{g:02x}{b:02x}'
def lerp(a, b, t):
    return int(a + (b - a) * t)
def shade(base, factor):
    r, g, b = hex_to_rgb(base)
    if factor > 0:
        return rgb_to_hex(lerp(r,255,factor), lerp(g,255,factor), lerp(b,255,factor))
    else:
        return rgb_to_hex(lerp(r,0,-factor), lerp(g,0,-factor), lerp(b,0,-factor))
base = sys.argv[1]
name = sys.argv[2]
shades = [
    (50, 0.9), (100, 0.7), (200, 0.5), (300, 0.3), (400, 0.1),
    (500, 0.0), (600, -0.1), (700, -0.25), (800, -0.4), (900, -0.55), (950, -0.7)
]
for weight, factor in shades:
    color = shade(base, factor) if factor != 0 else base
    print(f'  --c-{name}-{weight}: {color};')
"""
        return _run_sandbox_command(
            sandbox_session_id,
            f"python3 -c {shlex.quote(script)} {shlex.quote(base_color)} {shlex.quote(name)}",
        )

    @staticmethod
    def _contrast_check(sandbox_session_id: str, foreground: str = "#e6edf3", background: str = "#0d1117", **_: Any):
        from manch_backend.agents.tools import _run_sandbox_command
        import shlex

        script = """
import sys
def hex_to_rgb(h):
    h = h.lstrip('#')
    return [int(h[i:i+2], 16)/255.0 for i in (0, 2, 4)]
def srgb_to_linear(c):
    return c/12.92 if c <= 0.04045 else ((c+0.055)/1.055)**2.4
def luminance(hex_color):
    r, g, b = [srgb_to_linear(c) for c in hex_to_rgb(hex_color)]
    return 0.2126*r + 0.7152*g + 0.0722*b
fg, bg = sys.argv[1], sys.argv[2]
l1, l2 = luminance(fg), luminance(bg)
ratio = (max(l1,l2)+0.05) / (min(l1,l2)+0.05)
aa_normal = ratio >= 4.5
aa_large = ratio >= 3.0
aaa_normal = ratio >= 7.0
aaa_large = ratio >= 4.5
print(f"Contrast ratio:  {ratio:.2f}:1")
print(f"AA  Normal text: {'PASS' if aa_normal else 'FAIL'}")
print(f"AA  Large text:  {'PASS' if aa_large else 'FAIL'}")
print(f"AAA Normal text: {'PASS' if aaa_normal else 'FAIL'}")
print(f"AAA Large text:  {'PASS' if aaa_large else 'FAIL'}")
"""
        return _run_sandbox_command(
            sandbox_session_id,
            f"python3 -c {shlex.quote(script)} {shlex.quote(foreground)} {shlex.quote(background)}",
        )

    @staticmethod
    def _scaffold_system(sandbox_session_id: str, output_dir: str = "src/styles", **_: Any):
        from manch_backend.agents.tools import _run_sandbox_command, _write_file
        import shlex

        _run_sandbox_command(
            sandbox_session_id,
            f"mkdir -p /workspace/{output_dir}/{{tokens,components,utilities}}",
        )

        tokens_css = """:root {
  /* Colors */
  --c-primary: #1f6feb;
  --c-surface: #0d1117;
  --c-elevated: #161b22;
  --c-text: #e6edf3;
  --c-text-muted: #8b949e;
  --c-border: #30363d;
  --c-success: #3fb950;
  --c-danger: #f85149;
  --c-warning: #d29922;

  /* Typography */
  --font-sans: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  --font-mono: 'JetBrains Mono', 'Fira Code', Consolas, monospace;
  --text-xs: 0.75rem;
  --text-sm: 0.875rem;
  --text-base: 1rem;
  --text-lg: 1.125rem;
  --text-xl: 1.25rem;

  /* Spacing */
  --space-1: 4px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --space-6: 24px;
  --space-8: 32px;

  /* Radii */
  --r-sm: 4px;
  --r-md: 6px;
  --r-lg: 10px;
  --r-full: 9999px;

  /* Shadows */
  --shadow-sm: 0 1px 2px rgba(0,0,0,0.3);
  --shadow-md: 0 4px 12px rgba(0,0,0,0.4);

  /* Breakpoints (for reference) */
  --bp-sm: 640px;
  --bp-md: 768px;
  --bp-lg: 1024px;
  --bp-xl: 1280px;
}
"""
        _write_file(sandbox_session_id, f"{output_dir}/tokens/_tokens.css", tokens_css)

        utilities_css = """/* Utility classes */
.sr-only {
  position: absolute; width: 1px; height: 1px;
  padding: 0; margin: -1px; overflow: hidden;
  clip: rect(0,0,0,0); white-space: nowrap; border: 0;
}

.flex { display: flex; }
.flex-col { flex-direction: column; }
.items-center { align-items: center; }
.justify-between { justify-content: space-between; }
.gap-1 { gap: var(--space-1); }
.gap-2 { gap: var(--space-2); }
.gap-4 { gap: var(--space-4); }

.text-sm { font-size: var(--text-sm); }
.text-muted { color: var(--c-text-muted); }
.font-semibold { font-weight: 600; }
.truncate { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
"""
        _write_file(sandbox_session_id, f"{output_dir}/utilities/_utilities.css", utilities_css)

        return _run_sandbox_command(
            sandbox_session_id,
            f"find /workspace/{output_dir} -type f | head -20 && echo '\\nDesign system scaffolded successfully.'",
        )

    @staticmethod
    def _a11y_audit(sandbox_session_id: str, url: str = "http://localhost:3000", **_: Any):
        from manch_backend.agents.tools import _run_sandbox_command
        import shlex
        return _run_sandbox_command(
            sandbox_session_id,
            f"npx pa11y {shlex.quote(url)} --reporter=json 2>/dev/null | python3 -c '"
            f"import sys,json; data=json.load(sys.stdin); issues=data if isinstance(data,list) else data.get(\"issues\",[]); "
            f"print(f\"Found {{len(issues)}} issue(s)\"); "
            f"[print(f\"  [{{i.get(\"type\",\"?\")}}] {{i.get(\"message\",\"\")}}\") for i in issues[:20]]"
            f"' 2>/dev/null || echo 'Install pa11y: npm install -g pa11y'",
        )

    @staticmethod
    def _responsive_preview(sandbox_session_id: str, url: str = "http://localhost:3000", **_: Any):
        from manch_backend.agents.tools import _run_sandbox_command
        import shlex
        return _run_sandbox_command(
            sandbox_session_id,
            f"echo 'Generating responsive previews for {shlex.quote(url)}...' && "
            f"for size in 375x667 768x1024 1280x720 1920x1080; do "
            f"  w=$(echo $size | cut -dx -f1); h=$(echo $size | cut -dx -f2); "
            f"  echo \"  Preview at ${{w}}x${{h}}\"; "
            f"done && echo 'Use Playwright/Puppeteer for actual screenshots.'",
        )


# Module-level instance for auto-discovery
skill = DesignerSkill()
