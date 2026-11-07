from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from src.common.models import Lyric
from src.services.apply import (
    apply_lyric,
    has_lyrics,
    sidecar_extension,
    write_text_atomic,
)


@dataclass
class FakeFile:
    filename: str | None
    metadata: dict[str, str] = field(default_factory=dict)


def lyric(text: str = "hello", synced: bool = True, translation: str = "") -> Lyric:
    return Lyric(
        text=text,
        synced=synced,
        source="test",
        title="Song",
        translation=translation,
    )


def test_apply_lyric_merges_translation_when_bilingual(tmp_path: Path) -> None:
    audio = tmp_path / "song.flac"
    audio.write_bytes(b"")
    file = FakeFile(str(audio))
    bilingual = lyric(
        text="[00:01.00]Hello", synced=True, translation="[00:01.00]你好"
    )

    apply_lyric([file], bilingual, bilingual=True)

    expected = "[00:01.00]Hello\n[00:01.00]你好"
    assert file.metadata["lyrics"] == expected
    assert (tmp_path / "song.lrc").read_text(encoding="utf-8") == f"{expected}\n"


def test_apply_lyric_keeps_original_when_bilingual_off(tmp_path: Path) -> None:
    audio = tmp_path / "song.flac"
    audio.write_bytes(b"")
    file = FakeFile(str(audio))
    bilingual = lyric(
        text="[00:01.00]Hello", synced=True, translation="[00:01.00]你好"
    )

    apply_lyric([file], bilingual)

    assert file.metadata["lyrics"] == "[00:01.00]Hello"


def test_sidecar_extension() -> None:
    assert sidecar_extension(synced=True, plain_as_txt=False) == ".lrc"
    assert sidecar_extension(synced=False, plain_as_txt=False) == ".lrc"
    assert sidecar_extension(synced=False, plain_as_txt=True) == ".txt"
    assert sidecar_extension(synced=True, plain_as_txt=True) == ".lrc"


def test_apply_lyric_tags_and_writes_sidecar(tmp_path: Path) -> None:
    audio = tmp_path / "song.flac"
    audio.write_bytes(b"")
    file = FakeFile(str(audio))

    errors = apply_lyric([file], lyric())

    assert errors == []
    assert file.metadata["lyrics"] == "hello"
    assert (tmp_path / "song.lrc").read_text(encoding="utf-8") == "hello\n"


def test_apply_lyric_can_write_txt_for_plain_lyrics(tmp_path: Path) -> None:
    audio = tmp_path / "song.mp3"
    audio.write_bytes(b"")
    file = FakeFile(str(audio))

    apply_lyric([file], lyric("plain", synced=False), plain_as_txt=True)

    assert (tmp_path / "song.txt").exists()
    assert not (tmp_path / "song.lrc").exists()


def test_apply_lyric_can_skip_the_sidecar(tmp_path: Path) -> None:
    audio = tmp_path / "song.mp3"
    audio.write_bytes(b"")
    file = FakeFile(str(audio))

    apply_lyric([file], lyric(), save_sidecar=False)

    assert file.metadata["lyrics"] == "hello"
    assert not (tmp_path / "song.lrc").exists()


def test_apply_lyric_skips_files_without_a_path() -> None:
    file = FakeFile(None)
    apply_lyric([file], lyric())
    assert file.metadata["lyrics"] == "hello"


def test_apply_lyric_reports_write_errors(tmp_path: Path) -> None:
    missing = tmp_path / "gone" / "song.flac"
    file = FakeFile(str(missing))
    errors = apply_lyric([file], lyric())
    assert errors
    assert str(missing) in errors[0]


def test_write_text_atomic_creates_parent_relative_files(tmp_path: Path) -> None:
    target = tmp_path / "out.lrc"
    assert write_text_atomic(str(target), "text\n") is None
    assert target.read_text(encoding="utf-8") == "text\n"


def test_has_lyrics() -> None:
    assert not has_lyrics([FakeFile("/a.mp3")])
    assert not has_lyrics([FakeFile("/a.mp3", {"lyrics": "   "})])
    assert has_lyrics([FakeFile("/a.mp3", {"lyrics": "words"})])
