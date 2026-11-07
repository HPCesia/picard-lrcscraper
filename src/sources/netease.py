from __future__ import annotations

from typing import Any

from ..common.models import Candidate, Lyric, Query, Request, SessionOptions
from ..common.text import clean_lyrics, is_synced
from .base import Session, Source

SEARCH_URL = "https://music.163.com/api/search/get"
LYRIC_URL = "https://music.163.com/api/song/lyric"
HEADERS = {
    "Referer": "https://music.163.com/",
    "Accept": "application/json",
    "Cookie": "appver=2.0.2",
}
SEARCH_LIMIT = "10"


class NeteaseSession(Session):
    def __init__(self, query: Query, options: SessionOptions) -> None:
        self.query = query
        self.options = options

    def begin_search(self) -> Request:
        return Request(
            url=SEARCH_URL,
            queryargs={
                "s": self.query.keyword,
                "type": "1",
                "limit": SEARCH_LIMIT,
                "offset": "0",
            },
            headers=HEADERS,
        )

    def handle_search(self, response: Any) -> list[Candidate]:
        return parse_search(response)

    def begin_fetch(self, candidate: Candidate) -> Request:
        return Request(
            url=LYRIC_URL,
            queryargs={
                "id": str(candidate.payload["id"]),
                "lv": "-1",
                "kv": "-1",
                "tv": "-1",
            },
            headers=HEADERS,
        )

    def handle_fetch(self, response: Any, candidate: Candidate) -> Lyric | None:
        return parse_lyric(response, candidate)


def _artist_names(song: dict[str, Any]) -> str:
    artists = song.get("artists") or song.get("ar") or []
    names = [str(artist.get("name")) for artist in artists if artist.get("name")]
    return ", ".join(names)


def parse_search(response: Any) -> list[Candidate]:
    if not isinstance(response, dict):
        return []
    songs = (response.get("result") or {}).get("songs") or []
    candidates: list[Candidate] = []
    for song in songs:
        if not isinstance(song, dict) or song.get("id") is None:
            continue
        album = song.get("album") or song.get("al") or {}
        duration = song.get("duration") or song.get("dt")
        candidates.append(
            Candidate(
                source=NeteaseSource.ID,
                title=str(song.get("name") or ""),
                artist=_artist_names(song),
                album=str(album.get("name") or ""),
                duration=int(duration) // 1000 if duration else None,
                payload={"id": song["id"]},
            )
        )
    return candidates


def parse_lyric(response: Any, candidate: Candidate) -> Lyric | None:
    if not isinstance(response, dict):
        return None
    raw = (response.get("lrc") or {}).get("lyric") or ""
    text = clean_lyrics(str(raw))
    if not text:
        return None
    return Lyric(
        text=text,
        synced=is_synced(raw),
        source=NeteaseSource.ID,
        title=candidate.title,
        artist=candidate.artist,
    )


class NeteaseSource(Source):
    ID = "netease"
    NAME = "NetEase Cloud Music"

    def session(self, query: Query, options: SessionOptions) -> Session:
        return NeteaseSession(query, options)
