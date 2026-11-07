from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from src.common.models import Candidate, Lyric, Query, Request, SessionOptions
from src.services.runner import (
    AutoScrape,
    CandidateFetch,
    CandidateSearch,
    deduplicate,
)
from src.sources.base import Session, Source
from src.sources.netease import NeteaseSource


class ScriptedTransport:
    """Answers requests from a route table, synchronously."""

    def __init__(self, routes: Sequence[tuple[str, Any]]) -> None:
        self.routes = list(routes)
        self.requests: list[Request] = []

    def __call__(self, request: Request, handler: Any) -> None:
        self.requests.append(request)
        for fragment, response in self.routes:
            if fragment in request.url:
                if isinstance(response, Exception):
                    handler(None, response)
                else:
                    handler(response, None)
                return
        handler(None, RuntimeError(f"unrouted request: {request.url}"))

    def urls(self) -> list[str]:
        return [request.url for request in self.requests]


class StubSession(Session):
    def __init__(
        self,
        identifier: str,
        hits: list[Candidate] | None = None,
        options: SessionOptions | None = None,
        inline: bool = False,
        error: Exception | None = None,
    ) -> None:
        self.identifier = identifier
        self.hits = hits or []
        self.options = options or SessionOptions()
        self.inline = inline
        self.error = error

    def begin_search(self) -> Any:
        if self.error is not None:
            raise self.error
        if self.inline:
            return self.hits
        return Request(url=f"https://{self.identifier}.test/search")

    def handle_search(self, response: Any) -> Any:
        if isinstance(response, Exception):
            raise response
        return self.hits

    def begin_fetch(self, candidate: Candidate) -> Any:
        return Request(
            url=f"https://{self.identifier}.test/lyric/{candidate.payload['id']}"
        )

    def handle_fetch(self, response: Any, candidate: Candidate) -> Any:
        if isinstance(response, dict) and "next" in response:
            return Request(url=response["next"])
        text = response.get("text", "") if isinstance(response, dict) else ""
        return Lyric(text=text, synced=False, source=self.identifier)


class StubSource(Source):
    NAME = "Stub"

    def __init__(
        self,
        identifier: str,
        hits: list[Candidate] | None = None,
        inline: bool = False,
        error: Exception | None = None,
    ) -> None:
        self.ID = identifier
        self.hits = hits or []
        self.inline = inline
        self.error = error

    def session(self, query: Query, options: SessionOptions) -> Session:
        return StubSession(
            self.ID, self.hits, options, inline=self.inline, error=self.error
        )


def hit(
    source: str, title: str = "Bohemian Rhapsody", artist: str = "Queen"
) -> Candidate:
    return Candidate(source, title, artist, payload={"id": "42"})


QUERY = Query(title="Bohemian Rhapsody", artist="Queen", duration=355)


def test_auto_scrape_falls_through_a_failing_source() -> None:
    transport = ScriptedTransport(
        [
            ("first.test/search", RuntimeError("404")),
            ("second.test/search", ["ignored"]),
            ("second.test/lyric", {"text": "hello"}),
        ]
    )
    finished: list[Lyric | None] = []
    runner = AutoScrape(
        QUERY,
        [StubSource("first"), StubSource("second", [hit("second")])],
        SessionOptions(),
        transport,
        finished.append,
    )
    runner.start()
    assert finished and finished[0] is not None
    assert finished[0].text == "hello"
    assert "first.test/search" in transport.urls()[0]


def test_auto_scrape_stops_at_first_source_with_lyrics() -> None:
    transport = ScriptedTransport(
        [
            ("first.test/search", []),
            ("first.test/lyric", {"text": "first"}),
            ("second.test/search", []),
            ("second.test/lyric", {"text": "second"}),
            ("third.test/search", []),
            ("third.test/lyric", {"text": "third"}),
        ]
    )
    finished: list[Lyric | None] = []
    AutoScrape(
        QUERY,
        [
            StubSource("first", [hit("first")]),
            StubSource("second", [hit("second")]),
            StubSource("third", [hit("third")]),
        ],
        SessionOptions(),
        transport,
        finished.append,
    ).start()
    searches = [url for url in transport.urls() if url.endswith("/search")]
    assert searches == ["https://first.test/search"]
    assert finished[0] is not None and finished[0].text == "first"


