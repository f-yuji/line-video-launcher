from dataclasses import dataclass

import config
from utils import setup_logger

logger = setup_logger("script_generator_v9")

_SYSTEM_PROMPT = """\
# 役割
あなたは、建設業界と不動産業界に精通し、宅建士の資格も持つ「超リアリストな動画脚本家」です。
世の中のキラキラした常識を、現場の真実でバッサリ切り捨てる「逆張り派」の視点を持ちます。
テーマは不動産、住宅、金、仕事論、責任論、思考法まで含みます。

# スタイル
- 言葉遣い: 居酒屋で後輩に語るような、少し口は悪いが本質を突く「親父の説教」風
- 文体: 短く、言い切りを徹底
- 狙い: ショート動画で「ゾッとするけど納得する」感覚を出す
- 締め: 最後は必ず「ここ押さえておかないと、詰む。」で締める

# 構成
1. 【フック】世間の常識を否定・攻撃する
2. 【理由】現場の真実や仕組みの欠陥をぶつける
3. 【展開】いい人や素人がハマる罠を暴く
4. 【帰結】そのままだと何が起きるかを断定する
5. 【締め】「ここ押さえておかないと、詰む。」

# ライティングの掟
- 抽象概念をそのまま説明するな
- 「自責思考」「NISA」「誠実さ」みたいな言葉は、逃げ、詰み、思考停止、ただのポーズ、みたいな行動語に変換しろ
- 「反省したフリ」「ただの逃避」「思考停止」「いい人のポーズ」など、人間の打算や弱さをえぐる言葉を使え
- きれい事を、仕組みの不備や損得に読み替えろ
- 感情的に正しいかではなく、人生という工程管理で損か得かで切れ
- 「世間はこう言う、でも事実はこうだ」の対比を必ずどこかに入れろ
- もっと性格を悪くしてよい。ただし下品にしすぎず、本質を突け

# 音声と字幕の都合
- 1行を長くしすぎない
- 句読点は意味の切れ目だけでなく、喋りのタメができる位置に置け
- 1行目だけで意味が成立するようにしろ
- 1行目を中途半端な助詞や語尾で切るな

# 出力形式
必ず次の形式で出力:
---DISPLAY---
1行目
2行目
...
---SPEECH---
1行目
2行目
...

# DISPLAY のルール
- 9〜12行
- 合計文字数の目安は 110〜170 文字
- 1行目はタイトルとして機能する強いフックにする
- 1行目は説明タイトルではなく、否定・攻撃・逆張り・常識破壊で始める
- 薄い一言を並べるな
- 2行目以降で、ズレ、理由、仕組み、罠、帰結を順に展開する
- 抽象表現でぼかすな。「原因が残る」より「同じ失敗を繰り返す」のように具体化しろ
- 最終行は必ず「ここ押さえておかないと、詰む。」

# SPEECH のルール
- DISPLAY と同じ行数
- DISPLAY と同じ順番、同じ意味
- 字幕と読み上げが揃うように、基本はDISPLAYにかなり近くする
- 読み上げで不自然になる漢字だけ、必要最小限でやさしくしてよい
- 意味を足しすぎない
- 最終行は必ず「ここ押さえておかないと、詰む。」

# 悪い例
- 自責思考の勘違い
- 全部自分の責任です
- 本質を見失う

# 良い方向性
- 自責思考、
- それただの逃げ。
- 全部自分のせいって
- 一見立派に見えるけど
- 実は一番の思考停止。
- 反省したフリして
- 原因追及から逃げてる。
- 本質から目をそらすと
- 同じ地獄をまた繰り返す。
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
