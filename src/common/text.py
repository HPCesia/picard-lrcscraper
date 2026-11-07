from __future__ import annotations

import os
import re

_TIME_TAG_RE = re.compile(r"\[\d{1,3}:\d{1,2}(?:[.:]\d{1,3})?\]")
_TIME_TAG_PARTS_RE = re.compile(r"\[(\d{1,3}):(\d{1,2})(?:[.:](\d{1,3}))?\]")
_LEADING_TAGS_RE = re.compile(r"^(?:\[\d{1,3}:\d{1,2}(?:[.:]\d{1,3})?\])+")
_JUNK_TAG_RE = re.compile(r"^\[(id|by|hash|krc|sign|qq|total|language):", re.IGNORECASE)
BILINGUAL_TOLERANCE = 0.3
_CREDIT_LABEL_RE = re.compile(r"^(?P<label>[^\s:：]{1,8})\s*[:：]\s*\S")
_CREDIT_LABEL_SUFFIXES = (
    "词",
    "曲",
    "编曲",
    "制作",
    "录音",
    "混音",
    "母带",
    "和声",
    "合声",
    "配唱",
    "演唱",
    "演奏",
    "助理",
    "工程",
    "编写",
    "监制",
    "出品",
    "发行",
    "统筹",
    "企划",
    "吉他",
    "贝斯",
    "鼓",
    "键盘",
    "弦乐",
    "人声",
    "制作人",
    "出品人",
    "发行人",
    "词人",
    "曲人",
    "师",
)
_CREDIT_WORD_RE = re.compile(
    r"^(?:lyrics?|composer|producer|arranger|mixed|mastered|recorded)\s*[:：]",
    re.IGNORECASE,
)
_CREDIT_BY_RE = re.compile(
    r"^(?:produced|written|composed|arranged|recorded|mixed|mastered|engineered)"
    r"\s+by\b",
    re.IGNORECASE,
)
_NOISE_MARKERS = (
    "以下歌词翻译",
    "歌词翻译由",
    "纯音乐",
    "暂无歌词",
    "没有填词的纯音乐",
    "此歌曲为",
    "本歌词由",
    "www.",
    "http://",
    "https://",
)


def is_synced(text: str) -> bool:
    """True when the text carries LRC time tags."""
    return bool(_TIME_TAG_RE.search(text or ""))


def parse_duration(value: str) -> int | None:
    """Parse a `M:SS` or `H:MM:SS` value such as Picard's `~length`.

    Returns None when the value doesn't parse.
    """
    parts = [part for part in str(value).strip().split(":") if part.isdigit()]
    if len(parts) == 2:
        minutes, seconds = (int(part) for part in parts)
        return minutes * 60 + seconds
    if len(parts) == 3:
        hours, minutes, seconds = (int(part) for part in parts)
        return hours * 3600 + minutes * 60 + seconds
    return None


def format_duration(seconds: int | None) -> str:
    if not seconds:
        return ""
    hours, remainder = divmod(int(seconds), 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02}:{secs:02}"
    return f"{minutes}:{secs:02}"


def lrc_timestamp(seconds: float) -> str:
    """Format a number of seconds the way `.lrc` files expect it."""
    total = max(0.0, float(seconds))
    minutes = int(total // 60)
    secs = total - minutes * 60
    return f"[{minutes:02d}:{secs:05.2f}]"


def _looks_like_credit(content: str) -> bool:
    """Credit lines put a short role label before a colon. Lyric lines rarely do."""
    match = _CREDIT_LABEL_RE.match(content)
    if match is None:
        return False
    return match.group("label").casefold().endswith(_CREDIT_LABEL_SUFFIXES)


def _is_noise(content: str) -> bool:
    lowered = content.casefold()
    if _CREDIT_WORD_RE.match(lowered) or _CREDIT_BY_RE.match(lowered):
        return True
    if _looks_like_credit(content):
        return True
    return any(marker in lowered for marker in _NOISE_MARKERS)


def clean_lyrics(text: str) -> str:
    """Drop credits, notices and junk tags, and collapse blank lines."""
    if not text:
        return ""
    text = text.replace("\ufeff", "").replace("\r\n", "\n").replace("\r", "\n")
    kept: list[str] = []
    for raw in text.split("\n"):
        line = raw.rstrip()
        if _JUNK_TAG_RE.match(line):
            continue
        content = _TIME_TAG_RE.sub("", line).strip()
        if not content:
            if kept and kept[-1] != "":
                kept.append("")
            continue
        if _is_noise(content):
            continue
        kept.append(line)
    while kept and kept[-1] == "":
        kept.pop()
    return "\n".join(kept)


def _tag_seconds(tag: str) -> float | None:
    match = _TIME_TAG_PARTS_RE.fullmatch(tag)
    if match is None:
        return None
    minutes, seconds, fraction = match.groups()
    fraction_seconds = int(fraction) / 10 ** len(fraction) if fraction else 0.0
    return int(minutes) * 60 + int(seconds) + fraction_seconds


def _leading_tags(line: str) -> list[str]:
    match = _LEADING_TAGS_RE.match(line)
    if match is None:
        return []
    return _TIME_TAG_RE.findall(match.group(0))


def _timed_lines(text: str) -> list[tuple[float, str]]:
    """Split LRC text into `(seconds, content)` pairs, sorted by time."""
    entries: list[tuple[float, str]] = []
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    for raw in normalized.split("\n"):
        tags = _leading_tags(raw)
        if not tags:
            continue
        seconds = _tag_seconds(tags[0])
        content = _TIME_TAG_RE.sub("", raw).strip()
        if seconds is None or not content:
            continue
        entries.append((seconds, content))
    entries.sort(key=lambda item: item[0])
    return entries


def merge_bilingual(
    original: str, translation: str, tolerance: float = BILINGUAL_TOLERANCE
) -> str:
    """Write the original lines with each matching translated line beneath them.

    A translated line reuses the original's timestamp so players stack equal
    timestamps. Translations within `tolerance` seconds pair with a line;
    unmatched ones are dropped rather than shown on the wrong line.
    """
    translated = _timed_lines(translation)
    if not original or not translated:
        return original
    pointer = 0
    merged: list[str] = []
    for raw in original.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        merged.append(raw)
        for tag in _leading_tags(raw):
            seconds = _tag_seconds(tag)
            if seconds is None:
                continue
            while (
                pointer < len(translated)
                and translated[pointer][0] < seconds - tolerance
            ):
                pointer += 1
            if pointer >= len(translated):
                break
            if abs(translated[pointer][0] - seconds) <= tolerance:
                content = translated[pointer][1]
                pointer += 1
                merged.append(f"{tag}{content}")
    return "\n".join(merged)


def sidecar_base(audio_path: str) -> str:
    directory, name = os.path.split(audio_path)
    stem = os.path.splitext(name)[0]
    return os.path.join(directory, stem)


def sidecar_path(audio_path: str, extension: str) -> str:
    return f"{sidecar_base(audio_path)}{extension}"
