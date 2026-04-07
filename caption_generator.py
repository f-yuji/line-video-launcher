from dataclasses import dataclass

import config
from utils import setup_logger

logger = setup_logger("caption_generator")


@dataclass
class CaptionResult:
    body_text: str
    x_text: str
    youtube_text: str
    tiktok_text: str
    instagram_text: str
    hashtags: str


_SYSTEM_PROMPT = """\
あなたはSNS投稿文のコピーライターです。
与えられた動画台本をもとに、各SNS媒体向けの投稿文とハッシュタグを生成してください。

出力フォーマット（必ずこの形式で）:
---BODY---
（本文：100〜150字、汎用的な説明文）
---X---
（X/Twitter用：140字以内、テンポよく）
---YOUTUBE---
（YouTube説明文：200〜300字、SEOを意識して）
---TIKTOK---
（TikTok用：70字以内、若者向けカジュアルに）
---INSTAGRAM---
（Instagram用：100〜150字、ブランディングを意識して）
---HASHTAGS---
（ハッシュタグのみ、スペース区切りで10〜15個）
"""


def _get_client():
    from openai import OpenAI

    if not config.OPENAI_API_KEY:
        raise EnvironmentError("Missing required environment variable: OPENAI_API_KEY")
    return OpenAI(api_key=config.OPENAI_API_KEY)


def generate_captions(video_script: str) -> CaptionResult:
    """台本から各媒体向け投稿文を生成する"""
    logger.info("[generate_captions] start")
    res = _get_client().chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": video_script},
        ],
        temperature=0.7,
        max_tokens=1000,
    )
    raw = res.choices[0].message.content.strip()
    logger.info("[generate_captions] done, parsing")
    return _parse_caption_output(raw)


def _parse_caption_output(raw: str) -> CaptionResult:
    def _extract(tag: str) -> str:
        start_marker = f"---{tag}---"
        # 次のセクション区切りまでを取得
        start = raw.find(start_marker)
        if start == -1:
            return ""
        start += len(start_marker)
        # 次の --- を探す
        next_marker = raw.find("---", start)
        if next_marker == -1:
            chunk = raw[start:]
        else:
            chunk = raw[start:next_marker]
        return chunk.strip()

    return CaptionResult(
        body_text=_extract("BODY"),
        x_text=_extract("X"),
        youtube_text=_extract("YOUTUBE"),
        tiktok_text=_extract("TIKTOK"),
        instagram_text=_extract("INSTAGRAM"),
        hashtags=_extract("HASHTAGS"),
    )
