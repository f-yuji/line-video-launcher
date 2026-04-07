import requests

import config
from utils import setup_logger, audio_path_for

logger = setup_logger("voice_generator")

_API_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"

_MODEL_ID = "eleven_v3"

# v3 向け設定
# stability=0.5: ブレを抑えつつ自然な抑揚を保つ
# style=0.3: 適度な表現力を持たせ、文末の溜めや間を自然に出す
# similarity_boost=0.75: ボイスキャラを維持
_VOICE_SETTINGS = {
    "stability": 0.5,
    "similarity_boost": 0.75,
    "style": 0.3,
    "use_speaker_boost": True,
}


def generate_voice(post_id: str, script: str) -> str:
    """音声用テキスト（speech_text）から音声を生成し、ファイルパスを返す。

    - eleven_v3 は日本語漢字の読みを高精度で処理するため、
      過度なひらがな化は不要。speech_text は自然な漢字構成で渡す。
    - 改行は「、」に変換してイントネーションの寸断を防ぐ
    - language_code=ja を明示して日本語判定を強制する
    """
    if not config.ELEVENLABS_API_KEY:
        raise EnvironmentError("Missing required environment variable: ELEVENLABS_API_KEY")
    if not config.ELEVENLABS_VOICE_ID:
        raise EnvironmentError("Missing required environment variable: ELEVENLABS_VOICE_ID")

    # 改行を読点に変換（v3 は冒頭バッファ不要のため ... プレフィックスは外す）
    tts_text = script.lstrip().replace("\n", "、")

    url = _API_URL.format(voice_id=config.ELEVENLABS_VOICE_ID)
    headers = {
        "xi-api-key": config.ELEVENLABS_API_KEY,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    }
    payload = {
        "text": tts_text,
        "model_id": _MODEL_ID,
        "language_code": "ja",
        "voice_settings": _VOICE_SETTINGS,
    }

    logger.info(
        f"[generate_voice] post_id={post_id} "
        f"model={_MODEL_ID} "
        f"voice={config.ELEVENLABS_VOICE_ID}"
    )
    logger.info(f"[generate_voice] text_original=\n{script}")
    logger.info(f"[generate_voice] text_tts={tts_text!r}")

    res = requests.post(url, json=payload, headers=headers, timeout=120)

    if res.status_code != 200:
        raise RuntimeError(
            f"ElevenLabs API error: {res.status_code} {res.text[:200]}"
        )

    out_path = audio_path_for(post_id)
    with open(out_path, "wb") as f:
        f.write(res.content)

    logger.info(f"[generate_voice] saved to {out_path}")
    return out_path
