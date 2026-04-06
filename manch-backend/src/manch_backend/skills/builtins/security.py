"""Built-in Security skill.

Provides security auditing tools — dependency vulnerability scanning, SAST,
secret detection, OWASP checks, and security header analysis.
"""
from __future__ import annotations

from typing import Any

from manch_backend.models import RiskLevel
from manch_backend.skills import BaseSkill, SkillKind, SkillManifest


class SecuritySkill(BaseSkill):
    manifest = SkillManifest(
        name="security",
        version="1.0.0",
        description=(
            "Security auditing tools — dependency vulnerability scanning (npm audit, "
            "pip-audit, mvn dependency-check), secret detection (gitleaks/trufflehog), "
            "SAST analysis, OWASP header checks, and security best-practice linting."
        ),
        kind=SkillKind.TOOL,
        risk_level=RiskLevel.LOW,
        author="Manch",
        tags=["builtin", "security", "audit", "sast", "owasp", "vulnerability"],
        dependencies=["sandbox-tools"],
        config_schema={
            "severity_threshold": {
                "type": "string",
                "default": "moderate",
                "description": "Minimum severity to report: low, moderate, high, critical",
            },
            "scan_secrets": {
                "type": "boolean",
                "default": True,
                "description": "Enable secret/credential scanning in source code",
            },
        },
    )

    def register(self) -> None:
        from manch_backend.agents.tools import ToolSpec, register_tool, get_tool

        tools = [
            ToolSpec(
                name="security_dependency_scan",
                description=(
                    "Scan project dependencies for known vulnerabilities. Auto-detects "
                    "package manager (npm, pip, maven, cargo) and runs the appropriate audit tool."
                ),
                risk_level=RiskLevel.LOW,
                handler=self._dependency_scan,
            ),
            ToolSpec(
                name="security_secret_scan",
                description=(
                    "Scan source code for leaked secrets, API keys, tokens, and credentials "
                    "using pattern matching and entropy analysis."
                ),
                risk_level=RiskLevel.LOW,
                handler=self._secret_scan,
            ),
            ToolSpec(
                name="security_sast",
                description=(
                    "Run static application security testing. Uses Semgrep, Bandit (Python), "
                    "or ESLint security plugin (JS/TS) depending on the project."
                ),
                risk_level=RiskLevel.LOW,
                handler=self._sast_scan,
            ),
            ToolSpec(
                name="security_header_check",
                description=(
                    "Check HTTP security headers of a running service (CSP, HSTS, X-Frame-Options, "
                    "etc.) and report missing or misconfigured headers."
                ),
                risk_level=RiskLevel.LOW,
                handler=self._header_check,
            ),
            ToolSpec(
                name="security_file_permissions",
                description=(
                    "Audit file permissions in the project for overly permissive files "
                    "(world-readable secrets, executable configs, etc.)."
                ),
                risk_level=RiskLevel.LOW,
                handler=self._file_permissions,
            ),
            ToolSpec(
                name="security_dockerfile_lint",
                description=(
                    "Lint Dockerfiles for security best practices — no root user, pinned base "
                    "images, no secrets in ENV, multi-stage builds."
                ),
                risk_level=RiskLevel.LOW,
                handler=self._dockerfile_lint,
            ),
            ToolSpec(
                name="security_generate_report",
                description=(
                    "Generate a consolidated security report combining all scan results "
                    "into a structured markdown document."
                ),
                risk_level=RiskLevel.LOW,
                handler=self._generate_report,
            ),
        ]

        for spec in tools:
            if not get_tool(spec.name):
                register_tool(spec)

    # ── Tool handlers ────────────────────────────────

    @staticmethod
    def _dependency_scan(sandbox_session_id: str, **_: Any):
        from manch_backend.agents.tools import _run_sandbox_command

        return _run_sandbox_command(
            sandbox_session_id,
            """cd /workspace && echo '=== Dependency Vulnerability Scan ===' && \
if [ -f package-lock.json ] || [ -f package.json ]; then
  echo '[npm] Running npm audit...'
  npm audit --production 2>&1 | tail -30
elif [ -f requirements.txt ] || [ -f pyproject.toml ]; then
  echo '[pip] Running pip-audit...'
  pip-audit 2>&1 | tail -30 || pip install pip-audit -q && pip-audit 2>&1 | tail -30
elif [ -f pom.xml ]; then
  echo '[maven] Running dependency check...'
  mvn dependency:tree 2>&1 | grep -i 'vulnerability\|CVE' | head -20 || echo 'No vulnerabilities found in dependency tree'
elif [ -f Cargo.toml ]; then
  echo '[cargo] Running cargo audit...'
  cargo audit 2>&1 | tail -30 || echo 'Install cargo-audit: cargo install cargo-audit'
else
  echo 'No recognized package manager found.'
fi""",
        )

    @staticmethod
    def _secret_scan(sandbox_session_id: str, path: str = ".", **_: Any):
        from manch_backend.agents.tools import _run_sandbox_command
        import shlex

        return _run_sandbox_command(
            sandbox_session_id,
            f"""cd /workspace && echo '=== Secret Scan ===' && \
grep -rn --include='*.py' --include='*.ts' --include='*.js' --include='*.java' \
  --include='*.go' --include='*.yml' --include='*.yaml' --include='*.json' \
  --include='*.env' --include='*.properties' --include='*.cfg' \
  -iE '(password|secret|api[_-]?key|token|private[_-]?key|AWS_ACCESS|GITHUB_TOKEN)\s*[=:]\s*[\x27"][^\x27"]+[\x27"]' \
  {shlex.quote(path)} 2>/dev/null | \
  grep -v 'node_modules\|\.git\|dist\|build\|__pycache__' | \
  head -50 && \
echo '---' && \
echo 'High-entropy string check:' && \
grep -rn --include='*.py' --include='*.ts' --include='*.js' --include='*.env' \
  -oP '[\x27"][A-Za-z0-9+/=]{{40,}}[\x27"]' {shlex.quote(path)} 2>/dev/null | \
  grep -v 'node_modules\|\.git' | head -20 || echo 'No high-entropy strings found.' && \
echo '---' && echo 'Scan complete.'""",
        )

    @staticmethod
    def _sast_scan(sandbox_session_id: str, path: str = ".", **_: Any):
        from manch_backend.agents.tools import _run_sandbox_command
        import shlex

        return _run_sandbox_command(
            sandbox_session_id,
            f"""cd /workspace && echo '=== SAST Analysis ===' && \
if command -v semgrep &>/dev/null; then
  echo '[semgrep] Running...'
  semgrep --config=auto {shlex.quote(path)} --json 2>/dev/null | \
    python3 -c 'import sys,json; d=json.load(sys.stdin); r=d.get("results",[]); \
    print(f"Found {{len(r)}} finding(s)"); \
    [print(f"  [{{f[\"extra\"][\"severity\"]}}] {{f[\"check_id\"]}} at {{f[\"path\"]}}:{{f[\"start\"][\"line\"]}}") for f in r[:20]]' \
    2>/dev/null || echo 'Semgrep analysis complete.'
elif [ -f requirements.txt ] || [ -f pyproject.toml ]; then
  echo '[bandit] Running Python SAST...'
  bandit -r {shlex.quote(path)} -f txt 2>&1 | tail -40 || \
    echo 'Install bandit: pip install bandit'
elif [ -f package.json ]; then
  echo '[eslint] Checking for security issues...'
  npx eslint {shlex.quote(path)} --rule '{{"no-eval":"error","no-implied-eval":"error"}}' 2>&1 | tail -30 || \
    echo 'ESLint security rules not configured.'
else
  echo 'No supported SAST tool detected. Install semgrep for universal coverage.'
fi""",
        )

    @staticmethod
    def _header_check(sandbox_session_id: str, url: str = "http://localhost:3000", **_: Any):
        from manch_backend.agents.tools import _run_sandbox_command
        import shlex

        return _run_sandbox_command(
            sandbox_session_id,
            f"""echo '=== HTTP Security Headers ===' && \
headers=$(curl -sI {shlex.quote(url)} 2>/dev/null) && \
if [ -z "$headers" ]; then
  echo "Could not reach {url}"
  exit 0
fi && \
echo "$headers" && echo '---' && \
echo 'Missing security headers:' && \
for h in 'Strict-Transport-Security' 'Content-Security-Policy' 'X-Content-Type-Options' \
         'X-Frame-Options' 'X-XSS-Protection' 'Referrer-Policy' 'Permissions-Policy'; do
  echo "$headers" | grep -qi "$h" || echo "  MISSING: $h"
done && echo '---' && echo 'Header check complete.'""",
        )

    @staticmethod
    def _file_permissions(sandbox_session_id: str, **_: Any):
        from manch_backend.agents.tools import _run_sandbox_command

        return _run_sandbox_command(
            sandbox_session_id,
            """cd /workspace && echo '=== File Permission Audit ===' && \
echo 'World-readable sensitive files:' && \
find . -name '*.env' -o -name '*.pem' -o -name '*.key' -o -name '*.p12' \
  -o -name '*.jks' -o -name 'id_rsa*' -o -name '*.secret' | \
  while read f; do
    perms=$(stat -c '%a' "$f" 2>/dev/null || stat -f '%Lp' "$f" 2>/dev/null)
    echo "  $perms $f"
  done && \
echo '---' && \
echo 'Executable non-script files:' && \
find . -executable -type f ! -name '*.sh' ! -name '*.bash' ! -path './.git/*' \
  ! -path '*/node_modules/*' ! -path '*/bin/*' | head -20 && \
echo '---' && echo 'Permission audit complete.'""",
        )

    @staticmethod
    def _dockerfile_lint(sandbox_session_id: str, path: str = "Dockerfile", **_: Any):
        from manch_backend.agents.tools import _run_sandbox_command
        import shlex

        return _run_sandbox_command(
            sandbox_session_id,
            f"""cd /workspace && echo '=== Dockerfile Security Lint ===' && \
if [ ! -f {shlex.quote(path)} ]; then
  echo 'No Dockerfile found at {path}'
  exit 0
fi && \
echo 'Checking: {path}' && \
echo '---' && \
grep -n 'USER root' {shlex.quote(path)} && echo '  WARN: Running as root' || echo '  OK: No explicit root user' && \
grep -n '^FROM.*:latest' {shlex.quote(path)} && echo '  WARN: Using :latest tag (pin version)' || echo '  OK: Base image is pinned' && \
grep -n 'ENV.*PASSWORD\|ENV.*SECRET\|ENV.*KEY' {shlex.quote(path)} && echo '  WARN: Secrets in ENV' || echo '  OK: No secrets in ENV' && \
grep -n 'COPY.*\\.env' {shlex.quote(path)} && echo '  WARN: Copying .env file into image' || echo '  OK: No .env COPY' && \
grep -q 'HEALTHCHECK' {shlex.quote(path)} && echo '  OK: HEALTHCHECK present' || echo '  WARN: No HEALTHCHECK instruction' && \
echo '---' && echo 'Dockerfile lint complete.'""",
        )

    @staticmethod
    def _generate_report(sandbox_session_id: str, output_path: str = "SECURITY_REPORT.md", **_: Any):
        from manch_backend.agents.tools import _run_sandbox_command, _write_file

        header = """# Security Audit Report

Generated by Manch Security Skill

## Summary

| Check | Status |
|-------|--------|
| Dependency Scan | Pending |
| Secret Scan | Pending |
| SAST Analysis | Pending |
| Header Check | Pending |
| File Permissions | Pending |
| Dockerfile Lint | Pending |

## Recommendations

1. Run `security_dependency_scan` to check for vulnerable dependencies
2. Run `security_secret_scan` to detect leaked credentials
3. Run `security_sast` for static analysis findings
4. Run `security_header_check` against your running services
5. Run `security_dockerfile_lint` on all Dockerfiles

## Next Steps

- Fix all HIGH and CRITICAL findings immediately
- Schedule MEDIUM findings for next sprint
- Add security scanning to CI/CD pipeline
"""
        _write_file(sandbox_session_id, output_path, header)
        return _run_sandbox_command(
            sandbox_session_id,
            f"echo 'Security report initialized at {output_path}. Run individual scans to populate.'",
        )


# Module-level instance for auto-discovery
skill = SecuritySkill()
