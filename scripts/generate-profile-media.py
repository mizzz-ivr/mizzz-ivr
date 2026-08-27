from __future__ import annotations

import io
import math
import random
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
PINK = (244, 119, 206)
WHITE = (244, 241, 255)
MUTED = (179, 174, 204)
GRID = (100, 76, 145)

random.seed(42)


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
            glow = max(0.0, 1.0 - math.dist((diagonal, vertical), (0.78, 0.28)) / 0.74)
            pixels[x, y] = (
                min(255, int(BG_TOP[0] * (1 - vertical) + BG_BOTTOM[0] * vertical + 20 * glow)),
                min(255, int(BG_TOP[1] * (1 - vertical) + BG_BOTTOM[1] * vertical + 8 * glow)),
                min(255, int(BG_TOP[2] * (1 - vertical) + BG_BOTTOM[2] * vertical + 32 * glow)),
            )
    return image


def load_current_avatar(size: int) -> Image.Image:
    request = urllib.request.Request(AVATAR_URL, headers={"User-Agent": "mizzz-profile-media/2.0"})
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


def add_stars(image: Image.Image, count: int, max_y_ratio: float = 1.0) -> None:
    layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    for _ in range(count):
        x = random.randrange(image.width)
        y = random.randrange(max(1, int(image.height * max_y_ratio)))
        radius = random.choice([1, 1, 1, 2, 2])
        color = random.choice([WHITE, CYAN, PURPLE, LAVENDER])
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=(*color, random.randrange(55, 190)))
    image.alpha_composite(layer)


def add_halftone(image: Image.Image, origin: tuple[int, int], width: int, height: int, spacing: int = 22) -> None:
    layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    ox, oy = origin
    for row, y in enumerate(range(oy, oy + height, spacing)):
        for col, x in enumerate(range(ox, ox + width, spacing)):
            distance = math.dist((x, y), (ox + width * 0.58, oy + height * 0.48))
            strength = max(0.0, 1.0 - distance / max(1.0, math.dist((0, 0), (width * 0.7, height * 0.7))))
            radius = 1 + int(3 * strength)
            color = PURPLE if (row + col) % 3 else CYAN
            draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=(*color, 22 + int(58 * strength)))
    image.alpha_composite(layer)


def rounded_panel(draw: ImageDraw.ImageDraw, box, radius: int = 22) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=(13, 15, 32, 218), outline=(147, 112, 222, 120), width=2)


