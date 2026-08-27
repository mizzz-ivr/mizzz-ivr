from __future__ import annotations

import io
import math
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
ASSETS.mkdir(parents=True, exist_ok=True)

W, H = 1600, 640
AVATAR_URL = "https://avatars.githubusercontent.com/u/86910433?v=4"

BG_TOP = (7, 7, 18)
BG_BOTTOM = (28, 14, 48)
PURPLE = (158, 105, 255)
LAVENDER = (204, 184, 255)
CYAN = (92, 226, 255)
WHITE = (244, 241, 255)
MUTED = (179, 174, 204)
GRID = (100, 76, 145)


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size=size)
    return ImageFont.load_default()


def gradient(width: int, height: int) -> Image.Image:
    image = Image.new("RGB", (width, height))
    pixels = image.load()
    for y in range(height):
        vertical = y / max(1, height - 1)
        for x in range(width):
            diagonal = x / max(1, width - 1)
            glow = max(0.0, 1.0 - math.dist((diagonal, vertical), (0.79, 0.30)) / 0.78)
            pixels[x, y] = (
                min(255, int(BG_TOP[0] * (1 - vertical) + BG_BOTTOM[0] * vertical + 20 * glow)),
                min(255, int(BG_TOP[1] * (1 - vertical) + BG_BOTTOM[1] * vertical + 8 * glow)),
                min(255, int(BG_TOP[2] * (1 - vertical) + BG_BOTTOM[2] * vertical + 34 * glow)),
            )
    return image


def load_current_avatar(size: int) -> Image.Image:
    request = urllib.request.Request(AVATAR_URL, headers={"User-Agent": "mizzz-profile-media/3.0"})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            avatar = Image.open(io.BytesIO(response.read())).convert("RGB")
    except Exception as exc:
        print(f"warning: could not fetch current GitHub avatar: {exc}")
        avatar = gradient(size, size)
        draw = ImageDraw.Draw(avatar)
        draw.ellipse((size * 0.22, size * 0.22, size * 0.78, size * 0.78), fill=(42, 25, 72))
        draw.text((size * 0.41, size * 0.39), "M", font=font(int(size * 0.18), True), fill=WHITE)
    return ImageOps.fit(avatar, (size, size), method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))


def draw_capability(draw: ImageDraw.ImageDraw, x: int, y: int, label: str) -> None:
    text_font = font(16, True)
    box = draw.textbbox((0, 0), label, font=text_font)
    width = box[2] - box[0] + 34
    draw.rounded_rectangle((x, y, x + width, y + 44), radius=18, fill=(15, 15, 34, 225), outline=(*PURPLE, 165), width=2)
    draw.text((x + 17, y + 11), label, font=text_font, fill=WHITE)


def make_hero() -> None:
    base = gradient(W, H).convert("RGBA")
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    for x in range(0, W, 80):
        draw.line((x, 0, x, H), fill=(*GRID, 17), width=1)
    for y in range(0, H, 80):
        draw.line((0, y, W, y), fill=(*GRID, 15), width=1)

    draw.text((92, 92), "mizzz / ivuru", font=font(84, True), fill=WHITE)
    draw.text((98, 196), "PURPLE SIGNAL // PRODUCT ENGINEERING", font=font(22, True), fill=CYAN)
    draw.text((98, 246), "Build the product. Connect the system. Operate it safely.", font=font(25), fill=LAVENDER)
    draw.text((98, 298), "PUBLIC WORK  •  ENGINEERING EVIDENCE  •  CONTINUOUS DELIVERY", font=font(15, True), fill=MUTED)
    draw.line((96, 342, 848, 342), fill=(*PURPLE, 220), width=3)

    capabilities = [
        "PRODUCT ENGINEERING",
        "REALTIME AI",
        "PLATFORM / TOOLING",
        "OPS / RELIABILITY",
    ]
    x, y = 98, 390
    for index, label in enumerate(capabilities):
        draw_capability(draw, x, y + index * 54, label)

    avatar_size = 520
    avatar = load_current_avatar(avatar_size)
    mask = Image.new("L", (avatar_size, avatar_size), 0)
    ImageDraw.Draw(mask).ellipse((12, 12, avatar_size - 12, avatar_size - 12), fill=255)
    portrait = Image.new("RGBA", (avatar_size, avatar_size), (0, 0, 0, 0))
    portrait.paste(avatar.convert("RGBA"), (0, 0), mask)

    glow = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse((1010, 65, 1570, 625), fill=(*PURPLE, 62))
    layer.alpha_composite(glow.filter(ImageFilter.GaussianBlur(42)))
    layer.alpha_composite(portrait, (1020, 60))

    center_x, center_y = 1280, 320
    draw.arc((center_x - 272, center_y - 272, center_x + 272, center_y + 272), start=198, end=468, fill=(*PURPLE, 225), width=6)
    draw.arc((center_x - 252, center_y - 252, center_x + 252, center_y + 252), start=18, end=96, fill=(*CYAN, 225), width=5)
    draw.text((1090, 562), "CURRENT GITHUB IDENTITY", font=font(13, True), fill=LAVENDER)

    base.alpha_composite(layer)
    base.convert("RGB").save(ASSETS / "profile-hero.png", optimize=True, quality=95)


if __name__ == "__main__":
    make_hero()
    print("Generated profile-hero.png")
