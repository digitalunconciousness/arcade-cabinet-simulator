#!/usr/bin/env python3
# license:CC0-1.0
"""Side-by-side zoom of where a faulted frame differs from the baseline.

A one-tile change is invisible in a full 240x256 frame, so for every run with
before and after images this writes <after>_zoom.png: the baseline crop on
the left, the faulted crop on the right, both scaled up 8x, around the
bounding box of the changed pixels.

  python tools/audit/zoom.py evidence/stage0
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

SCALE = 8
PAD = 12
MAX_SIDE = 96  # crop at most this many source pixels per side, so big changes stay readable


def zoom_diff(before: Path, after: Path, out: Path) -> tuple[int, int, int, int] | None:
    from PIL import Image, ImageChops
    a = Image.open(before).convert("RGB")
    b = Image.open(after).convert("RGB")
    bbox = ImageChops.difference(a, b).getbbox()
    if bbox is None:
        return None
    x0, y0, x1, y1 = bbox
    x1, y1 = min(x1, x0 + MAX_SIDE), min(y1, y0 + MAX_SIDE)
    box = (max(0, x0 - PAD), max(0, y0 - PAD), min(a.width, x1 + PAD), min(a.height, y1 + PAD))
    w, h = box[2] - box[0], box[3] - box[1]
    canvas = Image.new("RGB", (w * SCALE * 2 + SCALE, h * SCALE), (255, 255, 255))
    canvas.paste(a.crop(box).resize((w * SCALE, h * SCALE), Image.NEAREST), (0, 0))
    canvas.paste(b.crop(box).resize((w * SCALE, h * SCALE), Image.NEAREST), (w * SCALE + SCALE, 0))
    canvas.save(out, optimize=True)
    return bbox


def add_zooms(evidence: Path) -> None:
    """Write zoom images for every result with images, and record them in results.json."""
    path = evidence / "results.json"
    results = json.loads(path.read_text())
    for r in results["results"]:
        imgs = r.get("images")
        if not imgs:
            continue
        zoom_rel = imgs["faulted"].replace(".png", "_zoom.png")
        bbox = zoom_diff(evidence / imgs["baseline"], evidence / imgs["faulted"], evidence / zoom_rel)
        if bbox is not None:
            imgs["zoom"] = zoom_rel
            imgs["changed_box"] = list(bbox)
    path.write_text(json.dumps(results, indent=1))


if __name__ == "__main__":
    add_zooms(Path(sys.argv[1]))
