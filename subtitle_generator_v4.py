import config
from utils import format_srt_time, get_audio_duration, setup_logger, subtitle_path_for

logger = setup_logger("subtitle_generator_v4")


def generate_srt(post_id: str, script: str, audio_path: str) -> str:
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
    lead_in = max(config.VOICE_LEAD_IN_SECONDS, 0.0)
    usable_duration = max(total_duration - lead_in, 0.8 * len(lines))
    weights = [_line_weight(line) for line in lines]
    if weights:
        weights[0] += int(round(max(lead_in * 2.0, 6.0)))
    total_weight = sum(weights)
    elapsed = 0.0
    blocks = []

    for i, (line, weight) in enumerate(zip(lines, weights)):
        start = elapsed
        duration = usable_duration * (weight / total_weight)
        end = start + duration
        if i == len(lines) - 1:
            end = max(start + 0.8, total_duration - 0.1)

        display_line = _wrap_subtitle_line(line)
        blocks.append(
            f"{i + 1}\n"
            f"{format_srt_time(start)} --> {format_srt_time(end)}\n"
            f"{display_line}\n"
        )
        elapsed = end

    return "\n".join(blocks)


def _line_weight(line: str) -> int:
    weight = 0
    for ch in line:
        if ch in "、。，．！？!?":
            weight += 1
        elif ch.isspace():
            continue
        else:
            weight += 2
    return max(weight, 1)


def _wrap_subtitle_line(text: str, max_chars: int = 14) -> str:
    text = text.strip()
    if len(text) <= max_chars:
        return text

    split_at = max_chars
    for marker in ("、", "。", " ", "・"):
        pos = text.rfind(marker, 0, max_chars + 1)
        if pos > 0:
            split_at = pos + 1
            break

    first = text[:split_at].strip()
    second = text[split_at:].strip()
    if len(second) > max_chars:
        second = second[:max_chars].strip()
    return f"{first}\n{second}"
