import glob
import os
import subprocess

import config
from display_formatter import format_hook
from utils import get_audio_duration, setup_logger, video_path_for

logger = setup_logger("video_processor_v5")

OUTPUT_WIDTH = 1080
OUTPUT_HEIGHT = 1920

_SUBTITLE_STYLE = (
    "FontName=Noto Sans CJK JP,"
    "FontSize=14,"
    "PrimaryColour=&H00FFFFFF,"
    "OutlineColour=&H00000000,"
    "BackColour=&HFF000000,"
    "Outline=3,"
    "Shadow=1,"
    "Bold=1,"
    "BorderStyle=4,"
    "Alignment=2,"
    "MarginL=60,"
    "MarginR=60,"
    "MarginV=120,"
    "WrapStyle=2"
)

_HOOK_STYLE_LINE = (
    "Style: Hook,Noto Sans CJK JP,138,&H0000A5FF,&H0000A5FF,&H00000000,&HEE000000,"
    "-1,0,0,0,100,100,0,0,4,3,0,5,40,40,260,1\n"
)

_CTA_STYLE_LINE = (
    "Style: Cta,Noto Sans CJK JP,124,&H00FFFFFF,&H00FFFFFF,&H00000000,&HFF000000,"
    "-1,0,0,0,100,100,0,0,4,2,0,5,80,80,0,1\n"
)


def pick_raw_video() -> str:
    exts = ("*.mp4", "*.mov", "*.avi", "*.mkv")
    files = []
    for ext in exts:
        files.extend(glob.glob(os.path.join(config.RAW_DIR, ext)))
    if not files:
        raise FileNotFoundError(f"No video files found in {config.RAW_DIR}")
    files.sort()
    return files[0]


def process_video(
    post_id: str,
    audio_path: str,
    subtitle_path: str,
    hook_text: str = "",
    hook_image_path: str | None = None,
    cta_image_path: str | None = None,
) -> str:
    raw_video = pick_raw_video()
    output_path = video_path_for(post_id)
    audio_duration = get_audio_duration(audio_path)

    use_hook_image = bool(hook_image_path and os.path.isfile(hook_image_path))
    use_cta_image = bool(cta_image_path and os.path.isfile(cta_image_path))
    hook_ass_path = None if use_hook_image else _create_hook_ass(post_id, subtitle_path, hook_text)
    cta_ass_path = None if use_cta_image else _create_end_cta_ass(post_id, subtitle_path, audio_duration)
    overlay_ass_path = _merge_ass_overlays(post_id, hook_ass_path, cta_ass_path)
    subtitle_events = _read_srt_events(subtitle_path)
    se_path = _find_se_path()

    logger.info(
        f"[process_video] post_id={post_id} raw={raw_video} duration={audio_duration:.2f}s "
        f"hook_image={hook_image_path if use_hook_image else 'none'} "
        f"cta_image={cta_image_path if use_cta_image else 'none'}"
    )
    cmd = _build_ffmpeg_command(
        raw_video_path=raw_video,
        audio_path=audio_path,
        subtitle_path=subtitle_path,
        output_path=output_path,
        audio_duration=audio_duration,
        overlay_ass_path=overlay_ass_path,
        hook_image_path=hook_image_path if use_hook_image else None,
        cta_image_path=cta_image_path if use_cta_image else None,
        subtitle_events=subtitle_events,
        se_path=se_path,
    )
    _run_ffmpeg(cmd)
    logger.info(f"[process_video] saved to {output_path}")
    return output_path


