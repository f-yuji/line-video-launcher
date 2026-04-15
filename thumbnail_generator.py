from __future__ import annotations

from pathlib import Path

from utils import hook_image_path_for, setup_logger

logger = setup_logger("thumbnail_generator")

WIDTH = 1080
HEIGHT = 1920
BACKGROUND = (0, 0, 0, 255)
TEXT_COLOR = (255, 232, 90, 255)
STROKE_COLOR = (35, 28, 0, 255)

FONT_CANDIDATES = [
    r"C:\Windows\Fonts\YuGothB.ttc",
    r"C:\Windows\Fonts\meiryob.ttc",
    r"C:\Windows\Fonts\meiryo.ttc",
]


def generate_hook_image(post_id: str, text: str) -> str | None:
    text = (text or "").strip()
    if not text:
        return None

    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as exc:
        raise RuntimeError(
            "Pillow is required for hook image generation. Run: pip install -r requirements.txt"
        ) from exc

    lines = _split_into_lines(text)
    image = Image.new("RGBA", (WIDTH, HEIGHT), BACKGROUND)
    draw = ImageDraw.Draw(image)
    font = _pick_font(ImageFont)

    spacing = 8
    metrics = [draw.textbbox((0, 0), line, font=font, stroke_width=8) for line in lines]
    heights = [(bbox[3] - bbox[1]) for bbox in metrics]
    total_height = sum(heights) + spacing * (len(lines) - 1)
    y = max(120, (HEIGHT - total_height) // 2 - 40)

    for line, bbox, line_height in zip(lines, metrics, heights):
        line_width = bbox[2] - bbox[0]
        x = (WIDTH - line_width) // 2
        draw.text(
            (x, y),
            line,
            font=font,
            fill=TEXT_COLOR,
            stroke_width=8,
            stroke_fill=STROKE_COLOR,
        )
        y += line_height + spacing

    out_path = hook_image_path_for(post_id)
    image.save(out_path)
    logger.info(f"[generate_hook_image] saved to {out_path}")
    return out_path


def _pick_font(ImageFont):
    for candidate in FONT_CANDIDATES:
        if Path(candidate).is_file():
            return ImageFont.truetype(candidate, 180)
    return ImageFont.load_default()


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
    if len(compact) <= 12:
        return _balanced_split(compact, 2)
    if len(compact) <= 18:
        return _balanced_split(compact, 3)
    return _balanced_split(compact, 4)


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