def make_hero() -> None:
    base = gradient(W, H).convert("RGBA")
    add_stars(base, 210, 0.9)
    add_halftone(base, (820, 40), 720, 520, 22)
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    for x in range(0, W, 80):
        draw.line((x, 0, x, H), fill=(*GRID, 18), width=1)
    for y in range(0, H, 80):
        draw.line((0, y, W, y), fill=(*GRID, 16), width=1)

    draw.text((88, 78), "mizzz / ivuru", font=font(82, True), fill=WHITE)
    draw.text((94, 177), "PURPLE SIGNAL // BUILD · SHIP · OPERATE", font=font(22, True), fill=CYAN)
    draw.text((94, 221), "Product-minded Full Stack Developer", font=font(24), fill=MUTED)
    draw.text((94, 260), "Web  •  Discord  •  Realtime AI  •  Developer Experience", font=font(16), fill=LAVENDER)
    draw.line((92, 304, 706, 304), fill=(*PURPLE, 220), width=3)

    cards = [
        ((96, 354, 345, 450), "RooMate Voice", "REALTIME AI / VOICE"),
        ((365, 354, 614, 450), "QuizVerse", "WEB PRODUCT"),
        ((96, 472, 345, 568), "Site Sentry Go", "OPS / GO"),
        ((365, 472, 614, 568), "Tech Writing", "NOTES / OUTPUT"),
    ]
    for box, title, label in cards:
        rounded_panel(draw, box)
        draw.text((box[0] + 18, box[1] + 18), title, font=font(18, True), fill=WHITE)
        draw.text((box[0] + 18, box[1] + 58), label, font=font(11, True), fill=PURPLE)
        draw.ellipse((box[2] - 33, box[1] + 19, box[2] - 19, box[1] + 33), fill=(*CYAN, 210))

    rounded_panel(draw, (655, 354, 900, 568))
    draw.text((682, 380), "NOW PLAYING", font=font(13, True), fill=CYAN)
    draw.text((682, 416), "React / TypeScript", font=font(16, True), fill=WHITE)
    draw.text((682, 451), "OpenAI Realtime", font=font(16, True), fill=WHITE)
    draw.text((682, 486), "Discord / Docker", font=font(16, True), fill=WHITE)
    draw.text((682, 533), "PUBLIC WORK ONLY", font=font(11, True), fill=LAVENDER)

    avatar = load_current_avatar(540)
    mask = Image.new("L", (540, 540), 0)
    ImageDraw.Draw(mask).ellipse((12, 12, 528, 528), fill=255)
    portrait = Image.new("RGBA", (540, 540), (0, 0, 0, 0))
    portrait.paste(avatar.convert("RGBA"), (0, 0), mask)
    glow = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse((1010, 70, 1570, 630), fill=(*PURPLE, 58))
    layer.alpha_composite(glow.filter(ImageFilter.GaussianBlur(40)))
    layer.alpha_composite(portrait, (1020, 54))
    for radius, color, start, span in [(276, PURPLE, 200, 270), (257, CYAN, 20, 76), (241, PINK, 118, 54)]:
        draw.arc((1290-radius, 324-radius, 1290+radius, 324+radius), start=start, end=start+span, fill=(*color, 220), width=6)
    draw.text((1090, 555), "CURRENT AVATAR", font=font(13, True), fill=LAVENDER)

    base.alpha_composite(layer)
    base.convert("RGB").save(ASSETS / "profile-hero.png", optimize=True, quality=95)


def make_motion() -> None:
    frames = []
    for frame_index in range(28):
        progress = frame_index / 28.0
        image = Image.new("RGBA", (1200, 180), (7, 8, 19, 255))
        draw = ImageDraw.Draw(image)
        for x in range(-100, 1300, 44):
            shifted_x = x + int((progress * 44) % 44)
            draw.line((shifted_x, 0, shifted_x, 180), fill=(*GRID, 28), width=1)
        for y in range(14, 180, 28):
            draw.line((0, y, 1200, y), fill=(*GRID, 22), width=1)
        streak = Image.new("RGBA", (1200, 180), (0, 0, 0, 0))
        streak_draw = ImageDraw.Draw(streak)
        for index, color in enumerate((CYAN, PURPLE, PINK)):
            x = int(((progress + index * 0.31) % 1.25) * 1620) - 210
            y = 118 + index * 13
            streak_draw.line((x - 190, y, x + 110, y), fill=(*color, 205), width=3)
        image.alpha_composite(streak.filter(ImageFilter.GaussianBlur(7)))
        start = int(progress * 360)
        draw.arc((982, 42, 1078, 138), start=start, end=start + 225, fill=(*CYAN, 230), width=4)
        draw.arc((994, 54, 1066, 126), start=-start, end=-start + 165, fill=(*PINK, 205), width=3)
        draw.text((58, 43), "LIVE BUILD SIGNAL", font=font(18, True), fill=CYAN)
        draw.text((58, 78), "PUBLIC WORK // REALTIME AI // WEB // OPS", font=font(21, True), fill=WHITE)
        draw.text((58, 116), "building small, polishing fast, operating safely", font=font(14), fill=MUTED)
        frames.append(image.convert("P", palette=Image.Palette.ADAPTIVE))
    frames[0].save(ASSETS / "profile-motion.gif", save_all=True, append_images=frames[1:], duration=70, loop=0, optimize=True, disposal=2)


if __name__ == "__main__":
    make_hero()
    make_motion()
    print("Generated profile-hero.png and profile-motion.gif")
