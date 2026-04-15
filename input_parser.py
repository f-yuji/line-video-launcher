import re
from dataclasses import dataclass


_HASHTAG_RE = re.compile(r"(?<!\w)#([A-Za-z0-9_\u3040-\u30ff\u3400-\u9fffー・]+)")


@dataclass
class ParsedInput:
    source_text: str
    clean_text: str
    manual_hashtags: list[str]

    @property
    def context_text(self) -> str:
        if not self.manual_hashtags:
            return self.clean_text
        tags = " ".join(self.manual_hashtags)
        return f"{self.clean_text}\n\n参考タグ・重要語: {tags}".strip()


def parse_input_text(text: str) -> ParsedInput:
    source_text = (text or "").strip()
    found = _HASHTAG_RE.findall(source_text)
    manual_hashtags: list[str] = []
    seen: set[str] = set()

    for tag in found:
        normalized = "#" + tag.lstrip("#")
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        manual_hashtags.append(normalized)

    clean_text = _HASHTAG_RE.sub("", source_text)
    clean_text = re.sub(r"[ \t]+", " ", clean_text)
    clean_text = re.sub(r"\n\s*\n+", "\n", clean_text).strip()

    return ParsedInput(
        source_text=source_text,
        clean_text=clean_text or source_text,
        manual_hashtags=manual_hashtags,
    )
