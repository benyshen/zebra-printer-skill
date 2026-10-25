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
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

import zpl_core  # noqa: E402


def line(t: str) -> None:
    print(f"\n=== {t} ===")


def strip_comments(text: str) -> str:
    return "\n".join(l for l in text.splitlines() if not l.lstrip().startswith("#"))


# ---------------------------------------------------------------- 1. layout

line("layout")
required = [
    "SKILL.md", "README.md", "LICENSE", ".gitignore", "requirements.txt",
    "docs/install.md", "vendor/PROVENANCE.md",
    "scripts/setup.py", "scripts/label.py",
    "references/calibration.md", "references/spec-schema.md",
    "templates/warehouse-label-70x70.zpl", "templates/photo-reprint-70x70.zpl",
    "examples/warehouse-70x70.spec.json", "examples/product-70x70.spec.json",
    "examples/employees.xlsx",
    "tests/test_skill.py",
    "vendor/wheels/zpl_core-0.1.0-py3-none-any.whl",
]
for rel in required:
    p = ROOT / rel
    assert p.is_file(), f"missing required file: {rel}"
    assert p.stat().st_size > 0, f"empty file: {rel}"
print(f"{len(required)} required files present")

# 引擎只有一个来源：vendor/wheels 里的 wheel。仓库里不许再出现源码副本。
assert not (ROOT / "vendor" / "src").exists(), \
    "vendor/src must not exist anymore — the engine is the zpl-core wheel, not a source fork"
assert not (ROOT / "scripts" / "_bootstrap.py").exists(), \
    "scripts/_bootstrap.py is gone: zpl_core is a normal installed package now"
assert not (ROOT / "vendor" / "data").exists(), \
    "vendor/data is gone: the command catalog and OCR weights ship inside the wheel"
print("no source fork in vendor/ (wheel only), no bootstrap shim, no loose data")

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

# ---------------------------------------------------------------- 3. engine is the pinned wheel

line("engine resolution")
import hashlib

setup_src = (ROOT / "scripts" / "setup.py").read_text(encoding="utf-8")
pinned_sha = re.search(r'ENGINE_SHA256\s*=\s*"([0-9a-f]{64})"', setup_src).group(1)
pinned_wheel = re.search(r'ENGINE_WHEEL\s*=\s*"([^"]+)"', setup_src).group(1)

wheel = ROOT / "vendor" / "wheels" / pinned_wheel
actual_sha = hashlib.sha256(wheel.read_bytes()).hexdigest()
assert actual_sha == pinned_sha, f"wheel hash drifted: {actual_sha} != {pinned_sha}"
print(f"wheel {pinned_wheel} sha256 ok ({wheel.stat().st_size/1048576:.1f} MB)")

engine_dir = Path(zpl_core.__file__).resolve().parent
assert zpl_core.__version__ == "0.1.0", zpl_core.__version__
assert "site-packages" in str(engine_dir), f"unexpected engine location: {engine_dir}"
assert f"{os.sep}vendor{os.sep}" not in str(engine_dir), \
    f"engine must not come from vendor/: {engine_dir}"
data_dir = str(Path(zpl_core.DATA_DIR).resolve())
assert "site-packages" in data_dir and f"{os.sep}vendor{os.sep}" not in data_dir, \
    f"engine data must ship inside the installed wheel, got {data_dir}"
from zpl_core import builder, catalog, knowledge, transport  # noqa: E402,F401
print(f"engine {zpl_core.__version__} from {engine_dir}")
print(f"engine data inside the wheel: {zpl_core.DATA_DIR}")

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
    from zpl_core import photo, ocr
except ImportError as exc:
    raise SystemExit(f"photo pipeline not importable ({exc}) — run scripts/setup.py")
models = Path(ocr.models_dir())
assert models.is_dir(), f"OCR model dir missing: {models}"
for f in ("ch_PP-OCRv4_det_infer.onnx", "ch_PP-OCRv4_rec_infer.onnx", "ppocr_keys_v1.txt"):
    assert (models / f).is_file(), f"OCR model missing: {models / f}"
print("photo/ocr import ok; models at", models)
assert callable(photo.convert)

line("render")
from zpl_core import render as renderer
out = ROOT / "scratch" / "test_render.png"
out.parent.mkdir(parents=True, exist_ok=True)
res = renderer.render(zpl, scale=2, out=str(out))
assert res.get("ok"), res
assert out.is_file() and out.stat().st_size > 1000, "render produced no png"
assert tuple(res["dots"]) == (559, 559), res["dots"]
print(f"render ok: {out.name}, dots={res['dots']}, drawn={len(res.get('drawn', []))}")

# ---------------------------------------------------------------- 8. CLI surface

line("cli surface")
CLI = ROOT / "scripts" / "label.py"
SUBS = ["build", "validate", "render", "status", "send", "print",
        "photo", "printers", "knowledge", "xlsx"]
help_txt = subprocess.run([sys.executable, str(CLI), "--help"],
                          capture_output=True, text=True, cwd=str(ROOT)).stdout
missing_subs = [s for s in SUBS if s not in help_txt]
assert not missing_subs, f"subcommands missing from --help: {missing_subs}"
print(f"{len(SUBS)} subcommands exposed")


def run_cli(args: list[str]) -> dict:
    r = subprocess.run([sys.executable, str(CLI)] + args,
                       capture_output=True, text=True, cwd=str(ROOT))
    assert r.returncode == 0, (args, r.returncode, r.stdout[-500:], r.stderr[-500:])
    return json.loads(r.stdout)


line("knowledge")
lst = run_cli(["knowledge", "--mode", "list"])
assert lst["count"] == 253, lst["count"]
bc = run_cli(["knowledge", "--mode", "barcodes"])
assert len(bc["supported_by_build"]) == 28, len(bc["supported_by_build"])
assert set(bc["supported_by_build"]) == specs, "barcodes mode disagrees with BARCODE_SPECS"
by = run_cli(["knowledge", "BY"])
assert by["found"] and by["syntax"].startswith("^BY"), by
assert "ratio" in by["defaults"], by
sw = run_cli(["knowledge", "--mode", "sgd"])
st = run_cli(["knowledge", "--mode", "status"])
sr = run_cli(["knowledge", "darkness", "--mode", "search"])
assert sw["count"] and st["count"] and sr["results"], (sw["count"], st["count"], sr["results"])
print(f"list=253, barcodes=28, sgd={sw['count']}, status={st['count']}, "
      f"search('darkness')={len(sr['results'])}, ^BY lookup ok")

line("xlsx")
x = run_cli(["xlsx", "examples/employees.xlsx", "--width", "50", "--height", "30", "--dry-run"])
assert x["ok"], x
assert x["labels"] == 3, x["labels"]
assert x["rows_read"] == 4, x["rows_read"]          # 3 data rows + header
assert x["first_label"].startswith("^XA") and x["first_label"].endswith("^XZ"), x["first_label"]
assert Path(x["zpl_file"]).is_file(), x["zpl_file"]
job = Path(x["zpl_file"]).read_text(encoding="utf-8")
assert job.count("^XA") == 3 and job.count("^XZ") == 3, (job.count("^XA"), job.count("^XZ"))
print(f"xlsx: rows_read=4 -> labels=3, one stream of {len(job)} chars, 3 ^XA/^XZ pairs")

print("\nALL CHECKS PASSED")
