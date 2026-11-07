from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from ..common.models import Candidate, Lyric, Query, Request, SessionOptions
from ..common.scoring import ranked
from ..sources.base import Session, Source

ResponseHandler = Callable[[Any, BaseException | None], None]
Transport = Callable[[Request, ResponseHandler], None]
Logger = Callable[[str], None]


def _null_logger(message: str) -> None:
    return None


class _Runner:
    def __init__(self, transport: Transport, logger: Logger | None = None) -> None:
        self._transport = transport
        self._log = logger or _null_logger
        self._closed = False

    def send(self, request: Request, handler: ResponseHandler) -> None:
        def deliver(response: Any, error: BaseException | None) -> None:
            if self._closed:
                return
            handler(response, error)

        self._transport(request, deliver)

    def close(self) -> None:
        self._closed = True

    @property
    def closed(self) -> bool:
        return self._closed


def deduplicate(candidates: Sequence[Candidate]) -> list[Candidate]:
    """Drop repeats of the same recording. Input must already be ranked best first."""
    seen: set[tuple[str, str, str, int | None]] = set()
    unique: list[Candidate] = []
    for candidate in candidates:
        key = (
            candidate.source,
            candidate.title.casefold().strip(),
            candidate.artist.casefold().strip(),
            candidate.duration,
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(candidate)
    return unique


class AutoScrape(_Runner):
    """Walk sources in priority order and stop at the first lyric found."""

    def __init__(
        self,
        query: Query,
        sources: Sequence[Source],
        options: SessionOptions,
        transport: Transport,
        on_finish: Callable[[Lyric | None], None],
        min_score: float = 0.6,
        max_candidates: int = 3,
        logger: Logger | None = None,
    ) -> None:
        super().__init__(transport, logger)
        self._query = query
        self._sources = list(sources)
        self._options = options
        self._on_finish = on_finish
        self._min_score = min_score
        self._max_candidates = max_candidates
        self._index = 0
        self._session: Session | None = None
        self._candidates: list[Candidate] = []
        self._candidate_index = 0

    def start(self) -> None:
        self._next_source()

    def _next_source(self) -> None:
        if self.closed:
            return
        while self._index < len(self._sources):
            source = self._sources[self._index]
            self._index += 1
            if not source.supports(self._query):
                continue
            session = source.session(self._query, self._options)
            self._session = session
            self._log(f"{source.NAME}: searching for {self._query.keyword}")
            try:
                step = session.begin_search()
            except Exception as error:
                self._log(f"{source.NAME}: search failed: {error}")
                continue
            self._handle_search(step)
            return
        self._finish(None)

    def _handle_search(self, step: Any) -> None:
        if isinstance(step, Request):
            self.send(step, self._search_response)
        elif isinstance(step, list):
            self._choose(step)
        else:
            self._next_source()

    def _search_response(self, response: Any, error: BaseException | None) -> None:
        assert self._session is not None
        if error is not None:
            self._next_source()
            return
        try:
            step = self._session.handle_search(response)
        except Exception as parse_error:
            self._log(f"search response unreadable: {parse_error}")
            self._next_source()
            return
        self._handle_search(step)

    def _choose(self, candidates: Sequence[Candidate]) -> None:
        self._candidates = ranked(candidates, self._query, self._min_score)
        self._candidate_index = 0
        self._try_next_candidate()

    def _try_next_candidate(self) -> None:
        if self._candidate_index >= min(len(self._candidates), self._max_candidates):
            self._next_source()
            return
        candidate = self._candidates[self._candidate_index]
        self._candidate_index += 1
        self._begin_fetch(candidate)

    def _begin_fetch(self, candidate: Candidate) -> None:
        assert self._session is not None
        try:
            step = self._session.begin_fetch(candidate)
        except Exception as error:
            self._log(f"lyrics request failed: {error}")
            self._try_next_candidate()
            return
        self._handle_fetch(step, candidate)

    def _handle_fetch(self, step: Any, candidate: Candidate) -> None:
        if isinstance(step, Request):
            self.send(
                step,
                lambda response, error: self._fetch_response(
                    response, error, candidate
                ),
            )
        elif isinstance(step, Lyric) and not step.is_empty:
            self._finish(step)
        else:
            self._try_next_candidate()

    def _fetch_response(
        self, response: Any, error: BaseException | None, candidate: Candidate
    ) -> None:
        assert self._session is not None
        if error is not None:
            self._try_next_candidate()
            return
        try:
            step = self._session.handle_fetch(response, candidate)
        except Exception as parse_error:
            self._log(f"lyrics response unreadable: {parse_error}")
            self._try_next_candidate()
            return
        self._handle_fetch(step, candidate)

    def _finish(self, lyric: Lyric | None) -> None:
        if self.closed:
            return
        self.close()
        self._on_finish(lyric)


class CandidateSearch(_Runner):
    """Ask every enabled source for candidates, then report them ranked."""

    def __init__(
        self,
        query: Query,
        sources: Sequence[Source],
        options: SessionOptions,
        transport: Transport,
        on_finish: Callable[[list[Candidate]], None],
        min_score: float = 0.0,
        logger: Logger | None = None,
    ) -> None:
        super().__init__(transport, logger)
        self._query = query
        self._sources = list(sources)
        self._options = options
        self._on_finish = on_finish
        self._min_score = min_score
        self._index = 0
        self._session: Session | None = None
        self._found: list[Candidate] = []

    def start(self) -> None:
        self._next_source()

    def _next_source(self) -> None:
        if self.closed:
            return
        while self._index < len(self._sources):
            source = self._sources[self._index]
            self._index += 1
            if not source.supports(self._query):
                continue
            self._session = source.session(self._query, self._options)
            try:
                step = self._session.begin_search()
            except Exception as error:
                self._log(f"{source.NAME}: search failed: {error}")
                continue
            self._handle_search(step)
            return
        self._finish()

    def _handle_search(self, step: Any) -> None:
        if isinstance(step, Request):
            self.send(step, self._search_response)
        elif isinstance(step, list):
            self._found.extend(step)
            self._next_source()
        else:
            self._next_source()

    def _search_response(self, response: Any, error: BaseException | None) -> None:
        assert self._session is not None
        if error is not None:
            self._next_source()
            return
        try:
            step = self._session.handle_search(response)
        except Exception as parse_error:
            self._log(f"search response unreadable: {parse_error}")
            self._next_source()
            return
        self._handle_search(step)

    def _finish(self) -> None:
        if self.closed:
            return
        self.close()
        self._on_finish(deduplicate(ranked(self._found, self._query, self._min_score)))


class CandidateFetch(_Runner):
    def __init__(
        self,
        candidate: Candidate,
        query: Query,
        sources: Sequence[Source],
        options: SessionOptions,
        transport: Transport,
        on_finish: Callable[[Lyric | None], None],
        logger: Logger | None = None,
    ) -> None:
        super().__init__(transport, logger)
        self._candidate = candidate
        self._query = query
        self._options = options
        self._sources = list(sources)
        self._on_finish = on_finish
        self._session: Session | None = None

    def start(self) -> None:
        wanted = self._candidate.source
        source = next((item for item in self._sources if wanted == item.ID), None)
        if source is None:
            self._finish(None)
            return
        self._session = source.session(self._query, self._options)
        try:
            step = self._session.begin_fetch(self._candidate)
        except Exception as error:
            self._log(f"{source.NAME}: lyrics request failed: {error}")
            self._finish(None)
            return
        self._handle(step)

    def _handle(self, step: Any) -> None:
        if isinstance(step, Request):
            self.send(step, self._response)
        elif isinstance(step, Lyric) and not step.is_empty:
            self._finish(step)
        else:
            self._finish(None)

    def _response(self, response: Any, error: BaseException | None) -> None:
        assert self._session is not None
        if error is not None:
            self._finish(None)
            return
        try:
            step = self._session.handle_fetch(response, self._candidate)
        except Exception as parse_error:
            self._log(f"lyrics response unreadable: {parse_error}")
            self._finish(None)
            return
        self._handle(step)

    def _finish(self, lyric: Lyric | None) -> None:
        if self.closed:
            return
        self.close()
        self._on_finish(lyric)
