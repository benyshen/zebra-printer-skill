"""Self-check for the zebra-printer-skill project.

Run with the skill's own interpreter (needs pillow/cv2 for the photo+render steps):

    <skill>/.venv/Scripts/python.exe tests/test_skill.py

Every check raises AssertionError with context; the last line printed on
success is ALL CHECKS PASSED.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import _bootstrap  # noqa: E402


def line(t: str) -> None:
    print(f"\n=== {t} ===")


def strip_comments(text: str) -> str:
    return "\n".join(l for l in text.splitlines() if not l.lstrip().startswith("#"))


# ---------------------------------------------------------------- 1. layout

line("layout")
ENGINE_MODULES = ["__init__", "builder", "catalog", "knowledge", "transport",
                  "render", "photo", "ocr", "vision", "xlsx_batch"]
required = [
    "SKILL.md", "README.md", "LICENSE", ".gitignore", "requirements.txt",
    "docs/install.md", "vendor/PROVENANCE.md",
    "scripts/setup.py", "scripts/label.py", "scripts/_bootstrap.py",
    "references/calibration.md", "references/spec-schema.md",
    "templates/warehouse-label-70x70.zpl", "templates/photo-reprint-70x70.zpl",
    "examples/warehouse-70x70.spec.json", "examples/product-70x70.spec.json",
    "tests/test_skill.py",
    "vendor/data/command_catalog.txt",
    "vendor/data/ocr/ch_PP-OCRv4_det_infer.onnx",
    "vendor/data/ocr/ch_PP-OCRv4_rec_infer.onnx",
    "vendor/data/ocr/ppocr_keys_v1.txt",
] + [f"vendor/src/zebra_mcp/{m}.py" for m in ENGINE_MODULES]
for rel in required:
    p = ROOT / rel
    assert p.is_file(), f"missing required file: {rel}"
    assert p.stat().st_size > 0, f"empty file: {rel}"
print(f"{len(required)} required files present")

# the vendored engine must not carry the MCP server (no mcp dependency at all)
assert not (ROOT / "vendor" / "src" / "zebra_mcp" / "server.py").exists(), \
    "vendor must not include server.py (it would drag in the mcp SDK)"
print("no server.py in vendor (no MCP SDK needed)")

# ---------------------------------------------------------------- 2. frontmatter

line("SKILL.md frontmatter")
skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
m = re.match(r"^---\n(.*?)\n---\n", skill, re.S)
assert m, "SKILL.md must open with a YAML frontmatter block"
fm = m.group(1)
for key in ("name:", "description:", "version:"):
    assert key in fm, f"frontmatter missing {key}"
assert "name: zebra-printer-skill" in fm, fm
desc = re.search(r"^description:\s*(.+)$", fm, re.M).group(1).strip()
assert len(desc) >= 30, f"description too short to be a trigger: {desc!r}"
# a skill that claims to be self-contained must not tell the reader to clone
for bad in ("git clone", "ZEBRA_MCP_SRC", "pip install -e"):
    assert bad not in skill, f"SKILL.md still depends on an external checkout: {bad!r}"
print(f"name/version/description ok ({len(desc)} chars); no external-clone instructions")

mentioned = set(re.findall(r"`((?:references|templates|examples|scripts|vendor)/[\w\-./]+)`", skill))
missing = sorted(p for p in mentioned if not (ROOT / p).exists())
assert not missing, f"SKILL.md points at files that do not exist: {missing}"
print(f"{len(mentioned)} referenced paths all exist")

# ---------------------------------------------------------------- 3. engine is the vendored one

line("engine resolution")
src = _bootstrap.engine_src()
assert src.resolve() == (ROOT / "vendor" / "src").resolve(), \
    f"engine must resolve to the vendored copy, got {src}"
assert _bootstrap.vendored(), "vendored() must report True"
builder, catalog, knowledge, transport = _bootstrap.import_engine()
print("engine", _bootstrap.engine_version(), "from", src)

# prove the outside world is not consulted: blank every non-vendor candidate
saved = list(_bootstrap._CANDIDATES)
_bootstrap._CANDIDATES = [c for c in saved if "vendor" in c.replace("\\", "/")]
assert _bootstrap.engine_src().resolve() == (ROOT / "vendor" / "src").resolve()
_bootstrap._CANDIDATES = saved
print("resolves with every external candidate removed")

# ---------------------------------------------------------------- 4. barcode tables agree

line("barcode tables")
specs, cmds, notes = set(builder.BARCODE_SPECS), set(builder.BARCODE_CMDS), set(knowledge.BARCODE_NOTES)
assert specs == cmds == notes, {
    "specs-only": sorted(specs - cmds), "cmds-only": sorted(cmds - specs),
    "notes-only": sorted(notes - specs), "specs-no-notes": sorted(specs - notes),
}
assert len(specs) == 28, f"expected 28 symbologies, got {len(specs)}: {sorted(specs)}"
print(f"BARCODE_SPECS == BARCODE_CMDS == BARCODE_NOTES ({len(specs)} entries)")

schema = (ROOT / "references" / "spec-schema.md").read_text(encoding="utf-8")
sec = schema.split("## 3. ", 1)[1].split("## 4.", 1)[0]
doc_syms = set(re.findall(r"^\| `([a-z0-9]+)` \|", sec, re.M))
assert doc_syms == specs, {
    "documented-not-implemented": sorted(doc_syms - specs),
    "implemented-not-documented": sorted(specs - doc_syms),
}
print(f"spec-schema.md §3 documents exactly the {len(doc_syms)} implemented symbologies")

# ---------------------------------------------------------------- 5. templates

line("templates")
sym_cmds = {v["cmd"] for v in builder.BARCODE_SPECS.values()}
for name in ("warehouse-label-70x70.zpl", "photo-reprint-70x70.zpl"):
    body = strip_comments((ROOT / "templates" / name).read_text(encoding="utf-8"))
    issues = builder.validate_zpl(body)
    errs = [i for i in issues if i["severity"] == "error"]
    assert not errs, (name, errs)
    assert body.lstrip().startswith("^XA"), name
    assert body.rstrip().endswith("^XZ"), name
    for cmd in set(re.findall(r"\^B[A-Z0-9]", body)) - {"^BY"}:
        assert cmd in sym_cmds, f"{name}: {cmd} is not any symbology's command"
    print(f"{name}: {len(issues)} issue(s), 0 errors")

# ---------------------------------------------------------------- 6. example spec matches template

line("example spec -> template")
spec = json.loads((ROOT / "examples" / "warehouse-70x70.spec.json").read_text(encoding="utf-8"))
zpl, issues = builder.build_label(spec)
errs = [i for i in issues if i["severity"] == "error"]
assert not errs, errs
built = zpl.strip()
tpl = "".join(strip_comments(
    (ROOT / "templates" / "warehouse-label-70x70.zpl").read_text(encoding="utf-8")).split())
assert built == tpl, f"spec and template diverged:\nbuilt: {built}\ntpl  : {tpl}"
print(f"built ZPL is byte-identical to the template ({len(built)} chars)")

# ---------------------------------------------------------------- 7. calibration numbering

line("calibration numbering")
cal = (ROOT / "references" / "calibration.md").read_text(encoding="utf-8")
nums = [int(n) for n in re.findall(r"^## (\d+)\.", cal, re.M)]
assert nums == list(range(1, 7)), f"calibration.md must have sections 1..6 in order, got {nums}"
photo_tpl = (ROOT / "templates" / "photo-reprint-70x70.zpl").read_text(encoding="utf-8")
for cited in re.findall(r"calibration\.md 第 (\d+) 条", photo_tpl):
    assert int(cited) in nums, f"template cites calibration rule {cited} which does not exist"
print(f"calibration sections {nums}; template citations resolve")

# ---------------------------------------------------------------- 8. photo pipeline + render

line("photo pipeline")
try:
    from zebra_mcp import photo, ocr
except ImportError as exc:
    raise SystemExit(f"photo pipeline not importable ({exc}) — run scripts/setup.py")
models = Path(ocr.models_dir())
assert models.is_dir(), f"OCR model dir missing: {models}"
for f in ("ch_PP-OCRv4_det_infer.onnx", "ch_PP-OCRv4_rec_infer.onnx", "ppocr_keys_v1.txt"):
    assert (models / f).is_file(), f"OCR model missing: {models / f}"
print("photo/ocr import ok; models at", models)
assert callable(photo.convert)

line("render")
from zebra_mcp import render as renderer
out = ROOT / "scratch" / "test_render.png"
out.parent.mkdir(parents=True, exist_ok=True)
res = renderer.render(zpl, scale=2, out=str(out))
assert res.get("ok"), res
assert out.is_file() and out.stat().st_size > 1000, "render produced no png"
assert tuple(res["dots"]) == (559, 559), res["dots"]
print(f"render ok: {out.name}, dots={res['dots']}, drawn={len(res.get('drawn', []))}")

print("\nALL CHECKS PASSED")
