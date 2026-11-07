from __future__ import annotations

from collections.abc import Iterable, Sequence

from .base import Source
from .kugou import KugouSource
from .kuwo import KuwoSource
from .lrclib import LrclibSource
from .lyricsovh import LyricsOvhSource
from .netease import NeteaseSource

SOURCES: tuple[type[Source], ...] = (
    LrclibSource,
    NeteaseSource,
    KugouSource,
    KuwoSource,
    LyricsOvhSource,
)

SOURCES_BY_ID: dict[str, type[Source]] = {source.ID: source for source in SOURCES}

DEFAULT_ORDER: tuple[str, ...] = tuple(source.ID for source in SOURCES)


def source_ids() -> tuple[str, ...]:
    return tuple(SOURCES_BY_ID)


def source_names() -> dict[str, str]:
    return {source.ID: source.NAME for source in SOURCES}


def ordered_sources(
    order: Sequence[str] | None, disabled: Iterable[str] = ()
) -> list[Source]:
    """Build sources in the stored order, append new ones and skip disabled ones."""
    disabled_ids = {item for item in disabled}
    seen: set[str] = set()
    result: list[Source] = []
    for identifier in list(order or DEFAULT_ORDER) + list(DEFAULT_ORDER):
        if identifier in seen or identifier in disabled_ids:
            continue
        source = SOURCES_BY_ID.get(identifier)
        if source is None:
            continue
        seen.add(identifier)
        result.append(source())
    return result
