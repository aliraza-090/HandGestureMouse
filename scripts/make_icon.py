"""Generate the application icon (``resources/icons/app.ico``).

Run once during development / bundling:

    python scripts/make_icon.py

Requires Pillow (already a project dependency).  The icon is committed to the
repository, so this script only needs to run when the design changes.
"""

import os

from PIL import Image, ImageDraw

SIZE = 256
BG = (23, 27, 36, 255)
BLUE = (79, 140, 255, 255)
BLUE_DARK = (52, 96, 190, 255)
WHITE = (240, 244, 252, 255)


def draw_icon() -> Image.Image:
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([8, 8, SIZE - 8, SIZE - 8], radius=54, fill=BG, outline=BLUE_DARK, width=4)
    d.ellipse([78, 58, 178, 158], fill=BLUE)
    # fingers
    for i, x in enumerate((96, 120, 144, 168)):
        d.rounded_rectangle([x, 40 + i * 4, x + 16, 118], radius=8, fill=WHITE)
    # thumb
    d.rounded_rectangle([70, 108, 104, 128], radius=10, fill=WHITE)
    # palm
    d.rounded_rectangle([92, 112, 190, 196], radius=26, fill=WHITE)
    # cursor hint
    d.polygon([(150, 150), (150, 210), (168, 192), (182, 218), (196, 210), (182, 186), (204, 186)], fill=BLUE)
    return img


def main() -> None:
    here = os.path.dirname(os.path.abspath(__file__))
    out_dir = os.path.join(here, "..", "src", "handgesturemouse", "resources", "icons")
    os.makedirs(out_dir, exist_ok=True)
    img = draw_icon()
    ico_path = os.path.join(out_dir, "app.ico")
    png_path = os.path.join(out_dir, "app.png")
    img.save(png_path, format="PNG")
    img.save(ico_path, format="ICO", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print(f"Wrote {ico_path}")
    print(f"Wrote {png_path}")


if __name__ == "__main__":
    main()