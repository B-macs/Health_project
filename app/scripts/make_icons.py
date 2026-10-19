"""Draws the app icon (rebuild Phase 3): a dark square, a light ring with a gap, one dot.
Run from the repo root: venv/Scripts/python.exe app/scripts/make_icons.py
Neutral on purpose: the design is not chosen yet, and the icon must suit all three."""
from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parents[1] / "public"
BG = (19, 21, 23)
RING = (242, 238, 230)
DOT = (141, 176, 255)
BIG = 1024


def draw() -> Image.Image:
    img = Image.new("RGB", (BIG, BIG), BG)
    d = ImageDraw.Draw(img)
    pad, width = 250, 70
    box = (pad, pad, BIG - pad, BIG - pad)
    d.arc(box, start=-60, end=230, fill=RING, width=width)
    r = 46
    cx, cy = BIG // 2, BIG // 2
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=DOT)
    return img


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    big = draw()
    for name, size in (("icon-512.png", 512), ("icon-192.png", 192), ("apple-touch-icon.png", 180)):
        big.resize((size, size), Image.LANCZOS).save(OUT / name, optimize=True)
        print("wrote", name)


if __name__ == "__main__":
    main()
