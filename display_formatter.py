"""
表示専用整形レイヤー。
文節チャンクベースの改行で字幕・フックの品質を安定化する。

設計方針:
- 助詞の「後ろ」で切る（助詞を行頭に置かない）
- 文節単位を崩さない
- 1文字行・助詞単独行を禁止
- 動詞途中分割を避ける
"""
import re

# 助詞1文字（これで終わるチャンクの後ろが自然な改行位置）
_BREAK_AFTER_1 = frozenset("のはがをにとでもへやか")

# 助詞・接続語2文字（これで終わるチャンクの後ろも自然な改行位置）
_BREAK_AFTER_2 = frozenset({
    "から", "まで", "より", "けど", "ので", "だが",
    "ても", "でも", "たら", "なら", "には", "では",
    "とは", "には", "では", "には",
})

# 行頭禁則文字（これが行頭に来てはいけない）
_KINSOKU_START = frozenset(
    "のはがをにとでもへやかっッょゅぁぃぅぇぉんンーっ。、！？…―"
)

# 条件節を示す末尾文字（行3の境界になる）※「に」は除外（方向・場所のにが多い）
_CONDITION_CHARS = frozenset("とば")
_CONDITION_2 = frozenset({"たら", "なら", "ので", "けど"})

# 「と」の前に来やすい動詞・形容詞語尾（これ以外は条件のとと見なさない）
_VERB_ENDINGS_BEFORE_TO = frozenset("すくむつぬるいなきわれせしてでぐ")

# 複合語リスト（これらの内部では改行しない）
_COMPOUND_WORDS = [
    "住宅ローン", "固定資産税", "不動産取得税", "マイホーム",
    "火災保険", "権利証", "修繕積立金", "管理費用",
    "団体信用", "変動金利", "固定金利",
]

# 話題・主題の末尾文字（行1の境界になる）
_TOPIC_CHARS = frozenset("のがはもを")

# 文末語尾の除去パターン
_STRIP_ENDINGS = re.compile(
    r"(だ|です|ます|だよ|だぞ|だね|だわ|である|ですね|ですよ|だろう|だろ|だけど)$"
)


# ──────────────────────────────────────────────
# 文節チャンク分割
# ──────────────────────────────────────────────

def _to_chunks(text: str) -> list[str]:
    """
    テキストを文節ライクなチャンクに分割する。
    助詞・接続語の「後ろ」でチャンクを切る。
    例: "マイホームの書類なくすと地獄だ"
        → ["マイホームの", "書類なくすと", "地獄だ"]
    """
    chunks: list[str] = []
    current = ""
    i = 0
    n = len(text)

    while i < n:
        # 複合語チェック（複合語を1チャンクとして切り出す）
        _compound_found = False
        for w in _COMPOUND_WORDS:
            wlen = len(w)
            if text[i:i + wlen] == w:
                if current:
                    chunks.append(current)
                    current = ""
                chunks.append(w)
                i += wlen
                _compound_found = True
                break
        if _compound_found:
            continue

        # 2文字の区切り語チェック
        if i + 1 < n and text[i:i + 2] in _BREAK_AFTER_2:
            current += text[i:i + 2]
            chunks.append(current)
            current = ""
            i += 2
            continue

        current += text[i]

        # 句読点の後は必ず切る
        if text[i] in "。、！？!?":
            chunks.append(current)
            current = ""

        # 助詞の後で切れる（次の文字が助詞でなければ）
        elif text[i] in _BREAK_AFTER_1:
            next_ch = text[i + 1] if i + 1 < n else ""
            # 「とし」は動詞継続形の一部（落とし穴、〜として等）→ 切らない
            if text[i] == "と" and next_ch == "し":
                pass
            elif next_ch not in _BREAK_AFTER_1:
                chunks.append(current)
                current = ""

        i += 1

    if current:
        chunks.append(current)

    return [c for c in chunks if c]


# ──────────────────────────────────────────────
# 字幕整形
# ──────────────────────────────────────────────

def format_subtitle(text: str, max_chars: int = 12) -> str:
    """
    字幕テキストを最大2行・1行max_chars文字に整形する。
    - 文節チャンク単位で改行
    - 助詞行頭禁止
    - 2行目が長すぎる場合は切り詰め
    """
    text = text.strip()
    if not text:
        return text
    if len(text) <= max_chars:
        return text

    chunks = _to_chunks(text)
    lines = _pack_chunks(chunks, max_chars, max_lines=2)

    if not lines:
        # フォールバック: 強制的に max_chars で切る
        return text[:max_chars * 2]

    if len(lines) > 1 and len(lines[1]) > max_chars:
        lines[1] = _truncate_at_boundary(lines[1], max_chars)

    return "\n".join(lines)


def _pack_chunks(chunks: list[str], max_chars: int, max_lines: int) -> list[str]:
    """チャンクを max_chars 制約で行に詰める（貪欲法）"""
    lines: list[str] = []
    current = ""

    for chunk in chunks:
        if len(lines) >= max_lines:
            break
        if len(current + chunk) <= max_chars:
            current += chunk
        else:
            if current:
                lines.append(current)
            # 1チャンクが max_chars を超える場合はそのまま入れる
            current = chunk

    if current and len(lines) < max_lines:
        lines.append(current)

    return lines


