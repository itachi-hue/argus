"""Baseline screenshot storage and visual comparison.

Stores named screenshot baselines in memory. Compares new screenshots
against baselines using pixel-level diff via Pillow.
"""

import base64
import io
import threading

from PIL import Image, ImageChops


class BaselineStore:
    """In-memory store for named baseline screenshots."""

    def __init__(self, max_baselines: int = 50):
        self._baselines: dict[str, str] = {}  # name -> base64 JPEG
        self._max = max_baselines
        self._lock = threading.Lock()

    def save(self, name: str, data: str) -> None:
        """Save a baseline screenshot by name."""
        with self._lock:
            self._baselines[name] = data
            # Evict oldest if over limit
            if len(self._baselines) > self._max:
                oldest = next(iter(self._baselines))
                del self._baselines[oldest]

    def get(self, name: str) -> str | None:
        """Get a baseline screenshot by name."""
        with self._lock:
            return self._baselines.get(name)

    def list_names(self) -> list[str]:
        """List all baseline names."""
        with self._lock:
            return list(self._baselines.keys())

    def delete(self, name: str) -> bool:
        """Delete a baseline by name."""
        with self._lock:
            if name in self._baselines:
                del self._baselines[name]
                return True
            return False

    def clear(self) -> None:
        """Clear all baselines."""
        with self._lock:
            self._baselines.clear()


def _b64_to_image(data: str) -> Image.Image:
    """Decode base64 JPEG to PIL Image."""
    raw = base64.b64decode(data)
    return Image.open(io.BytesIO(raw)).convert("RGB")


def _image_to_b64(img: Image.Image, quality: int = 50) -> str:
    """Encode PIL Image to base64 JPEG."""
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def compare_screenshots(baseline_b64: str, current_b64: str) -> dict:
    """Compare two screenshots and return diff metrics.

    Returns:
        dict with:
            changed_pixels: number of pixels that differ
            total_pixels: total pixel count
            change_percent: percentage of changed pixels
            diff_image: base64-encoded diff image (red highlights differences)
            match: True if images are identical (or <0.1% change)
    """
    baseline_img = _b64_to_image(baseline_b64)
    current_img = _b64_to_image(current_b64)

    # Resize current to match baseline if dimensions differ
    if baseline_img.size != current_img.size:
        current_img = current_img.resize(baseline_img.size, Image.LANCZOS)

    # Compute difference
    diff = ImageChops.difference(baseline_img, current_img)

    # Count changed pixels (threshold: any channel > 20 = changed)
    pixels = list(diff.getdata())
    total = len(pixels)
    changed = sum(1 for r, g, b in pixels if max(r, g, b) > 20)
    change_pct = round((changed / total) * 100, 2) if total > 0 else 0.0

    # Build visual diff image: red overlay on changed areas
    diff_visual = current_img.copy()
    diff_data = list(diff_visual.getdata())
    for i, (r, g, b) in enumerate(pixels):
        if max(r, g, b) > 20:
            # Tint changed pixels red
            orig = diff_data[i]
            diff_data[i] = (min(255, orig[0] + 150), max(0, orig[1] - 50), max(0, orig[2] - 50))
    diff_visual.putdata(diff_data)

    return {
        "changed_pixels": changed,
        "total_pixels": total,
        "change_percent": change_pct,
        "diff_image": _image_to_b64(diff_visual),
        "match": change_pct < 0.1,
    }
