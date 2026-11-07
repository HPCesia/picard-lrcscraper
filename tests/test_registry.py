from __future__ import annotations

from src.sources.registry import (
    DEFAULT_ORDER,
    ordered_sources,
    source_ids,
    source_names,
)


def test_default_order_covers_every_source() -> None:
    assert set(DEFAULT_ORDER) == set(source_ids())
    assert len(DEFAULT_ORDER) == len(set(DEFAULT_ORDER))


def test_source_names_are_human_readable() -> None:
    names = source_names()
    assert names["lrclib"] == "LRCLIB"
    assert all(name for name in names.values())


def test_ordered_sources_follows_the_configured_order() -> None:
    sources = ordered_sources(["kuwo", "lrclib"], [])
    assert [source.ID for source in sources][:2] == ["kuwo", "lrclib"]
    assert {source.ID for source in sources} == set(DEFAULT_ORDER)


def test_ordered_sources_skips_disabled_ones() -> None:
    sources = ordered_sources(None, ["kugou", "kuwo"])
    identifiers = {source.ID for source in sources}
    assert "kugou" not in identifiers
    assert "kuwo" not in identifiers
    assert identifiers == set(DEFAULT_ORDER) - {"kugou", "kuwo"}


def test_ordered_sources_ignores_unknown_identifiers() -> None:
    sources = ordered_sources(["does-not-exist", "lrclib"], [])
    assert next(source.ID for source in sources) == "lrclib"


def test_ordered_sources_appends_new_sources_missing_from_saved_order() -> None:
    sources = ordered_sources(["lrclib"], [])
    assert {source.ID for source in sources} == set(DEFAULT_ORDER)


def test_ordered_sources_never_duplicates() -> None:
    identifiers = [source.ID for source in ordered_sources(["lrclib", "lrclib"], [])]
    assert len(identifiers) == len(set(identifiers))
