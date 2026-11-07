from __future__ import annotations

import base64
import hashlib
import html
import re
import time
from typing import Any

from ..common.models import Candidate, Lyric, Query, Request, SessionOptions
from ..common.text import clean_lyrics, is_synced
from .base import Session, Source

SEARCH_URL = "https://complexsearch.kugou.com/v2/search/song"
KRCS_URL = "https://krcs.kugou.com/search"
DOWNLOAD_URL = "https://lyrics.kugou.com/download"
SECRET = "NVPh5oo715z5DIWAeQlhMDsWXXQV4hwt"
PAGE_SIZE = "10"

_TAG_RE = re.compile(r"</?em>")


def sign(params: str) -> str:
    return hashlib.md5(f"{SECRET}{params}{SECRET}".encode()).hexdigest()


def build_search_queryargs(keyword: str, stamp: str) -> dict[str, str]:
    signed = (
        f"bitrate=0clienttime={stamp}clientver=2000dfid=-inputtype=0iscorrection=1"
        f"isfuzzy=0keyword={keyword}mid={stamp}page=1pagesize={PAGE_SIZE}"
        f"platform=WebFilterprivilege_filter=0srcappid=2919tag=emuserid=-1uuid={stamp}"
    )
    return {
        "keyword": keyword,
        "page": "1",
        "pagesize": PAGE_SIZE,
        "bitrate": "0",
        "isfuzzy": "0",
        "tag": "em",
        "inputtype": "0",
        "platform": "WebFilter",
        "userid": "-1",
        "clientver": "2000",
        "iscorrection": "1",
        "privilege_filter": "0",
        "srcappid": "2919",
        "clienttime": stamp,
        "mid": stamp,
        "uuid": stamp,
        "dfid": "-",
        "signature": sign(signed),
    }


def clean_field(value: Any) -> str:
    cleaned = html.unescape(_TAG_RE.sub("", str(value or "")))
    return cleaned.replace("\xa0", " ").strip()


class KugouSession(Session):
    def __init__(self, query: Query, options: SessionOptions) -> None:
        self.query = query
        self.options = options
        self._accesskey = ""
        self._lyric_id = ""
        self._phase = ""

    def begin_search(self) -> Request:
        stamp = str(int(time.time() * 1000))
        return Request(
            url=SEARCH_URL,
            queryargs=build_search_queryargs(self.query.keyword, stamp),
        )

    def handle_search(self, response: Any) -> list[Candidate]:
        return parse_search(response)

    def begin_fetch(self, candidate: Candidate) -> Request | None:
        self._phase = "krcs"
        hash_value = candidate.payload.get("hash")
        if not hash_value:
            return None
        return Request(
            url=KRCS_URL,
            queryargs={
                "ver": "1",
                "man": "yes",
                "client": "mobi",
                "keyword": "",
                "duration": "",
                "hash": str(hash_value),
            },
        )

    def handle_fetch(
        self, response: Any, candidate: Candidate
    ) -> Request | Lyric | None:
        if self._phase != "krcs":
            return parse_download(response, candidate)
        picked = pick_candidate(response)
        if picked is None:
            return None
        self._lyric_id = str(picked.get("id") or "")
        self._accesskey = str(picked.get("accesskey") or "")
        self._phase = "download"
        return Request(
            url=DOWNLOAD_URL,
            queryargs={
                "ver": "1",
                "client": "pc",
                "id": self._lyric_id,
                "accesskey": self._accesskey,
                "fmt": "lrc",
                "charset": "utf8",
            },
        )


def parse_search(response: Any) -> list[Candidate]:
    if not isinstance(response, dict):
        return []
    lists = (response.get("data") or {}).get("lists") or []
    candidates: list[Candidate] = []
    for item in lists:
        if not isinstance(item, dict) or not item.get("FileHash"):
            continue
        duration = item.get("Duration")
        candidates.append(
            Candidate(
                source=KugouSource.ID,
                title=clean_field(item.get("SongName")),
                artist=clean_field(
                    str(item.get("SingerName") or "").replace("、", ", ")
                ),
                album=clean_field(item.get("AlbumName")),
                duration=int(duration) if duration else None,
                payload={"hash": item["FileHash"]},
            )
        )
    return candidates


def pick_candidate(response: Any) -> dict[str, Any] | None:
    if not isinstance(response, dict):
        return None
    for candidate in response.get("candidates") or []:
        if isinstance(candidate, dict) and candidate.get("id"):
            return candidate
    return None


def parse_download(response: Any, candidate: Candidate) -> Lyric | None:
    if not isinstance(response, dict):
        return None
    encoded = response.get("content")
    if not isinstance(encoded, str) or not encoded:
        return None
    try:
        raw = base64.b64decode(encoded).decode("utf-8-sig", "replace")
    except (ValueError, TypeError):
        return None
    text = clean_lyrics(raw)
    if not text:
        return None
    return Lyric(
        text=text,
        synced=is_synced(raw),
        source=KugouSource.ID,
        title=candidate.title,
        artist=candidate.artist,
    )


class KugouSource(Source):
    ID = "kugou"
    NAME = "Kugou Music"

    def session(self, query: Query, options: SessionOptions) -> Session:
        return KugouSession(query, options)
