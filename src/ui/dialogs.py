from __future__ import annotations

from collections.abc import Sequence

from PyQt6 import QtWidgets

from picard.plugin3.api import PluginApi

from ..common.models import Candidate
from ..common.text import format_duration


def active_parent() -> QtWidgets.QWidget | None:
    return QtWidgets.QApplication.activeWindow()


def confirm(api: PluginApi, title: str, text: str, default_no: bool = True) -> bool:
    try:
        default = (
            QtWidgets.QMessageBox.StandardButton.No
            if default_no
            else QtWidgets.QMessageBox.StandardButton.Yes
        )
        answer = QtWidgets.QMessageBox.question(
            active_parent(),
            title,
            text,
            QtWidgets.QMessageBox.StandardButton.Yes
            | QtWidgets.QMessageBox.StandardButton.No,
            default,
        )
        return answer == QtWidgets.QMessageBox.StandardButton.Yes
    except Exception:
        api.logger.exception("could not show confirmation dialog")
        return False


def confirm_overwrite(api: PluginApi, name: str) -> bool:
    return confirm(
        api,
        "Overwrite existing lyrics?",
        f"{name or 'This track'} already has lyrics.\n\nReplace them with freshly scraped lyrics?",
    )


def show_warning(api: PluginApi, title: str, text: str) -> None:
    try:
        QtWidgets.QMessageBox.warning(active_parent(), title, text)
    except Exception:
        api.logger.exception("could not show warning dialog")


class CandidateDialog(QtWidgets.QDialog):
    COLUMNS = ("Source", "Title", "Artist", "Album", "Length", "Match")

    def __init__(
        self,
        candidates: Sequence[Candidate],
        keyword: str,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.candidates = list(candidates)
        self.setWindowTitle(f"Lyrics search results: {keyword}")
        self.resize(820, 420)

        layout = QtWidgets.QVBoxLayout(self)
        self.table = QtWidgets.QTableWidget(
            len(self.candidates), len(self.COLUMNS), self
        )
        self.table.setHorizontalHeaderLabels(list(self.COLUMNS))
        self.table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.table.setSelectionMode(
            QtWidgets.QAbstractItemView.SelectionMode.SingleSelection
        )
        self.table.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.table.verticalHeader().setVisible(False)
        for row, candidate in enumerate(self.candidates):
            values = (
                candidate.source,
                candidate.title,
                candidate.artist,
                candidate.album,
                format_duration(candidate.duration),
                f"{candidate.score:.2f}",
            )
            for column, value in enumerate(values):
                self.table.setItem(row, column, QtWidgets.QTableWidgetItem(str(value)))
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.resizeColumnsToContents()
        layout.addWidget(self.table)
        if self.candidates:
            self.table.selectRow(0)

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def selected(self) -> Candidate | None:
        row = self.table.currentRow()
        if 0 <= row < len(self.candidates):
            return self.candidates[row]
        return None


def choose_candidate(
    api: PluginApi, candidates: Sequence[Candidate], keyword: str
) -> Candidate | None:
    try:
        dialog = CandidateDialog(candidates, keyword, active_parent())
        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            return dialog.selected()
    except Exception:
        api.logger.exception("could not show lyrics search results")
    return None
