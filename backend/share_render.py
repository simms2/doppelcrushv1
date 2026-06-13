"""Server-side share-card / OG image generator.

Used by `/api/og/twin/{user_id}.png` so that crawlers (iMessage, Slack,
WhatsApp, Facebook, Twitter, Discord, …) get a rich preview image when a
user shares their `/your-twin/:user_id` link.

Pure Pillow — no headless browser required.
"""
from __future__ import annotations

import io
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFilter, ImageFont

# 1.91 : 1 — standard OG / Twitter card / iMessage rich-link ratio
OG_W = 1200
OG_H = 630

# Brand palette (same hues as the frontend CTA)
HOT = (255, 45, 138)   # #ff2d8a
ORANGE = (255, 106, 61)  # #ff6a3d
YELLOW = (255, 216, 77)  # #ffd84d
INK = (15, 23, 42)       # #0f172a
WHITE = (255, 255, 255)

_FONT_REGULAR = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
_FONT_FALLBACK = "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf"


def _font(size: int) -> ImageFont.FreeTypeFont:
    for p in (_FONT_REGULAR, _FONT_FALLBACK):
        try:
            return ImageFont.truetype(p, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def _hex(c: tuple[int, int, int], a: int = 255) -> tuple[int, int, int, int]:
    return (c[0], c[1], c[2], a)


def _gradient_bg(w: int, h: int) -> Image.Image:
    """Diagonal gradient yellow → hot pink → orange (matches the brand)."""
    base = Image.new("RGB", (w, h), HOT)
    top = Image.new("RGB", (w, h), YELLOW)
    bot = Image.new("RGB", (w, h), ORANGE)

    # Build a linear alpha mask top-left → bottom-right
    mask = Image.linear_gradient("L").rotate(-45, expand=True)
    mask = mask.resize((w, h))

    # Blend top onto base by mask (lighter near upper left)
    base = Image.composite(top, base, mask)
    # Blend bottom onto base by inverse-ish mask
    inv = mask.point(lambda v: 255 - v)
    base = Image.composite(bot, base, inv.point(lambda v: max(0, v - 90)))
    return base


def _rounded_rect(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    radius: int,
    fill,
    outline=None,
    width: int = 0,
) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def _paste_circle(canvas: Image.Image, img: Image.Image, center: tuple[int, int], diameter: int) -> None:
    """Paste `img` cropped to a circle of `diameter` centred at `center`."""
    img = img.convert("RGB").resize((diameter, diameter))
    mask = Image.new("L", (diameter, diameter), 0)
    md = ImageDraw.Draw(mask)
    md.ellipse((0, 0, diameter - 1, diameter - 1), fill=255)
    x = center[0] - diameter // 2
    y = center[1] - diameter // 2
    # white ring behind
    ring = Image.new("RGBA", (diameter + 24, diameter + 24), (255, 255, 255, 0))
    rd = ImageDraw.Draw(ring)
    rd.ellipse((0, 0, diameter + 23, diameter + 23), fill=(255, 255, 255, 235))
    canvas.paste(ring, (x - 12, y - 12), ring)
    canvas.paste(img, (x, y), mask)


def _stroked_text(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    font: ImageFont.FreeTypeFont,
    fill,
    stroke_width: int = 6,
    stroke_fill=INK,
    anchor: str = "lt",
) -> None:
    draw.text(
        xy,
        text,
        font=font,
        fill=fill,
        stroke_width=stroke_width,
        stroke_fill=stroke_fill,
        anchor=anchor,
    )


def _draw_heart(
    canvas: Image.Image, center: tuple[int, int], size: int, color=HOT
) -> None:
    layer = Image.new("RGBA", (size * 2, size * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    s = size
    # two circles + triangle
    d.ellipse((0, 0, s, s), fill=_hex(color))
    d.ellipse((s, 0, s * 2, s), fill=_hex(color))
    d.polygon(
        [(0, s // 2), (s * 2, s // 2), (s, s * 2)],
        fill=_hex(color),
    )
    # outline
    out = layer.filter(ImageFilter.FIND_EDGES)
    canvas.paste(layer, (center[0] - size, center[1] - size), layer)
    canvas.paste(out, (center[0] - size, center[1] - size), out)


def render_twin_og(
    *,
    name: str,
    photo_bytes: Optional[bytes] = None,
    referral_code: str = "",
    mode: str = "doppel",
) -> bytes:
    """Return PNG bytes for the twin's Open Graph card."""
    canvas = _gradient_bg(OG_W, OG_H).convert("RGBA")
    draw = ImageDraw.Draw(canvas)

    # Inner card panel
    pad = 36
    _rounded_rect(
        draw,
        (pad, pad, OG_W - pad, OG_H - pad),
        radius=48,
        fill=None,
        outline=INK,
        width=10,
    )

    # halftone dots
    for y in range(pad + 20, OG_H - pad, 22):
        for x in range(pad + 20, OG_W - pad, 22):
            draw.ellipse((x, y, x + 3, y + 3), fill=(15, 23, 42, 25))

    # Selfie circle on the left
    selfie_diam = 380
    selfie_center = (260, OG_H // 2 + 10)
    if photo_bytes:
        try:
            img = Image.open(io.BytesIO(photo_bytes))
            _paste_circle(canvas, img, selfie_center, selfie_diam)
        except Exception:
            # silent fallback to placeholder ring
            d2 = ImageDraw.Draw(canvas)
            d2.ellipse(
                (
                    selfie_center[0] - selfie_diam // 2,
                    selfie_center[1] - selfie_diam // 2,
                    selfie_center[0] + selfie_diam // 2,
                    selfie_center[1] + selfie_diam // 2,
                ),
                fill=WHITE,
                outline=INK,
                width=8,
            )
    else:
        d2 = ImageDraw.Draw(canvas)
        d2.ellipse(
            (
                selfie_center[0] - selfie_diam // 2,
                selfie_center[1] - selfie_diam // 2,
                selfie_center[0] + selfie_diam // 2,
                selfie_center[1] + selfie_diam // 2,
            ),
            fill=WHITE,
            outline=INK,
            width=8,
        )

    # Right-side text block
    text_x = 540
    draw = ImageDraw.Draw(canvas)

    # Top pill
    f_tag = _font(24)
    tag_text = f"+ DOPPELCRUSH +  {mode.upper()} MODE"
    bbox = draw.textbbox((0, 0), tag_text, font=f_tag)
    pill_w = bbox[2] - bbox[0] + 40
    pill_h = 50
    _rounded_rect(
        draw,
        (text_x, 90, text_x + pill_w, 90 + pill_h),
        radius=pill_h // 2,
        fill=INK,
    )
    draw.text(
        (text_x + 20, 90 + pill_h // 2 - 14),
        tag_text,
        font=f_tag,
        fill=YELLOW,
    )

    # Headline lines
    f_big = _font(82)
    safe_name = (name or "your twin")[:14]
    _stroked_text(
        draw, (text_x, 170), "MEET", f_big, fill=WHITE, stroke_width=6
    )
    _stroked_text(
        draw, (text_x, 260), safe_name.upper(), f_big, fill=YELLOW, stroke_width=6
    )

    # Sub
    f_sub = _font(34)
    _stroked_text(
        draw,
        (text_x, 370),
        "Find your twin or your chaos.",
        f_sub,
        fill=INK,
        stroke_width=0,
        stroke_fill=INK,
    )

    # Code badge
    if referral_code:
        f_code = _font(36)
        f_label = _font(22)
        code_text = referral_code.upper()
        bbox = draw.textbbox((0, 0), code_text, font=f_code)
        cw = bbox[2] - bbox[0] + 56
        ch = 78
        x0 = text_x
        y0 = OG_H - 90 - ch
        _rounded_rect(draw, (x0, y0, x0 + cw, y0 + ch), radius=ch // 2, fill=WHITE, outline=INK, width=5)
        draw.text((x0 + 28, y0 + 12), "CODE", font=f_label, fill=(120, 130, 145))
        draw.text((x0 + 28, y0 + 38), code_text, font=f_code, fill=HOT)

        # URL pill next to it
        f_url = _font(22)
        url_text = "doppelcrush · join.me"
        bw = draw.textbbox((0, 0), url_text, font=f_url)
        uw = bw[2] - bw[0] + 48
        ux = x0 + cw + 18
        _rounded_rect(draw, (ux, y0, ux + uw, y0 + ch), radius=ch // 2, fill=INK)
        draw.text((ux + 24, y0 + 26), url_text, font=f_url, fill=WHITE)

    # Stickers (decoration)
    _draw_heart(canvas, (OG_W - 130, 130), 50, HOT)
    _draw_heart(canvas, (110, 110), 38, YELLOW)
    _draw_heart(canvas, (OG_W - 90, OG_H - 130), 42, ORANGE)

    out = io.BytesIO()
    canvas.convert("RGB").save(out, format="PNG", optimize=True)
    return out.getvalue()


def render_twin_og_fallback(*, name: str, referral_code: str = "", mode: str = "doppel") -> bytes:
    """No-photo fallback (used when the user's photo can't be fetched)."""
    return render_twin_og(name=name, photo_bytes=None, referral_code=referral_code, mode=mode)


# Optional: where to drop a local placeholder if needed
PLACEHOLDER_PATH = Path(__file__).parent / "assets" / "twin_placeholder.png"
