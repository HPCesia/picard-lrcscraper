from __future__ import annotations

from typing import NamedTuple

from picard.plugin3.api import PluginApi

from ..sources.registry import DEFAULT_ORDER


class FlagOption(NamedTuple):
    key: str
    label: str
    default: bool


FLAGS: tuple[FlagOption, ...] = (
    FlagOption(
        "get_on_load",
        "Fetch lyrics when a track is loaded (slows down loading)",
        False,
    ),
    FlagOption("get_on_save", "Fetch lyrics when a file is saved", False),
    FlagOption("prefer_synced", "Prefer synchronized lyrics", True),
    FlagOption(
        "save_lrc_file", "Write a lyric sidecar file next to the audio file", True
    ),
    FlagOption("plain_as_txt", "Save plain lyrics as .txt instead of .lrc", False),
)

OVERWRITE_CHOICES: tuple[tuple[str, str], ...] = (
    ("never", "Never"),
    ("ask", "Ask me"),
    ("always", "Always"),
)

DEFAULT_OVERWRITE = "ask"
DEFAULT_MIN_SCORE = 0.6


def register_options(api: PluginApi) -> None:
    config = api.plugin_config
    config.register_option("source_order", list(DEFAULT_ORDER))
    config.register_option("disabled_sources", [])
    config.register_option("overwrite", DEFAULT_OVERWRITE)
    config.register_option("min_score", DEFAULT_MIN_SCORE, bounds=(0.0, 1.0))
    for flag in FLAGS:
        config.register_option(flag.key, flag.default)
