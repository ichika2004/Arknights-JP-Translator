from __future__ import annotations
import numpy as np
import mss


def capture_rect(rect: tuple[int, int, int, int]) -> np.ndarray:
    """Capture a physical-pixel (left, top, width, height) rectangle as BGR."""
    x, y, w, h = rect
    if w <= 0 or h <= 0:
        raise ValueError("Capture rectangle must have positive dimensions")
    with mss.mss() as sct:
        shot = np.asarray(sct.grab({"left": x, "top": y, "width": w, "height": h}))
    return np.ascontiguousarray(shot[:, :, :3])
