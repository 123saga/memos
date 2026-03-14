#!/usr/bin/env python3
"""
memos — CLI for MemOS

  import   --source chatgpt --input ~/Downloads/memories.json
  import   --source claude  --input ~/Downloads/memory.json --preview
  search   "python research"
  list     [--limit 50] [--verbose]
  stats
  health   [--verbose]
  export   --output ~/backup.json
  audit
  edit     <id> --content "new text" [--category professional] [--tags python,AI]
  delete   <id>
  mark     <id> --sensitive / --not-sensitive
  pack     create "coding" --categories professional,project
  pack     inject "coding" [--exclude-tags health,therapy]
  pack     list
  prompt   "help me write a cover letter"
  rules    show / set <key> <value>
  clear    --source chatgpt
  serve
"""
from __future__ import annotations
import sys
import os
import argparse

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)


def cmd_import(args):
    source = args.source.lower()
    if source == "chatgpt":
        from adapters.chatgpt_adapter import parse, print_summary
    elif source == "claude":
        from adapters.claude_adapter import parse, print_summary
    elif source == "gemini":
        from adapters.gemini_adapter import parse, print_summary
    else:
        print(f"Unknown source: {source}")
        sys.exit(1)

    memories, skipped = parse(args.input)
    print_summary(memories, skipped)

    if args.preview:
        print("  Preview mode — nothing saved. Remove --preview to import.\n")
        return

    from core.store import MemoryStore
    store = MemoryStore()
    added = store.add_many(memories)
    print(f"  Saved {added} new memories ({len(memories) - added} duplicates skipped)")
    print(f"  Total in store: {store.count()}")
    print(f"  Sources: {dict(store.count_by_source())}\n")


def cmd_serve(args):
    import asyncio
    from mcp_server.server import main
    asyncio.run(main())


def cmd_stats(args):
    from core.store import MemoryStore
    store = MemoryStore()

    if store.count() == 0:
        print("\n  Memory store is empty.")
        print("  Run: ./memos.sh import --source chatgpt --input ~/Downloads/memories.json\n")
        return

    by_src = store.count_by_source()
    by_cat = store.count_by_category()
    sensitive_count = len(store.get_sensitive())

    print(f"\n{'─'*50}")
    print(f"  MemOS — ~/.memos/memories.db")
    print(f"{'─'*50}")
    print(f"  Total: {store.count()}  (sensitive: {sensitive_count})\n")
    print("  By source:")
    for src, n in sorted(by_src.items()):
        print(f"    {src:12} {n:3}  {'|' * min(n, 40)}")
    print("\n  By category:")
    for cat, n in sorted(by_cat.items()):
        print(f"    {cat:14} {n:3}  {'|' * min(n, 40)}")
    print(f"{'─'*50}\n")


def cmd_list(args):
    from core.store import MemoryStore
    store = MemoryStore()
    memories = store.get_all(limit=args.limit, offset=args.offset)
    total = store.count()

    if not memories:
        print("\n  No memories found.\n")
        return

    print(f"\n  Showing {len(memories)} of {total} memories\n")
    for i, m in enumerate(memories, args.offset + 1):
        sens = " [SENSITIVE]" if m.sensitive else ""
        print(f"  {i:3}. [{m.source:8}] [{m.category:12}] {m.content[:60]}{sens}")
        if args.verbose:
            if m.tags:
                print(f"       Tags: {', '.join(m.tags)}")
            print(f"       ID: {m.id}  |  Age: {m.age_days()}d")
    print()


def cmd_search(args):
    from core.store import MemoryStore
    store = MemoryStore()
    results = store.search(args.query, limit=args.limit)

    if not results:
        print(f"\n  No memories found for: '{args.query}'\n")
        return

    print(f"\n  {len(results)} results for '{args.query}':\n")
    for i, m in enumerate(results, 1):
        sens = " [SENSITIVE]" if m.sensitive else ""
        print(f"  {i}. [{m.source:8}] [{m.category:12}] {m.content[:65]}{sens}")
        if m.tags:
            print(f"     Tags: {', '.join(m.tags)}")
    print()


