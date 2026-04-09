from dataclasses import dataclass

import config
from utils import setup_logger

logger = setup_logger("caption_generator_v2")


@dataclass
class CaptionResult:
    body_text: str
    x_text: str
    youtube_text: str
    tiktok_text: str
    instagram_text: str
    hashtags: str


_SYSTEM_PROMPT = """\
あなたは「詰み回避ラボ」の本文ライターです。
与えられた動画台本をもとに、まず本文をしっかり作ってください。
このアカウントでは動画内で「詰み回避は本文で。」と誘導しているため、
本文はただの要約ではなく、読みに来た人がちゃんと得する内容にしてください。

本文の最重要ルール:
- 構成は「陥りがちな間違い → 詳しい説明 → 対策や解決策」
- 本文を読めば、動画の続きや答えが分かる形にする
- ふわっとした一般論ではなく、損得や現実ベースで書く
- 「しっかり考えましょう」みたいな弱い締めは禁止
- 読者が次に何を意識すべきかまで書く
- トーンは動画と同じく、やや強めで本質を突く

BODY のルール:
- 220〜380字
- 冒頭で「何がよくある間違いか」を短く示す
- 中盤で「なぜ危ないのか」を具体的に説明する
- 終盤で「じゃあどうするべきか」を実務寄りに示す
- 箇条書きではなく、読み物として自然につなげる

他SNS欄のルール:
- X / YOUTUBE / TIKTOK / INSTAGRAM は BODY を短く要約したものにする
- 媒体ごとに無理にキャラを変えなくてよい
- 本文誘導の流れを壊さない
- YouTube は少し長め、X と TikTok は短めでよい

ハッシュタグのルール:
- 10〜15個
- テーマと投稿内容に合うものだけ
- 無理にバズワードを混ぜない

出力フォーマット（必ずこの形式で）:
---BODY---
（本文：220〜380字、「間違い→詳しい説明→対策」構成）
---X---
（X/Twitter用：140字以内、本文の要約）
---YOUTUBE---
（YouTube説明文：180〜320字、本文の要約）
---TIKTOK---
（TikTok用：60〜100字、本文の要約）
---INSTAGRAM---
（Instagram用：120〜220字、本文の要約）
---HASHTAGS---
（ハッシュタグのみ、スペース区切りで10〜15個）
"""


def _get_client():
    from openai import OpenAI

    if not config.OPENAI_API_KEY:
        raise EnvironmentError("Missing required environment variable: OPENAI_API_KEY")
    return OpenAI(api_key=config.OPENAI_API_KEY)


def generate_captions(video_script: str) -> CaptionResult:
    logger.info("[generate_captions] start")
    res = _get_client().chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": video_script},
        ],
        temperature=0.7,
        max_tokens=1200,
    )
    raw = res.choices[0].message.content.strip()
    logger.info("[generate_captions] done, parsing")
    return _parse_caption_output(raw)


def _parse_caption_output(raw: str) -> CaptionResult:
    def _extract(tag: str) -> str:
        start_marker = f"---{tag}---"
        start = raw.find(start_marker)
        if start == -1:
            return ""
        start += len(start_marker)
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
