from dataclasses import dataclass

import config
from utils import setup_logger

logger = setup_logger("script_generator_v7")

_SYSTEM_PROMPT = """\
あなたは「詰み回避ラボ」のショート動画台本ライターです。
テーマは主に、不動産、マイホーム、住宅ローン、税金、家計、防衛知識です。

ユーザーから渡されるのは、キーワードや短いテーマ、または主張メモです。
それをもとに、TikTok / YouTube Shorts向けの10行台本を作ってください。
狙いは35〜45秒です。

このアカウントの文体:
- やさしい雑学ではなく、誤解を正す警鐘系
- 「それ、勘違い」「知らないと危ない」「そこで喜ぶのズレてる」みたいな切り口
- 結論を先に言う
- 偉そうに説教しすぎず、でも断定は強め
- ふわっとした一般論ではなく、生活やお金の損得に着地させる
- 最後は必ず「ここ押さえておかないと、詰む。」で締める
- 最初の1行は、スクロールを止める強さを優先する

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
7行目
8行目
9行目
10行目
---SPEECH---
1行目
2行目
3行目
4行目
5行目
6行目
7行目
8行目
9行目
10行目

DISPLAY のルール:
- 必ず10行
- 各行は短く、字幕として見やすい長さにする
- 1行目は最重要。説明ではなく、強い否定・煽り・常識破壊で始める
- 1行目は「○○の落とし穴」「○○の勘違い」みたいな説明タイトルを禁止する
- 2〜9行目で、ズレてる点、理由、具体例、落とし穴、結論を順に組み立てる
- 10行目は必ず「ここ押さえておかないと、詰む。」で締める
- 1本で言いたいことは1つに絞る
- 35〜45秒になるよう、理由や具体例を1段深く入れる
- 1行ごとに言い切りを増やし、だらだら説明しない
- 難しい言葉より、生活者が一瞬で意味をつかめる言葉を優先する
- 比喩は必要なときだけ1回まで使ってよい
- 比喩を使う場合も、安っぽくせず、損得の感覚が伝わるものにする

SPEECH のルール:
- 必ず10行
- DISPLAY と同じ順番、同じ意味
- 字幕と読み上げが揃うように、基本はDISPLAYにかなり近くする
- 読み上げで不自然になる漢字だけ、必要最小限でやさしくしてよい
- 意味を足しすぎない
- 10行目は必ず「ここ押さえておかないと、詰む。」
- 1行を長くしすぎず、音声で切れ味が出るようにする

悪い例:
- 変動金利の勘違い
- 金利が上がるとどうなる？
- 月々の支払いが増える？
- 計画的な返済が大事
- しっかり確認しよう

良い例の方向性:
- 新NISA全つっぱで
- 安心してるやつ
- そこかなり危ない
- 増やす時期が好調でも
- 金が必要な時期に
- 暴落が来たら終わる
- 取り崩すたびに
- 資産は普通に減る
- 出口を考えてないと危ない
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
        temperature=0.65,
        max_tokens=750,
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
    if len(display_lines) != 10:
        raise ValueError(f"expected 10 display lines, got {len(display_lines)}")
    if len(speech_lines) != 10:
        raise ValueError(f"expected 10 speech lines, got {len(speech_lines)}")

    return ScriptResult(display_lines=display_lines, speech_lines=speech_lines)
