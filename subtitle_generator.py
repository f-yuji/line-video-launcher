import os

from utils import setup_logger, get_audio_duration, format_srt_time, subtitle_path_for

logger = setup_logger("subtitle_generator")


def generate_srt(post_id: str, script: str, audio_path: str) -> str:
    """台本と音声から SRT ファイルを生成し、ファイルパスを返す"""
    lines = [line.strip() for line in script.splitlines() if line.strip()]
    if not lines:
        raise ValueError("script is empty")

    duration = get_audio_duration(audio_path)
    logger.info(
        f"[generate_srt] post_id={post_id} lines={len(lines)} duration={duration:.2f}s"
    )

    srt_content = _build_srt(lines, duration)
    out_path = subtitle_path_for(post_id)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(srt_content)

    logger.info(f"[generate_srt] saved to {out_path}")
    return out_path


def _build_srt(lines: list[str], total_duration: float) -> str:
    """行リストと総再生時間から SRT 文字列を生成する"""
    n = len(lines)
    interval = total_duration / n
    blocks = []
    for i, line in enumerate(lines):
        start = i * interval
        end = (i + 1) * interval
        # 最後の行は音声末尾より少し手前で終わらせる
        if i == n - 1:
            end = min(end, total_duration - 0.1)
        blocks.append(
            f"{i + 1}\n"
            f"{format_srt_time(start)} --> {format_srt_time(end)}\n"
            f"{_wrap_subtitle_line(line)}\n"
        )
    return "\n".join(blocks)


def _wrap_subtitle_line(text: str, max_chars: int = 14) -> str:
    text = text.strip()
    if len(text) <= max_chars:
        return text

    split_at = max_chars
    for marker in ("、", "。", "？", "！", " ", "　"):
        pos = text.rfind(marker, 0, max_chars + 1)
        if pos > 0:
            split_at = pos + 1
            break

    first = text[:split_at].strip()
    second = text[split_at:].strip()
    if len(second) > max_chars:
        second = second[:max_chars].strip()
    return f"{first}\n{second}"
