import json
from core.schema import Memory, MemorySource, MemoryCategory
from core.rules import ExclusionRules


def test_add_and_count(tmp_store):
    assert tmp_store.count() == 0
    m = Memory(content="Test memory", source=MemorySource.MANUAL, category=MemoryCategory.PERSONAL)
    tmp_store.add(m)
    assert tmp_store.count() == 1


def test_duplicate_skipped(tmp_store):
    m = Memory(content="Duplicate content", source=MemorySource.MANUAL, category=MemoryCategory.PERSONAL)
    added1 = tmp_store.add(m)
    added2 = tmp_store.add(m)
    assert added1 is True
    assert added2 is False
    assert tmp_store.count() == 1


def test_add_many(tmp_store):
    memories = [
        Memory(content=f"Memory {i}", source=MemorySource.MANUAL, category=MemoryCategory.PERSONAL)
        for i in range(5)
    ]
    added = tmp_store.add_many(memories)
    assert added == 5
    assert tmp_store.count() == 5


def test_get_by_id(seeded_store):
    all_m = seeded_store.get_all()
    target = all_m[0]
    fetched = seeded_store.get_by_id(target.id)
    assert fetched is not None
    assert fetched.id == target.id
    assert fetched.content == target.content


def test_get_by_category(seeded_store):
    results = seeded_store.get_by_category("professional")
    assert len(results) >= 1
    assert all(m.category == "professional" for m in results)


def test_get_by_source(seeded_store):
    results = seeded_store.get_by_source("claude")
    assert len(results) >= 1
    assert all(m.source == "claude" for m in results)


def test_search_fts(seeded_store):
    results = seeded_store.search("python", limit=5)
    assert len(results) >= 1
    assert any("python" in m.content.lower() or "python" in m.tags for m in results)


def test_search_no_results(seeded_store):
    results = seeded_store.search("xyznonexistent123", limit=5)
    assert results == []


def test_update(seeded_store):
    m = seeded_store.get_all()[0]
    success = seeded_store.update(m.id, content="Updated content")
    assert success is True
    updated = seeded_store.get_by_id(m.id)
    assert updated.content == "Updated content"


def test_update_nonexistent(tmp_store):
    success = tmp_store.update("nonexistent-id", content="whatever")
    assert success is False


def test_delete(seeded_store):
    m = seeded_store.get_all()[0]
    before = seeded_store.count()
    deleted = seeded_store.delete(m.id)
    assert deleted is True
    assert seeded_store.count() == before - 1


def test_delete_nonexistent(tmp_store):
    assert tmp_store.delete("nonexistent-id") is False


def test_clear_source(seeded_store):
    before = seeded_store.count_by_source().get("chatgpt", 0)
    deleted = seeded_store.clear_source("chatgpt")
    assert deleted == before
    assert seeded_store.count_by_source().get("chatgpt", 0) == 0


def test_clear_all(seeded_store):
    assert seeded_store.count() > 0
    seeded_store.clear_all()
    assert seeded_store.count() == 0


def test_count_by_category(seeded_store):
    counts = seeded_store.count_by_category()
    assert isinstance(counts, dict)
    assert sum(counts.values()) == seeded_store.count()


def test_export_json(seeded_store, tmp_path):
    output = tmp_path / "export.json"
    count = seeded_store.export_json(output)
    assert count == seeded_store.count()
    assert output.exists()
    data = json.loads(output.read_text())
    assert len(data) == count
    assert "content" in data[0]
    assert "source" in data[0]
    assert "sensitive" in data[0]


def test_get_stale_empty(tmp_store):
    stale = tmp_store.get_stale(threshold_days=180)
    assert stale == []


def test_find_near_duplicates(tmp_store):
    m1 = Memory(content="User enjoys drinking black coffee every morning",
                source=MemorySource.MANUAL, category=MemoryCategory.PREFERENCE)
    m2 = Memory(content="User enjoys drinking black coffee every morning at work",
                source=MemorySource.MANUAL, category=MemoryCategory.PREFERENCE)
    m3 = Memory(content="User has a golden retriever named Biscuit",
                source=MemorySource.MANUAL, category=MemoryCategory.PERSONAL)
    tmp_store.add_many([m1, m2, m3], skip_duplicates=False)
    pairs = tmp_store.find_near_duplicates(threshold=0.7)
    assert len(pairs) >= 1


# ── Sensitive flag tests ─────────────────────────────────────────────────────

def test_sensitive_flag_stored(tmp_store):
    m = Memory(content="Health info", source=MemorySource.MANUAL,
               category=MemoryCategory.PERSONAL, sensitive=True)
    tmp_store.add(m)
    fetched = tmp_store.get_by_id(m.id)
    assert fetched.sensitive is True


def test_set_sensitive(seeded_store):
    non_sensitive = [m for m in seeded_store.get_all() if not m.sensitive]
    assert len(non_sensitive) > 0
    m = non_sensitive[0]
    assert m.sensitive is False

    seeded_store.set_sensitive(m.id, True)
    updated = seeded_store.get_by_id(m.id)
    assert updated.sensitive is True

    seeded_store.set_sensitive(m.id, False)
    reverted = seeded_store.get_by_id(m.id)
    assert reverted.sensitive is False


