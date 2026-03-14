from __future__ import annotations
import json
from pathlib import Path

from core.schema import Memory

RULES_PATH = Path.home() / ".memos" / "rules.json"


class ExclusionRules:
    """User-defined rules that filter memories out of MCP responses and pack injection."""

    def __init__(self, rules_path: Path = RULES_PATH):
        self.rules_path = rules_path
        self._rules: dict = self._load()

    def _load(self) -> dict:
        if self.rules_path.exists():
            try:
                return json.loads(self.rules_path.read_text())
            except (json.JSONDecodeError, OSError):
                return self._defaults()
        return self._defaults()

    @staticmethod
    def _defaults() -> dict:
        return {
            "exclude_sensitive": True,
            "exclude_tags": [],
            "exclude_categories": [],
            "exclude_keywords": [],
        }

    def save(self) -> None:
        self.rules_path.parent.mkdir(parents=True, exist_ok=True)
        self.rules_path.write_text(json.dumps(self._rules, indent=2))

    @property
    def exclude_sensitive(self) -> bool:
        return self._rules.get("exclude_sensitive", True)

    @property
    def exclude_tags(self) -> list[str]:
        return self._rules.get("exclude_tags", [])

    @property
    def exclude_categories(self) -> list[str]:
        return self._rules.get("exclude_categories", [])

    @property
    def exclude_keywords(self) -> list[str]:
        return self._rules.get("exclude_keywords", [])

    def set_rule(self, key: str, value) -> None:
        if key not in self._defaults():
            raise ValueError(f"Unknown rule: {key}. Valid: {list(self._defaults())}")
        self._rules[key] = value
        self.save()

    def to_dict(self) -> dict:
        return dict(self._rules)

    def should_exclude(self, memory: Memory) -> bool:
        if self.exclude_sensitive and memory.sensitive:
            return True
        if self.exclude_categories:
            cat = memory.category if isinstance(memory.category, str) else memory.category.value
            if cat in self.exclude_categories:
                return True
        if self.exclude_tags:
            if set(memory.tags) & set(self.exclude_tags):
                return True
        if self.exclude_keywords:
            content_lower = memory.content.lower()
            if any(kw.lower() in content_lower for kw in self.exclude_keywords):
                return True
        return False

    def apply(self, memories: list[Memory]) -> list[Memory]:
        return [m for m in memories if not self.should_exclude(m)]
