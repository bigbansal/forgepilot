from pathlib import Path
from fastapi import APIRouter
from manch_backend.models import AgentDefinition

router = APIRouter()


def _project_root() -> Path:
    return Path(__file__).resolve().parents[5]


@router.get("")
def list_agents():
    """List agents from .github/agents/*.md definitions."""
    base = _project_root() / ".github" / "agents"
    results: list[AgentDefinition] = []
    if not base.exists():
        return results

    for file in sorted(base.glob("*.md")):
        if file.name.lower() == "readme.md" or file.name.lower() == "platform-builder.md":
            continue
        name = file.stem
        tier = "specialist"
        purpose = "agent definition"
        content = file.read_text(encoding="utf-8")
        for line in content.splitlines():
            if line.startswith("tier:"):
                tier = line.split(":", 1)[1].strip()
            if line.startswith("purpose:"):
                purpose = line.split(":", 1)[1].strip()
        results.append(AgentDefinition(name=name, tier=tier, purpose=purpose, file_path=str(file)))

    return results


@router.get("/registry")
def list_registered_agents():
    """List agents from the live Python agent registry."""
    from manch_backend.agents.registry import list_agents as _list_agents
    agents = _list_agents()
    return [
        {
            "name": a.name,
            "tier": a.tier.value,
            "model_class": a.model_class.value,
            "parallel_safe": a.parallel_safe,
            "purpose": a.purpose,
        }
        for a in agents
    ]