def test_set_sensitive_nonexistent(tmp_store):
    assert tmp_store.set_sensitive("does-not-exist", True) is False


def test_get_sensitive(seeded_store):
    sensitive = seeded_store.get_sensitive()
    assert len(sensitive) >= 1
    assert all(m.sensitive for m in sensitive)


# ── Exclusion rules tests ───────────────────────────────────────────────────

def test_exclusion_rules_defaults(tmp_path):
    rules = ExclusionRules(rules_path=tmp_path / "rules.json")
    assert rules.exclude_sensitive is True
    assert rules.exclude_tags == []
    assert rules.exclude_categories == []
    assert rules.exclude_keywords == []


def test_exclusion_rules_set_and_persist(tmp_path):
    rules_path = tmp_path / "rules.json"
    rules = ExclusionRules(rules_path=rules_path)
    rules.set_rule("exclude_tags", ["health", "therapy"])
    rules.set_rule("exclude_sensitive", False)

    reloaded = ExclusionRules(rules_path=rules_path)
    assert reloaded.exclude_tags == ["health", "therapy"]
    assert reloaded.exclude_sensitive is False


def test_exclusion_rules_filter_sensitive(tmp_path):
    rules = ExclusionRules(rules_path=tmp_path / "rules.json")
    memories = [
        Memory(content="Normal memory", source=MemorySource.MANUAL,
               category=MemoryCategory.PERSONAL, sensitive=False),
        Memory(content="Therapy session notes", source=MemorySource.MANUAL,
               category=MemoryCategory.PERSONAL, sensitive=True),
    ]
    filtered = rules.apply(memories)
    assert len(filtered) == 1
    assert filtered[0].content == "Normal memory"


def test_exclusion_rules_filter_tags(tmp_path):
    rules = ExclusionRules(rules_path=tmp_path / "rules.json")
    rules.set_rule("exclude_tags", ["health"])
    memories = [
        Memory(content="I code in Python", source=MemorySource.MANUAL,
               category=MemoryCategory.PROFESSIONAL, tags=["python"]),
        Memory(content="Doctor visit", source=MemorySource.MANUAL,
               category=MemoryCategory.PERSONAL, tags=["health"]),
    ]
    filtered = rules.apply(memories)
    assert len(filtered) == 1
    assert filtered[0].tags == ["python"]


def test_exclusion_rules_filter_categories(tmp_path):
    rules = ExclusionRules(rules_path=tmp_path / "rules.json")
    rules.set_rule("exclude_categories", ["personal"])
    memories = [
        Memory(content="I code in Python", source=MemorySource.MANUAL,
               category=MemoryCategory.PROFESSIONAL),
        Memory(content="My dog is named Biscuit", source=MemorySource.MANUAL,
               category=MemoryCategory.PERSONAL),
    ]
    filtered = rules.apply(memories)
    assert len(filtered) == 1
    assert filtered[0].category == "professional"


def test_exclusion_rules_filter_keywords(tmp_path):
    rules = ExclusionRules(rules_path=tmp_path / "rules.json")
    rules.set_rule("exclude_keywords", ["therapy", "anxiety"])
    memories = [
        Memory(content="I enjoy hiking on weekends", source=MemorySource.MANUAL,
               category=MemoryCategory.PERSONAL),
        Memory(content="I have been dealing with anxiety recently", source=MemorySource.MANUAL,
               category=MemoryCategory.PERSONAL),
    ]
    filtered = rules.apply(memories)
    assert len(filtered) == 1
    assert "hiking" in filtered[0].content


def test_exclusion_rules_invalid_key(tmp_path):
    import pytest
    rules = ExclusionRules(rules_path=tmp_path / "rules.json")
    with pytest.raises(ValueError):
        rules.set_rule("invalid_key", "value")


def test_exclusion_rules_combined(tmp_path):
    rules = ExclusionRules(rules_path=tmp_path / "rules.json")
    rules.set_rule("exclude_tags", ["health"])
    rules.set_rule("exclude_keywords", ["salary"])
    memories = [
        Memory(content="I code in Python", source=MemorySource.MANUAL,
               category=MemoryCategory.PROFESSIONAL, tags=["python"]),
        Memory(content="Doctor visit last week", source=MemorySource.MANUAL,
               category=MemoryCategory.PERSONAL, tags=["health"]),
        Memory(content="My salary is 150k", source=MemorySource.MANUAL,
               category=MemoryCategory.PROFESSIONAL, tags=["work"]),
        Memory(content="Therapy notes from session", source=MemorySource.MANUAL,
               category=MemoryCategory.PERSONAL, sensitive=True),
    ]
    filtered = rules.apply(memories)
    assert len(filtered) == 1
    assert filtered[0].content == "I code in Python"
