import os
import subprocess
from typing import List, Tuple

import requests

import config
from utils import audio_path_for, get_audio_duration, setup_logger

logger = setup_logger("voice_generator_v3")

_API_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"


def generate_voice(post_id: str, text: str) -> Tuple[str, List[float]]:
    if not config.ELEVENLABS_API_KEY:
        raise EnvironmentError("Missing required environment variable: ELEVENLABS_API_KEY")
    if not config.ELEVENLABS_VOICE_ID:
        raise EnvironmentError("Missing required environment variable: ELEVENLABS_VOICE_ID")

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        raise ValueError("text for voice generation is empty")

    logger.info(f"[generate_voice] post_id={post_id} requesting ElevenLabs per line")
    logger.info(f"[generate_voice] model_id={config.ELEVENLABS_MODEL_ID}")
    logger.info(f"[generate_voice] language_code={config.ELEVENLABS_LANGUAGE_CODE}")
    logger.info(f"[generate_voice] source_text=\n{text}")

    segment_paths: list[str] = []
    segment_durations: list[float] = []
    for i, line in enumerate(lines, start=1):
        segment_path = _segment_path_for(post_id, i)
        _generate_segment(line, segment_path)
        if i == 1 and config.VOICE_LEAD_IN_SECONDS > 0:
            _add_lead_in_silence(segment_path, config.VOICE_LEAD_IN_SECONDS)
        duration = get_audio_duration(segment_path)
        logger.info(
            f"[generate_voice] segment={i} duration={duration:.2f}s text=\n{line}"
        )
        segment_paths.append(segment_path)
        segment_durations.append(duration)

    out_path = audio_path_for(post_id)
    _concat_segments(segment_paths, out_path)
    logger.info(f"[generate_voice] saved to {out_path}")
    return out_path, segment_durations


def _generate_segment(text: str, out_path: str) -> None:
    url = _API_URL.format(voice_id=config.ELEVENLABS_VOICE_ID)
    headers = {
        "xi-api-key": config.ELEVENLABS_API_KEY,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    }
    payload = {
        "text": text,
        "model_id": config.ELEVENLABS_MODEL_ID,
        "language_code": config.ELEVENLABS_LANGUAGE_CODE,
        "voice_settings": {
            "stability": config.ELEVENLABS_STABILITY,
            "similarity_boost": config.ELEVENLABS_SIMILARITY_BOOST,
            "style": config.ELEVENLABS_STYLE,
            "use_speaker_boost": config.ELEVENLABS_USE_SPEAKER_BOOST,
        },
    }
    res = requests.post(url, json=payload, headers=headers, timeout=120)
    if res.status_code != 200:
        raise RuntimeError(
            f"ElevenLabs API error: {res.status_code} {res.text[:200]}"
        )
    with open(out_path, "wb") as f:
        f.write(res.content)


def _concat_segments(segment_paths: list[str], out_path: str) -> None:
    list_path = f"{out_path}.segments.txt"
    with open(list_path, "w", encoding="utf-8") as f:
        for path in segment_paths:
            abs_path = os.path.abspath(path).replace("\\", "/")
            f.write(f"file '{abs_path}'\n")

    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        list_path,
        "-c",
        "copy",
        out_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    try:
        os.remove(list_path)
    except OSError:
        pass
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg concat failed: {result.stderr[-500:]}")


def _segment_path_for(post_id: str, index: int) -> str:
    return os.path.join(config.AUDIO_DIR, f"post_{post_id}_segment_{index:02d}.mp3")


def _add_lead_in_silence(audio_path: str, silence_seconds: float) -> None:
    temp_path = f"{audio_path}.tmp.mp3"
    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"anullsrc=r=44100:cl=mono:d={silence_seconds}",
        "-i",
        audio_path,
        "-filter_complex",
        "[0:a][1:a]concat=n=2:v=0:a=1[aout]",
        "-map",
        "[aout]",
        "-c:a",
        "libmp3lame",
        "-q:a",
        "2",
        temp_path,
    ]
    logger.info(f"[generate_voice] adding lead-in silence {silence_seconds:.2f}s")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg silence prepend failed: {result.stderr[-500:]}")
    os.replace(temp_path, audio_path)
