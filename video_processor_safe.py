import glob
import os
import subprocess

import config
from utils import get_audio_duration, setup_logger, video_path_for

logger = setup_logger("video_processor_safe")

OUTPUT_WIDTH = 1080
OUTPUT_HEIGHT = 1920

_SUBTITLE_STYLE = (
    "FontName=Yu Gothic,"
    "FontSize=14,"
    "PrimaryColour=&H00FFFFFF,"
    "OutlineColour=&H00000000,"
    "BackColour=&H80000000,"
    "Outline=3,"
    "Shadow=1,"
    "Bold=1,"
    "BorderStyle=1,"
    "Alignment=2,"
    "MarginL=60,"
    "MarginR=60,"
    "MarginV=120,"
    "WrapStyle=2"
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


def build_ffmpeg_command(
    post_id: str,
    raw_video_path: str,
    audio_path: str,
    subtitle_path: str,
    output_path: str,
    audio_duration: float,
) -> list[str]:
    escaped_sub = subtitle_path.replace("\\", "/").replace(":", "\\:")
    subtitle_filter = (
        f"subtitles={escaped_sub}:charenc=UTF-8:"
        f"force_style='{_SUBTITLE_STYLE}'"
    )
    filter_complex = (
        f"[0:v]crop=ih*{OUTPUT_WIDTH}/{OUTPUT_HEIGHT}:ih,"
        f"scale={OUTPUT_WIDTH}:{OUTPUT_HEIGHT},"
        f"{subtitle_filter}"
        "[vout]"
    )

    return [
        "ffmpeg",
        "-y",
        "-stream_loop",
        "-1",
        "-i",
        raw_video_path,
        "-i",
        audio_path,
        "-t",
        str(audio_duration),
        "-filter_complex",
        filter_complex,
        "-map",
        "[vout]",
        "-map",
        "1:a",
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-crf",
        "23",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-shortest",
        output_path,
    ]


def run_ffmpeg(cmd: list[str]) -> None:
    logger.info(f"[run_ffmpeg] cmd={' '.join(cmd[:6])} ...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        stderr_snippet = result.stderr[-1000:]
        raise RuntimeError(f"ffmpeg failed:\n{stderr_snippet}")
    logger.info("[run_ffmpeg] done")


def process_video(post_id: str, audio_path: str, subtitle_path: str) -> str:
    raw_video = pick_raw_video()
    output_path = video_path_for(post_id)
    audio_duration = get_audio_duration(audio_path)

    logger.info(
        f"[process_video] post_id={post_id} raw={raw_video} "
        f"duration={audio_duration:.2f}s"
    )

    cmd = build_ffmpeg_command(
        post_id=post_id,
        raw_video_path=raw_video,
        audio_path=audio_path,
        subtitle_path=subtitle_path,
        output_path=output_path,
        audio_duration=audio_duration,
    )
    run_ffmpeg(cmd)
    logger.info(f"[process_video] saved to {output_path}")
    return output_path
