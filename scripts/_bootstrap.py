"""Locate the zebra_mcp engine (the zebra-printer-mcp repo) and import it.

This skill drives the engine from zebra-printer-mcp; it carries no engine copy.
Search order:
  1. ZEBRA_MCP_SRC env var (directory that contains the `zebra_mcp` package)
  2. <skill>/../zebra-printer-mcp/src      (side-by-side checkout)
  3. <skill>/../../zebra-printer-mcp/src   (skill nested under workspace/)
  4. ZEBRA_MCP_HOME or ~/workspace/zebra-printer-mcp/src, E:/workspace/...
If none found, the error text tells the user exactly what to clone and set.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]

_CANDIDATES = [
    os.environ.get("ZEBRA_MCP_SRC", ""),
    str(SKILL_DIR.parent / "zebra-printer-mcp" / "src"),
    str(SKILL_DIR.parent.parent / "zebra-printer-mcp" / "src"),
    os.environ.get("ZEBRA_MCP_HOME", "") and os.environ["ZEBRA_MCP_HOME"] + "/src",
    str(Path.home() / "workspace" / "zebra-printer-mcp" / "src"),
    r"E:\workspace\zebra-printer-mcp\src",
]


def engine_src() -> Path:
    for c in _CANDIDATES:
        if c and (Path(c) / "zebra_mcp" / "__init__.py").is_file():
            return Path(c)
    raise SystemExit(
        "zebra_mcp engine not found. Clone https://github.com/benyshen/zebra-printer-mcp\n"
        "and point ZEBRA_MCP_SRC at its src/ directory (see README.md).")


def import_engine():
    src = str(engine_src())
    if src not in sys.path:
        sys.path.insert(0, src)
    from zebra_mcp import builder, catalog, knowledge, transport  # noqa: E402
    return builder, catalog, knowledge, transport


def engine_version() -> str:
    try:
        from zebra_mcp import __version__
        return __version__
    except Exception:
        return "?"
