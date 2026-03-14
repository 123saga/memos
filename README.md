# MemOS — Memory Operating System for AI

> The local-first, open-source memory layer that works across **all** your AI tools.

[![CI](https://github.com/Sagar/MemOS/actions/workflows/ci.yml/badge.svg)](https://github.com/Sagar/MemOS/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)

---

## The Problem

Your AI memory is siloed. Claude knows your research style. ChatGPT knows your work projects. Gemini knows your preferences. Every time you switch tools, you start over — as a stranger.

Worse: even if an AI platform lets you import memories from another, those memories still live on their cloud, locked to their tool. No privacy. No portability. No control.

**MemOS fixes this.**

```
ChatGPT memories ─┐
Claude memories  ─┼──▶ ~/.memos/memories.db ──▶ Any MCP client
Gemini memories  ─┘         (local SQLite)      Claude Desktop · Cursor · Windsurf · ...
```

One store. Every tool. Yours to own.

---

## Why Not Just Use Claude's Memory?

Claude's native memory is great — if you only use Claude. MemOS is for people who use **multiple AI tools** and want consistent context everywhere. It also:

- Runs 100% locally — no cloud, no subscription, no privacy tradeoff
- Works with Cursor, Windsurf, and any MCP-compatible client, not just Claude
- Gives you a CLI to search, audit, export, and manage your memories programmatically
- Detects stale memories, near-duplicates, and sensitive data — things cloud tools are disincentivized to do

---

## Quickstart

### 1. Install

```bash
git clone https://github.com/Sagar/MemOS
cd MemOS
bash setup.sh
```

### 2. Import your memories

```bash
# From ChatGPT (Settings > Data Controls > Export data > memories.json)
./memos.sh import --source chatgpt --input ~/Downloads/memories.json

# From Claude (Settings > Privacy > Export data > memory.json)
./memos.sh import --source claude --input ~/Downloads/memory.json

# From Gemini (Google Takeout > Gemini Apps Activity)
./memos.sh import --source gemini --input ~/Downloads/gemini_memories.json

# Preview before importing
./memos.sh import --source chatgpt --input ~/Downloads/memories.json --preview
```

### 3. Connect to Claude Desktop

Edit `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "memos": {
      "command": "/path/to/MemOS/memos.sh",
      "args": ["serve"]
    }
  }
}
```

Restart Claude Desktop. Ask: *"What do you know about me?"*

Works the same way for **Cursor** and **Windsurf** — just point their MCP config to the same file.

---

## CLI Reference

```bash
# Import
./memos.sh import  --source chatgpt --input ~/Downloads/memories.json
./memos.sh import  --source claude  --input ~/Downloads/memory.json --preview

# Explore
./memos.sh stats                          # Memory counts by source and category
./memos.sh list   [--limit 50] [--verbose]
./memos.sh search "python research"       # Full-text search (FTS5 + porter stemming)

# Health & Safety
./memos.sh health                         # Staleness, duplicates, gaps
./memos.sh health --verbose               # Show example stale/duplicate memories
./memos.sh audit                          # Scan for emails, phone numbers, API keys

# Context Packs
./memos.sh pack create "coding" --categories professional,project --description "For coding sessions"
./memos.sh pack create "writing" --categories personal,preference
./memos.sh pack list
./memos.sh pack inject "coding"           # Outputs context block ready to paste
./memos.sh pack delete "coding"

# Memory-Aware Prompting
./memos.sh prompt "help me write a cover letter"   # Injects relevant memories into prompt
./memos.sh prompt "review my code style" | pbcopy  # Pipe to clipboard

# Export & Backup
./memos.sh export --output ~/memos-backup.json
./memos.sh export --output ~/chatgpt-backup.json --source chatgpt

# Edit / Delete / Sensitive
./memos.sh edit   <id> --content "Updated text" [--category professional] [--tags python,AI]
./memos.sh delete <id>                    # Delete a single memory (with confirmation)
./memos.sh mark   <id> --sensitive        # Exclude from all AI responses
./memos.sh mark   <id> --not-sensitive    # Remove the exclusion

# Exclusion Rules (applied to all MCP responses, pack injections, and prompts)
./memos.sh rules show
./memos.sh rules set exclude_tags "health,therapy"
./memos.sh rules set exclude_categories "personal"
./memos.sh rules set exclude_keywords "medication,diagnosis"
# Note: rule changes take effect immediately in the CLI but require an MCP client
# restart (e.g. Claude Desktop) to apply to active AI sessions.

# Bulk manage
./memos.sh clear --source chatgpt         # Remove all ChatGPT memories
./memos.sh clear --all                    # Remove everything (with confirmation)
./memos.sh serve                          # Start MCP server (Claude Desktop uses this)
```

---

## MCP Tools

Exposed to any MCP-compatible AI client:

| Tool | Description |
|------|-------------|
| `get_relevant_memories` | Full-text search — exclusion rules applied |
| `get_all_memories` | Paginated retrieval — exclusion rules applied |
| `get_memories_by_category` | Filter by category — exclusion rules applied |
| `add_memory` | Save a memory (optional `sensitive` flag) |
| `update_memory` | Edit an existing memory by ID |
| `delete_memory` | Remove a memory by ID |
| `mark_sensitive` | Flag or unflag a memory as sensitive |
| `get_memory_stats` | Store overview + active exclusion rules |

---

## Memory Categories

Memories are automatically classified into:

| Category | Examples |
|----------|---------|
| `professional` | Job, skills, research, tech stack |
| `personal` | Name, location, family, hobbies |
| `preference` | Likes, dislikes, habits, style |
| `project` | Side projects, ongoing work, goals |
| `relationship` | Colleagues, mentors, friends |

---

## Architecture

```
MemOS/
├── core/
│   ├── schema.py          # Memory model — source, category, tags, sensitive, confidence
│   ├── store.py           # SQLite store with FTS5 search, update, stale detection, export
│   └── rules.py           # ExclusionRules — tag, category, keyword, and sensitive filtering
├── adapters/
│   ├── base.py            # BaseAdapter — implement this to add a new platform
│   ├── chatgpt_adapter.py # ChatGPT memories.json parser
│   ├── claude_adapter.py  # Claude memory.json parser (strings or dicts)
│   └── gemini_adapter.py  # Gemini / Google Takeout parser
├── mcp_server/
│   └── server.py          # 8 MCP tools via stdio (exclusion rules applied per call)
├── memos.py               # CLI entry point (15 commands)
├── setup.sh               # One-command install (macOS + Linux)
├── examples/              # Fake export files for testing
├── tests/                 # pytest suite — store, adapters, rules
└── docs/
    └── adding-an-adapter.md
```

**Why SQLite?** Zero dependencies, local file, indexed queries, and FTS5 virtual tables give full-text search with porter stemming out of the box. No Postgres, no Redis, no vector DB required for the base install.

---

## Feature Comparison

| | mem0 | Rewind | ChatGPT Memory | **MemOS** |
|---|---|---|---|---|
| Storage | Cloud | Local | Cloud | **Local** |
| Privacy | Limited | Good | Limited | **Full** |
| MCP support | No | No | No | **Yes** |
| Multi-tool | No | No | No | **Yes** |
| Open source | Partial | No | No | **MIT** |
| Memory health / staleness | No | No | No | **Yes** |
| Privacy audit | No | No | No | **Yes** |
| Context packs | No | No | No | **Yes** |
| Memory-aware CLI prompts | No | No | No | **Yes** |
| Programmatic export | No | No | No | **Yes** |

---

## Adding a New Platform

See [docs/adding-an-adapter.md](docs/adding-an-adapter.md) for a step-by-step guide.

In short: extend `BaseAdapter`, implement `parse(filepath) -> (list[Memory], int)`, and add it to the `cmd_import` dispatch in `memos.py`.

Community adapters we'd love to see: **Obsidian**, **Notion**, **Perplexity**, **Raycast AI**, **Bear**.

---

## Running Tests

```bash
pip install -r requirements.txt
pytest tests/ -v
```

---

## Contributing

PRs welcome. See [docs/adding-an-adapter.md](docs/adding-an-adapter.md) to add platform support.

Please run `ruff check .` before submitting.

---

## License

MIT — use it, fork it, build on it.
