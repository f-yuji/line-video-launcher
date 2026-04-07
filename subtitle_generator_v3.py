from utils import format_srt_time, setup_logger, subtitle_path_for

logger = setup_logger("subtitle_generator_v3")


def generate_srt(post_id: str, script: str, segment_durations: list[float]) -> str:
    lines = [line.strip() for line in script.splitlines() if line.strip()]
    if not lines:
        raise ValueError("script is empty")
    if len(lines) != len(segment_durations):
        raise ValueError(
            f"line count and segment duration count differ: {len(lines)} vs {len(segment_durations)}"
        )

    logger.info(
        f"[generate_srt] post_id={post_id} lines={len(lines)} durations={segment_durations}"
    )

    elapsed = 0.0
    blocks = []
    for i, (line, duration) in enumerate(zip(lines, segment_durations), start=1):
        start = elapsed
        end = start + duration
        blocks.append(
            f"{i}\n"
            f"{format_srt_time(start)} --> {format_srt_time(end)}\n"
            f"{_wrap_subtitle_line(line)}\n"
        )
        elapsed = end

    out_path = subtitle_path_for(post_id)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(blocks))

    logger.info(f"[generate_srt] saved to {out_path}")
    return out_path


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
