import os
import requests
import subprocess

import config
from utils import audio_path_for, setup_logger

logger = setup_logger("voice_generator_v2")

_API_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
_VOICE_VOLUME_MULTIPLIER = float(os.environ.get("VOICE_VOLUME_MULTIPLIER", "1.25"))


def _format_text_for_tts(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return ""

    formatted = "、".join(lines)
    formatted = formatted.replace("？？", "？").replace("！！", "！")
    formatted = formatted.replace("。、", "。").replace("？、", "？").replace("！、", "！")
    return formatted

def generate_voice(post_id: str, text: str) -> str:
    if not config.ELEVENLABS_API_KEY:
        raise EnvironmentError("Missing required environment variable: ELEVENLABS_API_KEY")
    if not config.ELEVENLABS_VOICE_ID:
        raise EnvironmentError("Missing required environment variable: ELEVENLABS_VOICE_ID")

    formatted_text = _format_text_for_tts(text)
    if not formatted_text:
        raise ValueError("text for voice generation is empty")

    url = _API_URL.format(voice_id=config.ELEVENLABS_VOICE_ID)
    headers = {
        "xi-api-key": config.ELEVENLABS_API_KEY,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    }
    payload = {
        "text": formatted_text,
        "model_id": config.ELEVENLABS_MODEL_ID,
        "language_code": config.ELEVENLABS_LANGUAGE_CODE,
        "voice_settings": {
            "stability": config.ELEVENLABS_STABILITY,
            "similarity_boost": config.ELEVENLABS_SIMILARITY_BOOST,
            "style": config.ELEVENLABS_STYLE,
            "use_speaker_boost": config.ELEVENLABS_USE_SPEAKER_BOOST,
        },
    }

    logger.info(f"[generate_voice] post_id={post_id} requesting ElevenLabs")
    logger.info(f"[generate_voice] model_id={config.ELEVENLABS_MODEL_ID}")
    logger.info(f"[generate_voice] language_code={config.ELEVENLABS_LANGUAGE_CODE}")
    logger.info(f"[generate_voice] source_text=\n{text}")
    logger.info(f"[generate_voice] text_sent=\n{formatted_text}")
    res = requests.post(url, json=payload, headers=headers, timeout=120)
    if res.status_code != 200:
        raise RuntimeError(
            f"ElevenLabs API error: {res.status_code} {res.text[:200]}"
        )

    out_path = audio_path_for(post_id)
    with open(out_path, "wb") as f:
        f.write(res.content)

    if config.VOICE_LEAD_IN_SECONDS > 0:
        _add_lead_in_silence(out_path, config.VOICE_LEAD_IN_SECONDS)

    if abs(config.VOICE_PLAYBACK_SPEED - 1.0) > 0.001:
        _adjust_playback_speed(out_path, config.VOICE_PLAYBACK_SPEED)

    if abs(_VOICE_VOLUME_MULTIPLIER - 1.0) > 0.001:
        _adjust_volume(out_path, _VOICE_VOLUME_MULTIPLIER)

    if config.END_PADDING_SECONDS > 0:
        _add_tail_silence(out_path, config.END_PADDING_SECONDS)

    logger.info(f"[generate_voice] saved to {out_path}")
    return out_path


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

    import os
    os.replace(temp_path, audio_path)


def _adjust_playback_speed(audio_path: str, speed: float) -> None:
    temp_path = f"{audio_path}.speed.mp3"
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        audio_path,
        "-filter:a",
        _build_atempo_filter(speed),
        "-c:a",
        "libmp3lame",
        "-q:a",
        "2",
        temp_path,
    ]
    logger.info(f"[generate_voice] adjusting playback speed to {speed:.3f}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg atempo failed: {result.stderr[-500:]}")

    import os
    os.replace(temp_path, audio_path)


def _build_atempo_filter(speed: float) -> str:
    remaining = speed
    parts: list[str] = []
    while remaining > 2.0:
        parts.append("atempo=2.0")
        remaining /= 2.0
    while remaining < 0.5:
        parts.append("atempo=0.5")
        remaining /= 0.5
    parts.append(f"atempo={remaining:.3f}")
    return ",".join(parts)


def _add_tail_silence(audio_path: str, silence_seconds: float) -> None:
    temp_path = f"{audio_path}.tail.mp3"
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        audio_path,
        "-f",
        "lavfi",
        "-i",
        f"anullsrc=r=44100:cl=mono:d={silence_seconds}",
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
    logger.info(f"[generate_voice] adding tail silence {silence_seconds:.2f}s")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg tail silence failed: {result.stderr[-500:]}")

    import os
    os.replace(temp_path, audio_path)


def _adjust_volume(audio_path: str, volume_multiplier: float) -> None:
    temp_path = f"{audio_path}.volume.mp3"
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        audio_path,
        "-filter:a",
        f"volume={volume_multiplier:.3f}",
        "-c:a",
        "libmp3lame",
        "-q:a",
        "2",
        temp_path,
    ]
    logger.info(f"[generate_voice] adjusting volume to {volume_multiplier:.3f}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg volume failed: {result.stderr[-500:]}")

    import os
    os.replace(temp_path, audio_path)
