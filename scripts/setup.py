"""One-shot setup for the zebra-printer skill.

Creates <skill>/.venv, installs zpl-core from PyPI (falls back to the pinned wheel in vendor/wheels)
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
ENGINE_SHA256 = "3fbe0e56fd40a04d0d801f1e6c5a45e2dba6da7f6fa17178e5f68d8b40354894"
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


def verify_wheel() -> Path | None:
    """校验 vendor 里的兜底 wheel。缺失时返回 None（在线可从 PyPI 装），哈希不符仍然拒绝。"""
    wheel = WHEEL_DIR / ENGINE_WHEEL
    if not wheel.is_file():
        print(f"note: vendored wheel not found ({wheel.name}) — will install from PyPI")
        return None
    digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
    if digest != ENGINE_SHA256:
        raise SystemExit(
            f"engine wheel hash mismatch:\n  expected {ENGINE_SHA256}\n  actual   {digest}\n"
            "  Refusing to install an unverified engine. If this wheel is an intentional\n"
            "  upgrade, re-pin ENGINE_SHA256 and note it in vendor/PROVENANCE.md.")
    print(f"engine wheel verified: {wheel.name} "
          f"({wheel.stat().st_size / 1048576:.1f} MB, sha256 ok)")
    return wheel


def _run(c: list[str]) -> bool:
    print("$", " ".join(c[1:]))
    return subprocess.run(c).returncode == 0


def install_engine(py: Path, offline: bool, wheel: Path | None) -> None:
    """PyPI 优先；连不上或指定 --offline 时用 vendor/wheels 里哈希已验过的那份。"""
    if not offline:
        if _run([str(py), "-m", "pip", "install", "--quiet", "--upgrade", ENGINE_REQ]):
            print(f"engine installed from PyPI: {ENGINE_REQ}")
            return
        print("PyPI install failed — falling back to the vendored wheel")
    if wheel is None:
        raise SystemExit(
            "no engine available: PyPI unreachable and vendor/wheels/ has no wheel.\n"
            "  Rebuild it from https://github.com/benyshen/zpl-core (see vendor/PROVENANCE.md).")
    if not _run([str(py), "-m", "pip", "install", "--no-index", "--no-deps",
                 "--find-links", str(WHEEL_DIR), ENGINE_REQ]):
        raise SystemExit("pip failed to install the vendored engine wheel")
    print(f"engine installed from vendored wheel: {wheel.name}")


def install(py: Path, offline: bool = False) -> None:
    _run([str(py), "-m", "pip", "install", "--upgrade", "pip", "--quiet"])
    wheel = verify_wheel()
    install_engine(py, offline, wheel)
    if not _run([str(py), "-m", "pip", "install", "-r", str(REQ)]):
        raise SystemExit("pip failed installing runtime requirements")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="report only, install nothing")
    ap.add_argument("--offline", action="store_true",
                    help="install the engine from vendor/wheels only, never touch PyPI")
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

    wheel = verify_wheel()
    if a.offline and wheel is None:
        raise SystemExit("--offline given but vendor/wheels/ has no engine wheel")
    py = create_venv()
    if missing(py) or engine_problem(py):
        install(py, offline=a.offline)
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
