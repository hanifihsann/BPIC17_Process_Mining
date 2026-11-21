"""Embeddable PySide6 page for Exercise 11.22 (O_Cancelled -> O_Accepted).

Designed to be mounted inside Member 5's main application window as a QWidget.
Does not instantiate a QApplication or a second QMainWindow, and never reloads
the XES file from disk.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, QThread, Qt, Signal, Slot
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from modules.exercise_1122 import RULE_DESCRIPTION, analyze_1122


class Exercise1122Worker(QObject):
    """Background worker executing ``analyze_1122`` off the UI thread."""

    completed = Signal(object)
    failed = Signal(str)

    def __init__(self, log_or_df: Any) -> None:
        super().__init__()
        self._log_or_df = log_or_df

    @Slot()
    def run(self) -> None:
        try:
            result = analyze_1122(self._log_or_df)
            self.completed.emit(result)
        except Exception as error:
            self.failed.emit(str(error))


class Exercise1122Page(QWidget):
    """Embeddable Exercise 11.22 page widget.

    Integration signals
    -------------------
    ``analysis_started()``
        Emitted when background analysis starts.
    ``analysis_completed(result)``
        Emitted with the result dict from ``analyze_1122``.
    ``analysis_failed(message)``
        Emitted when validation or analysis raises an error.
    ``case_selected(case_id, evidence_record)``
        Emitted when a matching case row is clicked.
    ``open_case_requested(case_id, evidence_record)``
        Emitted when the user double-clicks a row or clicks "Buka di Case Explorer".
    """

    analysis_started = Signal()
    analysis_completed = Signal(object)
    analysis_failed = Signal(str)
    case_selected = Signal(object, object)
    open_case_requested = Signal(object, object)
    state_changed = Signal(str)

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        on_open_case: Callable[[Any, dict[str, Any]], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self._active_log: Any | None = None
        self._active_metadata: dict[str, Any] | None = None
        self._last_result: dict[str, Any] | None = None
        self._evidence_rows: list[dict[str, Any]] = []
        self._on_open_case = on_open_case
        self._state: str = "no_dataset"

        self._thread: QThread | None = None
        self._worker: Exercise1122Worker | None = None
        self._closing = False

        self._build_ui()
        self._apply_state("no_dataset", "Dataset belum dimuat. Muat file XES pada halaman Import/Overview.")

    def _build_ui(self) -> None:
        self.setObjectName("exercise1122Page")
        root = QVBoxLayout(self)

        # Control & rule header
        control_box = QGroupBox("Exercise 11.22 — O_Cancelled diikuti O_Accepted")
        control_layout = QVBoxLayout(control_box)

        self.rule_label = QLabel(f"Aturan filter: {RULE_DESCRIPTION}")
        self.rule_label.setWordWrap(True)
        control_layout.addWidget(self.rule_label)

        btn_row = QHBoxLayout()
        self.run_button = QPushButton("Jalankan Analisis")
        self.run_button.clicked.connect(self.run_analysis)
        self.reset_button = QPushButton("Reset Hasil")
        self.reset_button.clicked.connect(self.reset_results)
        self.open_explorer_button = QPushButton("Buka di Case Explorer")
        self.open_explorer_button.clicked.connect(self._open_selected_row)

        btn_row.addWidget(self.run_button)
        btn_row.addWidget(self.reset_button)
        btn_row.addWidget(self.open_explorer_button)
        btn_row.addStretch(1)
        control_layout.addLayout(btn_row)

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        control_layout.addWidget(self.status_label)
        root.addWidget(control_box)

        # Summary metrics
        summary_box = QGroupBox("Ringkasan Hasil")
        summary_layout = QGridLayout(summary_box)

        self.count_label = QLabel("-")
        self.denominator_label = QLabel("-")
        self.percentage_label = QLabel("-")
        self.dataset_label = QLabel("Belum ada dataset aktif")

        summary_layout.addWidget(QLabel("Dataset aktif:"), 0, 0)
        summary_layout.addWidget(self.dataset_label, 0, 1, 1, 3)
        summary_layout.addWidget(QLabel("Jumlah case lolos:"), 1, 0)
        summary_layout.addWidget(self.count_label, 1, 1)
        summary_layout.addWidget(QLabel("Total active cases (denominator):"), 1, 2)
        summary_layout.addWidget(self.denominator_label, 1, 3)
        summary_layout.addWidget(QLabel("Persentase:"), 2, 0)
        summary_layout.addWidget(self.percentage_label, 2, 1)
        root.addWidget(summary_box)

        # Matching cases table
        table_box = QGroupBox("Daftar Case Terpilih (Klik dua kali untuk membuka Case Explorer)")
        table_layout = QVBoxLayout(table_box)

        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Filter Case ID:"))
        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("Ketik sebagian Case ID...")
        self.filter_input.textChanged.connect(self._filter_table)
        filter_row.addWidget(self.filter_input)
        table_layout.addLayout(filter_row)

        self.result_table = QTableWidget(0, 6)
        self.result_table.setHorizontalHeaderLabels(
            [
                "Case ID",
                "Urutan O_Cancelled",
                "Timestamp O_Cancelled",
                "Urutan O_Accepted",
                "Timestamp O_Accepted",
                "Total Event",
            ]
        )
        self._configure_table(self.result_table)
        self.result_table.cellClicked.connect(self._on_row_clicked)
        self.result_table.cellDoubleClicked.connect(self._on_row_double_clicked)
        self.result_table.itemSelectionChanged.connect(self._update_open_button_state)
        table_layout.addWidget(self.result_table)
        root.addWidget(table_box, 1)

        # Error / diagnostics info
        diag_box = QGroupBox("Status / Pesan")
        diag_layout = QFormLayout(diag_box)
        self.message_label = QLabel("-")
        self.message_label.setWordWrap(True)
        diag_layout.addRow("Keterangan:", self.message_label)
        root.addWidget(diag_box)

    @staticmethod
    def _configure_table(table: QTableWidget) -> None:
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setSelectionMode(QAbstractItemView.SingleSelection)
        table.setAlternatingRowColors(True)
        table.setSortingEnabled(False)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        table.horizontalHeader().setStretchLastSection(True)
        table.verticalHeader().setVisible(False)

    @property
    def current_state(self) -> str:
        """Return the current UI state name."""

        return self._state

    @property
    def last_result(self) -> dict[str, Any] | None:
        """Return the latest result dictionary from ``analyze_1122``."""

        return self._last_result

    def is_running(self) -> bool:
        """Return True if a background analysis thread is currently active."""

        return self._thread is not None

    def _apply_state(self, state: str, message: str) -> None:
        self._state = state
        self.status_label.setText(message)
        self.message_label.setText(message)

        has_dataset = self._active_log is not None
        running = state == "loading"

        self.run_button.setEnabled(has_dataset and not running)
        self.reset_button.setEnabled(has_dataset and not running)
        self.filter_input.setEnabled(not running and len(self._evidence_rows) > 0)
        self._update_open_button_state()
        self.state_changed.emit(state)

    def _update_open_button_state(self) -> None:
        has_selection = (
            self._state != "loading"
            and self.result_table.currentRow() >= 0
            and self.result_table.currentRow() < len(self._evidence_rows)
        )
        self.open_explorer_button.setEnabled(has_selection)

    @Slot(object)
    @Slot(object, object)
    @Slot(object, object, object)
    def set_dataset(
        self,
        log_or_df: Any,
        metadata: dict[str, Any] | None = None,
        overview: dict[str, Any] | None = None,
    ) -> None:
        """Attach the active in-memory dataset without reading XES from disk."""

        del overview  # Not required for 11.22; accepted for signal compatibility.
        if self.is_running():
            self._apply_state("loading", "Analisis sedang berjalan; tunggu hingga selesai sebelum mengganti dataset.")
            return

        self._active_log = log_or_df
        self._active_metadata = metadata if isinstance(metadata, dict) else None
        self._clear_result_widgets()

        if log_or_df is None:
            self.dataset_label.setText("Belum ada dataset aktif")
            self._apply_state("no_dataset", "Dataset belum dimuat.")
            return

        file_name = (
            self._active_metadata.get("file_name")
            if self._active_metadata
            else None
        )
        case_count = (
            self._active_metadata.get("case_count")
            if self._active_metadata
            else (len(log_or_df) if hasattr(log_or_df, "__len__") else "-")
        )
        label_text = (
            f"{file_name} ({case_count} cases)"
            if file_name
            else f"Objek {type(log_or_df).__name__} aktif"
        )
        self.dataset_label.setText(label_text)
        self._apply_state("ready", "Dataset aktif siap. Klik 'Jalankan Analisis' untuk memulai.")

    @Slot()
    def clear_dataset(self) -> None:
        """Detach the current dataset and reset all UI state."""

        self._active_log = None
        self._active_metadata = None
        self._clear_result_widgets()
        self.dataset_label.setText("Belum ada dataset aktif")
        self._apply_state("no_dataset", "Dataset belum dimuat.")

    @Slot()
    def reset_results(self) -> None:
        """Reset displayed analysis results while keeping the active dataset."""

        if self.is_running():
            return
        self._clear_result_widgets()
        if self._active_log is None:
            self._apply_state("no_dataset", "Dataset belum dimuat.")
        else:
            self._apply_state(
                "ready",
                "Hasil analisis direset. Dataset masih aktif dan siap dianalisis ulang.",
            )

    def _clear_result_widgets(self) -> None:
        self._last_result = None
        self._evidence_rows = []
        self.filter_input.clear()
        self.count_label.setText("-")
        self.denominator_label.setText("-")
        self.percentage_label.setText("-")
        self.result_table.setRowCount(0)

    @Slot()
    def run_analysis(self) -> None:
        """Run Exercise 11.22 on the active dataset using a background QThread."""

        if self._active_log is None:
            self._apply_state("no_dataset", "Dataset belum dimuat. Tidak dapat menjalankan analisis.")
            return

        if self.is_running():
            self._apply_state("loading", "Analisis sebelumnya masih berjalan.")
            return

        self._clear_result_widgets()
        self._apply_state("loading", "Sedang menjalankan analisis Exercise 11.22...")
        self.analysis_started.emit()

        thread = QThread(self)
        worker = Exercise1122Worker(self._active_log)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.completed.connect(self._on_worker_completed)
        worker.failed.connect(self._on_worker_failed)
        worker.completed.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(self._on_thread_finished)
        thread.finished.connect(thread.deleteLater)

        self._thread = thread
        self._worker = worker
        thread.start()

    @Slot(object)
    def _on_worker_completed(self, result: dict[str, Any]) -> None:
        if self._closing:
            return

        self._last_result = result
        self._evidence_rows = list(result.get("evidence", []))

        count = result.get("count", 0)
        total_cases = result.get("total_cases", 0)
        percentage = result.get("percentage", 0.0)

        self.count_label.setText(str(count))
        self.denominator_label.setText(str(total_cases))
        self.percentage_label.setText(f"{percentage:.2f}%")
        self.rule_label.setText(f"Aturan filter: {result.get('rule', RULE_DESCRIPTION)}")

        self._populate_table(self._evidence_rows)

        if count == 0:
            self._apply_state(
                "empty",
                f"Analisis selesai: 0 dari {total_cases} case (0.00%) memenuhi aturan 11.22.",
            )
        else:
            self._apply_state(
                "loaded",
                f"Analisis selesai: {count} dari {total_cases} case ({percentage:.2f}%) memenuhi aturan 11.22.",
            )

        self.analysis_completed.emit(result)

    @Slot(str)
    def _on_worker_failed(self, message: str) -> None:
        if self._closing:
            return

        self._apply_state("error", f"Analisis gagal: {message}")
        self.analysis_failed.emit(message)

    @Slot()
    def _on_thread_finished(self) -> None:
        if self.sender() is self._thread or self._thread is None:
            self._thread = None
            self._worker = None

    def _populate_table(self, evidence_rows: list[dict[str, Any]]) -> None:
        self.result_table.setRowCount(len(evidence_rows))
        for row_idx, record in enumerate(evidence_rows):
            values = (
                record.get("case_id"),
                f"#{record.get('cancelled_seq')} (idx {record.get('cancelled_index')})",
                record.get("cancelled_timestamp"),
                f"#{record.get('accepted_seq')} (idx {record.get('accepted_index')})",
                record.get("accepted_timestamp"),
                record.get("trace_length"),
            )
            for col_idx, val in enumerate(values):
                text = "" if val is None else str(val)
                item = QTableWidgetItem(text)
                if col_idx == 0:
                    item.setData(Qt.UserRole, record)
                self.result_table.setItem(row_idx, col_idx, item)

    def _filter_table(self, query: str) -> None:
        normalized = query.strip().casefold()
        for row_idx in range(self.result_table.rowCount()):
            item = self.result_table.item(row_idx, 0)
            case_text = item.text().casefold() if item else ""
            self.result_table.setRowHidden(row_idx, normalized not in case_text)

    def _get_record_at_row(self, row: int) -> dict[str, Any] | None:
        if 0 <= row < len(self._evidence_rows):
            return self._evidence_rows[row]
        return None

    @Slot(int, int)
    def _on_row_clicked(self, row: int, _col: int) -> None:
        record = self._get_record_at_row(row)
        if record is not None:
            self.case_selected.emit(record["case_id"], record)

    @Slot(int, int)
    def _on_row_double_clicked(self, row: int, _col: int) -> None:
        self._emit_open_case(row)

    @Slot()
    def _open_selected_row(self) -> None:
        row = self.result_table.currentRow()
        if row >= 0:
            self._emit_open_case(row)

    def _emit_open_case(self, row: int) -> None:
        record = self._get_record_at_row(row)
        if record is None:
            return
        case_id = record["case_id"]
        self.open_case_requested.emit(case_id, record)
        if self._on_open_case is not None:
            self._on_open_case(case_id, record)

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt API name
        """Wait cleanly for any active worker thread before closing."""

        self._closing = True
        thread = self._thread
        if thread is not None and thread.isRunning():
            thread.requestInterruption()
            thread.quit()
            thread.wait()
        self._thread = None
        self._worker = None
        super().closeEvent(event)
