from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path

from adapters.base import BaseAdapter
from core.schema import Memory, MemorySource, MemoryCategory

_CATEGORY_RULES = [
    (MemoryCategory.PROFESSIONAL, [
        "engineer", "developer", "scientist", "researcher", "work", "job",
        "career", "startup", "code", "programming", "software", "data",
        "AI", "ML", "research", "paper", "published", "arXiv", "visa", "EB-1",
        "pipeline", "model", "embedding", "evaluation", "benchmark", "ETL", "agent",
    ]),
    (MemoryCategory.PROJECT, [
        "building", "side project", "working on", "developing", "creating",
        "launching", "project", "app", "tool", "platform", "product",
    ]),
    (MemoryCategory.PREFERENCE, [
        "prefer", "favourite", "favorite", "love", "hate", "dislike", "like",
        "enjoy", "dark mode", "coffee", "tea", "music", "food", "annoyed",
        "find it hard", "concise", "direct", "brief",
    ]),
    (MemoryCategory.PERSONAL, [
        "live", "lives", "dog", "cat", "pet", "family", "learning", "hobby",
        "book", "read", "morning", "evening", "named", "called", "located", "from",
    ]),
    (MemoryCategory.RELATIONSHIP, [
        "friend", "partner", "spouse", "colleague", "teammate", "mentor", "manager",
    ]),
]

_TAG_MAP = {
    "research": "research", "arXiv": "arxiv", "LLM": "LLM",
    "evaluation": "evaluation", "benchmark": "benchmark",
    "python": "python", "data scientist": "data-science",
    "engineer": "engineering", "coffee": "coffee", "music": "music",
    "dog": "pets", "book": "reading", "project": "project",
    "startup": "startup", "AI": "AI", "visa": "visa",
    "EB-1": "immigration", "embedding": "embeddings", "remote": "remote-work",
}


def _classify(content: str) -> MemoryCategory:
    cl = content.lower()
    scores = {cat: sum(1 for kw in kws if kw in cl) for cat, kws in _CATEGORY_RULES}
    best = max(scores, key=lambda c: scores[c])
    return best if scores[best] > 0 else MemoryCategory.PERSONAL


def _extract_tags(content: str) -> list[str]:
    cl = content.lower()
    return list({tag for kw, tag in _TAG_MAP.items() if kw.lower() in cl})[:5]


class ClaudeAdapter(BaseAdapter):
    """
    Parses Claude memory exports (Settings > Privacy > Export data > memory.json).
    Accepts both plain string lists and {memory, created_at} dicts.
    """

    def parse(self, filepath: str) -> tuple[list[Memory], int]:
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)

        memories, skipped = [], 0
        for item in raw:
            if isinstance(item, str):
                content, created_at = item.strip(), datetime.now(timezone.utc)
            elif isinstance(item, dict):
                content = (item.get("memory") or item.get("content") or "").strip()
                date_str = item.get("created_at")
                try:
                    created_at = datetime.fromisoformat(
                        date_str.replace("Z", "+00:00")
                    ) if date_str else datetime.now(timezone.utc)
                except (ValueError, AttributeError):
                    created_at = datetime.now(timezone.utc)
            else:
                skipped += 1
                continue

            if not content:
                skipped += 1
                continue

            memories.append(Memory(
                content=content,
                source=MemorySource.CLAUDE,
                category=_classify(content),
                tags=_extract_tags(content),
                confidence=0.92,
                created_at=created_at,
                updated_at=created_at,
                source_raw=content,
            ))
        return memories, skipped


_adapter = ClaudeAdapter()
parse = _adapter.parse
print_summary = _adapter.print_summary
