# Adding a New Platform Adapter

This guide walks you through adding support for a new AI platform to MemOS.

---

## Overview

An adapter is a single Python file that:
1. Reads a platform export file
2. Parses it into `Memory` objects
3. Returns `(memories, skipped)` for the CLI to handle

---

## Step 1: Create the adapter file

Create `adapters/your_platform_adapter.py`:

```python
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path

from adapters.base import BaseAdapter
from core.schema import Memory, MemorySource, MemoryCategory

# Add your platform to MemorySource in core/schema.py first:
#   YOUR_PLATFORM = "your_platform"

_CATEGORY_RULES = [
    (MemoryCategory.PROFESSIONAL, ["engineer", "developer", "work", "job", "career"]),
    (MemoryCategory.PROJECT,      ["building", "project", "working on", "creating"]),
    (MemoryCategory.PREFERENCE,   ["prefer", "favorite", "love", "hate", "like"]),
    (MemoryCategory.PERSONAL,     ["live", "family", "hobby", "book", "learning"]),
    (MemoryCategory.RELATIONSHIP, ["friend", "colleague", "mentor", "partner"]),
]

_TAG_MAP = {
    "python": "python", "AI": "AI", "research": "research",
    "coffee": "coffee", "project": "project",
    # Add more keyword -> tag mappings here
}


def _classify(content: str) -> MemoryCategory:
    cl = content.lower()
    scores = {cat: sum(1 for kw in kws if kw in cl) for cat, kws in _CATEGORY_RULES}
    best = max(scores, key=lambda c: scores[c])
    return best if scores[best] > 0 else MemoryCategory.PERSONAL


def _extract_tags(content: str) -> list[str]:
    cl = content.lower()
    return list({tag for kw, tag in _TAG_MAP.items() if kw.lower() in cl})[:5]


class YourPlatformAdapter(BaseAdapter):
    """
    Parses YourPlatform memory exports.

    How to export:
      1. Go to YourPlatform > Settings > Data > Export
      2. Download the ZIP
      3. Find the memory JSON file inside
    """

    def parse(self, filepath: str) -> tuple[list[Memory], int]:
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)

        memories, skipped = [], 0

        for item in raw:
            # Adapt this to your platform's export format
            if isinstance(item, str):
                content = item.strip()
                created_at = datetime.now(timezone.utc)
            elif isinstance(item, dict):
                content = (item.get("memory") or item.get("content") or "").strip()
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
                source=MemorySource.MANUAL,   # Change to your MemorySource enum value
                category=_classify(content),
                tags=_extract_tags(content),
                confidence=0.85,              # Adjust based on export quality
                created_at=created_at,
                updated_at=created_at,
                source_raw=content,
            ))

        return memories, skipped


# Module-level helpers for memos.py
_adapter = YourPlatformAdapter()
parse = _adapter.parse
print_summary = _adapter.print_summary
```

---

## Step 2: Add to MemorySource

In `core/schema.py`, add your platform to the enum:

```python
class MemorySource(str, Enum):
    CLAUDE        = "claude"
    CHATGPT       = "chatgpt"
    GEMINI        = "gemini"
    OBSIDIAN      = "obsidian"
    YOUR_PLATFORM = "your_platform"   # Add this
    MANUAL        = "manual"
```

---

## Step 3: Register in the CLI

In `memos.py`, add to `cmd_import`:

```python
elif source == "your_platform":
    from adapters.your_platform_adapter import parse, print_summary
```

And add to the `--source` choices:

```python
p.add_argument("--source", "-s", required=True,
               choices=["chatgpt", "claude", "gemini", "your_platform"])
```

---

## Step 4: Add an example export

Add a sample export file to `examples/fake_your_platform_export/` so contributors
can test without real user data.

---

## Step 5: Add tests

Add a test file `tests/test_your_platform_adapter.py` following the pattern
in `tests/test_adapters.py`. At minimum, test:

- That `parse()` returns the right number of memories
- That it handles empty/malformed items gracefully (`skipped` count)
- That `source` is set to the right enum value
- That classification works for at least one professional and one personal memory

---

## Checklist

- [ ] `adapters/your_platform_adapter.py` created
- [ ] `MemorySource.YOUR_PLATFORM` added to `core/schema.py`
- [ ] `cmd_import` updated in `memos.py`
- [ ] Example export added to `examples/`
- [ ] Tests added to `tests/`
- [ ] Export instructions documented in the adapter docstring

Once done, open a PR! We'll review and merge quickly.
