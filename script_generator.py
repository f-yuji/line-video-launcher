from dataclasses import dataclass

import config
from utils import setup_logger

logger = setup_logger("script_generator")


@dataclass
class ScriptResult:
    display_text: str  # 字幕用（漢字あり、6行改行区切り）
    speech_text: str   # 音声用（難読漢字をひらがな混じりに変換、6行改行区切り）


_SYSTEM_PROMPT = """\
あなたはショート動画の台本ライターです。
与えられたネタをもとに、縦型ショート動画用の台本を2種類出力してください。

【共通ルール】
- 必ず6行で構成すること
- 各行は短く（12〜24文字程度）、音声で聞き取りやすい長さにすること
- 自然な話し言葉で書くこと
- 行頭に番号や記号を付けないこと
- 各行を改行で区切ること
- 1行目は興味を引く導入にすること
- 最後の行は短い締めにすること

【出力フォーマット（必ずこの形式で出力すること）】
---DISPLAY---
（字幕表示用: 漢字を使って見栄えよく書くこと）
---SPEECH---
（音声合成用: ElevenLabs eleven_v3 向けに自然な日本語で出力すること）
（・基本的に自然な漢字・かな混じり文でよい。eleven_v3 は漢字の読みを高精度で処理できる）
（・「焚き火」「雰囲気」のような複合語や難読語だけ、ひらがな混じりにすること。例: 焚き火→たき火、施工→せこう）
（・読点「、」と句点「。」を自然な位置に入れてイントネーションを安定させること）
（・カタカナ語はそのまま使ってよい）
（・余計な説明不要。台本本文のみ出力すること）
"""


def _get_client():
    from openai import OpenAI

    if not config.OPENAI_API_KEY:
        raise EnvironmentError("Missing required environment variable: OPENAI_API_KEY")
    return OpenAI(api_key=config.OPENAI_API_KEY)


def _parse(raw: str) -> ScriptResult:
    def extract(tag: str) -> str:
        marker = f"---{tag}---"
        start = raw.find(marker)
        if start == -1:
            return ""
        start += len(marker)
        next_marker = raw.find("---", start)
        chunk = raw[start:next_marker] if next_marker != -1 else raw[start:]
        return chunk.strip()

    display = extract("DISPLAY")
    speech = extract("SPEECH")

    # パース失敗時は同じテキストを両方に使う
    if not display:
        display = raw.strip()
    if not speech:
        speech = display

    return ScriptResult(display_text=display, speech_text=speech)


def generate_script(raw_text: str) -> ScriptResult:
    """raw_text から動画台本を生成する。display_text と speech_text を返す。"""
    logger.info(f"[generate_script] raw_text={raw_text[:50]!r}")
    res = _get_client().chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": raw_text},
        ],
        temperature=0.7,
        max_tokens=800,
    )
    raw = res.choices[0].message.content.strip()
    result = _parse(raw)
    logger.info(
        f"[generate_script] done "
        f"display_lines={len(result.display_text.splitlines())} "
        f"speech_lines={len(result.speech_text.splitlines())}"
    )
    logger.info(f"[generate_script] display=\n{result.display_text}")
    logger.info(f"[generate_script] speech=\n{result.speech_text}")
    return result
