from dataclasses import dataclass

import config
from utils import setup_logger

logger = setup_logger("caption_generator_v4")


@dataclass
class CaptionResult:
    body_text: str
    x_text: str
    youtube_text: str
    tiktok_text: str
    instagram_text: str
    hashtags: str
    generated_hashtags: str


DEFAULT_FIXED_HASHTAGS = [
    "#詰み回避ラボ",
]


_SYSTEM_PROMPT = """\
あなたは「詰み回避ラボ」の投稿文ライターだ。
毒舌で本質を突く。優等生な文章は書くな。
動画台本をもとに、各セクションを生成しろ。

【全セクション共通ルール】
- 同じ単語・表現はBODY・X・YOUTUBE・TIKTOK・INSTAGRAM・HASHTAGSを通じて重複させるな
- 「しっかり考えましょう」「見直しましょう」「備えておきましょう」等の弱い締めは全禁止
- 締めは必ず行動強制か危機感で終わらせろ
- 「だ」「だろう」「〜してる時点でアウト」「〜が一番危ない」等の言い切りを混ぜろ
- ただ煽るだけで終わるな。読者が「その手があったか」と思う盲点の対策や見方を必ずどこかに入れろ
- 対策はテンプレ正論ではなく、実際に使える判断軸・見方・行動にする

【BODY】
- 220～380字
- 構成：「よくある勘違い → なぜ危ないか → 今すぐやるべきこと」
- 冒頭で勘違いや落とし穴を短く断言する
- 中盤で損失・リスクを具体的な数字や状況で示す
- 終盤は「じゃあどうするか」を実務レベルで書く
- 終盤には「その手があったか」と思わせる盲点の対策・判断軸・見方を最低1つ入れる
- 箇条書きにせず、読み物として自然につなげる
- 最後は強い行動喚起か警告で締める

【X】
- 140字以内
- 1行目は強い結論か警告から始める
- 「・」で2～4個の箇条書き
- 箇条書きのうち最低1個は「その手があったか」と思う盲点や対策にする
- BODYと同じ言い回しは使うな。別の角度で刺せ
- 最後は短く強く締める

【YOUTUBE】
- 180～320字
- BODYとは異なる切り口で書く
- 検索を意識して具体的なキーワードを自然に含める
- 単なる要約ではなく、本文で回収したくなる実務的な視点を1つ入れる

【TIKTOK】
- 60～100字
- 若い読者が一瞬で「ヤバい」と思う書き方
- BODYやXの言い回しと被らせるな
- 短くても、盲点や対策の匂いを1つ入れる

【INSTAGRAM】
- 120～220字
- 共感から入って危機感で終わる流れ
- 他セクションと表現を変えること
- 保存したくなる実務的な気づきや対策を1つ入れる

【HASHTAGS】
以下2種類を必ず混ぜて4～7個生成しろ。

王道タグ（検索流入用）:
動画テーマに直結する一般名詞系。例：#住宅ローン #不動産売却 #固定資産税 #マイホーム

感情タグ（バズ・停止率用）:
視聴者の不安・後悔・怒りに刺さる言葉。例：#知らないと損 #人生の落とし穴 #後悔しない家づくり #住宅ローンの闇

ルール:
- 真面目すぎる管理系タグ（#書類管理 等）は避ける
- テーマと無関係な汎用タグは入れるな
- タグ同士で同じ単語を繰り返すな

出力フォーマット（必ずこの形式で）:
---BODY---
（本文：220～380字）
---X---
（140字以内、箇条書きベース）
---YOUTUBE---
（180～320字）
---TIKTOK---
（60～100字）
---INSTAGRAM---
（120～220字）
---HASHTAGS---
（スペース区切りで4～7個）
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


def merge_manual_hashtags(result: CaptionResult, manual_hashtags: list[str]) -> CaptionResult:
    merged_hashtags = _merge_hashtags(" ".join([*manual_hashtags, result.generated_hashtags]).strip())
    return CaptionResult(
        body_text=result.body_text,
        x_text=result.x_text,
        youtube_text=result.youtube_text,
        tiktok_text=result.tiktok_text,
        instagram_text=result.instagram_text,
        hashtags=merged_hashtags,
        generated_hashtags=result.generated_hashtags,
    )


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

    generated_hashtags = _extract("HASHTAGS")
    final_hashtags = _merge_hashtags(generated_hashtags)
    formatted_body = _format_body_text(_extract("BODY"))
    raw_x = _extract("X")
    formatted_x = _format_social_text(raw_x) if raw_x else _format_social_text(formatted_body)
    formatted_youtube = _format_social_text(_extract("YOUTUBE"))
    formatted_instagram = _format_social_text(_extract("INSTAGRAM"))
    formatted_tiktok = formatted_instagram

    return CaptionResult(
        body_text=formatted_body,
        x_text=formatted_x,
        youtube_text=formatted_youtube,
        tiktok_text=formatted_tiktok,
        instagram_text=formatted_instagram,
        hashtags=final_hashtags,
        generated_hashtags=generated_hashtags,
    )


def _merge_hashtags(generated_hashtags: str) -> str:
    merged: list[str] = []
    seen: set[str] = set()

    for tag in DEFAULT_FIXED_HASHTAGS + _split_hashtags(generated_hashtags):
        normalized = _normalize_hashtag(tag)
        if not normalized:
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        merged.append(normalized)

    return " ".join(merged[:8])


def _split_hashtags(value: str) -> list[str]:
    parts = value.replace("\n", " ").replace("、", " ").replace(",", " ").split()
    return [part.strip() for part in parts if part.strip()]


def _normalize_hashtag(tag: str) -> str:
    cleaned = tag.strip()
    if not cleaned:
        return ""
    if not cleaned.startswith("#"):
        cleaned = "#" + cleaned.lstrip("#")
    return cleaned


def _format_body_text(text: str) -> str:
    text = (text or "").strip()
    if not text:
        return text

    normalized = text.replace("\r\n", "\n")
    if "\n" in normalized:
        paragraphs = [part.strip() for part in normalized.split("\n") if part.strip()]
        return "\n\n".join(paragraphs)

    sentences = []
    current = ""
    for ch in normalized:
        current += ch
        if ch in "。！？":
            sentence = current.strip()
            if sentence:
                sentences.append(sentence)
            current = ""
    if current.strip():
        sentences.append(current.strip())

    if not sentences:
        return normalized

    paragraphs: list[str] = []
    current_group: list[str] = []
    transition_markers = ("でも", "ただ", "むしろ", "だから", "じゃあ", "つまり", "結局", "ここで")

    for sentence in sentences:
        if current_group and (
            len(current_group) >= 2 or
            sentence.startswith(transition_markers)
        ):
            paragraphs.append("".join(current_group))
            current_group = []
        current_group.append(sentence)

    if current_group:
        paragraphs.append("".join(current_group))

    if paragraphs:
        last = paragraphs[-1]
        if "今すぐ" in last or "詰む" in last or "危ない" in last:
            tail_sentences = []
            current = ""
            for ch in last:
                current += ch
                if ch in "。！？":
                    tail_sentences.append(current.strip())
                    current = ""
            if current.strip():
                tail_sentences.append(current.strip())
            if len(tail_sentences) >= 2:
                paragraphs[-1] = "".join(tail_sentences[:-1]).strip()
                paragraphs.append(tail_sentences[-1].strip())
                paragraphs = [p for p in paragraphs if p]

    return "\n\n".join(paragraphs)


def _format_social_text(text: str) -> str:
    text = (text or "").strip()
    if not text:
        return text

    normalized = text.replace("\r\n", "\n")
    if "\n" in normalized:
        paragraphs = [part.strip() for part in normalized.split("\n") if part.strip()]
        return "\n".join(paragraphs)

    if "・" in normalized:
        parts = [part.strip() for part in normalized.split("・") if part.strip()]
        if len(parts) >= 2:
            head = parts[0]
            bullets = [f"・{part}" for part in parts[1:]]
            return "\n".join([head, *bullets])

    sentences = []
    current = ""
    for ch in normalized:
        current += ch
        if ch in "。！？":
            sentence = current.strip()
            if sentence:
                sentences.append(sentence)
            current = ""
    if current.strip():
        sentences.append(current.strip())

    if len(sentences) <= 1:
        return normalized

    lines: list[str] = []
    current_line = ""
    transition_markers = ("でも", "ただ", "むしろ", "だから", "じゃあ", "つまり", "結局", "今すぐ")

    for sentence in sentences:
        should_break = (
            bool(current_line)
            and (
                len(current_line) >= 36
                or sentence.startswith(transition_markers)
            )
        )
        if should_break:
            lines.append(current_line.strip())
            current_line = sentence
        else:
            current_line += sentence

    if current_line.strip():
        lines.append(current_line.strip())

    return "\n".join(lines)
