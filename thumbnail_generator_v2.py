from __future__ import annotations

from pathlib import Path

from display_formatter import format_hook_lines
from utils import cta_image_path_for, hook_image_path_for, setup_logger

logger = setup_logger("thumbnail_generator_v2")

WIDTH = 1080
HEIGHT = 1920
BACKGROUND = (0, 0, 0, 255)
HOOK_LINE1_COLOR = (255, 190, 20, 255)
HOOK_LINE2_COLOR = (255, 255, 255, 255)
HOOK_LINE3_COLOR = (235, 20, 0, 255)
STROKE_COLOR = (0, 0, 0, 255)

FONT_CANDIDATES = [
    r"C:\Windows\Fonts\YuGothB.ttc",
    r"C:\Windows\Fonts\meiryob.ttc",
    r"C:\Windows\Fonts\meiryo.ttc",
]

HOOK_MAX_TEXT_WIDTH = 940


def generate_hook_image(post_id: str, text: str) -> str | None:
    text = (text or "").strip()
    if not text:
        return None

    Image, ImageDraw, ImageFont = _load_pillow()
    raw_lines = format_hook_lines(text)
    # 必ず3要素に正規化
    if len(raw_lines) == 1:
        lines = [raw_lines[0], "", ""]
    elif len(raw_lines) == 2:
        lines = [raw_lines[0], raw_lines[1], ""]
    elif len(raw_lines) > 3:
        lines = [raw_lines[0], "".join(raw_lines[1:-1]), raw_lines[-1]]
    else:
        lines = raw_lines

    image = Image.new("RGBA", (WIDTH, HEIGHT), BACKGROUND)
    draw = ImageDraw.Draw(image)

    target_sizes = [138, 206, 286]
    fills = [HOOK_LINE1_COLOR, HOOK_LINE2_COLOR, HOOK_LINE3_COLOR]
    stroke_widths = [7, 9, 12]
    spacing = 8

    fonts = []
    metrics = []
    heights = []
    for line, target_size, stroke_width in zip(lines, target_sizes, stroke_widths):
        if not line:
            fonts.append(_pick_font(ImageFont, target_size))
            metrics.append((0, 0, 0, 0))
            heights.append(0)
            continue
        font = _fit_font(ImageFont, draw, line, target_size, HOOK_MAX_TEXT_WIDTH, stroke_width)
        bbox = draw.textbbox((0, 0), line, font=font, stroke_width=stroke_width)
        fonts.append(font)
        metrics.append(bbox)
        heights.append(bbox[3] - bbox[1])

    total_height = sum(heights) + spacing * (len(lines) - 1)
    y = max(330, (HEIGHT - total_height) // 2 + 120)

    for line, bbox, line_height, font, fill, stroke_width in zip(
        lines, metrics, heights, fonts, fills, stroke_widths
    ):
        if not line:
            continue
        line_width = bbox[2] - bbox[0]
        x = (WIDTH - line_width) // 2
        draw.text(
            (x, y),
            line,
            font=font,
            fill=fill,
            stroke_width=stroke_width,
            stroke_fill=STROKE_COLOR,
        )
        y += line_height + spacing

    out_path = hook_image_path_for(post_id)
    image.save(out_path)
    logger.info(f"[generate_hook_image] saved to {out_path}")
    return out_path


def generate_cta_image(post_id: str, text: str) -> str | None:
    text = (text or "").strip()
    if not text:
        return None

    Image, ImageDraw, ImageFont = _load_pillow()
    image = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    font = _pick_font(ImageFont, 120)
    bbox = draw.textbbox((0, 0), text, font=font, stroke_width=4)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    pad_x = 74
    pad_y = 44
    box_width = text_width + pad_x * 2
    box_height = text_height + pad_y * 2
    x = (WIDTH - box_width) // 2
    y = int((HEIGHT - box_height) * 0.69)

    draw.rounded_rectangle(
        (x, y, x + box_width, y + box_height),
        radius=36,
        fill=(0, 0, 0, 255),
    )
    draw.text(
        (x + pad_x, y + pad_y - 8),
        text,
        font=font,
        fill=(255, 255, 255, 255),
        stroke_width=5,
        stroke_fill=(0, 0, 0, 255),
    )

    out_path = cta_image_path_for(post_id)
    image.save(out_path)
    logger.info(f"[generate_cta_image] saved to {out_path}")
    return out_path


def _load_pillow():
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as exc:
        raise RuntimeError(
            "Pillow is required for image generation. Run: pip install Pillow"
        ) from exc
    return Image, ImageDraw, ImageFont


def _pick_font(ImageFont, size: int):
    for candidate in FONT_CANDIDATES:
        if Path(candidate).is_file():
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default()


def _fit_font(ImageFont, draw, text: str, start_size: int, max_width: int, stroke_width: int):
    size = start_size
    while size >= 72:
        font = _pick_font(ImageFont, size)
        bbox = draw.textbbox((0, 0), text, font=font, stroke_width=stroke_width)
        width = bbox[2] - bbox[0]
        if width <= max_width:
            return font
        size -= 8
    return _pick_font(ImageFont, 72)


