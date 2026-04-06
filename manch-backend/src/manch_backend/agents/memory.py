"""MemoryAgent — preserves reusable knowledge across sessions without polluting short-term execution."""
from __future__ import annotations

import json
import logging
from datetime import datetime, UTC
from uuid import uuid4

from manch_backend.agents.base import AgentContext, AgentResult, BaseAgent
from manch_backend.agents.llm import LLMMessage
from manch_backend.agents.registry import register_agent
from manch_backend.models import AgentTier, ModelClass, RiskLevel

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are Memory, the long-horizon context agent for Manch.
Your job is to capture stable patterns that improve future executions.

When given a completed task and its context, you should:
1. Extract reusable knowledge (conventions, patterns, decisions)
2. Assign retention value and retrieval tags
3. Score confidence

Respond in JSON:
{
  "entries": [
    {
      "key": "short-kebab-case-identifier",
      "category": "convention" | "pattern" | "decision" | "constraint" | "playbook",
      "content": "The actual knowledge to store",
      "tags": ["tag1", "tag2"],
      "confidence": 0.0 to 1.0,
      "retention_value": "HIGH" | "MEDIUM" | "LOW",
      "source_task_id": "optional reference"
    }
  ],
  "summary": "What was captured and why"
}

What to store:
- coding conventions, event naming rules
- agent routing patterns, retry strategies
- known integration constraints
- proven architecture decisions

What NOT to store:
- raw logs, one-off noise
- unverified hypotheses
- transient partial thoughts

Guidelines:
- Quality over quantity
- Compress aggressively
- Keep retrieval simple
"""


@register_agent
class MemoryAgent(BaseAgent):
    name = "memory"
    tier = AgentTier.SUPPORT
    model_class = ModelClass.FAST
    parallel_safe = True
    purpose = "Preserves reusable knowledge without polluting short-term execution."

    def run(self, ctx: AgentContext) -> AgentResult:
        self._logger.info("Extracting knowledge for task=%s", ctx.task_id)

        system_prompt = self.build_system_prompt() or _SYSTEM_PROMPT
        from manch_backend.agents.llm import llm_client as llm

        # Combine all available context for knowledge extraction
        knowledge_input = f"Task: {ctx.prompt}\n\n"
        scout_report = ctx.extra.get("scout_report", "")
        if scout_report:
            knowledge_input += f"## Scout Report\n{scout_report[:3000]}\n\n"
        files_changed = ctx.extra.get("files_changed", [])
        if files_changed:
            knowledge_input += f"## Files Changed\n{json.dumps(files_changed)}\n\n"
        if ctx.repo_context:
            knowledge_input += f"## Repository Context\n{json.dumps(ctx.repo_context, indent=2)[:2000]}\n\n"

        # Include conversation history for decision context
        if ctx.history:
            recent = ctx.history[-6:]
            history_str = "\n".join(f"[{h.get('role', '?')}]: {h.get('content', '')[:300]}" for h in recent)
            knowledge_input += f"## Recent History\n{history_str}\n\n"

        knowledge_input += "Extract reusable knowledge from this completed task."

        messages = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="user", content=knowledge_input),
        ]

        try:
            resp = llm.chat(messages, model_class=self.model_class, response_format="json")
            memory_data = json.loads(resp.content)
            entries = memory_data.get("entries", [])

            # Persist to database
            persisted = self._persist_entries(entries, ctx.task_id)

            return AgentResult(
                success=True,
                output=resp.content,
                risk_level=RiskLevel.LOW,
                metadata={
                    "entries_extracted": len(entries),
                    "entries_persisted": persisted,
                    "usage": resp.usage,
                },
                artifacts=[{"type": "memory_extraction", "content": resp.content}],
            )
        except Exception as exc:
            self._logger.exception("Memory extraction failed")
            return AgentResult(success=False, output="", error=str(exc))

    @staticmethod
    def _persist_entries(entries: list[dict], task_id: str) -> int:
        """Persist memory entries to the database. Returns count of entries persisted."""
        try:
            from manch_backend.db.models import MemoryEntryRecord
            from manch_backend.db.session import SessionLocal

            count = 0
            with SessionLocal() as db:
                for entry in entries:
                    record = MemoryEntryRecord(
                        id=str(uuid4()),
                        key=entry.get("key", str(uuid4())[:8]),
                        category=entry.get("category", "pattern"),
                        content=entry.get("content", ""),
                        tags_json=json.dumps(entry.get("tags", [])),
                        confidence=entry.get("confidence", 0.5),
                        retention_value=entry.get("retention_value", "MEDIUM"),
                        source_task_id=task_id,
                    )
                    db.add(record)
                    count += 1
                db.commit()
            return count
        except Exception:
            logger.exception("Failed to persist memory entries")
            return 0

    @staticmethod
    def retrieve(tags: list[str] | None = None, category: str | None = None, limit: int = 20) -> list[dict]:
        """Retrieve memory entries by tags or category. Used by other agents."""
        try:
            from manch_backend.db.models import MemoryEntryRecord
            from manch_backend.db.session import SessionLocal
            from sqlalchemy import select

            with SessionLocal() as db:
                stmt = select(MemoryEntryRecord).order_by(MemoryEntryRecord.created_at.desc())
                if category:
                    stmt = stmt.where(MemoryEntryRecord.category == category)
                stmt = stmt.limit(limit)
                records = db.execute(stmt).scalars().all()

                results = []
                for r in records:
                    entry_tags = json.loads(r.tags_json) if r.tags_json else []
                    if tags and not set(tags).intersection(set(entry_tags)):
                        continue
                    results.append({
                        "id": r.id,
                        "key": r.key,
                        "category": r.category,
                        "content": r.content,
                        "tags": entry_tags,
                        "confidence": r.confidence,
                        "retention_value": r.retention_value,
                        "created_at": r.created_at.isoformat() if r.created_at else None,
                    })
                return results
        except Exception:
            logger.exception("Failed to retrieve memory entries")
            return []
