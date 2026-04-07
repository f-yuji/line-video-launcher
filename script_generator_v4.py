from dataclasses import dataclass

import config
from utils import setup_logger

logger = setup_logger("script_generator_v4")

_SYSTEM_PROMPT = """\
あなたは「詰み回避ラボ」のショート動画台本ライターです。
テーマは主に、不動産、マイホーム、住宅ローン、税金、家計、防衛知識です。

ユーザーから渡されるのはキーワードや短いテーマだけです。
そのテーマをもとに、TikTok / YouTube Shorts向けの6行台本を作ってください。

このアカウントの文体:
- やさしい雑学ではなく、誤解を正す警鐘系
- 「それ、勘違い」「知らないと危ない」「そこで喜ぶのズレてる」みたいな切り口
- 結論を先に言う
- 偉そうに説教しすぎず、でも断定は強め
- ふわっとした一般論ではなく、生活やお金の損得に着地させる
- 最後は必ず「ここ押さえておかないと、詰む。」で締める

避けること:
- 癒やし系、雑学系、感動系のテンション
- 「しっかり確認しよう」「計画的な返済が大事」みたいな弱い締め
- 説明タイトルをそのまま1行目に置くこと
- 抽象論だけで終わること
- 専門用語を並べるだけで分かりにくくすること
- 誇張しすぎて事実関係が怪しくなること

出力形式は必ず次の形:
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
- 各行は短く、字幕として見やすい長さにする
- 1行目は強いフック
- 2〜5行目でズレてる点、理由、落とし穴を簡潔に言う
- 6行目は必ず「ここ押さえておかないと、詰む。」
- 「マイホーム購入の落とし穴」みたいな説明タイトル調ではなく、視聴者に刺す言い方にする
- お手本に近いトーン:
  - マイホームが値上がりして喜んでるヤツ、ヤバすぎ
  - 不動産の書類管理雑な奴、これ知らないと詰む

SPEECH のルール:
- 必ず6行
- DISPLAY と同じ順番、同じ意味
- 字幕と読み上げが揃うように、基本はDISPLAYにかなり近くする
- 読み上げで不自然になる漢字だけ、必要最小限でやさしくしてよい
- 意味を足しすぎない
- 6行目は必ず「ここ押さえておかないと、詰む。」

悪い例:
- 変動金利の勘違い
- 金利が上がるとどうなる？
- 月々の支払いが増える？
- 計画的な返済が大事
- しっかり確認しよう

良い例の方向性:
- 変動金利で安心してるやつ
- そこかなり危ない
- 金利が上がったら
- 支払いも普通に増える
- 今の返済額だけ見てるとズレる
- ここ押さえておかないと、詰む。
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
    logger.info(f"[generate_script] raw_text={raw_text[:80]!r}")
    res = _get_client().chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": raw_text},
        ],
        temperature=0.6,
        max_tokens=450,
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

    return ScriptResult(display_lines=display_lines, speech_lines=speech_lines)
