"""Command line front-end for the zebra-printer skill.

Subcommands (all print JSON on stdout, exit 1 on error):

  photo     <image> [--width 70 --height 70] [--paper 76] [--dry-run]
                                                photo of a label -> ZPL (+ print)
  build     <spec.json> [--out label.zpl]       spec -> ZPL + issues
  validate  <file.zpl|spec.json>                syntax/manual check
  render    <file.zpl> [--scale 2] [--out x.png]
  status    [--host 192.168.28.90]              ~HI/~HS reachability + status word
  send      <file.zpl> [--host ...] [--dry-run]
  print     <spec.json> [--host ...] [--dry-run]  build -> validate -> render -> send
  printers                                      list Windows printer queues

The engine ships inside this skill (vendor/src), so no second repository and no
MCP client are needed. ZEBRA_HOST sets the default printer address.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _bootstrap  # noqa: E402

builder, catalog, knowledge, transport = _bootstrap.import_engine()


# ---------------------------------------------------------------- helpers

def read_text(path: str) -> str:
    """Read ZPL/spec text. Whole-line '#' comments are dropped so the annotated
    templates in templates/ can be fed straight back in."""
    text = Path(path).read_text(encoding="utf-8-sig")
    return "\n".join(l for l in text.splitlines() if not l.lstrip().startswith("#"))


def load_spec(path: str) -> dict:
    return json.loads(read_text(path))


def errors_of(issues: list) -> list:
    return [i for i in issues if i.get("severity") == "error"]


def emit(obj) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def default_host() -> str:
    """Printer address from ZEBRA_HOST so callers need not repeat --host."""
    return os.environ.get("ZEBRA_HOST", "").strip()


def save_zpl(zpl: str, out: str) -> None:
    p = Path(out)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(zpl, encoding="utf-8")


# ---------------------------------------------------------------- commands

def cmd_build(a) -> int:
    spec = load_spec(a.spec)
    zpl, issues = builder.build_label(spec)
    if a.out:
        save_zpl(zpl, a.out)
    errs = errors_of(issues)
    emit({"zpl": zpl, "issues": issues, "errors": len(errs),
          "bytes": len(zpl.encode("utf-8")), "out": a.out or None})
    return 1 if errs else 0


def cmd_validate(a) -> int:
    text = read_text(a.file)
    if text.lstrip().startswith("{"):
        issues = builder.validate_label(load_spec(a.file))
    else:
        issues = builder.validate_zpl(text)
    errs = errors_of(issues)
    emit({"issues": issues, "ok": not errs, "errors": len(errs)})
    return 1 if errs else 0


def cmd_render(a) -> int:
    try:
        from zebra_mcp import render as renderer
    except ImportError as exc:
        # Distinguish "module not shipped/vendored" from "module present but the
        # optional image libs are missing" — the old message blamed the extra
        # even when render.py was simply absent.
        msg = str(exc)
        if "zebra_mcp.render" in msg or "cannot import name" in msg:
            emit({"ok": False, "error": f"render module not available: {msg}. "
                  "The engine checkout (or a vendored copy) must include "
                  "src/zebra_mcp/render.py."})
        else:
            emit({"ok": False, "error": f"render needs the image libs: {msg}. "
                  "Install them: pip install -e '.[render]' in the engine checkout."})
        return 1
    zpl = read_text(a.file)
    result = renderer.render(zpl, scale=max(1, a.scale), out=a.out or None)
    emit(result)
    return 0 if result.get("ok") else 1


def cmd_status(a) -> int:
    """Query status. Prefer the engine's own printer_status so the ~HS parsing
    (~HS line 3, STX/ETX framed) is not duplicated; that lives in
    zebra_mcp.server, which imports FastMCP — so fall back to a local read when
    the MCP SDK is not installed."""
    try:
        from zebra_mcp import server as _server
        fn = getattr(_server, "printer_status", None)
        if fn is None:
            raise ImportError("printer_status missing from zebra_mcp.server")
        print(fn(host=a.host, port=a.port, timeout=a.timeout))
        return 0
    except ImportError:
        pass                      # no MCP SDK (or no server module) -> local read
    host = a.host or default_host()
    if not host:
        emit({"ok": False, "error": "no printer address: pass --host or set ZEBRA_HOST"})
        return 1
    emit(read_status(host, a.port, a.timeout))
    return 0


def read_status(host: str, port: int = 9100, timeout: float = 5.0) -> dict:
    """Minimal ~HI / ~HS probe, no MCP SDK needed.

    ~HS is three STX/ETX-framed lines; the status word is the 4 digits that open
    the THIRD line. Do not scan every 4-digit token: line 1 field 4 (e.g. 0559)
    is not a status word and will be picked up by a naive scan.
    """
    import re as _re
    import socket

    def _read(sock, payload: bytes) -> str:
        sock.sendall(payload)
        sock.settimeout(timeout)
        buf = b""
        while True:
            try:
                chunk = sock.recv(4096)
            except socket.timeout:
                break
            if not chunk:
                break
            buf += chunk
            sock.settimeout(0.5)      # data arrived -> short idle window
        return buf.decode("utf-8", "replace").strip("\x02\x03 \r\n")

    out: dict = {"ok": False, "host": host, "port": port}
    try:
        with socket.create_connection((host, port), timeout=timeout) as s:
            ident = _read(s, b"~HI\r\n")
            hs = _read(s, b"~HS\r\n")
    except OSError as exc:
        out["error"] = f"{type(exc).__name__}: {exc}"
        return out

    out["ok"] = bool(ident or hs)
    if ident:
        bits = ident.split(",")
        out["identification"] = {"printer": bits[0]}
        for key, i in (("firmware", 1), ("dots_per_mm", 2), ("memory", 3)):
            if len(bits) > i:
                out["identification"][key] = bits[i]
    code = None
    for raw in reversed(hs.replace("\x02", "").replace("\x03", "").split("\n")):
        m = _re.match(r"^\s*(\d{4})\b", raw)
        if m:
            code = m.group(1)
            break
    if code:
        note = {"0000": ("PRINTER READY", "ok"),
                "0001": ("HEAD OPEN", "error"), "0002": ("HEAD OPEN", "error"),
                "0003": ("HEAD TOO HOT", "error"), "0004": ("HEAD COLD", "error"),
                "0005": ("MEDIA OUT", "error"), "0006": ("RIBBON OUT", "error"),
                "0007": ("REWINDER FULL", "warn"), "0008": ("PAUSED", "warn"),
                "0009": ("HEAD ELEMENT BAD", "error"),
                "00A0": ("CUTTER FAULT", "error")}.get(code, ("UNKNOWN STATUS WORD", "warn"))
        out["status"] = {"code": code, "name": note[0], "level": note[1]}
    else:
        out["status"] = None
    out["ready"] = bool(out.get("status") and out["status"]["code"] == "0000")
    return out


def cmd_send(a) -> int:
    zpl = read_text(a.file)
    issues = builder.validate_zpl(zpl)
    if errors_of(issues):
        emit({"ok": False, "error": "refusing to send: validation errors",
              "issues": issues})
        return 1
    if a.dry_run:
        try:
            from zebra_mcp import render as renderer
            png = Path(a.out or "scratch/label.png")
            png.parent.mkdir(parents=True, exist_ok=True)
            renderer.render(zpl, out=str(png))
            out = str(png)
        except Exception:
            out = None
        emit({"ok": True, "dry_run": True, "issues": issues,
              "bytes": len(zpl.encode("utf-8")), "preview": out})
        return 0
    if a.transport == "tcp":
        host = a.host or default_host()
        if not host:
            emit({"ok": False, "stage": "send",
                  "error": "no printer address: pass --host <ip> or set ZEBRA_HOST",
                  "bytes": len(zpl.encode("utf-8"))})
            return 1
        res = transport.send_tcp(host, zpl, port=a.port, timeout=a.timeout)
    elif a.transport == "windows":
        res = transport.send_windows_printer(a.printer, zpl)
    elif a.transport == "usb":
        res = transport.send_usb(a.printer, zpl)
    else:
        emit({"ok": False, "error": f"unknown transport {a.transport}"})
        return 1
    emit(res)
    return 0 if res.get("ok", True) else 1


def cmd_print(a) -> int:
    spec = load_spec(a.spec)
    zpl, issues = builder.build_label(spec)
    errs = errors_of(issues)
    if errs:
        emit({"ok": False, "stage": "build", "issues": issues})
        return 1
    check = builder.validate_zpl(zpl)
    if errors_of(check):
        emit({"ok": False, "stage": "validate", "issues": check})
        return 1
    if a.out:
        save_zpl(zpl, a.out)
    preview = None
    try:
        from zebra_mcp import render as renderer
        png = Path(a.preview or "scratch/preview.png")
        png.parent.mkdir(parents=True, exist_ok=True)
        result = renderer.render(zpl, scale=a.scale, out=str(png))
        preview = result.get("png") or str(png)
    except Exception as exc:                      # preview is best-effort
        preview = f"unavailable: {type(exc).__name__}"
    if a.dry_run:
        emit({"ok": True, "dry_run": True, "stage": "preview", "zpl": zpl,
              "issues": issues + check, "preview": preview})
        return 0
    host = a.host or default_host()
    if not host:
        emit({"ok": False, "stage": "send", "zpl": zpl, "preview": preview,
              "error": "no printer address: pass --host <ip> or set ZEBRA_HOST",
              "bytes": len(zpl.encode("utf-8"))})
        return 1
    res = transport.send_tcp(host, zpl, port=a.port, timeout=a.timeout)
    emit({"ok": res.get("ok", True), "stage": "sent", "zpl": zpl,
          "preview": preview, "send": res})
    return 0 if res.get("ok", True) else 1


def cmd_printers(a) -> int:
    res = transport.list_windows_printers()
    emit({"ok": True, "count": len(res), "printers": res})
    return 0


def cmd_photo(a) -> int:
    """Photo of an existing label -> ZPL (and optionally print it).

    Text comes from the local PP-OCRv4 weights shipped in vendor/data/ocr;
    barcode payload always comes from zxing decoding, never from a model.
    """
    try:
        from zebra_mcp import photo
    except ImportError as exc:
        emit({"ok": False, "error": f"photo pipeline unavailable: {exc}",
              "hint": "run scripts/setup.py to install opencv-python-headless / "
                      "numpy / onnxruntime / zxing-cpp"})
        return 1
    if not Path(a.image).is_file():
        emit({"ok": False, "error": f"image not found: {a.image}"})
        return 1
    try:
        res = photo.convert(
            a.image, width_mm=a.width, height_mm=a.height, dpi=a.dpi,
            frame=a.frame, use_ocr=not a.no_ocr, font_file=a.font,
            paper_mm=a.paper, paper_height_mm=a.paper_height,
            offset_x_mm=a.offset_x, offset_y_mm=a.offset_y)
    except Exception as exc:
        emit({"ok": False, "error": f"{type(exc).__name__}: {exc}"})
        return 1

    zpl = res.get("zpl", "")
    check = builder.validate_zpl(zpl) if zpl else []
    errs = errors_of(check)
    preview = None
    if a.preview or a.dry_run:
        try:
            from zebra_mcp import render as renderer
            png = Path(a.preview or "scratch/photo_preview.png")
            png.parent.mkdir(parents=True, exist_ok=True)
            preview = renderer.render(zpl, scale=a.scale, out=str(png)).get("png") or str(png)
        except Exception as exc:
            preview = f"unavailable: {type(exc).__name__}"
    if a.out and zpl:
        save_zpl(zpl, a.out)

    out = {"ok": not errs, "zpl": zpl, "elements": res.get("elements", []),
           "warnings": res.get("warnings", []), "issues": check,
           "preview": preview, "out": a.out or None}
    if errs:
        out["stage"] = "validate"
        emit(out)
        return 1

    host = a.host or default_host()
    if a.dry_run or not host:
        out.update({"dry_run": True,
                    "note": "nothing sent" if a.dry_run else "no --host and no ZEBRA_HOST set"})
        emit(out)
        return 0
    res_send = transport.send_tcp(host, zpl, port=a.port, timeout=a.timeout)
    out.update({"stage": "sent", "host": host, "send": res_send})
    out["ok"] = res_send.get("ok", True)
    emit(out)
    return 0 if out["ok"] else 1


# ---------------------------------------------------------------- parser

def main() -> int:
    p = argparse.ArgumentParser(prog="label.py", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build", help="spec.json -> ZPL")
    b.add_argument("spec")
    b.add_argument("--out")
    b.set_defaults(fn=cmd_build)

    v = sub.add_parser("validate", help="check a .zpl or spec.json")
    v.add_argument("file")
    v.set_defaults(fn=cmd_validate)

    r = sub.add_parser("render", help="render ZPL to PNG (offline)")
    r.add_argument("file")
    r.add_argument("--scale", type=int, default=1)
    r.add_argument("--out")
    r.set_defaults(fn=cmd_render)

    s = sub.add_parser("status", help="printer reachability + status word")
    s.add_argument("--host", default="", help="printer IP (default: ZEBRA_HOST)")
    s.add_argument("--port", type=int, default=9100)
    s.add_argument("--timeout", type=float, default=5.0)
    s.set_defaults(fn=cmd_status)

    n = sub.add_parser("send", help="send a .zpl file")
    n.add_argument("file")
    n.add_argument("--host", default="")
    n.add_argument("--port", type=int, default=9100)
    n.add_argument("--transport", default="tcp", choices=["tcp", "windows", "usb"])
    n.add_argument("--printer", default="")
    n.add_argument("--timeout", type=float, default=5.0)
    n.add_argument("--dry-run", action="store_true")
    n.add_argument("--out", help="preview png path for --dry-run")
    n.set_defaults(fn=cmd_send)

    q = sub.add_parser("print", help="spec.json -> build, validate, render, send")
    q.add_argument("spec")
    q.add_argument("--host", default="")
    q.add_argument("--port", type=int, default=9100)
    q.add_argument("--timeout", type=float, default=5.0)
    q.add_argument("--dry-run", action="store_true")
    q.add_argument("--out", help="keep the generated .zpl here")
    q.add_argument("--preview", help="preview png path")
    q.add_argument("--scale", type=int, default=2)
    q.set_defaults(fn=cmd_print)

    ph = sub.add_parser("photo", help="photo of a label -> ZPL (and optionally print)")
    ph.add_argument("image", help=".png/.jpg of the existing label")
    ph.add_argument("--width", type=float, default=70.0, help="printed design width mm")
    ph.add_argument("--height", type=float, default=70.0, help="printed design height mm")
    ph.add_argument("--paper", type=float, default=0.0,
                    help="physical paper width mm, when paper is larger than the design")
    ph.add_argument("--paper-height", type=float, default=0.0,
                    help="physical paper height mm (defaults to --paper)")
    ph.add_argument("--offset-x", type=float, default=0.0, help="nudge all elements, mm")
    ph.add_argument("--offset-y", type=float, default=0.0, help="nudge all elements, mm")
    ph.add_argument("--dpi", type=int, default=203)
    ph.add_argument("--frame", default="auto", choices=["auto", "full"])
    ph.add_argument("--font", default="E:SIMSUN.TTF", help="resident TrueType font name")
    ph.add_argument("--no-ocr", action="store_true", help="symbols only, no text")
    ph.add_argument("--host", default="")
    ph.add_argument("--port", type=int, default=9100)
    ph.add_argument("--timeout", type=float, default=5.0)
    ph.add_argument("--dry-run", action="store_true", help="do not print")
    ph.add_argument("--out", help="save the generated .zpl here")
    ph.add_argument("--preview", help="preview png path")
    ph.add_argument("--scale", type=int, default=2)
    ph.set_defaults(fn=cmd_photo)

    lp = sub.add_parser("printers", help="list Windows printer queues")
    lp.set_defaults(fn=cmd_printers)

    a = p.parse_args()
    if a.cmd in ("send", "print", "photo") and not getattr(a, "host", ""):
        a.host = default_host()
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main())
