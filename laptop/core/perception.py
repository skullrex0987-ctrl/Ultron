"""Screen perception - three modes (Q9 A+B+C).

A) scrcpy screen capture -> OCR (needs scrcpy + tesseract on laptop)
B) ADB screenshot -> OCR (no scrcpy needed)
C) UiAutomator node tree (accessibility) -> structured, no OCR

All return a normalized "scene" the planner can reason over.
"""
from __future__ import annotations
import subprocess
import os
import tempfile
from typing import Optional

from core.audit import log


def _ocr(image_path: str) -> str:
    try:
        import pytesseract  # type: ignore
        from PIL import Image  # type: ignore
        return pytesseract.image_to_string(Image.open(image_path))
    except Exception as e:  # noqa
        return f"[ocr-unavailable:{e}]"


def mode_a_scrcpy_ocr() -> str:
    """scrcpy screencap + OCR. Returns recognized text."""
    out = os.path.join(tempfile.gettempdir(), "scrcpy_cap.png")
    # scrcpy --screenshot-to-file works in headless mode briefly
    r = subprocess.run(["scrcpy", "-S", f"--screenshot={out}", "--max-fps=1",
                        "--no-window", "-t", "2"],
                       capture_output=True, text=True, timeout=30)
    log("perception", {"mode": "A", "rc": r.returncode})
    if os.path.exists(out):
        return _ocr(out)
    return ""


def _ocr_bytes(data: bytes) -> str:
    try:
        import pytesseract  # type: ignore
        from PIL import Image  # type: ignore
        import io
        return pytesseract.image_to_string(Image.open(io.BytesIO(data)))
    except Exception as e:  # noqa
        return f"[ocr-unavailable:{e}]"


def mode_b_adb_ocr(android) -> str:
    """ADB exec-out screencap -> PNG bytes -> OCR. Works for laptop->phone and
    phone self-control (routes through the same ADB handle as taps/launches)."""
    try:
        r = android._adb("exec-out", "screencap", "-p")
        data = getattr(r, "stdout", b"") or b""
        if len(data) < 100:
            return ""
        return _ocr_bytes(data)
    except Exception as e:  # noqa
        log("perception", {"mode": "B", "err": str(e)})
        return ""


def mode_c_uiautomator(android) -> list[dict]:
    """Accessibility node tree -> list of tappable items."""
    root = android.dump_ui()
    if root is None:
        return []
    items = []
    for node in root.iter("node"):
        t = node.get("text") or node.get("content-desc") or ""
        if t:
            items.append({"text": t, "bounds": node.get("bounds")})
    log("perception", {"mode": "C", "items": len(items)})
    return items


def perceive(android, mode: str = "C") -> dict:
    if mode == "A":
        return {"mode": "A", "text": mode_a_scrcpy_ocr()}
    if mode == "B":
        return {"mode": "B", "text": mode_b_adb_ocr(android)}
    return {"mode": "C", "items": mode_c_uiautomator(android)}