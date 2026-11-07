from __future__ import annotations

from abc import abstractmethod
from collections.abc import Iterable
from typing import Any

from picard.plugin3.api import Album, BaseAction, Track

from ..common.models import Candidate, Query
from ..services.scrape import (
    fetch_candidate,
    fetch_lyrics,
    plugin_label,
    query_from_metadata,
    search_candidates,
)
from ..ui.dialogs import choose_candidate, show_warning


class LyricsAction(BaseAction):
    def callback(self, objs: Iterable[Any]) -> None:
        for item in objs:
            if isinstance(item, Track):
                self.handle_track(item)
            elif isinstance(item, Album):
                for track in item.tracks:
                    self.handle_track(track)

    def handle_track(self, track: Track) -> None:
        if not track.files:
            return
        try:
            self.run(track)
        except Exception:
            self.api.logger.exception(
                f"{plugin_label(self.api)}: lyrics action failed for {track}"
            )

    @abstractmethod
    def run(self, track: Track) -> None: ...


class FetchLyricsAuto(LyricsAction):
    TITLE = "Fetch lyrics from configured sources"

    def run(self, track: Track) -> None:
        self.api.logger.debug(f"{plugin_label(self.api)}: fetching lyrics for {track}")
        fetch_lyrics(self.api, track.album, track.metadata, list(track.files))


class FetchLyricsManual(LyricsAction):
    TITLE = "Search lyrics and pick a result…"

    def run(self, track: Track) -> None:
        query = query_from_metadata(track.metadata)
        if not query.has_title:
            return
        search_candidates(
            self.api,
            track.album,
            query,
            lambda candidates: self._choose(track, query, candidates),
        )

    def _choose(self, track: Track, query: Query, candidates: list[Candidate]) -> None:
        if not candidates:
            show_warning(
                self.api,
                "No lyrics found",
                f"No source returned a match for {query.keyword}.",
            )
            return
        chosen = choose_candidate(self.api, candidates, query.keyword)
        if chosen is None:
            return
        fetch_candidate(self.api, track.album, query, chosen, list(track.files))
