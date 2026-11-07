from __future__ import annotations

from typing import Any

from ..common.models import Candidate, Lyric, Query, Request, SessionOptions
from ..common.text import clean_lyrics, is_synced
from .base import Session, Source

SEARCH_URL = "https://lrclib.net/api/search"
USER_AGENT = "picard-lrcscraper/1.0.0 (https://github.com/hpcesia/picard-lrcscraper)"


class LrclibSession(Session):
    def __init__(self, query: Query, options: SessionOptions) -> None:
        self.query = query
        self.options = options

    def begin_search(self) -> Request:
        queryargs = {"track_name": self.query.title}
        if self.query.artist:
            queryargs["artist_name"] = self.query.artist
        return Request(
            url=SEARCH_URL,
            queryargs=queryargs,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        )

    def handle_search(self, response: Any) -> list[Candidate]:
        return parse_search(response)

    def begin_fetch(self, candidate: Candidate) -> Lyric | None:
        return pick_lyrics(candidate, self.options.prefer_synced)


def parse_search(response: Any) -> list[Candidate]:
    if not isinstance(response, list):
        return []
    candidates: list[Candidate] = []
    for item in response:
        if not isinstance(item, dict) or item.get("instrumental"):
            continue
        if not (item.get("plainLyrics") or item.get("syncedLyrics")):
            continue
        candidates.append(
            Candidate(
                source=LrclibSource.ID,
                title=str(item.get("trackName") or ""),
                artist=str(item.get("artistName") or ""),
                album=str(item.get("albumName") or ""),
                duration=int(item["duration"]) if item.get("duration") else None,
                payload={
                    "plain": item.get("plainLyrics"),
                    "synced": item.get("syncedLyrics"),
                },
            )
        )
    return candidates


def pick_lyrics(candidate: Candidate, prefer_synced: bool) -> Lyric | None:
    synced = candidate.payload.get("synced")
    plain = candidate.payload.get("plain")
    order = (synced, plain) if prefer_synced else (plain, synced)
    for text in order:
        if isinstance(text, str) and text.strip():
            cleaned = clean_lyrics(text)
            if not cleaned:
                continue
            return Lyric(
                text=cleaned,
                synced=is_synced(text),
                source=LrclibSource.ID,
                title=candidate.title,
                artist=candidate.artist,
            )
    return None


class LrclibSource(Source):
    ID = "lrclib"
    NAME = "LRCLIB"

    def session(self, query: Query, options: SessionOptions) -> Session:
        return LrclibSession(query, options)
