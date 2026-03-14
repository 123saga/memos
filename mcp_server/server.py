# memos MCP server
# exposes the local memory store to Claude Desktop, Cursor, Windsurf, etc.
from __future__ import annotations
import sys
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
os.chdir(PROJECT_ROOT)

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

from core.schema import Memory, MemorySource, MemoryCategory
from core.store import MemoryStore
from core.rules import ExclusionRules

app = Server("memos")
store = MemoryStore()

_CATEGORIES = ["professional", "personal", "preference", "project", "relationship"]
_SOURCES = ["claude", "chatgpt", "gemini", "obsidian", "manual"]


def _format_memory(m: Memory, idx: int) -> str:
    sens = " [SENSITIVE]" if m.sensitive else ""
    return (
        f"{idx}. [{m.category.upper()}] {m.content}{sens}\n"
        f"   Source: {m.source} | Confidence: {m.confidence:.0%} | "
        f"Tags: {', '.join(m.tags) or 'none'} | ID: {m.id}"
    )


@app.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="get_relevant_memories",
            description=(
                "Search the user's personal memory store using full-text search. "
                "Call this at the start of any conversation to load personal context. "
                "Results are filtered by the user's exclusion rules (sensitive memories, "
                "excluded tags/categories/keywords are automatically hidden)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "What you want to know about the user"},
                    "limit": {"type": "integer", "description": "Max results to return", "default": 5},
                },
                "required": ["query"],
            },
        ),
        types.Tool(
            name="get_all_memories",
            description="Retrieve all memories from the store, paginated. Exclusion rules are applied.",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit":  {"type": "integer", "default": 20},
                    "offset": {"type": "integer", "default": 0},
                },
            },
        ),
        types.Tool(
            name="get_memories_by_category",
            description="Get memories filtered by category. Exclusion rules are applied.",
            inputSchema={
                "type": "object",
                "properties": {
                    "category": {"type": "string", "enum": _CATEGORIES},
                },
                "required": ["category"],
            },
        ),
        types.Tool(
            name="add_memory",
            description="Save a new memory about the user learned during conversation.",
            inputSchema={
                "type": "object",
                "properties": {
                    "content":  {"type": "string"},
                    "category": {"type": "string", "enum": _CATEGORIES},
                    "tags":     {"type": "array", "items": {"type": "string"}},
                    "source":   {"type": "string", "enum": _SOURCES, "default": "manual"},
                    "sensitive": {"type": "boolean", "default": False,
                                  "description": "Mark as sensitive (excluded from future queries by default)"},
                },
                "required": ["content", "category"],
            },
        ),
        types.Tool(
            name="update_memory",
            description="Update the content of an existing memory by its ID.",
            inputSchema={
                "type": "object",
                "properties": {
                    "memory_id": {"type": "string"},
                    "content":   {"type": "string"},
                    "category":  {"type": "string", "enum": _CATEGORIES},
                    "tags":      {"type": "array", "items": {"type": "string"}},
                },
                "required": ["memory_id", "content"],
            },
        ),
        types.Tool(
            name="delete_memory",
            description="Delete a memory by its ID.",
            inputSchema={
                "type": "object",
                "properties": {
                    "memory_id": {"type": "string"},
                },
                "required": ["memory_id"],
            },
        ),
        types.Tool(
            name="mark_sensitive",
            description="Mark or unmark a memory as sensitive. Sensitive memories are excluded from queries by default.",
            inputSchema={
                "type": "object",
                "properties": {
                    "memory_id": {"type": "string"},
                    "sensitive": {"type": "boolean", "description": "true to mark, false to unmark"},
                },
                "required": ["memory_id", "sensitive"],
            },
        ),
        types.Tool(
            name="get_memory_stats",
            description="Get an overview of the memory store including health signals and active exclusion rules.",
            inputSchema={"type": "object", "properties": {}},
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    try:
        if name == "get_relevant_memories":
            query   = arguments.get("query", "")
            limit   = int(arguments.get("limit", 5))
            rules   = ExclusionRules()
            # Fetch a generous pool so exclusion rules don't silently shrink results
            results = store.search(query, limit=max(limit * 4, 20))
            results = rules.apply(results)[:limit]
            if not results:
                return [types.TextContent(type="text", text="No relevant memories found.")]
            lines = [f"Found {len(results)} relevant memories:\n"]
            for i, m in enumerate(results, 1):
                lines.append(_format_memory(m, i))
            return [types.TextContent(type="text", text="\n".join(lines))]

        elif name == "get_all_memories":
            limit  = int(arguments.get("limit", 20))
            offset = int(arguments.get("offset", 0))
            rules  = ExclusionRules()
            # Apply rules first, then paginate — so offset/limit are stable across rule changes
            all_m  = store.get_all(limit=1000, offset=0)
            all_m  = rules.apply(all_m)
            total_visible = len(all_m)
            page   = all_m[offset:offset + limit]
            if not page:
                return [types.TextContent(type="text", text="Memory store is empty.")]
            lines = [f"Showing {len(page)} of {total_visible} visible memories:\n"]
            for i, m in enumerate(page, offset + 1):
                lines.append(_format_memory(m, i))
            return [types.TextContent(type="text", text="\n".join(lines))]

        elif name == "get_memories_by_category":
            category = arguments.get("category", "")
            rules    = ExclusionRules()
            results  = store.get_by_category(category)
            results  = rules.apply(results)
            if not results:
                return [types.TextContent(type="text", text=f"No memories in '{category}'.")]
            lines = [f"Found {len(results)} memories in '{category}':\n"]
            for i, m in enumerate(results, 1):
                lines.append(_format_memory(m, i))
            return [types.TextContent(type="text", text="\n".join(lines))]

        elif name == "add_memory":
            new_memory = Memory(
                content=arguments["content"],
                source=MemorySource(arguments.get("source", "manual")),
                category=MemoryCategory(arguments["category"]),
                tags=arguments.get("tags", []),
                sensitive=arguments.get("sensitive", False),
                confidence=0.9,
            )
            added = store.add(new_memory)
            if added:
                return [types.TextContent(type="text", text=f"Memory saved. ID: {new_memory.id}")]
            return [types.TextContent(type="text", text="Memory already exists (duplicate skipped).")]

        elif name == "update_memory":
            memory_id = arguments.get("memory_id", "")
            content   = arguments.get("content", "")
            category  = arguments.get("category")
            tags      = arguments.get("tags")
            success   = store.update(memory_id, content, category=category, tags=tags)
            if success:
                return [types.TextContent(type="text", text=f"Memory {memory_id} updated.")]
            return [types.TextContent(type="text", text=f"Memory not found: {memory_id}")]

        elif name == "delete_memory":
            memory_id = arguments.get("memory_id", "")
            success   = store.delete(memory_id)
            if success:
                return [types.TextContent(type="text", text=f"Memory {memory_id} deleted.")]
            return [types.TextContent(type="text", text=f"Memory not found: {memory_id}")]

        elif name == "mark_sensitive":
            memory_id = arguments.get("memory_id", "")
            sensitive = arguments.get("sensitive", True)
            success   = store.set_sensitive(memory_id, sensitive)
            label = "sensitive" if sensitive else "not sensitive"
            if success:
                return [types.TextContent(type="text", text=f"Memory {memory_id} marked as {label}.")]
            return [types.TextContent(type="text", text=f"Memory not found: {memory_id}")]

        elif name == "get_memory_stats":
            rules     = ExclusionRules()
            total     = store.count()
            by_cat    = store.count_by_category()
            by_src    = store.count_by_source()
            stale     = store.get_stale(threshold_days=180)
            sensitive = store.get_sensitive()
            lines     = [f"MemOS Stats\n{'─'*20}", f"Total: {total}\n", "By category:"]
            for cat, count in sorted(by_cat.items()):
                lines.append(f"  {cat}: {count}")
            lines.append("\nBy source:")
            for src, count in sorted(by_src.items()):
                lines.append(f"  {src}: {count}")
            if sensitive:
                lines.append(f"\nSensitive: {len(sensitive)} memories marked (excluded from queries)")
            if stale:
                lines.append(f"\nHealth: {len(stale)} memories older than 6 months may be stale.")
            active_rules = rules.to_dict()
            if any(v for v in active_rules.values() if v):
                lines.append(f"\nActive exclusion rules:")
                for k, v in active_rules.items():
                    if v:
                        lines.append(f"  {k}: {v}")
            return [types.TextContent(type="text", text="\n".join(lines))]

        return [types.TextContent(type="text", text=f"Unknown tool: {name}")]

    except Exception as e:
        return [types.TextContent(type="text", text=f"Error in {name}: {e}")]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
