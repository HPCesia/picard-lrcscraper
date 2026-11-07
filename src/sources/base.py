from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar

from ..common.models import Candidate, Lyric, Query, Request, SessionOptions


class Session(ABC):
    """State machine for one lookup against one source.

    Each step returns the next request or the final result, so multi-step APIs
    stay inside the provider.
    """

    query: Query
    options: SessionOptions

    def begin_search(self) -> Request | list[Candidate] | None:
        """First search request, ready-made candidates, or None."""
        return None

    def handle_search(self, response: Any) -> Request | list[Candidate] | None:
        return None

    def begin_fetch(self, candidate: Candidate) -> Request | Lyric | None:
        return None

    def handle_fetch(
        self, response: Any, candidate: Candidate
    ) -> Request | Lyric | None:
        return None


class Source(ABC):
    """A lyrics provider.

    `ID` is stored in the plugin configuration, so changing it after release
    loses the user's saved position and disabled state for this source.
    """

    ID: ClassVar[str]
    NAME: ClassVar[str]
    REQUIRES_ARTIST: ClassVar[bool] = False

    def supports(self, query: Query) -> bool:
        if not query.has_title:
            return False
        return not self.REQUIRES_ARTIST or bool(query.artist.strip())

    @abstractmethod
    def session(self, query: Query, options: SessionOptions) -> Session: ...
