#!/usr/bin/env python3
"""
Impact Analyzer — PostToolUse hook on Read tool.

When AI reads a .md file (plan, design, spec), extracts function/class names
from inline code and code blocks, queries codegraph.db for callers,
and injects blast radius as additionalContext.

Hook input:  JSON from Claude Code via stdin
Hook output: JSON with hookSpecificOutput.additionalContext
"""

from __future__ import annotations

import ast
import json
import re
import sqlite3
import sys
from pathlib import Path
from typing import Optional


# ── Thresholds ────────────────────────────────────────────────────────────────

def label(count: int) -> str:
    if count <= 2:
        return "LOW"
    elif count <= 5:
        return "MEDIUM"
    elif count <= 15:
        return "HIGH"
    else:
        return "CRITICAL"


# ── DB discovery ──────────────────────────────────────────────────────────────

def find_codegraph_db(start: str) -> Path | None:
    p = Path(start).resolve()
    if p.is_file():
        p = p.parent
    while True:
        candidate = p / ".codegraph" / "codegraph.db"
        if candidate.exists():
            return candidate
        parent = p.parent
        if parent == p:
            return None
        p = parent


# ── Name extraction ───────────────────────────────────────────────────────────

_PYTHON_KEYWORDS = {
    "if", "for", "while", "with", "print", "return", "raise", "import",
    "from", "class", "def", "assert", "yield", "lambda", "not", "and",
    "or", "in", "is", "else", "elif", "try", "except", "finally", "pass",
    "break", "continue", "del", "global", "nonlocal", "True", "False", "None",
}


def _ast_names(code: str) -> set[str]:
    names = set()
    try:
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                names.add(node.name)
    except SyntaxError:
        pass
    return names


def _regex_names(code: str) -> set[str]:
    names = set()
    for m in re.finditer(r'\b(?:def|class)\s+([a-zA-Z_][a-zA-Z0-9_]*)', code):
        names.add(m.group(1))
    return names


def extract_names(content: str) -> set[str]:
    names = set()

    # Inline code: `identifier` or `identifier()`
    for m in re.finditer(r'`([^`\n]+)`', content):
        item = m.group(1).strip().rstrip("()")
        if re.fullmatch(r'[a-zA-Z_][a-zA-Z0-9_]*', item) and item not in _PYTHON_KEYWORDS:
            names.add(item)

    # Code blocks: ```[lang]\n...\n```
    for m in re.finditer(r'```(?:\w+)?\n(.*?)```', content, re.DOTALL):
        block = m.group(1)
        ast_found = _ast_names(block)
        names.update(ast_found if ast_found else _regex_names(block))

    return names


# ── Codegraph query ───────────────────────────────────────────────────────────

def get_callers(db: Path, name: str) -> list[dict]:
    conn = sqlite3.connect(db)
    try:
        rows = conn.execute("""
            SELECT src.name, src.file_path, src.start_line
            FROM edges e
            JOIN nodes src ON e.source = src.id
            JOIN nodes tgt ON e.target = tgt.id
            WHERE tgt.name = ?
              AND e.kind IN ('calls', 'imports', 'instantiates')
        """, (name,)).fetchall()
        return [{"name": r[0], "file_path": r[1], "line": r[2]} for r in rows]
    finally:
        conn.close()


# ── Report formatting ─────────────────────────────────────────────────────────

def _group_by_dir(callers: list[dict]) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for c in callers:
        parts = Path(c["file_path"]).parts
        dir_key = parts[-2] if len(parts) > 1 else "."
        ref = f"{parts[-1]}:{c['line']}"
        grouped.setdefault(dir_key, []).append(ref)
    return grouped


def format_report(results: dict[str, list], md_name: str) -> str:
    if not results:
        return ""

    lines = [f"── IMPACT ANALYSIS: {md_name} ──"]

    # Sort by caller count descending
    for name, callers in sorted(results.items(), key=lambda x: -len(x[1])):
        count = len(callers)
        lbl = label(count)

        if count <= 2:
            refs = ", ".join(f"{Path(c['file_path']).name}:{c['line']}" for c in callers)
            lines.append(f"  {name} [{lbl}] {count} caller — {refs}")
        else:
            display = callers[:10] if count > 15 else callers
            truncated = f" (top 10 of {count} shown)" if count > 15 else f" ({count} callers)"
            lines.append(f"  {name} [{lbl}]{truncated}")
            for dir_name, refs in _group_by_dir(display).items():
                lines.append(f"    {dir_name}/: {', '.join(refs)}")

    lines.append("──────────────────────────────")
    return "\n".join(lines)


# ── Hook entrypoint ───────────────────────────────────────────────────────────

def main() -> None:
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        sys.exit(0)

    if data.get("tool_name") != "Read":
        sys.exit(0)

    file_path = data.get("tool_input", {}).get("file_path", "")
    if not file_path.endswith(".md"):
        sys.exit(0)

    # tool_result is the file content string (cat -n format from Read tool)
    tool_result = data.get("tool_result", "")
    content = tool_result if isinstance(tool_result, str) else json.dumps(tool_result)

    db = find_codegraph_db(data.get("cwd", file_path))
    if not db:
        sys.exit(0)

    names = extract_names(content)
    if not names:
        sys.exit(0)

    results: dict[str, list] = {}
    for name in names:
        callers = get_callers(db, name)
        if callers:
            results[name] = callers

    if not results:
        sys.exit(0)

    report = format_report(results, Path(file_path).name)
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": report,
        }
    }))


if __name__ == "__main__":
    main()
