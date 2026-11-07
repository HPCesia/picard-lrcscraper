from __future__ import annotations

from PyQt6 import QtWidgets

from picard.plugin3.api import OptionsPage

from ..ui.order_widget import SourceOrderWidget
from .config import (
    DEFAULT_MIN_SCORE,
    DEFAULT_OVERWRITE,
    FLAGS,
    OVERWRITE_CHOICES,
)


class LyricsOptionsPage(OptionsPage):
    NAME = "lrc_scraper"
    TITLE = "LRC Scraper"
    PARENT = "plugins"

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.box = QtWidgets.QVBoxLayout(self)

        self.box.addWidget(
            QtWidgets.QLabel(
                "Checked sources are queried top to bottom; the first source "
                "returning lyrics wins.",
                self,
            )
        )
        self.sources = SourceOrderWidget(self)
        self.box.addWidget(self.sources, 1)

        flags_box = QtWidgets.QGroupBox("Behaviour", self)
        flags_layout = QtWidgets.QVBoxLayout(flags_box)
        self.checkboxes: dict[str, QtWidgets.QCheckBox] = {}
        for flag in FLAGS:
            checkbox = QtWidgets.QCheckBox(flag.label, flags_box)
            flags_layout.addWidget(checkbox)
            self.checkboxes[flag.key] = checkbox

        row = QtWidgets.QHBoxLayout()
        row.addWidget(QtWidgets.QLabel("When lyrics already exist:", flags_box))
        self.overwrite = QtWidgets.QComboBox(flags_box)
        for identifier, label in OVERWRITE_CHOICES:
            self.overwrite.addItem(label, identifier)
        row.addWidget(self.overwrite)
        flags_layout.addLayout(row)

        score_row = QtWidgets.QHBoxLayout()
        score_row.addWidget(QtWidgets.QLabel("Minimum match score:", flags_box))
        self.min_score = QtWidgets.QDoubleSpinBox(flags_box)
        self.min_score.setRange(0.0, 1.0)
        self.min_score.setSingleStep(0.05)
        self.min_score.setDecimals(2)
        score_row.addWidget(self.min_score)
        score_row.addStretch(1)
        flags_layout.addLayout(score_row)

        self.box.addWidget(flags_box)

        note = QtWidgets.QLabel(
            "Lyrics are provided by third party services for personal use only. "
            "Lyrics.ovh is only used when the track has an artist.",
            self,
        )
        note.setWordWrap(True)
        self.box.addWidget(note)

    def load(self) -> None:
        config = self.api.plugin_config
        self.sources.load_order(
            list(config["source_order"] or []),
            list(config["disabled_sources"] or []),
        )
        for flag in FLAGS:
            self.checkboxes[flag.key].setChecked(bool(config[flag.key]))
        index = self.overwrite.findData(str(config["overwrite"] or DEFAULT_OVERWRITE))
        self.overwrite.setCurrentIndex(max(0, index))
        self.min_score.setValue(float(config["min_score"] or DEFAULT_MIN_SCORE))

    def save(self) -> None:
        config = self.api.plugin_config
        config["source_order"] = self.sources.order()
        config["disabled_sources"] = self.sources.disabled()
        for flag in FLAGS:
            config[flag.key] = self.checkboxes[flag.key].isChecked()
        config["overwrite"] = self.overwrite.currentData()
        config["min_score"] = round(self.min_score.value(), 2)
