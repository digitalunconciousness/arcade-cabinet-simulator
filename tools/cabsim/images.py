# license:CC0-1.0
"""Screen captures to PNG, and an 8x zoom of where two captures differ."""

from __future__ import annotations

from pathlib import Path

SCALE = 8
PAD = 12
MAX_SIDE = 96


def save_png(frame: tuple[int, int, bytes], path: Path, rotate: int = 0) -> None:
    """MAME's screen bitmap is 32-bit xRGB, little-endian. rotate (degrees,
    counter-clockwise) stands a rotated monitor upright."""
    from PIL import Image
    w, h, data = frame
    img = Image.frombytes("RGB", (w, h), data, "raw", "BGRX")
    if rotate:
        img = img.rotate(rotate, expand=True)
    img.save(path, optimize=True)


def zoom_diff(before: Path, after: Path, out: Path):
    """Baseline crop left, faulted crop right, scaled 8x around the changed
    pixels. Returns the changed box, or None when the images are identical."""
    from PIL import Image, ImageChops
    a = Image.open(before).convert("RGB")
    b = Image.open(after).convert("RGB")
    box = ImageChops.difference(a, b).getbbox()
    if box is None:
        return None
    x0, y0, x1, y1 = box
    x1, y1 = min(x1, x0 + MAX_SIDE), min(y1, y0 + MAX_SIDE)
    crop = (max(0, x0 - PAD), max(0, y0 - PAD), min(a.width, x1 + PAD), min(a.height, y1 + PAD))
    w, h = crop[2] - crop[0], crop[3] - crop[1]
    canvas = Image.new("RGB", (w * SCALE * 2 + SCALE, h * SCALE), (255, 255, 255))
    canvas.paste(a.crop(crop).resize((w * SCALE, h * SCALE), Image.NEAREST), (0, 0))
    canvas.paste(b.crop(crop).resize((w * SCALE, h * SCALE), Image.NEAREST), (w * SCALE + SCALE, 0))
    canvas.save(out, optimize=True)
    return box