def test_min_score_rejects_unrelated_hits() -> None:
    transport = ScriptedTransport(
        [
            ("first.test/search", []),
            ("second.test/search", []),
            ("second.test/lyric", {"text": "hello"}),
        ]
    )
    finished: list[Lyric | None] = []
    AutoScrape(
        QUERY,
        [
            StubSource("first", [hit("first", title="Cooking Lesson", artist="Chef")]),
            StubSource("second", [hit("second")]),
        ],
        SessionOptions(),
        transport,
        finished.append,
        min_score=0.7,
    ).start()
    assert finished[0] is not None
    assert finished[0].source == "second"


def test_auto_scrape_reports_nothing_found() -> None:
    transport = ScriptedTransport([("any.test", RuntimeError("offline"))])
    finished: list[Lyric | None] = []
    AutoScrape(
        QUERY,
        [StubSource("any", [hit("any")])],
        SessionOptions(),
        transport,
        finished.append,
    ).start()
    assert finished == [None]


def test_auto_scrape_survives_a_broken_payload() -> None:
    transport = ScriptedTransport(
        [
            ("first.test/search", "garbage"),
            ("second.test/search", []),
            ("second.test/lyric", {"text": "recovered"}),
        ]
    )
    finished: list[Lyric | None] = []
    AutoScrape(
        QUERY,
        [StubSource("first", [hit("first")]), StubSource("second", [hit("second")])],
        SessionOptions(),
        transport,
        finished.append,
    ).start()
    assert finished[0] is not None
    assert finished[0].text == "recovered"


def test_auto_scrape_accepts_inline_candidates_without_a_search_request() -> None:
    transport = ScriptedTransport([("inline.test/lyric", {"text": "inline lyrics"})])
    finished: list[Lyric | None] = []
    AutoScrape(
        QUERY,
        [StubSource("inline", [hit("inline")], inline=True)],
        SessionOptions(),
        transport,
        finished.append,
    ).start()
    assert transport.urls() == ["https://inline.test/lyric/42"]
    assert finished[0] is not None and finished[0].text == "inline lyrics"


def test_fetch_can_chain_several_requests() -> None:
    transport = ScriptedTransport(
        [
            ("chain.test/search", []),
            ("chain.test/lyric/42", {"next": "https://chain.test/download"}),
            ("chain.test/download", {"text": "chained"}),
        ]
    )
    finished: list[Lyric | None] = []
    AutoScrape(
        QUERY,
        [StubSource("chain", [hit("chain")])],
        SessionOptions(),
        transport,
        finished.append,
    ).start()
    assert finished[0] is not None and finished[0].text == "chained"
    assert transport.urls()[-1] == "https://chain.test/download"


def test_sources_that_cannot_handle_the_query_are_skipped() -> None:
    transport = ScriptedTransport([("artist.test/lyric", {"text": "found"})])

    class ArtistOnlySource(StubSource):
        REQUIRES_ARTIST = True

    finished: list[Lyric | None] = []
    AutoScrape(
        Query(title="No Artist Here"),
        [ArtistOnlySource("artist", [hit("artist")])],
        SessionOptions(),
        transport,
        finished.append,
    ).start()
    assert finished == [None]
    assert transport.requests == []


def test_candidate_search_collects_from_every_source() -> None:
    transport = ScriptedTransport(
        [
            ("a.test/search", []),
            ("b.test/search", []),
        ]
    )
    collected: list[list[Candidate]] = []
    CandidateSearch(
        QUERY,
        [
            StubSource("a", [hit("a"), hit("a", title="Something Else")]),
            StubSource("b", [hit("b")]),
        ],
        SessionOptions(),
        transport,
        collected.append,
        min_score=0.5,
    ).start()
    assert len(collected) == 1
    sources = sorted(candidate.source for candidate in collected[0])
    assert sources == ["a", "b"]
    assert "Something Else" not in [candidate.title for candidate in collected[0]]