def _truncate_at_boundary(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    # 句読点で切れる位置を探す
    for marker in ("。", "、", "！", "？"):
        pos = text.rfind(marker, 0, max_chars + 1)
        if pos > 0:
            return text[:pos + 1]
    return text[:max_chars]


# ──────────────────────────────────────────────
# フック整形（3行: 対象 / 問題提起 / 結論）
# ──────────────────────────────────────────────

def format_hook(text: str) -> str:
    """
    フックテキストを3行構成に整形する。
    1行目: 対象（名詞句）
    2行目: 問題提起（条件・動作）
    3行目: 結論・感情ワード

    例: "マイホームの書類なくすと地獄だ"
        → "マイホームの\n書類なくすと\n地獄"
    """
    text = _STRIP_ENDINGS.sub("", text.strip()).strip()
    if not text:
        return text

    chunks = _to_chunks(text)

    result = _semantic_hook_split(chunks)
    if result:
        line1, line2, line3 = result
    else:
        line1, line2, line3 = _balanced_three_split(text)

    # 1文字行があれば再フォールバック
    if any(len(p) <= 1 for p in (line1, line2, line3)):
        line1, line2, line3 = _balanced_three_split(text)

    return f"{line1}\n{line2}\n{line3}"


def format_hook_lines(text: str) -> list[str]:
    """format_hook の結果をリストで返す（thumbnail_generator用）"""
    return format_hook(text).splitlines()


def _semantic_hook_split(chunks: list[str]) -> tuple[str, str, str] | None:
    """
    チャンクから意味的3分割を試みる。
    失敗時は None を返す。
    """
    n = len(chunks)
    if n < 3:
        return None

    # ── Step1: 結論ブロック（line3）の開始位置を後ろから探す ──
    # 条件助詞（と/ば等）で終わるチャンクの次がline3
    # 結論部分が長すぎる場合は条件助詞と見なさない
    result_start = None
    for i in range(n - 1, 0, -1):
        chunk = chunks[i - 1]
        if not chunk:
            continue

        remaining_text = "".join(chunks[i:])
        # 結論が長すぎる（8文字超）なら条件節の境界ではない
        if len(remaining_text) > 8:
            continue

        # 2文字条件語（たら/なら/ので等）
        if len(chunk) >= 2 and chunk[-2:] in _CONDITION_2:
            result_start = i
            break

        # 「と」: 直前が動詞・形容詞語尾の場合のみ条件の「と」と判断
        if chunk[-1] == "と":
            prev_ch = chunk[-2] if len(chunk) >= 2 else ""
            if prev_ch in _VERB_ENDINGS_BEFORE_TO:
                result_start = i
                break

        # 「ば」: 無条件で条件助詞として扱う
        if chunk[-1] == "ば":
            result_start = i
            break

    if result_start is None or result_start >= n:
        return None

    # ── Step2: 話題ブロック（line1）の終了位置を前から探す ──
    # の/が/は/も/を で終わるチャンクの次がline2の始まり
    topic_end = None
    for i in range(min(result_start, n)):
        chunk = chunks[i]
        if not chunk:
            continue
        if chunk[-1] in _TOPIC_CHARS:
            topic_end = i + 1
            break

    if topic_end is None:
        topic_end = max(1, result_start // 2)

    if topic_end >= result_start:
        return None

    line1 = "".join(chunks[:topic_end])
    line2 = "".join(chunks[topic_end:result_start])
    line3 = "".join(chunks[result_start:])

    if not line1 or not line2 or not line3:
        return None
    if any(len(p) <= 1 for p in (line1, line2, line3)):
        return None

    return line1, line2, line3


def _balanced_three_split(text: str) -> tuple[str, str, str]:
    """
    禁則を守りながら文字数均等で3分割する（フォールバック）。
    """
    n = len(text)
    best_score: float | None = None
    best = (max(1, n // 3), max(2, (n * 2) // 3))

    for i in range(2, n - 2):
        for j in range(i + 2, n):
            p1 = text[:i]
            p2 = text[i:j]
            p3 = text[j:]
            if not p1 or not p2 or not p3:
                continue
            if len(p1) <= 1 or len(p2) <= 1 or len(p3) <= 1:
                continue

            lengths = [len(p1), len(p2), len(p3)]
            score = (max(lengths) - min(lengths)) + sum(
                abs(l - n / 3) for l in lengths
            )

            # 行頭禁則ペナルティ
            if text[i] in _KINSOKU_START:
                score += 5.0
            if text[j] in _KINSOKU_START:
                score += 5.0

            # 複合語途中分割ペナルティ
            for _w in _COMPOUND_WORDS:
                _wlen = len(_w)
                _pos = 0
                while True:
                    _wp = text.find(_w, _pos)
                    if _wp == -1:
                        break
                    _we = _wp + _wlen
                    if _wp < i < _we:
                        score += 15.0
                    if _wp < j < _we:
                        score += 15.0
                    _pos = _wp + 1

            # 助詞の後で切れるボーナス
            if text[i - 1] in _BREAK_AFTER_1:
                score -= 2.0
            if text[j - 1] in _BREAK_AFTER_1:
                score -= 2.0

            if best_score is None or score < best_score:
                best_score = score
                best = (i, j)

    i, j = best
    return text[:i].strip(), text[i:j].strip(), text[j:].strip()
