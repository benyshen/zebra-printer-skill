"""One-shot setup for the zebra-printer skill.

Creates <skill>/.venv, installs the pinned zpl-core wheel from vendor/wheels
(offline, no second repository), then its runtime deps from requirements.txt.
Idempotent: re-running only installs what is missing.

    python scripts/setup.py            # create/refresh .venv
    python scripts/setup.py --check    # report status, install nothing

After this, run everything with:
    Windows : .venv\\Scripts\\python.exe scripts/label.py ...
    POSIX   : .venv/bin/python        scripts/label.py ...

Exit code 0 = ready, 1 = something is missing/failed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
VENV = SKILL / ".venv"
REQ = SKILL / "requirements.txt"
WHEEL_DIR = SKILL / "vendor" / "wheels"

# The engine is a real package now: one pinned wheel, verified by hash.
# Upgrading the engine = drop a new wheel in and update these two lines
# (vendor/PROVENANCE.md has the rebuild steps).
ENGINE_WHEEL = "zpl_core-0.1.0-py3-none-any.whl"
ENGINE_SHA256 = "3f7e2575b153fc8a902ce80a3abdf15bea4dda30e76a59a2e0bb1a8f990f1a0a"
ENGINE_REQ = "zpl-core==0.1.0"

# import name -> pip requirement (they differ for a few packages)
CHECKS = {
    "zpl_core": "zpl-core",
    "PIL": "pillow",
    "segno": "segno",
    "barcode": "python-barcode",
    "cv2": "opencv-python-headless",
    "numpy": "numpy",
    "onnxruntime": "onnxruntime",
    "zxingcpp": "zxing-cpp",
}


def venv_python(venv: Path) -> Path:
    return venv / ("Scripts/python.exe" if sys.platform.startswith("win") else "bin/python")


def missing(py: Path) -> list[str]:
    """Which import names are absent in `py` (one subprocess, no imports here)."""
    code = ("import importlib.util as u, json, sys;"
            f"print(json.dumps([m for m in {list(CHECKS)!r} if not u.find_spec(m)]))")
    try:
        out = subprocess.run([str(py), "-c", code], capture_output=True, text=True,
                             timeout=120)
    except OSError as exc:
        return [f"<cannot run {py}: {exc}>"]
    if out.returncode != 0:
        return [f"<probe failed: {out.stderr.strip()[:200]}>"]
    return json.loads(out.stdout.strip().splitlines()[-1])


def engine_problem(py: Path) -> str:
    """Non-empty when the installed engine does not match the pinned wheel."""
    code = ("import zpl_core, json, pathlib;"
            "print(json.dumps({'v': zpl_core.__version__,"
            " 'p': str(pathlib.Path(zpl_core.__file__).resolve().parent)}))")
    out = subprocess.run([str(py), "-c", code], capture_output=True, text=True, timeout=120)
    if out.returncode != 0:
        return ""          # not installed at all -> missing() already reports it
    info = json.loads(out.stdout.strip().splitlines()[-1])
    if info["v"] != "0.1.0":
        return f"zpl-core {info['v']} installed, expected 0.1.0"
    # .venv 本身就在 skill 目录下，所以不能拿"路径含 skill 目录"当判据：
    # 真正要排除的是 vendor/ 里的源码副本和任何 sys.path 注入。
    if "site-packages" not in info["p"] or f"{os.sep}vendor{os.sep}" in info["p"]:
        return f"zpl_core imported from {info['p']} — expected .venv site-packages"
    return ""


def create_venv() -> Path:
    py = venv_python(VENV)
    if py.is_file():
        print(f"venv exists: {VENV}")
        return py
    print(f"creating venv: {VENV}")
    subprocess.run([sys.executable, "-m", "venv", str(VENV)], check=True)
    if not py.is_file():
        raise SystemExit(f"venv creation did not produce {py}")
    return py


def verify_wheel() -> Path:
    wheel = WHEEL_DIR / ENGINE_WHEEL
    if not wheel.is_file():
        raise SystemExit(
            f"engine wheel missing: {wheel}\n"
            "  vendor/wheels/ was not copied with the skill, or the filename changed.\n"
            "  Rebuild it from https://github.com/benyshen/zpl-core (see vendor/PROVENANCE.md).")
    digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
    if digest != ENGINE_SHA256:
        raise SystemExit(
            f"engine wheel hash mismatch:\n  expected {ENGINE_SHA256}\n  actual   {digest}\n"
            "  Refusing to install an unverified engine. If this wheel is an intentional\n"
            "  upgrade, re-pin ENGINE_SHA256 and note it in vendor/PROVENANCE.md.")
    print(f"engine wheel verified: {wheel.name} "
          f"({wheel.stat().st_size / 1048576:.1f} MB, sha256 ok)")
    return wheel


def install(py: Path) -> None:
    cmds = [
        [str(py), "-m", "pip", "install", "--upgrade", "pip", "--quiet"],
        # offline first: the engine wheel alone, dependencies untouched
        [str(py), "-m", "pip", "install", "--no-index", "--no-deps",
         "--find-links", str(WHEEL_DIR), ENGINE_REQ],
        # then the runtime deps (network unless already present)
        [str(py), "-m", "pip", "install", "-r", str(REQ)],
    ]
    for c in cmds:
        print("$", " ".join(c[1:]))
        r = subprocess.run(c)
        if r.returncode != 0:
            raise SystemExit(f"pip failed (exit {r.returncode})")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="report only, install nothing")
    a = ap.parse_args()

    py = venv_python(VENV)
    if a.check:
        if not py.is_file():
            print(f"MISSING venv: {VENV}  -> run: {sys.executable} scripts/setup.py")
            return 1
        miss = missing(py)
        if miss:
            print("MISSING packages:", ", ".join(CHECKS.get(m, m) for m in miss))
            return 1
        problem = engine_problem(py)
        if problem:
            print("ENGINE PROBLEM:", problem)
            return 1
        print("READY:", py)
        return 0

    verify_wheel()
    py = create_venv()
    if missing(py) or engine_problem(py):
        install(py)
    miss = missing(py)
    problem = engine_problem(py)
    if miss:
        print("STILL MISSING after install:", [CHECKS.get(m, m) for m in miss])
        return 1
    if problem:
        print("ENGINE PROBLEM:", problem)
        return 1
    print("\nREADY:", py)
    print("try: ", f'"{py}" scripts/label.py photo <image> --width 70 --height 70 --dry-run')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
