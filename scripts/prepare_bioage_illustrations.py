"""
scripts/prepare_bioage_illustrations.py -- One-shot asset prep for the
Strength BioAge detail screen (views/insights.py, ?bioage=strength).

The source PNGs in background_templates/ (Strength_button.png, Upperbody.png,
core.png, lowerbody.png, muscle_imbalances.png) are pre-rendered card graphics
with a label, chevron and rounded-rect border baked into the pixels -- correct
for the small BioAge category-grid cards (_bioage_card_html), which crop and
gradient-fade them just enough to hide that chrome. The taller Strength detail
cards (hero, body-region rows, muscle-balance summary) crop differently and
end up exposing that baked-in text/border instead of hiding it.

This script crops each source once into an illustration-only PNG (no text, no
chevron, no border stroke) written to background_templates/derived/, which
views/insights.py reads directly. Crop boxes were tuned by hand against these
specific source images -- re-run and re-tune by eye if the source PNGs change.

Usage:
    python scripts/prepare_bioage_illustrations.py
"""

from pathlib import Path

from PIL import Image

_SRC_DIR = Path(__file__).resolve().parent.parent / "background_templates"
_OUT_DIR = _SRC_DIR / "derived"

# name -> (source file, x0, x1, y0, y1) as fractions of source width/height.
# x0 is kept as far left as possible (just past each source's baked-in label
# text) rather than tight to the figure, so the derived crop keeps as much of
# the original's native resolution as the text/chevron/border allow — that
# resolution matters once these render full-bleed on a wide desktop card.
_CROPS: dict[str, tuple[str, float, float, float, float]] = {
    "strength_hero.png":   ("Strength_button.png",     0.30, 0.90, 0.27, 0.72),
    "upper_body.png":      ("Upperbody.png",           0.36, 0.90, 0.23, 0.75),
    "core.png":            ("core.png",                0.30, 0.90, 0.21, 0.77),
    "lower_body.png":      ("lowerbody.png",            0.36, 0.85, 0.21, 0.79),
    "muscle_balance.png":  ("muscle_imbalances.png",    0.44, 0.93, 0.17, 0.87),
}


def main() -> None:
    _OUT_DIR.mkdir(exist_ok=True)
    for out_name, (src_name, x0, x1, y0, y1) in _CROPS.items():
        src_path = _SRC_DIR / src_name
        im = Image.open(src_path)
        w, h = im.size
        box = (int(x0 * w), int(y0 * h), int(x1 * w), int(y1 * h))
        cropped = im.crop(box)
        out_path = _OUT_DIR / out_name
        cropped.save(out_path)
        print(f"{src_name} {box} -> {out_name} {cropped.size}")


if __name__ == "__main__":
    main()