def _build_ffmpeg_command(
    *,
    raw_video_path: str,
    audio_path: str,
    subtitle_path: str,
    output_path: str,
    audio_duration: float,
    overlay_ass_path: str | None,
    hook_image_path: str | None,
    cta_image_path: str | None,
    subtitle_events: list[tuple[float, float, str]],
    se_path: str | None,
) -> list[str]:
    escaped_sub = subtitle_path.replace("\\", "/").replace(":", "\\:")
    subtitle_filter = (
        f"subtitles={escaped_sub}:charenc=UTF-8:"
        f"force_style='{_SUBTITLE_STYLE}'"
    )

    filter_parts = [
        f"[0:v]scale={OUTPUT_WIDTH}:{OUTPUT_HEIGHT}:force_original_aspect_ratio=increase,"
        f"crop={OUTPUT_WIDTH}:{OUTPUT_HEIGHT},"
        f"{subtitle_filter}[vbase]"
    ]

    cmd = [
        "ffmpeg", "-y",
        "-stream_loop", "-1", "-i", raw_video_path,
        "-i", audio_path,
    ]

    current_video = "[vbase]"
    next_input_index = 2
    audio_map = "1:a"

    if hook_image_path:
        cmd.extend(["-loop", "1", "-i", hook_image_path])
        filter_parts.append(f"[{next_input_index}:v]format=rgba[hookimg]")
        filter_parts.append(
            f"{current_video}[hookimg]overlay=0:0:"
            f"enable='between(t,0,{config.HOOK_IMAGE_SECONDS})'[vhook]"
        )
        current_video = "[vhook]"
        next_input_index += 1

    if cta_image_path:
        cta_start = subtitle_events[-1][0] if subtitle_events else max(audio_duration - 2.5, 0.0)
        cmd.extend(["-loop", "1", "-i", cta_image_path])
        filter_parts.append(f"[{next_input_index}:v]format=rgba[ctaimg]")
        filter_parts.append(
            f"{current_video}[ctaimg]overlay=0:0:"
            f"enable='between(t,{cta_start},{max(audio_duration - 0.05, cta_start + 0.8)})'[vcta]"
        )
        current_video = "[vcta]"
        next_input_index += 1

    if overlay_ass_path:
        escaped_overlay = overlay_ass_path.replace("\\", "/").replace(":", "\\:")
        filter_parts.append(
            f"{current_video}subtitles={escaped_overlay}:charenc=UTF-8[vout]"
        )
    else:
        filter_parts.append(f"{current_video}null[vout]")

    if se_path and subtitle_events:
        cmd.extend(["-stream_loop", "-1", "-i", se_path])
        first_start = subtitle_events[0][0]
        delay = int(first_start * 1000)
        filter_parts.append(
            f"[{next_input_index}:a]atrim=0:0.45,asetpts=N/SR/TB,"
            f"afade=t=out:st=0.30:d=0.15,"
            f"adelay={delay}|{delay},volume=0.65,apad[se0]"
        )
        filter_parts.append("[1:a][se0]amix=inputs=2:duration=first:normalize=0[aout]")
        audio_map = "[aout]"
        logger.info(f"[process_video] SE timing={round(first_start, 3)}")
    else:
        logger.info("[process_video] SE skipped")

    cmd.extend([
        "-t", str(audio_duration),
        "-filter_complex", ";".join(filter_parts),
        "-map", "[vout]",
        "-map", audio_map,
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        output_path,
    ])
    return cmd


def _find_se_path() -> str | None:
    files = sorted(glob.glob(os.path.join(config.RAW_DIR, "*.mp3")))
    return files[0] if files else None


def _read_srt_events(subtitle_path: str) -> list[tuple[float, float, str]]:
    events: list[tuple[float, float, str]] = []
    try:
        with open(subtitle_path, "r", encoding="utf-8") as f:
            lines = [line.rstrip("\n") for line in f]
    except OSError:
        return events

    i = 0
    while i < len(lines):
        if " --> " not in lines[i]:
            i += 1
            continue
        start_text, end_text = [part.strip() for part in lines[i].split(" --> ", 1)]
        text_lines = []
        j = i + 1
        while j < len(lines) and lines[j].strip():
            text_lines.append(lines[j].strip())
            j += 1
        events.append((_parse_srt_time(start_text), _parse_srt_time(end_text), "\n".join(text_lines)))
        i = j + 1
    return events