def cmd_health(args):
    from core.store import MemoryStore
    from core.schema import MemoryCategory
    store = MemoryStore()
    total = store.count()

    if total == 0:
        print("\n  Memory store is empty — import some memories first.\n")
        return

    stale = store.get_stale(threshold_days=180)
    duplicates = store.find_near_duplicates(threshold=0.75)
    by_cat = store.count_by_category()
    missing = [c.value for c in MemoryCategory if by_cat.get(c.value, 0) == 0]
    sensitive = store.get_sensitive()

    score = 100
    score -= min(30, int(len(stale) / max(total, 1) * 100))
    score -= min(20, len(duplicates) * 5)
    score -= len(missing) * 5
    score = max(0, score)

    bar = "#" * (score // 5) + "-" * (20 - score // 5)
    grade = "A" if score >= 85 else "B" if score >= 70 else "C" if score >= 50 else "D"

    print(f"\n{'─'*55}")
    print(f"  MemOS Health Report")
    print(f"{'─'*55}")
    print(f"  Score: {score}/100  [{bar}]  Grade: {grade}")
    print(f"  Total memories: {total}\n")

    if stale:
        print(f"  [WARN] {len(stale)} memories older than 6 months may be stale")
        if args.verbose:
            for m in stale[:5]:
                print(f"         - [{m.age_days()}d] {m.content[:60]}")
    else:
        print(f"  [OK]   All memories are recent")

    if duplicates:
        print(f"  [WARN] {len(duplicates)} near-duplicate memory pairs detected")
        if args.verbose:
            for a, b in duplicates[:3]:
                print(f"         - \"{a.content[:40]}\" <-> \"{b.content[:40]}\"")
    else:
        print(f"  [OK]   No near-duplicates detected")

    if missing:
        print(f"  [INFO] No memories in: {', '.join(missing)}")
    else:
        print(f"  [OK]   All categories covered")

    if sensitive:
        print(f"  [INFO] {len(sensitive)} memories marked as sensitive (excluded from MCP)")

    if score < 70:
        print(f"\n  Tip: Run './memos.sh list --verbose' to review old memories.")
    print(f"{'─'*55}\n")


def cmd_export(args):
    from core.store import MemoryStore
    from pathlib import Path
    store = MemoryStore()
    count = store.export_json(Path(args.output), source=args.source)
    print(f"\n  Exported {count} memories to {args.output}\n")


def cmd_audit(args):
    import re
    from core.store import MemoryStore
    store = MemoryStore()
    memories = store.get_all(limit=10000)

    patterns = {
        "email": re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"),
        "phone": re.compile(r"\b(\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}\b"),
        "api_key": re.compile(r"\b(sk-|pk-|api[-_]?key)[A-Za-z0-9_\-]{10,}\b", re.I),
        "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
        "credit_card": re.compile(r"\b(?:\d[ -]?){13,16}\b"),
    }

    issues = []
    for m in memories:
        for label, pat in patterns.items():
            if pat.search(m.content):
                issues.append((label, m))

    print(f"\n{'─'*55}")
    print(f"  Privacy Audit — {len(memories)} memories scanned")
    print(f"{'─'*55}")

    if not issues:
        print("  [OK] No sensitive data patterns detected.\n")
        return

    print(f"  [WARN] {len(issues)} potential concern(s):\n")
    for label, m in issues:
        sens = " [SENSITIVE]" if m.sensitive else ""
        print(f"  [{label.upper()}] {m.content[:70]}{sens}")
        print(f"          ID: {m.id}")
    print(f"\n  Tip: Run './memos.sh mark <id> --sensitive' to flag these,")
    print(f"       or './memos.sh delete <id>' to remove them.")
    print(f"{'─'*55}\n")


def cmd_edit(args):
    from core.store import MemoryStore
    store = MemoryStore()

    memory = store.get_by_id(args.id)
    if not memory:
        print(f"\n  Memory not found: {args.id}\n")
        sys.exit(1)

    content = args.content or memory.content
    category = args.category or memory.category
    tags = [t.strip() for t in args.tags.split(",")] if args.tags else None

    success = store.update(args.id, content, category=category, tags=tags)
    if success:
        updated = store.get_by_id(args.id)
        print(f"\n  Memory updated.")
        print(f"  ID:       {updated.id}")
        print(f"  Content:  {updated.content[:80]}")
        print(f"  Category: {updated.category}")
        print(f"  Tags:     {', '.join(updated.tags)}\n")
    else:
        print(f"\n  Failed to update memory.\n")


def cmd_delete_memory(args):
    from core.store import MemoryStore
    store = MemoryStore()

    memory = store.get_by_id(args.id)
    if not memory:
        print(f"\n  Memory not found: {args.id}\n")
        sys.exit(1)

    if not args.yes:
        print(f"\n  About to delete:")
        print(f"  [{memory.source:8}] [{memory.category:12}] {memory.content[:70]}")
        confirm = input("  Confirm? (yes/no): ")
        if confirm.lower() != "yes":
            print("  Cancelled.\n")
            return

    store.delete(args.id)
    print(f"\n  Deleted memory {args.id}\n")


def cmd_mark(args):
    from core.store import MemoryStore
    store = MemoryStore()

    memory = store.get_by_id(args.id)
    if not memory:
        print(f"\n  Memory not found: {args.id}\n")
        sys.exit(1)

    if args.sensitive:
        sensitive = True
    elif args.not_sensitive:
        sensitive = False
    else:
        print("  Specify --sensitive or --not-sensitive")
        sys.exit(1)

    store.set_sensitive(args.id, sensitive)
    label = "SENSITIVE" if sensitive else "NOT SENSITIVE"
    print(f"\n  Marked memory as {label}:")
    print(f"  [{memory.source:8}] {memory.content[:70]}")
    print(f"  ID: {args.id}\n")


def cmd_pack(args):
    import json
    from pathlib import Path

    packs_dir = Path.home() / ".memos" / "packs"
    packs_dir.mkdir(parents=True, exist_ok=True)

    if args.pack_command == "create":
        pack = {
            "name": args.name,
            "categories": [c.strip() for c in args.categories.split(",")],
            "tags": [t.strip() for t in args.tags.split(",")] if args.tags else [],
            "exclude_tags": [t.strip() for t in args.exclude_tags.split(",")] if args.exclude_tags else [],
            "description": args.description or "",
        }
        (packs_dir / f"{args.name}.json").write_text(json.dumps(pack, indent=2))
        print(f"\n  Pack '{args.name}' saved.\n")

    elif args.pack_command == "list":
        packs = list(packs_dir.glob("*.json"))
        if not packs:
            print("\n  No packs yet. Try: ./memos.sh pack create coding --categories professional,project\n")
            return
        print(f"\n  {len(packs)} pack(s):\n")
        for p in packs:
            data = json.loads(p.read_text())
            excl = data.get("exclude_tags", [])
            excl_str = f"  exclude: {', '.join(excl)}" if excl else ""
            print(f"  {data['name']}  ({', '.join(data['categories'])}){excl_str}")
            if data.get("description"):
                print(f"    {data['description']}")
        print()

    elif args.pack_command == "inject":
        pack_file = packs_dir / f"{args.name}.json"
        if not pack_file.exists():
            print(f"\n  Pack '{args.name}' not found.\n")
            return
        pack = json.loads(pack_file.read_text())

        from core.store import MemoryStore
        from core.rules import ExclusionRules
        store = MemoryStore()
        rules = ExclusionRules()

        memories = []
        for cat in pack["categories"]:
            memories.extend(store.get_by_category(cat))

        # Apply global exclusion rules
        memories = rules.apply(memories)

        # Apply pack-level exclude_tags (from pack definition + CLI override)
        exclude_tags = set(pack.get("exclude_tags", []))
        if args.exclude_tags:
            exclude_tags.update(t.strip() for t in args.exclude_tags.split(","))
        if exclude_tags:
            memories = [m for m in memories if not (set(m.tags) & exclude_tags)]

        if not memories:
            print(f"\n  No memories found for pack '{args.name}' (after exclusion rules).\n")
            return

        print(f"\n# {pack['name']}")
        if pack.get("description"):
            print(f"# {pack['description']}")
        print()
        for m in memories:
            print(m.to_context_string())
        print()

    elif args.pack_command == "delete":
        pack_file = packs_dir / f"{args.name}.json"
        if pack_file.exists():
            pack_file.unlink()
            print(f"\n  Pack '{args.name}' deleted.\n")
        else:
            print(f"\n  Pack '{args.name}' not found.\n")


def cmd_prompt(args):
    from core.store import MemoryStore
    from core.rules import ExclusionRules
    store = MemoryStore()
    rules = ExclusionRules()

    results = store._keyword_search(args.task, limit=args.limit)
    results = rules.apply(results)

    if not results:
        print(args.task)
        return

    context = "\n".join(m.to_context_string() for m in results)
    print(f"## Personal Context\n{context}\n\n---\n\n{args.task}")


def cmd_rules(args):
    import json
    from core.rules import ExclusionRules
    rules = ExclusionRules()

    if args.rules_command == "show":
        print(f"\n{'─'*55}")
        print(f"  Exclusion Rules — ~/.memos/rules.json")
        print(f"{'─'*55}")
        for key, val in rules.to_dict().items():
            print(f"  {key:25} {json.dumps(val)}")
        print(f"{'─'*55}")
        print(f"\n  Memories matching these rules are excluded from MCP responses,")
        print(f"  pack injection, and memory-aware prompts.\n")

    elif args.rules_command == "set":
        key = args.key
        raw = args.value

        if key == "exclude_sensitive":
            value = raw.lower() in ("true", "1", "yes")
        elif key in ("exclude_tags", "exclude_categories", "exclude_keywords"):
            value = [v.strip() for v in raw.split(",") if v.strip()]
        else:
            print(f"\n  Unknown rule: {key}")
            print(f"  Valid rules: exclude_sensitive, exclude_tags, exclude_categories, exclude_keywords\n")
            sys.exit(1)

        rules.set_rule(key, value)
        print(f"\n  Rule updated: {key} = {json.dumps(value)}\n")


def cmd_clear(args):
    from core.store import MemoryStore
    store = MemoryStore()

    if args.source:
        confirm = input(f"  Delete all '{args.source}' memories? (yes/no): ")
        if confirm.lower() != "yes":
            print("  Cancelled.")
            return
        deleted = store.clear_source(args.source)
        print(f"  Deleted {deleted} memories from '{args.source}'")
    elif getattr(args, "all", False):
        confirm = input("  Delete ALL memories? This cannot be undone. (yes/no): ")
        if confirm.lower() != "yes":
            print("  Cancelled.")
            return
        deleted = store.clear_all()
        print(f"  Deleted {deleted} memories")
    else:
        print("  Specify --source <name> or --all")


def main():
    parser = argparse.ArgumentParser(
        prog="memos",
        description="MemOS — local memory layer for AI tools",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
commands:
  import   import from a platform export
  search   full-text search
  list     list all memories
  stats    counts by source and category
  health   staleness, duplicates, coverage gaps
  export   dump to JSON
  audit    scan for sensitive data
  edit     update a memory by ID
  delete   delete a single memory by ID
  mark     flag a memory as sensitive / not-sensitive
  pack     create / list / inject / delete context packs
  prompt   memory-aware prompt generation
  rules    view or set exclusion rules
  clear    bulk-delete memories
  serve    start MCP server (used by Claude Desktop / Cursor)
        """,
    )

    sub = parser.add_subparsers(dest="command", metavar="COMMAND")
    sub.required = True

    p = sub.add_parser("import", help="import from a platform export")
    p.add_argument("--source", "-s", required=True, choices=["chatgpt", "claude", "gemini"])
    p.add_argument("--input", "-i", required=True, help="path to export file")
    p.add_argument("--preview", "-p", action="store_true", help="preview without saving")

    sub.add_parser("serve", help="start the MCP server")
    sub.add_parser("stats", help="show memory statistics")

    p = sub.add_parser("list", help="list memories")
    p.add_argument("--limit", "-n", type=int, default=50)
    p.add_argument("--offset", type=int, default=0)
    p.add_argument("--verbose", "-v", action="store_true")

    p = sub.add_parser("search", help="search memories")
    p.add_argument("query")
    p.add_argument("--limit", "-n", type=int, default=10)

    p = sub.add_parser("health", help="memory health report")
    p.add_argument("--verbose", "-v", action="store_true")

    p = sub.add_parser("export", help="export memories to JSON")
    p.add_argument("--output", "-o", required=True)
    p.add_argument("--source", "-s", help="filter by source")

    sub.add_parser("audit", help="scan for sensitive data")

    # ── Edit ──────────────────────────────────────────────────────────────
    p = sub.add_parser("edit", help="update a memory by ID")
    p.add_argument("id", help="memory ID")
    p.add_argument("--content", "-c", help="new content")
    p.add_argument("--category", help="new category")
    p.add_argument("--tags", "-t", help="comma-separated tags")

    # ── Delete (single) ──────────────────────────────────────────────────
    p = sub.add_parser("delete", help="delete a single memory by ID")
    p.add_argument("id", help="memory ID")
    p.add_argument("--yes", "-y", action="store_true", help="skip confirmation")

    # ── Mark sensitive ───────────────────────────────────────────────────
    p = sub.add_parser("mark", help="flag a memory as sensitive or not-sensitive")
    p.add_argument("id", help="memory ID")
    p.add_argument("--sensitive", action="store_true", help="mark as sensitive")
    p.add_argument("--not-sensitive", action="store_true", help="remove sensitive flag")

    # ── Packs ────────────────────────────────────────────────────────────
    p_pack = sub.add_parser("pack", help="manage context packs")
    pack_sub = p_pack.add_subparsers(dest="pack_command", metavar="SUBCOMMAND")
    pack_sub.required = True

    p_create = pack_sub.add_parser("create")
    p_create.add_argument("name")
    p_create.add_argument("--categories", required=True, help="e.g. professional,project")
    p_create.add_argument("--tags")
    p_create.add_argument("--exclude-tags", help="tags to exclude from this pack")
    p_create.add_argument("--description")

    pack_sub.add_parser("list")

    p_inject = pack_sub.add_parser("inject")
    p_inject.add_argument("name")
    p_inject.add_argument("--exclude-tags", help="additional tags to exclude at inject time")

    p_del = pack_sub.add_parser("delete")
    p_del.add_argument("name")

    p = sub.add_parser("prompt", help="generate a memory-aware prompt")
    p.add_argument("task")
    p.add_argument("--limit", "-n", type=int, default=8)

    # ── Rules ────────────────────────────────────────────────────────────
    p_rules = sub.add_parser("rules", help="view or set exclusion rules")
    rules_sub = p_rules.add_subparsers(dest="rules_command", metavar="SUBCOMMAND")
    rules_sub.required = True

    rules_sub.add_parser("show")

    p_set = rules_sub.add_parser("set")
    p_set.add_argument("key", help="rule name (exclude_sensitive, exclude_tags, etc.)")
    p_set.add_argument("value", help="rule value")

    p = sub.add_parser("clear", help="bulk-delete memories")
    p.add_argument("--source", help="delete from specific source")
    p.add_argument("--all", action="store_true")

    args = parser.parse_args()

    {
        "import": cmd_import,
        "serve": cmd_serve,
        "stats": cmd_stats,
        "list": cmd_list,
        "search": cmd_search,
        "health": cmd_health,
        "export": cmd_export,
        "audit": cmd_audit,
        "edit": cmd_edit,
        "delete": cmd_delete_memory,
        "mark": cmd_mark,
        "pack": cmd_pack,
        "prompt": cmd_prompt,
        "rules": cmd_rules,
        "clear": cmd_clear,
    }[args.command](args)


if __name__ == "__main__":
    main()
