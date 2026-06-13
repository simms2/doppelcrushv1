"""Lightweight selfie moderation pipeline.

This is a defense-in-depth heuristic that runs server-side after upload.
It is intentionally simple (Pillow only — no large ML weights) so it ships
without a 3rd-party dependency. For production, swap this stub for a real
NSFW classifier (e.g. AWS Rekognition, Sightengine, or NSFW.js).

Returns: {"safe": bool, "score": float (0..1, higher = more suspicious),
          "reason": str | None}
"""
from __future__ import annotations

import io
import logging
from typing import Optional

logger = logging.getLogger("doppelcrush.moderation")

try:
    from PIL import Image
except Exception:  # pragma: no cover
    Image = None  # type: ignore


def _is_skin_pixel(r: int, g: int, b: int) -> bool:
    """Common heuristic: RGB skin-tone range used in classical skin detectors."""
    if r <= 95 or g <= 40 or b <= 20:
        return False
    if max(r, g, b) - min(r, g, b) <= 15:
        return False
    if abs(r - g) <= 15:
        return False
    if r <= g or r <= b:
        return False
    return True


def check_selfie(data: bytes) -> dict:
    """Quick safety check on uploaded selfie bytes."""
    if Image is None:
        return {"safe": True, "score": 0.0, "reason": None}
    try:
        img = Image.open(io.BytesIO(data))
        img = img.convert("RGB")
        # downscale for speed
        img.thumbnail((192, 192))
        pixels = list(img.getdata())
    except Exception as e:  # noqa: BLE001
        logger.warning("Could not decode image for moderation: %s", e)
        return {"safe": False, "score": 1.0, "reason": "invalid_image"}

    if not pixels:
        return {"safe": False, "score": 1.0, "reason": "empty_image"}

    skin = sum(1 for (r, g, b) in pixels if _is_skin_pixel(r, g, b))
    ratio = skin / len(pixels)
    # In a normal selfie, the face occupies maybe 10–35% of the frame.
    # Above ~55% skin pixels suggests a revealing photo with little context.
    score = max(0.0, min(1.0, (ratio - 0.35) / 0.4))
    safe = ratio < 0.55
    reason: Optional[str] = None if safe else "too_much_skin"
    return {"safe": safe, "score": round(score, 3), "ratio": round(ratio, 3), "reason": reason}
