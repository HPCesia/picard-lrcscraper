from __future__ import annotations

from picard.plugin3.api import File, PluginApi, Track

from ..common import state
from ..services.scrape import fetch_lyrics, plugin_label


def get_on_load(api: PluginApi, track: Track, file: File) -> None:
    if not api.plugin_config["get_on_load"]:
        return
    if not track.files:
        return
    if track.album is None:
        return
    key = id(track)
    # The hook fires once per added file, and the fetch blocks album loading.
    if key in state.tracks_processing:
        return
    state.tracks_processing.add(key)
    started = fetch_lyrics(
        api,
        track.album,
        track.metadata,
        list(track.files),
        blocking=True,
        policy="never",
        on_done=lambda _found: state.tracks_processing.discard(key),
    )
    if not started:
        state.tracks_processing.discard(key)


def get_on_save(api: PluginApi, file: File) -> None:
    """Scrape after a save, then save again when lyrics were found."""
    if not api.plugin_config["get_on_save"]:
        return
    filename = file.filename
    if not filename:
        return
    # The save below re-enters this hook, which must not scrape a second time.
    if filename in state.files_processing:
        state.files_processing.discard(filename)
        return
    parent = getattr(file, "parent_item", None)
    album = parent.album if isinstance(parent, Track) else None
    if album is None:
        return
    state.files_processing.add(filename)

    def finished(found: bool) -> None:
        state.files_processing.discard(filename)
        if not found:
            return
        try:
            file.save()
        except Exception:
            api.logger.exception(f"{plugin_label(api)}: could not save {filename}")

    started = fetch_lyrics(
        api, album, file.metadata, [file], policy="never", on_done=finished
    )
    if not started:
        state.files_processing.discard(filename)
