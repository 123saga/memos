import sys
import os
import pytest
from pathlib import Path

# Ensure project root is on path for all tests
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.store import MemoryStore
from core.schema import Memory, MemorySource, MemoryCategory


@pytest.fixture
def tmp_store(tmp_path):
    db = tmp_path / "test_memories.db"
    return MemoryStore(db_path=db)


@pytest.fixture
def seeded_store(tmp_store):
    memories = [
        Memory(content="User is a software engineer specialising in Python and data pipelines.",
               source=MemorySource.CHATGPT, category=MemoryCategory.PROFESSIONAL,
               tags=["python", "engineering"], confidence=0.9),
        Memory(content="User has a golden retriever named Biscuit.",
               source=MemorySource.CLAUDE, category=MemoryCategory.PERSONAL,
               tags=["pets"], confidence=0.95),
        Memory(content="User prefers dark mode in every application.",
               source=MemorySource.CHATGPT, category=MemoryCategory.PREFERENCE,
               tags=["preferences"], confidence=0.85),
        Memory(content="User is building an open-source AI memory platform called MemOS.",
               source=MemorySource.CLAUDE, category=MemoryCategory.PROJECT,
               tags=["project", "AI"], confidence=0.92),
        Memory(content="User works closely with their mentor on AI research papers.",
               source=MemorySource.MANUAL, category=MemoryCategory.RELATIONSHIP,
               tags=["research"], confidence=0.8),
        Memory(content="User has been dealing with anxiety and seeing a therapist.",
               source=MemorySource.CLAUDE, category=MemoryCategory.PERSONAL,
               tags=["health", "therapy"], sensitive=True, confidence=0.95),
    ]
    tmp_store.add_many(memories, skip_duplicates=False)
    return tmp_store
