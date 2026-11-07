from __future__ import annotations

from typing import Any
from urllib.parse import quote

from ..common.models import Candidate, Lyric, Query, Request, SessionOptions
from ..common.text import clean_lyrics
from .base import Session, Source

LYRIC_URL = "https://api.lyrics.ovh/v1/{artist}/{title}"


class LyricsOvhSession(Session):
    def __init__(self, query: Query, options: SessionOptions) -> None:
        self.query = query
        self.options = options

    def begin_search(self) -> list[Candidate]:
        return [
            Candidate(
                source=LyricsOvhSource.ID,
                title=self.query.title,
                artist=self.query.artist,
                album=self.query.album,
                duration=self.query.duration,
            )
        ]

    def begin_fetch(self, candidate: Candidate) -> Request:
        url = LYRIC_URL.format(
            artist=quote(candidate.artist.strip(), safe=""),
            title=quote(candidate.title.strip(), safe=""),
        )
        return Request(url=url, headers={"Accept": "application/json"})

    def handle_fetch(self, response: Any, candidate: Candidate) -> Lyric | None:
        return parse_lyric(response, candidate)


def parse_lyric(response: Any, candidate: Candidate) -> Lyric | None:
    if not isinstance(response, dict):
        return None
    text = clean_lyrics(str(response.get("lyrics") or ""))
    if not text:
        return None
    return Lyric(
        text=text,
        synced=False,
        source=LyricsOvhSource.ID,
        title=candidate.title,
        artist=candidate.artist,
    )


class LyricsOvhSource(Source):
    ID = "lyricsovh"
    NAME = "Lyrics.ovh"
    REQUIRES_ARTIST = True

    def session(self, query: Query, options: SessionOptions) -> Session:
        return LyricsOvhSession(query, options)
