from __future__ import annotations

from picard.plugin3.api import PluginApi

from .src.actions.actions import FetchLyricsAuto, FetchLyricsManual
from .src.callbacks.hooks import get_on_load, get_on_save
from .src.options.config import register_options
from .src.options.page import LyricsOptionsPage


def enable(api: PluginApi) -> None:
    register_options(api)
    api.register_file_post_addition_to_track_processor(get_on_load)
    api.register_file_post_save_processor(get_on_save)
    api.register_track_action(FetchLyricsAuto)
    api.register_album_action(FetchLyricsAuto)
    api.register_track_action(FetchLyricsManual)
    api.register_album_action(FetchLyricsManual)
    api.register_options_page(LyricsOptionsPage)


def disable() -> None:
    """Picard drops the registrations from `enable` itself."""
