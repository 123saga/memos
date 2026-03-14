import sys
import os
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.store import MemoryStore
from core.rules import ExclusionRules
from core.schema import Memory, MemorySource, MemoryCategory


def test_mcp_store_search():
    with tempfile.TemporaryDirectory() as tmp:
        store = MemoryStore(db_path=Path(tmp) / "test.db")

        memories = [
            Memory(content="User is a data scientist working on LLM evaluation.",
                   source=MemorySource.CLAUDE, category=MemoryCategory.PROFESSIONAL),
            Memory(content="User has published research on arXiv.",
                   source=MemorySource.CLAUDE, category=MemoryCategory.PROFESSIONAL),
            Memory(content="User prefers dark mode in every app.",
                   source=MemorySource.CHATGPT, category=MemoryCategory.PREFERENCE),
        ]
        store.add_many(memories)
        assert store.count() == 3

        results = store.search("research", limit=3)
        assert len(results) >= 1
        assert any("research" in m.content.lower() for m in results)


def test_mcp_exclusion_rules_applied_to_search():
    with tempfile.TemporaryDirectory() as tmp:
        store = MemoryStore(db_path=Path(tmp) / "test.db")
        rules = ExclusionRules(rules_path=Path(tmp) / "rules.json")

        store.add_many([
            Memory(content="User researches AI safety.",
                   source=MemorySource.CLAUDE, category=MemoryCategory.PROFESSIONAL),
            Memory(content="User discussed anxiety with therapist.",
                   source=MemorySource.CLAUDE, category=MemoryCategory.PERSONAL,
                   sensitive=True),
        ])

        results = store.search("user", limit=10)
        assert len(results) == 2

        filtered = rules.apply(results)
        assert len(filtered) == 1
        assert "AI safety" in filtered[0].content


def test_mcp_sensitive_memory_excluded_from_results():
    with tempfile.TemporaryDirectory() as tmp:
        store = MemoryStore(db_path=Path(tmp) / "test.db")
        rules = ExclusionRules(rules_path=Path(tmp) / "rules.json")

        m1 = Memory(content="User is a Python developer.",
                    source=MemorySource.MANUAL, category=MemoryCategory.PROFESSIONAL)
        m2 = Memory(content="User takes medication for chronic condition.",
                    source=MemorySource.MANUAL, category=MemoryCategory.PERSONAL,
                    sensitive=True)
        store.add_many([m1, m2])

        all_m = store.get_all()
        assert len(all_m) == 2

        visible = rules.apply(all_m)
        assert len(visible) == 1
        assert visible[0].content == "User is a Python developer."


def test_mark_sensitive_via_store():
    with tempfile.TemporaryDirectory() as tmp:
        store = MemoryStore(db_path=Path(tmp) / "test.db")

        m = Memory(content="Normal memory", source=MemorySource.MANUAL,
                   category=MemoryCategory.PERSONAL)
        store.add(m)
        assert store.get_by_id(m.id).sensitive is False

        store.set_sensitive(m.id, True)
        assert store.get_by_id(m.id).sensitive is True
        assert len(store.get_sensitive()) == 1

        store.set_sensitive(m.id, False)
        assert store.get_by_id(m.id).sensitive is False
        assert len(store.get_sensitive()) == 0
