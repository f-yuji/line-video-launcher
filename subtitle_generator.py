import os

from utils import setup_logger, get_audio_duration, subtitle_path_for

logger = setup_logger("subtitle_generator")

_PLAY_RES_X = 1080
_PLAY_RES_Y = 1920

# PlayResY=1920 でのベースフォントサイズ
# force_style FontSize=14 at libass PlayResY=288 と等価: 14 * 1920/288 = 93
_BASE_FONT_SIZE = 93

# 高インパクト単語 → 赤 (&HAABBGGRR 形式: AA=00=不透明, BGR=0000FF=赤)
_NG_HIGH = {"詰む", "地獄", "大損", "破産", "破綻", "終わり", "最悪", "死ぬ"}
# 中インパクト単語 → 黄 (FFFF=黄)
_NG_MED = {"損", "逃げ", "無意味", "カモ", "税金", "罠", "失敗", "危険", "怖い", "悲惨", "返済不能"}

# 重要単語ホールド（表示時間 +0.3 秒）
_IMPACT_WORDS = _NG_HIGH | _NG_MED
_IMPACT_HOLD = 0.3


def generate_srt(post_id: str, script: str, audio_path: str) -> str:
    """台本と音声から ASS ファイルを生成し、ファイルパスを返す。

    関数名は generate_srt のまま（worker.py との互換性維持）。
    出力は .ass 形式で、NG単語カラーリングと可変フォントサイズを含む。
    """
    lines = [line.strip() for line in script.splitlines() if line.strip()]
    if not lines:
        raise ValueError("script is empty")

    duration = get_audio_duration(audio_path)
    logger.info(f"[generate_srt] post_id={post_id} lines={len(lines)} duration={duration:.2f}s")

    ass_content = _build_ass(lines, duration)
    out_path = subtitle_path_for(post_id)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(ass_content)

    logger.info(f"[generate_srt] saved to {out_path}")
    return out_path


def _build_ass(lines: list[str], total_duration: float) -> str:
    n = len(lines)
    base_interval = total_duration / n

    # 重要単語ホールド: 対象行に +0.3秒、他の行から均等に借りる
    bonuses = [_IMPACT_HOLD if _has_impact(line) else 0.0 for line in lines]
    total_bonus = sum(bonuses)
    non_impact_count = sum(1 for b in bonuses if b == 0.0) or n
    deduct = total_bonus / non_impact_count

    durations = []
    for bonus in bonuses:
        dur = base_interval + bonus - (0.0 if bonus > 0 else deduct)
        durations.append(max(dur, 0.5))

    header = (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        f"PlayResX: {_PLAY_RES_X}\n"
        f"PlayResY: {_PLAY_RES_Y}\n"
        "WrapStyle: 2\n"
        "\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
        "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Default,Yu Gothic,{_BASE_FONT_SIZE},"
        "&H00FFFFFF,&H00FFFFFF,&H00000000,&HFF000000,"
        "-1,0,0,0,100,100,0,0,4,3,1,2,60,60,120,1\n"
        "\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )

    dialogues = []
    elapsed = 0.0
    for i, (line, dur) in enumerate(zip(lines, durations)):
        start = elapsed
        end = elapsed + dur
        if i == n - 1:
            end = min(end, total_duration - 0.1)

        wrapped = _wrap_line(line)
        escaped = _escape_ass(wrapped)
        tags = _color_tag(line)

        if i == 0:
            fs = _first_line_fontsize(line)
            if fs != _BASE_FONT_SIZE:
                tags = f"{{\\fs{fs}}}" + tags

        dialogues.append(
            f"Dialogue: 0,{_ass_time(start)},{_ass_time(end)},Default,,0,0,0,,{tags}{escaped}"
        )
        elapsed += dur

    return header + "\n".join(dialogues) + "\n"


def _has_impact(line: str) -> bool:
    return any(w in line for w in _IMPACT_WORDS)


def _color_tag(line: str) -> str:
    if any(w in line for w in _NG_HIGH):
        return r"{\c&H000000FF&}"   # 赤
    if any(w in line for w in _NG_MED):
        return r"{\c&H0000FFFF&}"   # 黄
    return ""


def _first_line_fontsize(text: str) -> int:
    """文字数が少ないほどフォントを大きくする（最大140、最小=BASE）"""
    chars = len(text.replace("\\N", "").replace(" ", "").replace("　", ""))
    if chars <= 6:
        return 140           # ~150%
    if chars <= 9:
        return 121           # ~130%
    if chars <= 12:
        return 107           # ~115%
    return _BASE_FONT_SIZE   # 100%


def _wrap_line(text: str, max_chars: int = 14) -> str:
    text = text.strip()
    if len(text) <= max_chars:
        return text

    split_at = max_chars
    for marker in ("、", "。", "？", "！", " ", "　"):
        pos = text.rfind(marker, 0, max_chars + 1)
        if pos > 0:
            split_at = pos + 1
            break

    first = text[:split_at].strip()
    second = text[split_at:].strip()
    if len(second) > max_chars:
        second = second[:max_chars].strip()
    return f"{first}\\N{second}"   # ASS の改行は \N


def _escape_ass(text: str) -> str:
    return text.replace("{", r"\{").replace("}", r"\}")


def _ass_time(seconds: float) -> str:
    """秒数を ASS タイムスタンプ形式 H:MM:SS.cc に変換する"""
    total = max(seconds, 0.0)
    h = int(total // 3600)
    m = int((total % 3600) // 60)
    s = total % 60
    return f"{h}:{m:02}:{s:05.2f}"
