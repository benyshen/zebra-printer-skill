"""One-shot setup for the zebra-printer skill.

Creates <skill>/.venv and installs requirements.txt into it, so a clean machine
needs no global packages and nothing else from the caller. Idempotent: re-running
only installs what is missing.

    python scripts/setup.py            # create/refresh .venv
    python scripts/setup.py --check    # report status, install nothing

After this, run everything with:
    Windows : .venv\\Scripts\\python.exe scripts/label.py ...
    POSIX   : .venv/bin/python        scripts/label.py ...

Exit code 0 = ready, 1 = something is missing/failed.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
VENV = SKILL / ".venv"
REQ = SKILL / "requirements.txt"

# import name -> pip requirement (they differ for a few packages)
CHECKS = {
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
    import json
    return json.loads(out.stdout.strip().splitlines()[-1])


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


def install(py: Path) -> None:
    cmds = [
        [str(py), "-m", "pip", "install", "--upgrade", "pip", "--quiet"],
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
        print("READY:", py)
        return 0

    py = create_venv()
    miss = missing(py)
    if miss:
        print("installing:", ", ".join(CHECKS.get(m, m) for m in miss))
        install(py)
        miss = missing(py)
    if miss:
        print("STILL MISSING after install:", miss)
        return 1
    print("\nREADY:", py)
    print("try: ", f'"{py}" scripts/label.py photo <image> --width 70 --height 70 --dry-run')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
