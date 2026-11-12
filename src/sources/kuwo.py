from __future__ import annotations

import ast
import html
import json
import re
from typing import Any

from ..common.models import Candidate, Lyric, Query, Request, SessionOptions
from ..common.text import clean_lyrics, is_synced, lrc_timestamp
from .base import Session, Source

SEARCH_URL = "https://search.kuwo.cn/r.s"
LYRIC_URLS = (
    "https://www.kuwo.cn/openapi/v1/www/lyric/getlyric",
    "https://m.kuwo.cn/newh5/singles/songinfoandlrc",
)
HEADERS = {
    "Referer": "https://m.kuwo.cn/",
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    ),
}
PAGE_SIZE = "10"

_TAG_RE = re.compile(r"<[^>]+>")


def parse_loose_json(text: str) -> Any:
    """Kuwo answers with single quoted, html escaped pseudo JSON."""
    try:
        return json.loads(text)
    except ValueError:
        pass
    try:
        return ast.literal_eval(text)
    except (ValueError, SyntaxError):
        return None


def clean_field(value: Any) -> str:
    cleaned = html.unescape(_TAG_RE.sub("", str(value or "")))
    return cleaned.replace("\xa0", " ").strip()


class KuwoSession(Session):
    def __init__(self, query: Query, options: SessionOptions) -> None:
        self.query = query
        self.options = options
        self._rid = ""
        self._url_index = 0

    def begin_search(self) -> Request:
        return Request(
            url=SEARCH_URL,
            queryargs={
                "all": self.query.keyword,
                "ft": "music",
                "itemset": "web_2013",
                "client": "kt",
                "pn": "0",
                "rn": PAGE_SIZE,
                "rformat": "json",
                "encoding": "utf8",
                "vipver": "1",
                "show_copyright_off": "1",
            },
            headers=HEADERS,
            response_type=None,
        )

    def handle_search(self, response: Any) -> list[Candidate]:
        return parse_search(response)

    def begin_fetch(self, candidate: Candidate) -> Request | None:
        rid = candidate.payload.get("rid")
        if not rid:
            self._rid = ""
            return None
        self._rid = str(rid)
        self._url_index = 0
        return self._lyric_request()

    def _lyric_request(self) -> Request:
        return Request(
            url=LYRIC_URLS[self._url_index],
            queryargs={"musicId": self._rid, "httpsStatus": "1"},
            headers=HEADERS,
            response_type=None,
        )

    def handle_fetch(
        self, response: Any, candidate: Candidate
    ) -> Request | Lyric | None:
        lyric = parse_lyric(response, candidate)
        if lyric is not None or not self._rid:
            return lyric
        self._url_index += 1
        if self._url_index >= len(LYRIC_URLS):
            return None
        return self._lyric_request()


def parse_search(response: Any) -> list[Candidate]:
    data = parse_loose_json(response) if isinstance(response, str) else response
    if not isinstance(data, dict):
        return []
    candidates: list[Candidate] = []
    for item in data.get("abslist") or []:
        if not isinstance(item, dict):
            continue
        rid = str(item.get("MUSICRID") or item.get("DC_TARGETID") or "").replace(
            "MUSIC_", ""
        )
        if not rid:
            continue
        duration = item.get("DURATION")
        candidates.append(
            Candidate(
                source=KuwoSource.ID,
                title=clean_field(item.get("SONGNAME")),
                artist=clean_field(item.get("ARTIST")),
                album=clean_field(item.get("ALBUM")),
                duration=int(duration) if str(duration or "").isdigit() else None,
                payload={"rid": rid},
            )
        )
    return candidates


def build_lrc(lines: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for line in lines:
        if not isinstance(line, dict):
            continue
        content = str(line.get("lineLyric") or "")
        try:
            seconds = float(line.get("time") or 0)
        except (TypeError, ValueError):
            continue
        parts.append(f"{lrc_timestamp(seconds)}{content}")
    return "\n".join(parts)


def parse_lyric(response: Any, candidate: Candidate) -> Lyric | None:
    data = parse_loose_json(response) if isinstance(response, str) else response
    if not isinstance(data, dict):
        return None
    lines = (data.get("data") or {}).get("lrclist") or []
    raw = build_lrc(lines)
    text = clean_lyrics(raw)
    if not text:
        return None
    return Lyric(
        text=text,
        synced=is_synced(raw),
        source=KuwoSource.ID,
        title=candidate.title,
        artist=candidate.artist,
    )


class KuwoSource(Source):
    ID = "kuwo"
    NAME = "Kuwo Music"

    def session(self, query: Query, options: SessionOptions) -> Session:
        return KuwoSession(query, options)
