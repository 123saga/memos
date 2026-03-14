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
        "AI", "research", "paper", "visa", "machine learning", "backend", "frontend",
    ]),
    (MemoryCategory.PROJECT, [
        "building", "side project", "working on", "developing", "creating",
        "launching", "project", "app", "tool", "platform",
    ]),
    (MemoryCategory.PREFERENCE, [
        "prefer", "favourite", "favorite", "love", "hate", "dislike", "like",
        "enjoy", "dark mode", "coffee", "tea", "music", "food", "annoyed", "find it hard",
    ]),
    (MemoryCategory.PERSONAL, [
        "live", "lives", "dog", "cat", "pet", "family", "learning", "hobby",
        "book", "read", "morning", "evening", "named", "called",
    ]),
    (MemoryCategory.RELATIONSHIP, [
        "friend", "partner", "spouse", "colleague", "teammate", "mentor", "manager",
    ]),
]

_TAG_MAP = {
    "engineer": "engineering", "python": "python", "rust": "rust",
    "javascript": "javascript", "typescript": "typescript",
    "coffee": "coffee", "music": "music", "jazz": "jazz",
    "dog": "pets", "cat": "pets", "book": "reading",
    "japanese": "languages", "spanish": "languages", "french": "languages",
    "dark mode": "preferences", "remote": "remote-work",
    "startup": "startup", "AI": "AI", "research": "research",
    "project": "project", "learning": "learning", "travel": "travel",
}


def _classify(content: str) -> MemoryCategory:
    cl = content.lower()
    scores = {cat: sum(1 for kw in kws if kw in cl) for cat, kws in _CATEGORY_RULES}
    best = max(scores, key=lambda c: scores[c])
    return best if scores[best] > 0 else MemoryCategory.PERSONAL


def _extract_tags(content: str) -> list[str]:
    cl = content.lower()
    return list({tag for kw, tag in _TAG_MAP.items() if kw.lower() in cl})[:5]


class ChatGPTAdapter(BaseAdapter):
    """Parses ChatGPT memory exports (Settings > Data Controls > Export data > memories.json)."""

    def parse(self, filepath: str) -> tuple[list[Memory], int]:
        with open(filepath, "r", encoding="utf-8") as f:
            raw = json.load(f)

        memories, skipped = [], 0
        for item in raw:
            content = item.get("memory", "").strip()
            if not content:
                skipped += 1
                continue
            date_str = item.get("created_at")
            try:
                created_at = datetime.fromisoformat(
                    date_str.replace("Z", "+00:00")
                ) if date_str else datetime.now(timezone.utc)
            except (ValueError, AttributeError):
                created_at = datetime.now(timezone.utc)

            memories.append(Memory(
                content=content,
                source=MemorySource.CHATGPT,
                category=_classify(content),
                tags=_extract_tags(content),
                confidence=0.85,
                created_at=created_at,
                updated_at=created_at,
                source_raw=content,
            ))
        return memories, skipped


_adapter = ChatGPTAdapter()
parse = _adapter.parse
print_summary = _adapter.print_summary