def test_candidate_fetch_only_touches_the_chosen_source() -> None:
    transport = ScriptedTransport([("b.test/lyric/42", {"text": "picked"})])
    finished: list[Lyric | None] = []
    CandidateFetch(
        hit("b"),
        QUERY,
        [StubSource("a"), StubSource("b")],
        SessionOptions(),
        transport,
        finished.append,
    ).start()
    assert transport.urls() == ["https://b.test/lyric/42"]
    assert finished[0] is not None and finished[0].source == "b"


def test_candidate_fetch_for_unknown_source_finishes_empty() -> None:
    transport = ScriptedTransport([])
    finished: list[Lyric | None] = []
    CandidateFetch(
        hit("missing"),
        QUERY,
        [StubSource("a")],
        SessionOptions(),
        transport,
        finished.append,
    ).start()
    assert finished == [None]
    assert transport.requests == []


def test_netease_source_end_to_end() -> None:
    search_payload = {
        "code": 200,
        "result": {
            "songs": [
                {
                    "id": 1868553,
                    "name": "Bohemian Rhapsody",
                    "duration": 355195,
                    "artists": [{"name": "Queen"}],
                    "album": {"name": "A Night at the Opera"},
                }
            ]
        },
    }
    lyric_payload = {"lrc": {"lyric": "[00:01.00] Is this the real life?"}}
    transport = ScriptedTransport(
        [
            ("api/search/get", search_payload),
            ("api/song/lyric", lyric_payload),
        ]
    )
    finished: list[Lyric | None] = []
    AutoScrape(
        QUERY,
        [NeteaseSource()],
        SessionOptions(),
        transport,
        finished.append,
    ).start()
    assert finished[0] is not None
    assert finished[0].source == "netease"
    assert finished[0].text == "[00:01.00] Is this the real life?"
    assert transport.urls() == [
        "https://music.163.com/api/search/get",
        "https://music.163.com/api/song/lyric",
    ]


def test_auto_scrape_tries_the_next_candidate_of_the_same_source() -> None:
    transport = ScriptedTransport(
        [
            ("retry.test/search", []),
            ("retry.test/lyric/42", {}),
            ("retry.test/lyric/43", {"text": "second hit"}),
        ]
    )
    second = Candidate("retry", "Bohemian Rhapsody", "Queen", payload={"id": "43"})
    finished: list[Lyric | None] = []
    AutoScrape(
        QUERY,
        [StubSource("retry", [hit("retry"), second])],
        SessionOptions(),
        transport,
        finished.append,
    ).start()
    assert finished[0] is not None
    assert finished[0].text == "second hit"


def test_auto_scrape_bounds_the_number_of_candidates_per_source() -> None:
    transport = ScriptedTransport(
        [
            ("many.test/search", []),
            ("many.test/lyric/42", {}),
            ("many/next.test/search", []),
            ("many/next.test/lyric/42", {"text": "later source"}),
        ]
    )
    hits = [
        Candidate("many", "Bohemian Rhapsody", f"Queen {index}", payload={"id": "42"})
        for index in range(6)
    ]
    finished: list[Lyric | None] = []
    AutoScrape(
        QUERY,
        [StubSource("many", hits), StubSource("many/next", [hit("many/next")])],
        SessionOptions(),
        transport,
        finished.append,
        max_candidates=2,
    ).start()
    attempts = [
        url for url in transport.urls() if url.startswith("https://many.test/lyric")
    ]
    assert len(attempts) == 2
    assert finished[0] is not None and finished[0].text == "later source"


def test_deduplicate_keeps_the_highest_ranked_copy() -> None:
    best = Candidate("a", "Song", "Artist", duration=200, score=0.9)
    worse = Candidate("a", "song", "artist", duration=200, score=0.5)
    other = Candidate("b", "Song", "Artist", duration=200, score=0.8)
    result = deduplicate([best, worse, other])
    assert [candidate.score for candidate in result] == [0.9, 0.8]
