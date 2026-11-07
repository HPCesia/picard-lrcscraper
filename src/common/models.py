from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from typing import Any


@dataclass(frozen=True)
class SessionOptions:
    prefer_synced: bool = True


@dataclass(frozen=True)
class Query:
    title: str
    artist: str = ""
    album: str = ""
    duration: int | None = None

    @property
    def has_title(self) -> bool:
        return bool(self.title.strip())

    @property
    def keyword(self) -> str:
        return " ".join(
            part.strip() for part in (self.title, self.artist) if part.strip()
        )


@dataclass(frozen=True)
class Candidate:
    """A search hit. `payload` is whatever the source needs to fetch it."""

    source: str
    title: str
    artist: str = ""
    album: str = ""
    duration: int | None = None
    payload: Mapping[str, Any] = field(default_factory=dict)
    score: float = 0.0

    def with_score(self, score: float) -> Candidate:
        return replace(self, score=score)


@dataclass(frozen=True)
class Lyric:
    """Lyrics from a source. `synced` says whether they carry LRC timestamps.

    `translation` holds the same lines translated, timed as LRC.
    """

    text: str
    synced: bool
    source: str
    title: str = ""
    artist: str = ""
    translation: str = ""

    @property
    def is_empty(self) -> bool:
        return not self.text.strip()


@dataclass(frozen=True)
class Request:
    """An HTTP request for the runner.

    `response_type` is passed to Picard's web service as `parse_response_type`:
    `"json"` parses the body, `None` returns it as text.
    """

    url: str
    method: str = "GET"
    queryargs: Mapping[str, str] | None = None
    headers: Mapping[str, str] | None = None
    data: bytes | str | None = None
    mimetype: str | None = None
    response_type: str | None = "json"
