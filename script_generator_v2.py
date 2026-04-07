from dataclasses import dataclass

import config
from utils import setup_logger

logger = setup_logger("script_generator_v2")

_SYSTEM_PROMPT = """\
あなたはショート動画の台本ライターです。
与えられたネタをもとに、表示用字幕と読み上げ用テキストを同時に作ってください。

ルール:
- 出力は必ず次の形式にする
---DISPLAY---
1行目
2行目
3行目
4行目
5行目
6行目
---SPEECH---
1行目
2行目
3行目
4行目
5行目
6行目

DISPLAY のルール:
- 必ず6行
- 各行は12〜24文字程度
- 1行に1つの意味だけを書く
- 聞いてすぐ分かる、やさしい話し言葉
- 難しい漢字や専門用語は避ける
- 1行目は興味を引く導入
- 最後の行は短い締め
- 行頭に番号や記号を付けない

SPEECH のルール:
- DISPLAY と同じ内容を、自然に読み上げやすい日本語に整える
- 必ず6行
- DISPLAY と同じ順番、同じ意味にする
- 1行ごとに、読み上げと字幕が一致するように作る
- 1行目を読んでいる間は字幕1行目、2行目を読んでいる間は字幕2行目になる構成にする
- 意味は DISPLAY から変えない
- 基本的には DISPLAY に近い表現を使う
- 漢字は無理にひらがなへ開かない
- 本当に誤読しやすいと判断できる語だけ、必要最小限でひらがなにする
- 言い換えは最小限にする
- 1行がそのまま自然に読める長さにする
- 行末に句点は付けなくてよい
- 読み上げで極端に不自然になりやすい語だけ、やさしい言い換えにしてよい
"""


@dataclass
class ScriptResult:
    display_lines: list[str]
    speech_lines: list[str]

    @property
    def display_text(self) -> str:
        return "\n".join(self.display_lines)

    @property
    def speech_text(self) -> str:
        return "\n".join(self.speech_lines)


def _get_client():
    from openai import OpenAI

    if not config.OPENAI_API_KEY:
        raise EnvironmentError("Missing required environment variable: OPENAI_API_KEY")
    return OpenAI(api_key=config.OPENAI_API_KEY)


def generate_script(raw_text: str) -> ScriptResult:
    logger.info(f"[generate_script] raw_text={raw_text[:50]!r}")
    res = _get_client().chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": raw_text},
        ],
        temperature=0.5,
        max_tokens=400,
    )
    raw = res.choices[0].message.content.strip()
    result = _parse_script_result(raw)
    logger.info(
        f"[generate_script] done display_lines={len(result.display_lines)} "
        f"speech_lines={len(result.speech_lines)}"
    )
    return result


def _parse_script_result(raw: str) -> ScriptResult:
    display_marker = "---DISPLAY---"
    speech_marker = "---SPEECH---"

    display_start = raw.find(display_marker)
    speech_start = raw.find(speech_marker)
    if display_start == -1 or speech_start == -1:
        raise ValueError("script output format invalid")

    display_chunk = raw[display_start + len(display_marker):speech_start].strip()
    speech_chunk = raw[speech_start + len(speech_marker):].strip()

    display_lines = [line.strip() for line in display_chunk.splitlines() if line.strip()]
    speech_lines = [line.strip() for line in speech_chunk.splitlines() if line.strip()]
    if len(display_lines) != 6:
        raise ValueError(f"expected 6 display lines, got {len(display_lines)}")
    if len(speech_lines) != 6:
        raise ValueError(f"expected 6 speech lines, got {len(speech_lines)}")

    return ScriptResult(
        display_lines=display_lines,
        speech_lines=speech_lines,
    )
