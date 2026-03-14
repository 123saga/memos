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
        "AI", "ML", "research", "paper", "visa",
    ]),
    (MemoryCategory.PROJECT, [
        "building", "side project", "working on", "developing", "creating",
        "launching", "project", "app", "tool", "platform", "product",
    ]),
    (MemoryCategory.PREFERENCE, [
        "prefer", "favourite", "favorite", "love", "hate", "dislike", "like",
        "enjoy", "dark mode", "coffee", "tea", "music", "food",
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
    "python": "python", "AI": "AI", "research": "research",
    "coffee": "coffee", "music": "music", "dog": "pets",
    "book": "reading", "project": "project", "startup": "startup",
    "learning": "learning", "travel": "travel", "google": "google",
}


def _classify(content: str) -> MemoryCategory:
    cl = content.lower()
    scores = {cat: sum(1 for kw in kws if kw in cl) for cat, kws in _CATEGORY_RULES}
    best = max(scores, key=lambda c: scores[c])
    return best if scores[best] > 0 else MemoryCategory.PERSONAL


def _extract_tags(content: str) -> list[str]:
    cl = content.lower()
    return list({tag for kw, tag in _TAG_MAP.items() if kw.lower() in cl})[:5]


class GeminiAdapter(BaseAdapter):
    """
    Parses Gemini memory exports.

    Accepted formats:
      1. Simple list: [{"memory": "...", "created_at": "ISO8601"}, ...]
      2. Google Takeout Gemini activity JSON with a "memories" key
      3. Plain string list: ["memory text", ...]

    How to export from Gemini:
      Google Takeout (takeout.google.com) > Select "Gemini Apps Activity" > Export.
      Extract the zip and locate the memory/activity JSON file.
    """

    def parse(self, filepath: str) -> tuple[list[Memory], int]:
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)

        # Support both top-level list and {"memories": [...]} wrapper
        if isinstance(raw, dict):
            items = raw.get("memories") or raw.get("items") or []
        else:
            items = raw

        memories, skipped = [], 0
        for item in items:
            if isinstance(item, str):
                content, created_at = item.strip(), datetime.now(timezone.utc)
            elif isinstance(item, dict):
                content = (
                    item.get("memory") or item.get("content")
                    or item.get("text") or item.get("title") or ""
                ).strip()
                date_str = item.get("created_at") or item.get("timestamp")
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
                source=MemorySource.GEMINI,
                category=_classify(content),
                tags=_extract_tags(content),
                confidence=0.85,
                created_at=created_at,
                updated_at=created_at,
                source_raw=content,
            ))
        return memories, skipped


_adapter = GeminiAdapter()
parse = _adapter.parse
print_summary = _adapter.print_summary
