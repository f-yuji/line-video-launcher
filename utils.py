import os
import subprocess
import logging
import sys
from datetime import datetime, timedelta

import config


def setup_logger(name: str) -> logging.Logger:
    os.makedirs(config.LOG_DIR, exist_ok=True)
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(logging.DEBUG)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    # ファイルハンドラ
    fh = logging.FileHandler(
        os.path.join(config.LOG_DIR, f"{name}.log"), encoding="utf-8"
    )
    fh.setFormatter(fmt)
    logger.addHandler(fh)
    # 標準出力ハンドラ
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    logger.addHandler(sh)
    return logger


def ensure_dirs() -> None:
    """必要なディレクトリをすべて作成する"""
    for d in [
        config.RAW_DIR,
        config.AUDIO_DIR,
        config.SUBTITLE_DIR,
        config.OUTPUT_DIR,
        config.LOG_DIR,
    ]:
        os.makedirs(d, exist_ok=True)


def file_exists(path: str) -> bool:
    return os.path.isfile(path)


def get_audio_duration(audio_path: str) -> float:
    """ffprobeで音声ファイルの長さ（秒）を取得する"""
    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        audio_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {result.stderr}")
    return float(result.stdout.strip())


def format_srt_time(seconds: float) -> str:
    """秒数をSRTタイムスタンプ形式 HH:MM:SS,mmm に変換する"""
    td = timedelta(seconds=seconds)
    total_seconds = int(td.total_seconds())
    millis = int((td.total_seconds() - total_seconds) * 1000)
    h = total_seconds // 3600
    m = (total_seconds % 3600) // 60
    s = total_seconds % 60
    return f"{h:02}:{m:02}:{s:02},{millis:03}"


def now_jst_str() -> str:
    """現在時刻を JST 文字列で返す（ログ用）"""
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def audio_path_for(post_id: str) -> str:
    return os.path.join(config.AUDIO_DIR, f"post_{post_id}_audio.mp3")


def subtitle_path_for(post_id: str) -> str:
    return os.path.join(config.SUBTITLE_DIR, f"post_{post_id}_subtitle.srt")


def video_path_for(post_id: str) -> str:
    return os.path.join(config.OUTPUT_DIR, f"post_{post_id}_video.mp4")
