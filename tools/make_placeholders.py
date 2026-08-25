#!/usr/bin/env python3
"""Generate the PNG brand assets (favicons, og-image) from the step mark.

The step-function mark IS the logo. Rerun after changing the mark's geometry.
og-image wordmark needs a TTF of Source Serif 4; the script converts the
shipped woff2 on the fly (requires fonttools + brotli + pillow).
"""

import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).parent.parent
IMG = ROOT / "static" / "img"
INK = (15, 35, 56)        # #0F2338
SIGNAL = (199, 98, 27)    # #C7621B
PAPER = (255, 255, 255)


def step(draw, x0, y_low, x_step, y_high, x1, width, neutral):
    draw.line([(x0, y_low), (x_step, y_low)], fill=neutral, width=width)
    draw.line([(x_step, y_low - width // 2), (x_step, y_high + width // 2)],
              fill=SIGNAL, width=width)
    draw.line([(x_step, y_high), (x1, y_high)], fill=neutral, width=width)


def square(size, name, stroke_ratio):
    """Mark on white, matching favicon.svg geometry (4/45/32/19/60 on 64)."""
    s = size / 64.0
    img = Image.new("RGB", (size, size), PAPER)
    d = ImageDraw.Draw(img)
    w = max(2, round(64 * stroke_ratio * s / 64))
    step(d, round(4 * s), round(45 * s), round(32 * s), round(19 * s),
         round(60 * s), max(2, round(7 * s)), INK)
    img.save(IMG / name)
    print("wrote", name)


def serif_font(px):
    from fontTools.ttLib import TTFont
    woff2 = ROOT / "static" / "fonts" / "source-serif-4-600.woff2"
    tmp = Path(tempfile.gettempdir()) / "tds-source-serif-4-600.ttf"
    if not tmp.exists():
        f = TTFont(woff2)
        f.flavor = None
        f.save(tmp)
    return ImageFont.truetype(str(tmp), px)


def og():
    """1200x630: Ink background, mark and wordmark centered, nothing else."""
    W, H = 1200, 630
    img = Image.new("RGB", (W, H), INK)
    d = ImageDraw.Draw(img)

    # Mark, centered horizontally, upper third.
    mw, mh, stroke = 340, 150, 14
    x0 = (W - mw) // 2
    y_low, y_high = 235, 145
    step(d, x0, y_low, x0 + mw // 2, y_high, x0 + mw, stroke, PAPER)

    # Wordmark below in the display serif.
    font = serif_font(64)
    text = "Threshold Data Sciences"
    bbox = d.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    d.text(((W - tw) / 2 - bbox[0], 330), text, font=font, fill=PAPER)
    img.save(IMG / "og-image.png")
    print("wrote og-image.png")


if __name__ == "__main__":
    square(32, "favicon-32.png", 7 / 64)
    square(180, "apple-touch-icon.png", 7 / 64)
    og()
