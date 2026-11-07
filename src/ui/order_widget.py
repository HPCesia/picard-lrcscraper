from __future__ import annotations

from PyQt6 import QtCore, QtWidgets

from ..sources.registry import DEFAULT_ORDER, source_names


class SourceOrderWidget(QtWidgets.QWidget):
    """Re-orderable, checkable list of lyric sources."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.names = source_names()

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.list = QtWidgets.QListWidget(self)
        self.list.setSelectionMode(
            QtWidgets.QAbstractItemView.SelectionMode.SingleSelection
        )
        self.list.setDragDropMode(QtWidgets.QAbstractItemView.DragDropMode.InternalMove)
        layout.addWidget(self.list, 1)

        buttons = QtWidgets.QVBoxLayout()
        self.up_button = QtWidgets.QPushButton("Move Up", self)
        self.down_button = QtWidgets.QPushButton("Move Down", self)
        self.reset_button = QtWidgets.QPushButton("Restore Defaults", self)
        for button in (self.up_button, self.down_button, self.reset_button):
            buttons.addWidget(button)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        self.up_button.clicked.connect(self._move_up)
        self.down_button.clicked.connect(self._move_down)
        self.reset_button.clicked.connect(self.restore_defaults)

    def _add_source(self, identifier: str, checked: bool) -> None:
        item = QtWidgets.QListWidgetItem(
            self.names.get(identifier, identifier), self.list
        )
        item.setData(QtCore.Qt.ItemDataRole.UserRole, identifier)
        item.setFlags(
            QtCore.Qt.ItemFlag.ItemIsEnabled
            | QtCore.Qt.ItemFlag.ItemIsSelectable
            | QtCore.Qt.ItemFlag.ItemIsUserCheckable
            | QtCore.Qt.ItemFlag.ItemIsDragEnabled
        )
        item.setCheckState(
            QtCore.Qt.CheckState.Checked if checked else QtCore.Qt.CheckState.Unchecked
        )

    def load_order(self, order: list[str], disabled: list[str]) -> None:
        self.list.clear()
        disabled_ids = set(disabled)
        known = set(self.names)
        for identifier in list(order) + list(DEFAULT_ORDER):
            if identifier in known:
                self._add_source(identifier, identifier not in disabled_ids)
                known.discard(identifier)

    def restore_defaults(self) -> None:
        self.load_order(list(DEFAULT_ORDER), [])

    def order(self) -> list[str]:
        return [
            str(self.list.item(row).data(QtCore.Qt.ItemDataRole.UserRole))
            for row in range(self.list.count())
        ]

    def disabled(self) -> list[str]:
        result = []
        for row in range(self.list.count()):
            item = self.list.item(row)
            if item.checkState() != QtCore.Qt.CheckState.Checked:
                result.append(str(item.data(QtCore.Qt.ItemDataRole.UserRole)))
        return result

    def _move_up(self) -> None:
        row = self.list.currentRow()
        if row <= 0:
            return
        item = self.list.takeItem(row)
        self.list.insertItem(row - 1, item)
        self.list.setCurrentRow(row - 1)

    def _move_down(self) -> None:
        row = self.list.currentRow()
        if row < 0 or row >= self.list.count() - 1:
            return
        item = self.list.takeItem(row)
        self.list.insertItem(row + 1, item)
        self.list.setCurrentRow(row + 1)
