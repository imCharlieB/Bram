"""Draw the BRAM icon and logo. Needs Pillow, and a bold font for the logo."""
import math
import sys
from collections.abc import Callable
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

OUT = Path(__file__).parents[1] / "custom_components/bram/brand"
S, C = 1024, 512
NIGHT, PLUM, CYAN, VIOLET = (12, 14, 34), (34, 20, 74), (0, 225, 255), (168, 85, 255)
WHITE = Image.new("RGB", (S, S), (255, 255, 255))


def gradient(start: tuple, end: tuple) -> Image.Image:
    ramp = Image.linear_gradient("L").resize((S * 2, S * 2)).rotate(
        45, Image.Resampling.BICUBIC).crop((C, C, C + S, C + S))
    low, high = ramp.getextrema()
    ramp = ramp.point(lambda v: int((v - low) * 255 / (high - low)))
    return Image.composite(Image.new("RGB", (S, S), end), Image.new("RGB", (S, S), start), ramp)


def mask(draw: Callable) -> Image.Image:
    image = Image.new("L", (S, S), 0)
    draw(ImageDraw.Draw(image))
    return image


def dot(d: ImageDraw.ImageDraw, x: float, y: float, r: float) -> None:
    d.ellipse((x - r, y - r, x + r, y + r), fill=255)


def line(d: ImageDraw.ImageDraw, points: list, width: float) -> None:
    d.line(points, fill=255, width=int(width), joint="curve")
    for x, y in points:
        dot(d, x, y, width / 2)


def arc(d: ImageDraw.ImageDraw, y: float, r: float, width: int, start: float, end: float) -> None:
    d.arc((C - r, y - r, C + r, y + r), start, end, fill=255, width=width)
    for angle in map(math.radians, (start, end)):
        dot(d, C + (r - width / 2) * math.cos(angle), y + (r - width / 2) * math.sin(angle),
            width / 2)


def glow(image: Image.Image, shape: Image.Image, fill: Image.Image, blur: int,
         power: float) -> None:
    halo = shape.filter(ImageFilter.GaussianBlur(blur)).point(lambda v: int(v * power))
    image.paste(fill, (0, 0), ImageChops.multiply(halo, image.getchannel("A")))
    image.paste(fill, (0, 0), shape)


def ring(d: ImageDraw.ImageDraw) -> None:
    arc(d, 360, 205, 40, -60, 205)
    arc(d, 360, 205, 40, 236, 268)


def bow(d: ImageDraw.ImageDraw) -> None:
    for side in (-1, 1):
        points = [(C + side * x, 672 + y)
                  for x, y in ((42, -21), (150, -82), (150, 82), (42, 21))]
        d.polygon(points, fill=255)
        line(d, [*points, points[0]], 32)


def shoulders(d: ImageDraw.ImageDraw) -> None:
    for side in (-1, 1):
        line(d, [(C + side * x, y) for x, y in ((302, 860), (262, 720), (177, 640))], 40)


def icon() -> Image.Image:
    image = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    tile = mask(lambda d: d.rounded_rectangle((30, 30, S - 30, S - 30), 235, fill=255))
    image.paste(gradient(NIGHT, PLUM), (0, 0), tile)
    neon = gradient(CYAN, VIOLET)
    glow(image, mask(ring), neon, 40, 0.6)
    glow(image, mask(lambda d: dot(d, C, 360, 78)), WHITE, 55, 0.65)
    glow(image, mask(shoulders), neon, 35, 0.5)
    glow(image, mask(bow), neon, 35, 0.6)
    glow(image, mask(lambda d: dot(d, C, 672, 34)), WHITE, 25, 0.5)
    return image


def logo(mark: Image.Image, font_path: str, color: tuple) -> Image.Image:
    font = ImageFont.truetype(font_path, 560)
    left, top, right, bottom = font.getbbox("BRAM")
    image = Image.new("RGBA", (S + 70 + right - left + 30, S), (0, 0, 0, 0))
    image.paste(mark, (0, 0), mark)
    ImageDraw.Draw(image).text((S + 70 - left, C - (top + bottom) // 2), "BRAM", font=font,
                               fill=color)
    return image


def save(image: Image.Image, name: str, height: int) -> None:
    size = (round(image.width * height / image.height), height)
    image.resize(size, Image.Resampling.LANCZOS).save(OUT / name, optimize=True)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    mark = icon()
    save(mark, "icon.png", 256)
    save(mark, "icon@2x.png", 512)
    for name, color in (("logo", PLUM), ("dark_logo", (245, 248, 250))):
        image = logo(mark, sys.argv[1], color)
        save(image, f"{name}.png", 200)
        save(image, f"{name}@2x.png", 400)


if __name__ == "__main__":
    main()