def _create_hook_ass(post_id: str, subtitle_path: str, hook_text: str) -> str | None:
    events = _read_srt_events(subtitle_path)
    if not events:
        return None

    start_seconds, end_seconds, srt_text = events[0]
    text = (hook_text or srt_text).strip()
    if not text:
        return None

    ass_path = os.path.join(config.SUBTITLE_DIR, f"post_{post_id}_hook.ass")
    escaped_text = _escape_ass_text(format_hook(text).replace("\n", r"\N"))
    ass = (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        f"PlayResX: {OUTPUT_WIDTH}\n"
        f"PlayResY: {OUTPUT_HEIGHT}\n"
        "\n"
        "[V4+ Styles]\n"
        "Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,"
        "BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,"
        "BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding\n"
        f"{_HOOK_STYLE_LINE}"
        "\n"
        "[Events]\n"
        "Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text\n"
        f"Dialogue: 0,{_format_ass_time(start_seconds)},{_format_ass_time(end_seconds)},Hook,,0,0,0,,{escaped_text}\n"
    )
    with open(ass_path, "w", encoding="utf-8") as f:
        f.write(ass)
    return ass_path


def _create_end_cta_ass(post_id: str, subtitle_path: str, audio_duration: float) -> str | None:
    cta_text = (config.END_CTA_TEXT or "").strip()
    if not cta_text:
        return None
    events = _read_srt_events(subtitle_path)
    if not events:
        return None

    start_seconds = events[-1][0]
    end_seconds = max(audio_duration - 0.05, start_seconds + 1.2)
    ass_path = os.path.join(config.SUBTITLE_DIR, f"post_{post_id}_cta.ass")
    escaped_text = _escape_ass_text(cta_text)
    ass = (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        f"PlayResX: {OUTPUT_WIDTH}\n"
        f"PlayResY: {OUTPUT_HEIGHT}\n"
        "\n"
        "[V4+ Styles]\n"
        "Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,"
        "BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,"
        "BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding\n"
        f"{_CTA_STYLE_LINE}"
        "\n"
        "[Events]\n"
        "Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text\n"
        f"Dialogue: 0,{_format_ass_time(start_seconds)},{_format_ass_time(end_seconds)},Cta,,0,0,0,,{escaped_text}\n"
    )
    with open(ass_path, "w", encoding="utf-8") as f:
        f.write(ass)
    return ass_path


def _merge_ass_overlays(post_id: str, *paths: str | None) -> str | None:
    valid = [path for path in paths if path]
    if not valid:
        return None
    if len(valid) == 1:
        return valid[0]

    merged_path = os.path.join(config.SUBTITLE_DIR, f"post_{post_id}_overlay.ass")
    styles: list[str] = []
    events: list[str] = []
    for path in valid:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()
        in_styles = False
        in_events = False
        for line in lines:
            if line == "[V4+ Styles]":
                in_styles = True
                in_events = False
                continue
            if line == "[Events]":
                in_styles = False
                in_events = True
                continue
            if in_styles and line.startswith("Style: "):
                styles.append(line)
            if in_events and line.startswith("Dialogue: "):
                events.append(line)

    merged = (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        f"PlayResX: {OUTPUT_WIDTH}\n"
        f"PlayResY: {OUTPUT_HEIGHT}\n"
        "\n"
        "[V4+ Styles]\n"
        "Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,"
        "BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,"
        "BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding\n"
        + "\n".join(styles)
        + "\n\n[Events]\n"
        "Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text\n"
        + "\n".join(events)
        + "\n"
    )
    with open(merged_path, "w", encoding="utf-8") as f:
        f.write(merged)
    return merged_path


def _run_ffmpeg(cmd: list[str]) -> None:
    logger.info(f"[run_ffmpeg] cmd={' '.join(cmd[:6])} ...")
    result = subprocess.run(cmd, capture_output=True, text=False)
    if result.returncode != 0:
        stderr = (result.stderr or b"").decode("utf-8", errors="replace")
        if not stderr:
            stderr = (result.stdout or b"").decode("utf-8", errors="replace")
        raise RuntimeError(f"ffmpeg failed:\n{stderr[-1200:]}")
    logger.info("[run_ffmpeg] done")




def _escape_ass_text(text: str) -> str:
    return text.replace("{", r"\{").replace("}", r"\}")


def _parse_srt_time(value: str) -> float:
    hhmmss, millis = value.split(",")
    hours, minutes, seconds = [int(part) for part in hhmmss.split(":")]
    return hours * 3600 + minutes * 60 + seconds + (int(millis) / 1000)


def _format_ass_time(seconds: float) -> str:
    total = max(seconds, 0.0)
    h = int(total // 3600)
    m = int((total % 3600) // 60)
    s = total % 60
    return f"{h}:{m:02}:{s:05.2f}"
