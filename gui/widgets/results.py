"""Table, result display, and action controls shared by feature panels."""

from collections.abc import Sequence

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QTableView,
    QVBoxLayout,
    QWidget,
)


class _RowsModel(QAbstractTableModel):
    def __init__(self, headers: Sequence[str], parent: QWidget) -> None:
        super().__init__(parent)
        self._headers = tuple(headers)
        self._rows: Sequence[Sequence[object]] = ()

    def set_rows(self, rows: Sequence[Sequence[object]]) -> None:
        self.beginResetModel()
        self._rows = rows
        self.endResetModel()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._headers)

    def headerData(
        self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole
    ) -> str | None:
        if (
            role == Qt.ItemDataRole.DisplayRole
            and orientation == Qt.Orientation.Horizontal
            and 0 <= section < len(self._headers)
        ):
            return self._headers[section]
        return None

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> str | None:
        if not index.isValid() or role != Qt.ItemDataRole.DisplayRole:
            return None
        value = self._rows[index.row()][index.column()]
        return "" if value is None else str(value)


class DataTable(QTableView):
    """Read-only table that formats cells on demand."""

    def __init__(self, headers: Sequence[str], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._rows_model = _RowsModel(headers, self)
        self.setModel(self._rows_model)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setAlternatingRowColors(True)
        self.verticalHeader().setVisible(False)
        self.horizontalHeader().setStretchLastSection(True)

    def set_rows(self, rows: Sequence[Sequence[object]]) -> None:
        """Use existing rows, each with one value per header. Replace rows to refresh."""
        self._rows_model.set_rows(rows)


class ResultArea(QFrame):
    """Switch between a feature's result widget and a plain-text message."""

    def __init__(self, content: QWidget, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("surface")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        self._stack = QStackedWidget()
        self._message = QLabel()
        self._message.setObjectName("helpText")
        self._message.setTextFormat(Qt.TextFormat.PlainText)
        self._message.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._message.setWordWrap(True)
        self._stack.addWidget(self._message)
        self._stack.addWidget(content)
        layout.addWidget(self._stack)
        self.show_message("Belum ada hasil.")

    def show_message(self, message: str) -> None:
        self._message.setText(message)
        self._stack.setCurrentIndex(0)

    def show_result(self) -> None:
        self._stack.setCurrentIndex(1)


class TaskControls(QWidget):
    """Buttons for a feature's initial run, reset, and re-run."""

    run_requested = Signal()
    reset_requested = Signal()
    rerun_requested = Signal()

    def __init__(
        self, run_label: str = "Jalankan Analisis", parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.run_button = QPushButton(run_label)
        self.run_button.setObjectName("primaryAction")
        self.reset_button = QPushButton("Reset hasil")
        self.rerun_button = QPushButton("Jalankan ulang")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        for button in (self.run_button, self.reset_button, self.rerun_button):
            layout.addWidget(button)
        layout.addStretch()
        self.run_button.clicked.connect(self.run_requested.emit)
        self.reset_button.clicked.connect(self.reset_requested.emit)
        self.rerun_button.clicked.connect(self.rerun_requested.emit)
        self.set_availability(run=False, reset=False, rerun=False)

    def set_availability(self, *, run: bool, reset: bool, rerun: bool) -> None:
        self.run_button.setEnabled(run)
        self.reset_button.setEnabled(reset)
        self.rerun_button.setEnabled(rerun)
