import json
import pytest
from pathlib import Path


def test_chatgpt_adapter_parse(tmp_path):
    export = [
        {"memory": "User is a Rust developer.", "created_at": "2024-11-01T10:00:00Z"},
        {"memory": "User drinks black coffee.", "created_at": "2024-11-02T09:00:00Z"},
        {"memory": "", "created_at": "2024-11-03T08:00:00Z"},  # should be skipped
    ]
    f = tmp_path / "memories.json"
    f.write_text(json.dumps(export))

    from adapters.chatgpt_adapter import parse
    memories, skipped = parse(str(f))

    assert len(memories) == 2
    assert skipped == 1
    assert all(m.source == "chatgpt" for m in memories)
    assert memories[0].content == "User is a Rust developer."


def test_chatgpt_adapter_classifies_professional(tmp_path):
    export = [{"memory": "User is a senior software engineer at a startup.", "created_at": "2024-01-01T00:00:00Z"}]
    f = tmp_path / "memories.json"
    f.write_text(json.dumps(export))

    from adapters.chatgpt_adapter import parse
    memories, _ = parse(str(f))
    assert memories[0].category == "professional"


def test_chatgpt_adapter_classifies_preference(tmp_path):
    export = [{"memory": "User prefers dark mode in all apps.", "created_at": "2024-01-01T00:00:00Z"}]
    f = tmp_path / "memories.json"
    f.write_text(json.dumps(export))

    from adapters.chatgpt_adapter import parse
    memories, _ = parse(str(f))
    assert memories[0].category == "preference"


def test_claude_adapter_parse_dict_format(tmp_path):
    export = [
        {"memory": "User is a data scientist.", "created_at": "2024-10-01T08:00:00Z"},
        {"memory": "User is building MemOS.", "created_at": "2024-10-02T08:00:00Z"},
    ]
    f = tmp_path / "memory.json"
    f.write_text(json.dumps(export))

    from adapters.claude_adapter import parse
    memories, skipped = parse(str(f))

    assert len(memories) == 2
    assert skipped == 0
    assert all(m.source == "claude" for m in memories)


def test_claude_adapter_parse_string_format(tmp_path):
    export = ["User loves jazz music.", "User has a dog."]
    f = tmp_path / "memory.json"
    f.write_text(json.dumps(export))

    from adapters.claude_adapter import parse
    memories, skipped = parse(str(f))

    assert len(memories) == 2
    assert skipped == 0


def test_claude_adapter_file_not_found():
    from adapters.claude_adapter import parse
    with pytest.raises(FileNotFoundError):
        parse("/nonexistent/path/memory.json")


def test_gemini_adapter_list_format(tmp_path):
    export = [
        {"memory": "User works as an AI researcher.", "created_at": "2024-10-01T08:00:00Z"},
        {"memory": "User prefers minimalist design.", "created_at": "2024-10-02T08:00:00Z"},
    ]
    f = tmp_path / "memories.json"
    f.write_text(json.dumps(export))

    from adapters.gemini_adapter import parse
    memories, skipped = parse(str(f))

    assert len(memories) == 2
    assert all(m.source == "gemini" for m in memories)


def test_gemini_adapter_wrapped_format(tmp_path):
    export = {"memories": [
        {"memory": "User enjoys hiking on weekends.", "created_at": "2024-10-01T08:00:00Z"},
    ]}
    f = tmp_path / "gemini_export.json"
    f.write_text(json.dumps(export))

    from adapters.gemini_adapter import parse
    memories, _ = parse(str(f))

    assert len(memories) == 1
    assert memories[0].source == "gemini"


def test_confidence_values(tmp_path):
    export = [{"memory": "User is a developer.", "created_at": "2024-01-01T00:00:00Z"}]
    f = tmp_path / "memories.json"
    f.write_text(json.dumps(export))

    from adapters.chatgpt_adapter import parse as chatgpt_parse
    from adapters.claude_adapter import parse as claude_parse

    chatgpt_memories, _ = chatgpt_parse(str(f))
    f2 = tmp_path / "memory.json"
    f2.write_text(json.dumps(export))
    claude_memories, _ = claude_parse(str(f2))

    # Claude exports are given higher confidence than ChatGPT
    assert claude_memories[0].confidence > chatgpt_memories[0].confidence
