"""Locate the zebra_mcp engine and import it.

This skill ships its own copy of the engine under ``vendor/src/zebra_mcp`` so it
works on a clean machine with no second repository and no MCP client — that copy
is always preferred. The external checkout is only a development fallback (so a
fix can be tested against the upstream tree without copying files around).

Search order:
  1. <skill>/vendor/src                     vendored copy — the normal case
  2. ZEBRA_MCP_SRC env var                  explicit override (development)
  3. <skill>/../zebra-printer-mcp/src       side-by-side checkout
  4. <skill>/../../zebra-printer-mcp/src
  5. ZEBRA_MCP_HOME/src, ~/workspace/..., E:/workspace/...
If none is found the error says exactly what is missing.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
VENDOR_SRC = SKILL_DIR / "vendor" / "src"

_CANDIDATES = [
    str(VENDOR_SRC),
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
        "zebra_mcp engine not found.\n"
        f"  expected the vendored copy at: {VENDOR_SRC}\n"
        "  This skill ships the engine; if it is missing, re-install the skill\n"
        "  (the vendor/ directory was not copied). For development you can also\n"
        "  point ZEBRA_MCP_SRC at a zebra-printer-mcp checkout's src/ directory.")


def import_engine():
    """Import the light modules (stdlib only). Heavy ones — render/photo/ocr —
    pull in pillow/cv2/onnxruntime, so import those at the call site instead."""
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


def vendored() -> bool:
    """True when the engine came from this skill's own vendor/ copy."""
    try:
        return engine_src().resolve() == VENDOR_SRC.resolve()
    except SystemExit:
        return False
