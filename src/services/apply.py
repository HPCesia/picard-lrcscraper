from __future__ import annotations

import contextlib
import os
import shutil
import tempfile
from collections.abc import Iterable
from typing import Any

from ..common.models import Lyric
from ..common.text import merge_bilingual, sidecar_path

LYRICS_TAG = "lyrics"


def sidecar_extension(synced: bool, plain_as_txt: bool) -> str:
    return ".txt" if (not synced and plain_as_txt) else ".lrc"


def lyrics_text(lyric: Lyric, bilingual: bool) -> str:
    if bilingual and lyric.synced and lyric.translation:
        return merge_bilingual(lyric.text, lyric.translation)
    return lyric.text


def write_text_atomic(path: str, text: str) -> str | None:
    """Write `text` atomically, returning an error message or None.

    Players watch sidecar files, so `path` must never hold a half-written file.
    """
    directory = os.path.dirname(path) or "."
    temp_path: str | None = None
    try:
        handle, temp_path = tempfile.mkstemp(
            dir=directory, prefix=".lyrics-", suffix=".tmp"
        )
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
        if os.path.exists(path):
            shutil.copymode(path, temp_path)
        else:
            os.chmod(temp_path, 0o644)
        os.replace(temp_path, path)
    except OSError as error:
        if temp_path is not None and os.path.exists(temp_path):
            with contextlib.suppress(OSError):
                os.remove(temp_path)
        return str(error)
    return None


def has_lyrics(files: Iterable[Any]) -> bool:
    for file in files:
        metadata = getattr(file, "metadata", None)
        if metadata is None:
            continue
        if str(metadata.get(LYRICS_TAG) or "").strip():
            return True
    return False


def apply_lyric(
    files: Iterable[Any],
    lyric: Lyric,
    save_sidecar: bool = True,
    plain_as_txt: bool = False,
    bilingual: bool = False,
) -> list[str]:
    """Set the `lyrics` tag on every file, write sidecars and return write errors."""
    errors: list[str] = []
    text = lyrics_text(lyric, bilingual)
    extension = sidecar_extension(lyric.synced, plain_as_txt)
    for file in files:
        metadata = getattr(file, "metadata", None)
        if metadata is not None:
            metadata[LYRICS_TAG] = text
        if not save_sidecar:
            continue
        filename = getattr(file, "filename", None)
        if not filename:
            continue
        error = write_text_atomic(sidecar_path(filename, extension), f"{text}\n")
        if error is not None:
            errors.append(f"{filename}: {error}")
    return errors
