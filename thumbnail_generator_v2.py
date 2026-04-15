from __future__ import annotations

from pathlib import Path

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
HOOK_IMPACT_SUFFIXES = [
    "地獄です",
    "損します",
    "危険です",
    "終わりです",
    "詰みます",
    "地獄",
    "危険",
    "詰む",
    "破滅",
    "終了",
    "無理",
    "損",
    "ない",
]

HOOK_MIDDLE_PHRASES = [
    "書類なくすと",
    "だけで安心は",
    "知らないと",
    "なくすと",
    "資産では",
    "意味がない",
    "現金一括",
    "値上がりで",
]


def generate_hook_image(post_id: str, text: str) -> str | None:
    text = (text or "").strip()
    if not text:
        return None

    Image, ImageDraw, ImageFont = _load_pillow()
    lines = _split_into_lines(text)
    if len(lines) == 1:
        lines = [lines[0], "", ""]
    elif len(lines) == 2:
        lines = [lines[0], lines[1], ""]
    elif len(lines) > 3:
        lines = [lines[0], "".join(lines[1:-1]), lines[-1]]

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


def _split_into_lines(text: str) -> list[str]:
    compact = (
        text.replace("\n", "")
        .replace("、", "")
        .replace("。", "")
        .replace("？", "")
        .replace("！", "")
        .strip()
    )
    if len(compact) <= 6:
        return [compact]
    semantic = _semantic_split(compact)
    if semantic:
        return semantic
    return _balanced_split(compact, 3)


def _semantic_split(text: str) -> list[str] | None:
    third = ""
    remaining = text

    for suffix in HOOK_IMPACT_SUFFIXES:
        if text.endswith(suffix) and len(text) > len(suffix) + 2:
            third = suffix
            remaining = text[: -len(suffix)].strip()
            break

    if not third:
        return None

    first, second = _split_first_and_second(remaining)
    if not first or not second:
        return None

    return [first, second, third]


def _split_first_and_second(text: str) -> tuple[str, str]:
    for phrase in HOOK_MIDDLE_PHRASES:
        idx = text.find(phrase)
        if idx > 0:
            first = text[:idx].strip()
            second = text[idx:].strip()
            if first and second:
                return first, second

    preferred_markers = ["だけで", "まで", "から", "とは", "には", "では", "の", "は", "が", "を"]
    best: tuple[str, str] | None = None
    best_score: float | None = None

    for i in range(1, len(text)):
        first = text[:i].strip()
        second = text[i:].strip()
        if not first or not second:
            continue
        if len(first) < 2 or len(second) < 3:
            continue

        score = abs(len(first) - len(second)) * 1.0
        matched = False
        for marker in preferred_markers:
            if first.endswith(marker):
                score -= 3.0
                matched = True
                break
        if not matched and len(first) <= 4:
            score -= 1.5
        if len(first) > 9:
            score += 3.0
        if len(second) > 10:
            score += 2.0

        if best_score is None or score < best_score:
            best_score = score
            best = (first, second)

    if best:
        return best
    return "", ""


def _balanced_split(text: str, parts_count: int) -> list[str]:
    preferred_breaks = {"の", "を", "が", "で", "に", "と", "は", "も"}
    break_count = parts_count - 1
    best_score = None
    best_breaks: list[int] | None = None

    def search(start: int, chosen: list[int]) -> None:
        nonlocal best_score, best_breaks
        if len(chosen) == break_count:
            pieces = []
            prev = 0
            for idx in chosen:
                pieces.append(text[prev:idx].strip())
                prev = idx
            pieces.append(text[prev:].strip())
            if any(not piece for piece in pieces):
                return

            lengths = [len(piece) for piece in pieces]
            ideal = len(text) / parts_count
            score = sum(abs(length - ideal) for length in lengths) + (max(lengths) - min(lengths))
            for idx in chosen:
                if text[idx - 1] in preferred_breaks:
                    score -= 1.2
            if best_score is None or score < best_score:
                best_score = score
                best_breaks = chosen[:]
            return

        for idx in range(start, len(text)):
            if idx <= 0 or idx >= len(text):
                continue
            if chosen and idx <= chosen[-1] + 1:
                continue
            chosen.append(idx)
            search(idx + 1, chosen)
            chosen.pop()

    search(1, [])

    if not best_breaks:
        avg = len(text) / parts_count
        best_breaks = [round(avg * i) for i in range(1, parts_count)]

    pieces = []
    prev = 0
    for idx in best_breaks:
        pieces.append(text[prev:idx].strip())
        prev = idx
    pieces.append(text[prev:].strip())
    return [piece for piece in pieces if piece]
