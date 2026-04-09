import glob
import os
import subprocess

import config
from utils import get_audio_duration, setup_logger, video_path_for

logger = setup_logger("video_processor_safe")

OUTPUT_WIDTH = 1080
OUTPUT_HEIGHT = 1920

_SE_FILENAME = "シーン切り替え2.mp3"

_CTA_STYLE_LINE = (
    "Style: Cta,Yu Gothic,96,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,"
    "-1,0,0,0,100,100,0,0,1,5,1,2,80,80,180,1\n"
)


# ──────────────────────────────────────────────
# ユーティリティ
# ──────────────────────────────────────────────

def pick_raw_video() -> str:
    exts = ("*.mp4", "*.mov", "*.avi", "*.mkv")
    files = []
    for ext in exts:
        files.extend(glob.glob(os.path.join(config.RAW_DIR, ext)))
    if not files:
        raise FileNotFoundError(f"No video files found in {config.RAW_DIR}")
    files.sort()
    return files[0]


def _find_se_path() -> str | None:
    path = os.path.join(config.RAW_DIR, _SE_FILENAME)
    return path if os.path.isfile(path) else None


def _parse_ass_time(value: str) -> float:
    """ASS タイムスタンプ H:MM:SS.cc を秒に変換する"""
    h, m, s = value.strip().split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


def _read_ass_timings(subtitle_path: str) -> list[float]:
    """ASS ファイルから各 Dialogue の開始時刻（秒）を返す"""
    timings = []
    try:
        with open(subtitle_path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.startswith("Dialogue:"):
                    continue
                parts = line.split(",", 9)
                if len(parts) >= 3:
                    timings.append(_parse_ass_time(parts[1]))
    except OSError:
        pass
    return timings


def _get_last_dialogue_start(subtitle_path: str) -> float | None:
    timings = _read_ass_timings(subtitle_path)
    return timings[-1] if timings else None


def _format_ass_time(seconds: float) -> str:
    total = max(seconds, 0.0)
    h = int(total // 3600)
    m = int((total % 3600) // 60)
    s = total % 60
    return f"{h}:{m:02}:{s:05.2f}"


def _escape_ass_text(text: str) -> str:
    return text.replace("\\", r"\\").replace("{", r"\{").replace("}", r"\}")


# ──────────────────────────────────────────────
# ffmpeg コマンド構築
# ──────────────────────────────────────────────

def build_ffmpeg_command(
    post_id: str,
    raw_video_path: str,
    audio_path: str,
    subtitle_path: str,
    output_path: str,
    audio_duration: float,
    cta_ass_path: str | None = None,
    se_path: str | None = None,
    se_start_timing: float | None = None,
    se_end_timing: float | None = None,
) -> list[str]:
    escaped_sub = subtitle_path.replace("\\", "/").replace(":", "\\:")
    video_chain = (
        f"[0:v]crop=ih*{OUTPUT_WIDTH}/{OUTPUT_HEIGHT}:ih,"
        f"scale={OUTPUT_WIDTH}:{OUTPUT_HEIGHT},"
        f"subtitles={escaped_sub}:charenc=UTF-8"
    )
    if cta_ass_path:
        escaped_cta = cta_ass_path.replace("\\", "/").replace(":", "\\:")
        video_chain += f",subtitles={escaped_cta}:charenc=UTF-8"

    # SE あり: asplit で冒頭(100%) と末尾(70%,+0.3s) の2発
    if se_path and se_start_timing is not None and se_end_timing is not None:
        start_ms = int(se_start_timing * 1000)
        end_ms = int((se_end_timing + 0.3) * 1000)  # 末尾SEは0.3秒遅らせる

        filter_complex = ";".join([
            f"{video_chain}[vout]",
            "[2:a]asplit=2[se_raw0][se_raw1]",
            f"[se_raw0]adelay={start_ms}|{start_ms},apad[se0]",
            f"[se_raw1]adelay={end_ms}|{end_ms},volume=0.7,apad[se1]",
            "[1:a][se0][se1]amix=inputs=3:duration=first:normalize=0[aout]",
        ])
        return [
            "ffmpeg", "-y",
            "-stream_loop", "-1", "-i", raw_video_path,
            "-i", audio_path,
            "-stream_loop", "-1", "-i", se_path,
            "-t", str(audio_duration),
            "-filter_complex", filter_complex,
            "-map", "[vout]",
            "-map", "[aout]",
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-c:a", "aac", "-b:a", "192k",
            "-shortest",
            output_path,
        ]

    # SE なし
    filter_complex = f"{video_chain}[vout]"
    return [
        "ffmpeg", "-y",
        "-stream_loop", "-1", "-i", raw_video_path,
        "-i", audio_path,
        "-t", str(audio_duration),
        "-filter_complex", filter_complex,
        "-map", "[vout]",
        "-map", "1:a",
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-c:a", "aac", "-b:a", "192k",
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


# ──────────────────────────────────────────────
# メイン処理
# ──────────────────────────────────────────────

def process_video(post_id: str, audio_path: str, subtitle_path: str) -> str:
    raw_video = pick_raw_video()
    output_path = video_path_for(post_id)
    audio_duration = get_audio_duration(audio_path)
    cta_ass_path = _create_end_cta_ass(post_id, subtitle_path, audio_duration)

    # SE: 冒頭タイミング（1行目）と末尾タイミング（最終行）のみ
    se_path = _find_se_path()
    se_start_timing: float | None = None
    se_end_timing: float | None = None
    if se_path:
        timings = _read_ass_timings(subtitle_path)
        if len(timings) >= 2:
            se_start_timing = timings[0]
            se_end_timing = timings[-1]
            logger.info(
                f"[process_video] SE={_SE_FILENAME} "
                f"start={se_start_timing:.2f}s end={se_end_timing:.2f}s(+0.3s)"
            )
        else:
            logger.info("[process_video] SE: not enough timings, skipping")
    else:
        logger.info("[process_video] SE file not found, skipping")

    logger.info(
        f"[process_video] post_id={post_id} raw={raw_video} duration={audio_duration:.2f}s"
    )
    cmd = build_ffmpeg_command(
        post_id=post_id,
        raw_video_path=raw_video,
        audio_path=audio_path,
        subtitle_path=subtitle_path,
        output_path=output_path,
        audio_duration=audio_duration,
        cta_ass_path=cta_ass_path,
        se_path=se_path,
        se_start_timing=se_start_timing,
        se_end_timing=se_end_timing,
    )
    run_ffmpeg(cmd)
    logger.info(f"[process_video] saved to {output_path}")
    return output_path


# ──────────────────────────────────────────────
# CTA オーバーレイ
# ──────────────────────────────────────────────

def _create_end_cta_ass(post_id: str, subtitle_path: str, audio_duration: float) -> str | None:
    cta_text = (config.END_CTA_TEXT or "").strip()
    if not cta_text:
        return None

    start_seconds = _get_last_dialogue_start(subtitle_path)
    if start_seconds is None:
        return None

    end_seconds = max(audio_duration - 0.05, start_seconds + 0.8)
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
