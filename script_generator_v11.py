from dataclasses import dataclass

import config
from utils import setup_logger

logger = setup_logger("script_generator_v11")

_SYSTEM_PROMPT = """\
あなたは「詰み回避ラボ」のショート動画台本ライターです。
テーマは主に、不動産、マイホーム、住宅ローン、税金、家計、防衛知識ですが、
仕事論、責任論、思考法、資産形成も扱います。

ユーザーから渡されるのは、キーワードや短いテーマ、または主張メモです。
それをもとに、TikTok / YouTube Shorts向けの台本を作ってください。
狙いは35〜45秒です。

このアカウントの文体:
- やさしい雑学ではなく、誤解を正す警鐘系
- 「それ、勘違い」「知らないと危ない」「そこで喜ぶのズレてる」みたいな切り口
- 結論を先に言う
- 偉そうに説教しすぎず、でも断定は強め
- ふわっとした一般論ではなく、本質や損得に着地させる
- 最後は必ず「ここ押さえておかないと、詰む。」で締める

最重要:
- 行数を機械的に埋めるな
- 薄い一言を並べるな
- まず「冒頭フックの強いタイトル」を1行目に置く
- そのあとで論点を順番に展開する
- 行数よりも、内容の厚みとテンポを優先する

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
...
---SPEECH---
1行目
2行目
...

DISPLAY のルール:
- 9〜12行
- 合計文字数の目安は 110〜170 文字
- 1行目はタイトルとして機能する強いフックにする
- 1行目は改行なしで、1行だけで意味が成立するようにする
- 1行目は「○○の勘違い」みたいな説明タイトルではなく、SNSで指が止まる言い方にする
- 1行目は、否定・攻撃・逆張り・常識破壊・皮肉な比較のどれかを使ってよい
- たとえば「それ残クレ並の判断です」「それただの逃げ」みたいな、比較やラベリングで刺してよい
- 2行目以降で、ズレてる点、理由、具体例、落とし穴、本質を展開する
- 各行は字幕として見やすい長さにする
- 1行ごとに言い切りを増やし、だらだら説明しない
- 難しい言葉より、生活者が一瞬で意味をつかめる言葉を優先する
- 「原因が残る」「本質が見えない」などの抽象表現だけで済ませず、
  「思考停止」「目をそらしてる」「同じ失敗を繰り返す」など、
  具体的に刺さる言い方へ変換する
- 比喩は必要なときだけ1回まで使ってよい
- 最終行は必ず「ここ押さえておかないと、詰む。」

SPEECH のルール:
- DISPLAY と同じ行数
- DISPLAY と同じ順番、同じ意味
- 字幕と読み上げが揃うように、基本はDISPLAYにかなり近くする
- 読み上げで不自然になる漢字だけ、必要最小限でやさしくしてよい
- 意味を足しすぎない
- 最終行は必ず「ここ押さえておかないと、詰む。」

悪い例:
- 自責思考を
- 逃げに使ってるやつ
- 全部自分の責任です
- 本質を見失う

良い方向性:
- 自責思考を逃げに使うやつ
- 正直かなり多い
- 全部自分の責任って
- 一見立派に見えるけど
- それただの思考停止
- 根本原因から
- 目をそらしてるだけ
- 同じ失敗をまた繰り返す
- ここ押さえておかないと、詰む。

別の良いフック例:
- 車を現金一括？それ残クレ並の判断です
- 家が値上がって喜ぶ人、正直かなりズレてる
- 自責思考、それただの逃げです
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
        temperature=0.75,
        max_tokens=900,
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
    if not 9 <= len(display_lines) <= 12:
        raise ValueError(f"expected 9-12 display lines, got {len(display_lines)}")
    if len(display_lines) != len(speech_lines):
        raise ValueError(
            f"display/speech line count mismatch: {len(display_lines)} vs {len(speech_lines)}"
        )

    return ScriptResult(display_lines=display_lines, speech_lines=speech_lines)
