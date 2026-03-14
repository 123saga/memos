from __future__ import annotations
from abc import ABC, abstractmethod
from core.schema import Memory


class BaseAdapter(ABC):
    """Base class for platform adapters. See docs/adding-an-adapter.md."""

    @abstractmethod
    def parse(self, filepath: str) -> tuple[list[Memory], int]:
        """Parse an export file. Returns (memories, skipped_count)."""
        ...

    def print_summary(self, memories: list[Memory], skipped: int) -> None:
        from collections import Counter
        print(f"\n{'─'*60}")
        print(f"  Parsed {len(memories)} memories  |  Skipped {skipped}")
        print(f"{'─'*60}\n")
        cats = Counter(m.category for m in memories)
        print("Categories:")
        for cat, count in cats.most_common():
            print(f"  {cat:20} {count}")
        print("\nMemories:\n")
        for i, m in enumerate(memories, 1):
            print(f"  {i:2}. [{m.category.upper():12}] {m.content[:72]}")
            if m.tags:
                print(f"       tags: {', '.join(m.tags)}")
            print()
