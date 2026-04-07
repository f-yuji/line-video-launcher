import os
import glob
import subprocess

import config
from utils import setup_logger, get_audio_duration, video_path_for

logger = setup_logger("video_processor")

# 出力解像度（縦型 9:16）
OUTPUT_WIDTH = 1080
OUTPUT_HEIGHT = 1920

# 字幕スタイル（下部中央の見やすい固定表示）
_SUBTITLE_STYLE = (
    "FontName=Yu Gothic,"
    "FontSize=56,"
    "PrimaryColour=&H00FFFFFF,"
    "OutlineColour=&H00000000,"
    "BackColour=&H80000000,"
    "Outline=3,"
    "Shadow=0,"
    "Bold=1,"
    "BorderStyle=4,"
    "Alignment=2,"
    "MarginL=80,"
    "MarginR=80,"
    "MarginV=180"
)


def pick_raw_video() -> str:
    """raw フォルダから動画ファイルを 1 本取得する"""
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
    """ffmpeg コマンドリストを組み立てる（実行はしない）"""
    # 字幕パスはバックスラッシュをエスケープ（Windows 対応）
    escaped_sub = subtitle_path.replace("\\", "/").replace(":", "\\:")
    subtitle_filter = (
        f"subtitles={escaped_sub}:charenc=UTF-8:"
        f"force_style='{_SUBTITLE_STYLE}'"
    )

    return [
        "ffmpeg",
        "-y",                        # 上書き許可
        "-stream_loop", "-1",        # 素材動画をループ
        "-i", raw_video_path,        # 入力: 素材動画
        "-i", audio_path,            # 入力: 音声
        "-t", str(audio_duration),   # 音声長に合わせて切り出す
        "-filter_complex",
        (
            # 1) 中央クロップ → 縦型リサイズ
            f"[0:v]crop=ih*{OUTPUT_WIDTH}/{OUTPUT_HEIGHT}:ih,"
            f"scale={OUTPUT_WIDTH}:{OUTPUT_HEIGHT},"
            # 2) SRT 字幕を焼き込み
            + subtitle_filter
            "[vout]"
        ),
        "-map", "[vout]",
        "-map", "1:a",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        output_path,
    ]


def run_ffmpeg(cmd: list[str]) -> None:
    """ffmpeg コマンドを実行し、失敗時は stderr を含む例外を投げる"""
    logger.info(f"[run_ffmpeg] cmd={' '.join(cmd[:6])} ...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        stderr_snippet = result.stderr[-1000:]
        raise RuntimeError(f"ffmpeg failed:\n{stderr_snippet}")
    logger.info("[run_ffmpeg] done")


def process_video(post_id: str, audio_path: str, subtitle_path: str) -> str:
    """
    素材動画 + 音声 + 字幕 から縦型動画を生成し、出力パスを返す。
    """
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
