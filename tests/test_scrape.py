from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("picard.plugin3.api")
pytest.importorskip("PyQt6")

from src.common.models import Lyric
from src.services import scrape
from src.services.scrape import (
    POLICY_ALWAYS,
    POLICY_ASK,
    POLICY_NEVER,
    overwrite_policy,
    query_from_metadata,
    scrape_allowed,
    store_lyric,
)


class FakeLogger:
    def __init__(self) -> None:
        self.records: list[tuple[str, str]] = []

    def debug(self, message: str, *args: object, **kwargs: object) -> None:
        self.records.append(("debug", message))

    info = warning = error = exception = debug


class FakeManifest:
    def name_i18n(self) -> str:
        return "LRC Scraper"


class FakeMetadata(dict):
    def __getitem__(self, key: str) -> str:
        return self.get(key) or ""


class FakeFile:
    def __init__(
        self, filename: str | None, metadata: FakeMetadata | None = None
    ) -> None:
        self.filename = filename
        self.metadata = metadata if metadata is not None else FakeMetadata()


class FakeApi:
    def __init__(self, config: dict[str, object]) -> None:
        self.plugin_config = config
        self.logger = FakeLogger()
        self.manifest = FakeManifest()


def config(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "overwrite": POLICY_ASK,
        "min_score": 0.6,
        "save_lrc_file": True,
        "plain_as_txt": False,
    }
    base.update(overrides)
    return base


def lyric(text: str = "[00:01.00] hello") -> Lyric:
    return Lyric(text=text, synced=True, source="lrclib", title="Song")


def test_query_from_metadata_parses_length() -> None:
    metadata = FakeMetadata({"~length": "5:55", "title": "Song", "artist": "Artist"})
    query = query_from_metadata(metadata)
    assert query.title == "Song"
    assert query.artist == "Artist"
    assert query.duration == 355


def test_query_from_metadata_without_length() -> None:
    query = query_from_metadata(FakeMetadata({"title": "Song"}))
    assert query.duration is None


def test_overwrite_policy_rejects_unknown_values() -> None:
    assert overwrite_policy(FakeApi(config(overwrite="nonsense"))) == POLICY_ASK
    assert overwrite_policy(FakeApi(config(overwrite=POLICY_NEVER))) == POLICY_NEVER


def test_scrape_allowed_when_no_lyrics_exist() -> None:
    files = [FakeFile("/music/a.mp3")]
    assert scrape_allowed(FakeApi(config()), files, POLICY_NEVER, "Song")


def test_scrape_allowed_never_blocks_existing_lyrics() -> None:
    files = [FakeFile("/music/a.mp3", FakeMetadata({"lyrics": "old"}))]
    assert not scrape_allowed(FakeApi(config()), files, POLICY_NEVER, "Song")


def test_scrape_allowed_ask_uses_the_dialog(monkeypatch: pytest.MonkeyPatch) -> None:
    files = [FakeFile("/music/a.mp3", FakeMetadata({"lyrics": "old"}))]
    monkeypatch.setattr(scrape, "confirm_overwrite", lambda api, name: False)
    assert not scrape_allowed(FakeApi(config()), files, POLICY_ASK, "Song")

    monkeypatch.setattr(scrape, "confirm_overwrite", lambda api, name: True)
    assert scrape_allowed(FakeApi(config()), files, POLICY_ASK, "Song")


def test_scrape_allowed_always_ignores_existing_lyrics() -> None:
    files = [FakeFile("/music/a.mp3", FakeMetadata({"lyrics": "old"}))]
    assert scrape_allowed(FakeApi(config()), files, POLICY_ALWAYS, "Song")


def test_store_lyric_writes_tag_and_sidecar(tmp_path: Path) -> None:
    audio = tmp_path / "song.mp3"
    audio.write_bytes(b"")
    files = [FakeFile(str(audio))]

    assert store_lyric(FakeApi(config()), files, lyric(), POLICY_ALWAYS)

    assert files[0].metadata["lyrics"] == "[00:01.00] hello"
    assert (tmp_path / "song.lrc").read_text(encoding="utf-8") == "[00:01.00] hello\n"


def test_store_lyric_honours_never_policy() -> None:
    files = [FakeFile("/music/a.mp3", FakeMetadata({"lyrics": "old"}))]
    assert not store_lyric(FakeApi(config()), files, lyric(), POLICY_NEVER)
    assert files[0].metadata["lyrics"] == "old"


def test_store_lyric_without_sidecar_configuration() -> None:
    files = [FakeFile(None)]
    assert store_lyric(FakeApi(config()), files, lyric("plain"), POLICY_ALWAYS)
    assert files[0].metadata["lyrics"] == "plain"


class FakeAlbum:
    id = "album-1"

    def __init__(self) -> None:
        self.tasks: list[str] = []

    def add_task(self, **kwargs: object) -> None:
        self.tasks.append(str(kwargs["task_id"]))


def test_fetch_lyrics_bails_out_without_a_title() -> None:
    album = FakeAlbum()
    api = FakeApi(config())
    assert not scrape.fetch_lyrics(
        api, album, FakeMetadata({"artist": "Nobody"}), [FakeFile("/music/a.mp3")]
    )
    assert album.tasks == []


def test_fetch_lyrics_bails_out_when_existing_lyrics_are_kept() -> None:
    album = FakeAlbum()
    api = FakeApi(config(overwrite=POLICY_NEVER))
    files = [FakeFile("/music/a.mp3", FakeMetadata({"lyrics": "old"}))]
    metadata = FakeMetadata({"title": "Song", "artist": "Artist"})
    assert not scrape.fetch_lyrics(api, album, metadata, files)
    assert album.tasks == []
