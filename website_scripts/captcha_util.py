import os
import random
import string
import math
import io
import base64

from PIL import Image, ImageDraw, ImageFont, ImageFilter

from . import config


def load_fonts(
    fonts_dir: str,
    font_sizes: tuple = (42, 50, 58),
) -> list[ImageFont.FreeTypeFont]:
    """Load all .ttf fonts from a directory at multiple sizes."""
    fonts = []
    for fname in os.listdir(fonts_dir):
        if not fname.lower().endswith(".ttf"):
            continue
        path = os.path.join(fonts_dir, fname)
        for size in font_sizes:
            try:
                fonts.append(ImageFont.truetype(path, size))
            except IOError:
                continue
    if not fonts:
        raise RuntimeError(f"No valid .ttf fonts found in {fonts_dir}")
    return fonts


def random_color(channel_ranges: tuple[tuple[int, int], ...]) -> tuple[int, int, int]:
    """Pick a random RGB color within the given per-channel ranges."""
    return tuple(random.randint(low, high) for (low, high) in channel_ranges)


def create_background(
    width: int,
    height: int,
    bg_color_range: tuple[tuple[int, int], ...],
) -> Image.Image:
    """Create a solid‐color background image."""
    color = random_color(bg_color_range)
    return Image.new("RGB", (width, height), color)


def draw_text(
    img: Image.Image,
    text: str,
    fonts: list[ImageFont.FreeTypeFont],
    fg_color_range: tuple[tuple[int, int], ...],
) -> None:
    """Draw each character of `text` at a random vertical offset & color."""
    draw = ImageDraw.Draw(img)

    # pick a random font per character
    char_fonts = [random.choice(fonts) for _ in text]

    # measure widths for centering
    widths = []
    for ch, f in zip(text, char_fonts):
        bbox = draw.textbbox((0, 0), ch, font=f)
        widths.append(bbox[2] - bbox[0])
    total_w = sum(widths)

    # starting x so text is horizontally centered
    x = (img.width - total_w) // 2
    for ch, f, w in zip(text, char_fonts, widths):
        y = random.randint(0, img.height - f.size)
        color = random_color(fg_color_range)
        draw.text((x, y), ch, font=f, fill=color)
        x += w + random.randint(-2, 4)


def add_noise_dots(
    img: Image.Image,
    count: int,
    fg_color_range: tuple[tuple[int, int], ...],
) -> None:
    """Sprinkle random colored dots across the image."""
    draw = ImageDraw.Draw(img)
    for _ in range(count):
        x = random.randint(0, img.width)
        y = random.randint(0, img.height)
        r = random.randint(1, 2)
        color = random_color(fg_color_range)
        draw.ellipse((x - r, y - r, x + r, y + r), fill=color)


def add_noise_lines(
    img: Image.Image,
    count: int,
    fg_color_range: tuple[tuple[int, int], ...],
) -> None:
    """Draw random colored lines across the image."""
    draw = ImageDraw.Draw(img)
    for _ in range(count):
        x1, y1 = random.randint(0, img.width), random.randint(0, img.height)
        x2, y2 = random.randint(0, img.width), random.randint(0, img.height)
        thickness = random.randint(1, 3)
        color = random_color(fg_color_range)
        draw.line((x1, y1, x2, y2), fill=color, width=thickness)


def wave_distort(img: Image.Image) -> Image.Image:
    """Apply a horizontal sinusoidal wave distortion."""
    amplitude = random.randint(5, 12)
    period = random.randint(100, 200)
    phase = random.random() * 2 * math.pi

    src = img
    dst = Image.new("RGB", src.size, (255, 255, 255))
    pix_src = src.load()
    pix_dst = dst.load()

    w, h = src.size
    for y in range(h):
        offset = int(amplitude * math.sin(2 * math.pi * y / period + phase))
        for x in range(w):
            new_x = x + offset
            if 0 <= new_x < w:
                pix_dst[new_x, y] = pix_src[x, y]
    return dst


def generate_captcha(
    text: str | None = None,
    fonts_dir: str = f"{config.WEBSITE_ROOT}/static/fonts/captcha/",
    font_sizes: tuple = (42, 50, 58),
    length: int = 6,
    width: int = 200,
    height: int = 80,
    bg_color_range: tuple[tuple[int, int], ...] = ((200, 255), (200, 255), (200, 255)),
    fg_color_range: tuple[tuple[int, int], ...] = ((0, 100), (0, 100), (0, 100)),
    noise_dots: int = 120,
    noise_lines: int = 6,
    webp_quality: int = 80,
) -> tuple[str, str]:
    """
    Generate a CAPTCHA, returning (base64_webp, text).
    If text is None, a random 6‐char string (A–Z0–9) is used.
    `webp_quality` controls lossy WebP compression (0–100).
    """
    # pick or build the text
    if text is None:
        text = "".join(random.choices(string.ascii_uppercase + string.digits, k=length))

    # load fonts
    fonts = load_fonts(fonts_dir, font_sizes)

    # compose image
    img = create_background(width, height, bg_color_range)
    draw_text(img, text, fonts, fg_color_range)
    add_noise_dots(img, noise_dots, fg_color_range)
    add_noise_lines(img, noise_lines, fg_color_range)

    # filters + distortion
    img = img.filter(ImageFilter.SMOOTH)
    img = wave_distort(img)
    img = img.filter(ImageFilter.SHARPEN)

    # encode as base64 WebP
    buffer = io.BytesIO()
    img.save(buffer, format="WEBP", quality=webp_quality)
    b64 = base64.b64encode(buffer.getvalue()).decode("ascii")

    return b64, text
