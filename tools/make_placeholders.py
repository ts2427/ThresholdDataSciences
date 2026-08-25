#!/usr/bin/env python3
"""Generate placeholder PNG assets (favicons, og-image) from the step mark.

One-off helper: rerun only if you want to regenerate the placeholders.
The real assets simply replace the files in static/img/.
"""

from pathlib import Path

from PIL import Image, ImageDraw

IMG = Path(__file__).parent.parent / "static" / "img"
INK = (15, 35, 56)        # #0F2338
SIGNAL = (199, 98, 27)    # #C7621B
PAPER = (255, 255, 255)
FIELD = (242, 244, 246)   # #F2F4F6


def step(draw, x0, y_low, x_step, y_high, x1, width):
    draw.line([(x0, y_low), (x_step, y_low)], fill=INK, width=width)
    draw.line([(x_step, y_low), (x_step, y_high)], fill=SIGNAL, width=width)
    draw.line([(x_step, y_high), (x1, y_high)], fill=INK, width=width)


def square(size, name, pad_ratio=0.16, stroke_ratio=0.09):
    img = Image.new("RGB", (size, size), PAPER)
    d = ImageDraw.Draw(img)
    pad = int(size * pad_ratio)
    w = max(2, int(size * stroke_ratio))
    step(d, pad, int(size * 0.68), int(size * 0.53), int(size * 0.32),
         size - pad, w)
    img.save(IMG / name)
    print("wrote", name)


def og():
    W, H = 1200, 630
    img = Image.new("RGB", (W, H), FIELD)
    d = ImageDraw.Draw(img)
    step(d, 140, 420, 660, 210, 1060, 10)
    img.save(IMG / "og-image.png")
    print("wrote og-image.png")


if __name__ == "__main__":
    square(32, "favicon-32.png")
    square(180, "apple-touch-icon.png", stroke_ratio=0.075)
    og()
