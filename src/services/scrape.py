from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any

from picard.plugin3.api import Album, Metadata, PluginApi

from ..common.models import Candidate, Lyric, Query, SessionOptions
from ..common.text import parse_duration
from ..sources.base import Source
from ..sources.registry import ordered_sources
from ..ui.dialogs import confirm_overwrite
from .apply import apply_lyric, has_lyrics
from .runner import AutoScrape, CandidateFetch, CandidateSearch
from .web import make_transport

POLICY_NEVER = "never"
POLICY_ASK = "ask"
POLICY_ALWAYS = "always"


def plugin_label(api: PluginApi) -> str:
    return api.manifest.name_i18n()


def query_from_metadata(metadata: Metadata) -> Query:
    duration = None
    length = metadata["~length"]
    if length:
        duration = parse_duration(str(length))
    return Query(
        title=metadata["title"],
        artist=metadata["artist"],
        album=metadata["album"],
        duration=duration,
    )


def session_options(api: PluginApi) -> SessionOptions:
    return SessionOptions(prefer_synced=bool(api.plugin_config["prefer_synced"]))


def active_sources(api: PluginApi) -> list[Source]:
    return ordered_sources(
        list(api.plugin_config["source_order"] or []),
        list(api.plugin_config["disabled_sources"] or []),
    )


def minimum_score(api: PluginApi) -> float:
    return float(api.plugin_config["min_score"])


def scrape_allowed(api: PluginApi, files: list[Any], policy: str, name: str) -> bool:
    """Whether existing lyrics may be replaced, asking the user when configured."""
    label = plugin_label(api)
    if not has_lyrics(files):
        return True
    if policy == POLICY_NEVER:
        api.logger.debug(f"{label}: keeping existing lyrics for {name}")
        return False
    if policy == POLICY_ASK and not confirm_overwrite(api, name):
        api.logger.debug(f"{label}: overwrite declined for {name}")
        return False
    return True


def store_lyric(api: PluginApi, files: list[Any], lyric: Lyric, policy: str) -> bool:
    """Write the lyric to the files, returning whether anything was written."""
    label = plugin_label(api)
    name = lyric.title or "track"
    if policy == POLICY_NEVER and has_lyrics(files):
        api.logger.debug(f"{label}: keeping existing lyrics for {name}")
        return False
    errors = apply_lyric(
        files,
        lyric,
        save_sidecar=bool(api.plugin_config["save_lrc_file"]),
        plain_as_txt=bool(api.plugin_config["plain_as_txt"]),
        bilingual=bool(api.plugin_config["bilingual_lyrics"]),
    )
    for error in errors:
        api.logger.warning(f"{label}: could not write lyrics sidecar: {error}")
    api.logger.info(
        f"{label}: lyrics from {lyric.source} applied to {len(files)} file(s) for {name}"
    )
    return True


def fetch_lyrics(
    api: PluginApi,
    album: Album,
    metadata: Metadata,
    files: list[Any],
    *,
    blocking: bool = False,
    policy: str | None = None,
    on_done: Callable[[bool], None] | None = None,
) -> bool:
    """Scrape the track, walking sources by priority.

    Returns False when nothing was started, so callers don't wait for a callback.
    """
    label = plugin_label(api)
    query = query_from_metadata(metadata)
    if not query.has_title or not files:
        return False
    policy = policy or overwrite_policy(api)
    if not scrape_allowed(api, files, policy, query.title):
        return False
    sources = active_sources(api)
    if not sources:
        api.logger.warning(f"{label}: every source is disabled")
        return False

    task_id = f"lyrics_{uuid.uuid4().hex[:8]}"
    api.add_album_task(album, task_id, "Fetching lyrics", blocking=blocking)

    def finish(lyric: Lyric | None) -> None:
        found = False
        try:
            if lyric is None:
                api.logger.debug(f"{label}: no lyrics found for {query.keyword}")
            else:
                found = store_lyric(api, files, lyric, POLICY_ALWAYS)
        except Exception:
            api.logger.exception(f"{label}: failed to store lyrics for {query.keyword}")
        finally:
            api.complete_album_task(album, task_id)
            if on_done is not None:
                on_done(found)

    runner = AutoScrape(
        query,
        sources,
        session_options(api),
        make_transport(api),
        finish,
        min_score=minimum_score(api),
        logger=api.logger.debug,
    )
    runner.start()
    return True


def overwrite_policy(api: PluginApi) -> str:
    policy = str(api.plugin_config["overwrite"] or POLICY_ASK)
    return policy if policy in (POLICY_NEVER, POLICY_ASK, POLICY_ALWAYS) else POLICY_ASK


def search_candidates(
    api: PluginApi,
    album: Album,
    query: Query,
    on_candidates: Callable[[list[Candidate]], None],
) -> None:
    """Collect candidates from every enabled source for the manual picker."""
    sources = active_sources(api)
    if not sources:
        on_candidates([])
        return
    task_id = f"lyrics_search_{uuid.uuid4().hex[:8]}"
    api.add_album_task(album, task_id, "Searching lyrics")

    def finish(candidates: list[Candidate]) -> None:
        try:
            on_candidates(candidates)
        finally:
            api.complete_album_task(album, task_id)

    runner = CandidateSearch(
        query,
        sources,
        session_options(api),
        make_transport(api),
        finish,
        min_score=minimum_score(api),
        logger=api.logger.debug,
    )
    runner.start()


def fetch_candidate(
    api: PluginApi,
    album: Album,
    query: Query,
    candidate: Candidate,
    files: list[Any],
    on_done: Callable[[bool], None] | None = None,
) -> None:
    """Fetch and store one candidate. Existing lyrics are replaced because the user picked it."""
    label = plugin_label(api)
    sources = active_sources(api)
    task_id = f"lyrics_pick_{uuid.uuid4().hex[:8]}"
    api.add_album_task(album, task_id, "Fetching lyrics")

    def finish(lyric: Lyric | None) -> None:
        found = False
        try:
            if lyric is None:
                api.logger.warning(f"{label}: lyrics unavailable for {candidate.title}")
            else:
                found = store_lyric(api, files, lyric, POLICY_ALWAYS)
        except Exception:
            api.logger.exception(
                f"{label}: failed to store lyrics for {candidate.title}"
            )
        finally:
            api.complete_album_task(album, task_id)
            if on_done is not None:
                on_done(found)

    runner = CandidateFetch(
        candidate,
        query,
        sources,
        session_options(api),
        make_transport(api),
        finish,
        logger=api.logger.debug,
    )
    runner.start()
