"""Image optimization for screenshots — resize + recompress to reduce context size."""

import base64
import io
import logging

from PIL import Image

logger = logging.getLogger(__name__)

# Target max width in pixels — keeps screenshots readable but much smaller
MAX_WIDTH = 1280
# JPEG quality for re-encoded screenshots (low but still clear for UI debugging)
JPEG_QUALITY = 35


def optimize_screenshot(base64_data: str, max_width: int = MAX_WIDTH, quality: int = JPEG_QUALITY) -> str:
    """Resize and recompress a base64 JPEG screenshot.

    Returns optimized base64 string (no data-url prefix).
    Falls back to original data on any error.
    """
    try:
        raw = base64.b64decode(base64_data)
        img = Image.open(io.BytesIO(raw))

        # Resize if wider than max_width, preserving aspect ratio
        if img.width > max_width:
            ratio = max_width / img.width
            new_height = int(img.height * ratio)
            img = img.resize((max_width, new_height), Image.LANCZOS)

        # Re-encode as JPEG at low quality
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality, optimize=True)
        optimized = base64.b64encode(buf.getvalue()).decode("ascii")

        original_kb = len(base64_data) / 1024
        optimized_kb = len(optimized) / 1024
        logger.debug(
            "Screenshot optimized: %.1fKB → %.1fKB (%.0f%% reduction)",
            original_kb, optimized_kb, (1 - optimized_kb / original_kb) * 100
        )
        return optimized
    except Exception:
        logger.warning("Failed to optimize screenshot, using original", exc_info=True)
        return base64_data

