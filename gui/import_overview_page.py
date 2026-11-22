"""PySide6 Import/Overview page for the BPIC17 application.

This module provides a QWidget that can be embedded by the main window. It
does not create a QApplication or a second main window. XES loading and
overview calculation run in a QThread so the host GUI remains responsive.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QHeaderView,
)

from gui.widgets import DataTable
from gui.workers import TaskThread
from modules.data_loader import load_xes, validate_log
from modules.overview import calculate_overview


def _load_overview(
    file_path: str, report: Callable[[str], None]
) -> tuple[Any, dict[str, Any], dict[str, Any] | None]:
    report("Membaca file XES dengan PM4Py...")
    log, metadata = load_xes(file_path)
    validation = metadata.get("validation")
    if validation is None:
        report("Memvalidasi atribut event log...")
        validation = validate_log(log)
        metadata["validation"] = validation
    if not validation["valid"]:
        return log, metadata, None
    report("Menghitung overview dan durasi case...")
    return log, metadata, calculate_overview(log, metadata)


class ImportOverviewPage(QWidget):
    """Embeddable Import/Overview page for the main application window.

    Integration signals:

    ``dataset_loaded(log, metadata, overview)``
        Emitted only after a successful read, validation, and overview.

    ``dataset_validation_failed(log, metadata, validation)``
        Emitted when the file is readable but its required attributes or
        values are invalid. The invalid log is provided for diagnostics, but
        it is never made active by this page.

    ``load_failed(message)``
        Emitted when reading or processing raises an exception.

    The latest objects are also available as ``active_log``,
    ``active_metadata``, and ``active_overview``.
    """

    dataset_loaded = Signal(object, object, object)
    dataset_validation_failed = Signal(object, object, object)
    load_failed = Signal(str)
    status_changed = Signal(str)
    load_started = Signal(str)
    _progress = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.active_log: Any | None = None
        self.active_metadata: dict[str, Any] | None = None
        self.active_overview: dict[str, Any] | None = None
        self._thread: TaskThread | None = None
        self._case_rows: list[tuple[Any, ...]] = []
        self._pending_file_path: str | None = None
        self._closing = False

        self._build_ui()
        self._progress.connect(self._set_status, Qt.ConnectionType.QueuedConnection)

    def _build_ui(self) -> None:
        self.setObjectName("importOverviewPage")
        root = QVBoxLayout(self)

        file_box = QGroupBox("Dataset aktif")
        file_layout = QGridLayout(file_box)
        self.select_button = QPushButton("Pilih file XES")
        self.select_button.clicked.connect(self._choose_file)
        self.file_label = QLabel("Belum ada file dipilih")
        self.file_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.status_label = QLabel("Siap")
        self.status_label.setWordWrap(True)
        file_layout.addWidget(self.select_button, 0, 0)
        file_layout.addWidget(self.file_label, 0, 1)
        file_layout.addWidget(QLabel("Status:"), 1, 0)
        file_layout.addWidget(self.status_label, 1, 1)
        root.addWidget(file_box)

        validation_box = QGroupBox("Validasi dataset")
        validation_layout = QFormLayout(validation_box)
        self.case_count_label = QLabel("-")
        self.event_count_label = QLabel("-")
        self.case_id_label = QLabel("-")
        self.activity_label = QLabel("-")
        self.timestamp_label = QLabel("-")
        self.lifecycle_label = QLabel("-")
        self.resource_label = QLabel("-")
        validation_layout.addRow("Jumlah case:", self.case_count_label)
        validation_layout.addRow("Jumlah event:", self.event_count_label)
        validation_layout.addRow("Case ID (trace concept:name):", self.case_id_label)
        validation_layout.addRow("Activity (event concept:name):", self.activity_label)
        validation_layout.addRow("Timestamp (time:timestamp):", self.timestamp_label)
        validation_layout.addRow("Lifecycle:", self.lifecycle_label)
        validation_layout.addRow("Resource:", self.resource_label)
        self.attributes_label = QLabel("-")
        self.attributes_label.setTextFormat(Qt.TextFormat.PlainText)
        self.attributes_label.setWordWrap(True)
        validation_layout.addRow("Atribut event dan trace:", self.attributes_label)
        root.addWidget(validation_box)

        overview_box = QGroupBox("Overview")
        overview_layout = QGridLayout(overview_box)
        self.total_cases_label = QLabel("-")
        self.total_events_label = QLabel("-")
        self.time_range_label = QLabel("-")
        self.mean_cycle_label = QLabel("-")
        overview_layout.addWidget(QLabel("Total cases:"), 0, 0)
        overview_layout.addWidget(self.total_cases_label, 0, 1)
        overview_layout.addWidget(QLabel("Total events:"), 0, 2)
        overview_layout.addWidget(self.total_events_label, 0, 3)
        overview_layout.addWidget(QLabel("Rentang waktu:"), 1, 0)
        overview_layout.addWidget(self.time_range_label, 1, 1, 1, 3)
        overview_layout.addWidget(QLabel("Rata-rata cycle time:"), 2, 0)
        overview_layout.addWidget(self.mean_cycle_label, 2, 1, 1, 3)
        root.addWidget(overview_box)

        activity_box = QGroupBox("Frekuensi aktivitas")
        activity_layout = QVBoxLayout(activity_box)
        self.activity_table = QTableWidget(0, 2)
        self.activity_table.setHorizontalHeaderLabels(["Activity", "Frekuensi"])
        self._configure_table(self.activity_table)
        activity_layout.addWidget(self.activity_table)
        root.addWidget(activity_box)

        duration_box = QGroupBox("Durasi per case")
        duration_layout = QVBoxLayout(duration_box)
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Cari Case ID:"))
        self.case_search = QLineEdit()
        self.case_search.setPlaceholderText("Ketik Case ID...")
        self.case_search.textChanged.connect(self._filter_case_table)
        search_layout.addWidget(self.case_search)
        duration_layout.addLayout(search_layout)
        self.case_table = DataTable(["Case ID", "Mulai", "Selesai", "Durasi", "Durasi (hari)"])
        for column, width in enumerate((160, 200, 200, 150)):
            self.case_table.setColumnWidth(column, width)
        duration_layout.addWidget(self.case_table)
        root.addWidget(duration_box, 1)

        self.message_box = QTextEdit()
        self.message_box.setReadOnly(True)
        self.message_box.setMaximumHeight(90)
        self.message_box.setPlaceholderText("Pesan validasi dan error akan tampil di sini.")
        root.addWidget(self.message_box)

    @staticmethod
    def _configure_table(table: QTableWidget) -> None:
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setAlternatingRowColors(True)
        table.setSortingEnabled(False)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        table.horizontalHeader().setStretchLastSection(True)
        table.verticalHeader().setVisible(False)

    def _choose_file(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Pilih file event log XES",
            "",
            "XES files (*.xes);;All files (*)",
        )
        if file_path:
            self.load_file(file_path)

    def load_file(self, file_path: str) -> None:
        """Start a background import for ``file_path``."""

        if self._thread is not None:
            self._set_status("Proses sebelumnya masih berjalan.")
            return

        path = str(Path(file_path))
        self._pending_file_path = path
        self.select_button.setEnabled(False)
        self._set_status(f"Menyiapkan import: {path}")
        self.load_started.emit(path)

        thread = TaskThread(
            lambda: _load_overview(path, self._progress.emit), "Impor XES", self
        )
        thread.finished.connect(self._on_thread_finished, Qt.ConnectionType.QueuedConnection)
        self._thread = thread
        thread.start()

    @Slot(str)
    def _set_status(self, message: str) -> None:
        self.status_label.setText(message)
        self.status_changed.emit(message)

    @Slot(object, object, object)
    def _on_worker_completed(
        self, log: Any, metadata: dict[str, Any], overview: dict[str, Any] | None
    ) -> None:
        if self._closing:
            return

        # Commit the pending dataset only after all background work succeeded.
        self.active_log = log
        self.active_metadata = metadata
        self.active_overview = overview
        if self._pending_file_path is not None:
            self.file_label.setText(self._pending_file_path)
        self._pending_file_path = None
        self.case_search.clear()
        self._clear_results()
        self._render_validation(metadata)

        self._render_overview(overview)
        self._set_status("Import, validasi, dan overview selesai.")
        self._append_messages(overview.get("errors", []))

        self.select_button.setEnabled(True)
        self.dataset_loaded.emit(log, metadata, overview)

    @Slot(object, object, object)
    def _on_worker_validation_failed(
        self, log: Any, metadata: dict[str, Any], validation: dict[str, Any]
    ) -> None:
        if self._closing:
            return

        self._pending_file_path = None
        self.select_button.setEnabled(True)
        self._set_status("File terbaca, tetapi validasi tidak lulus.")
        messages = validation.get("errors", [])
        self._append_messages(messages or ["Atribut atau nilai wajib tidak valid."])
        self.dataset_validation_failed.emit(log, metadata, validation)

    @Slot(str)
    def _on_worker_failed(self, message: str) -> None:
        if self._closing:
            return

        self._pending_file_path = None
        self.select_button.setEnabled(True)
        self._set_status("Import gagal.")
        self._append_messages([message])
        self.load_failed.emit(message)

    @Slot()
    def _on_thread_finished(self) -> None:
        thread = self._thread
        self._thread = None
        if thread is None:
            return
        thread.deleteLater()
        if self._closing:
            return
        if thread.error is not None:
            self._on_worker_failed(thread.error)
        else:
            log, metadata, overview = thread.result
            if overview is None:
                self._on_worker_validation_failed(log, metadata, metadata["validation"])
            else:
                self._on_worker_completed(log, metadata, overview)

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt API name
        self._closing = True
        if self._thread is not None:
            self._thread.wait()
        super().closeEvent(event)

    def _clear_results(self) -> None:
        self.case_count_label.setText("-")
        self.event_count_label.setText("-")
        self.total_cases_label.setText("-")
        self.total_events_label.setText("-")
        self.time_range_label.setText("-")
        self.mean_cycle_label.setText("-")
        for label in (
            self.case_id_label,
            self.activity_label,
            self.timestamp_label,
            self.lifecycle_label,
            self.resource_label,
            self.attributes_label,
        ):
            label.setText("-")
        self.activity_table.setRowCount(0)
        self._case_rows = []
        self.case_table.set_rows(())
        self.message_box.clear()

    def _render_validation(self, metadata: dict[str, Any]) -> None:
        validation = metadata.get("validation", {})
        self.case_count_label.setText(str(metadata.get("case_count", "-")))
        self.event_count_label.setText(str(metadata.get("event_count", "-")))

        missing = validation.get("missing_value_counts", {})
        invalid = validation.get("invalid_value_counts", {})
        missing_required = validation.get("missing_required_attributes", {})
        optional = validation.get("optional_attributes", {})

        self.case_id_label.setText(
            self._required_status(
                "concept:name",
                missing.get("trace:concept:name", 0),
                "trace" in missing_required and "concept:name" in missing_required["trace"],
            )
        )
        self.activity_label.setText(
            self._required_status(
                "concept:name",
                missing.get("concept:name", 0),
                "concept:name" in missing_required.get("event", []),
            )
        )
        timestamp_errors = missing.get("time:timestamp", 0) + invalid.get(
            "time:timestamp", 0
        )
        self.timestamp_label.setText(
            self._required_status(
                "time:timestamp",
                timestamp_errors,
                "time:timestamp" in missing_required.get("event", []),
            )
        )
        self.lifecycle_label.setText(
            "Tersedia" if optional.get("lifecycle:transition", False) else "Tidak tersedia"
        )
        self.resource_label.setText(
            "Tersedia" if optional.get("org:resource", False) else "Tidak tersedia"
        )

        trace = ", ".join(metadata.get("available_trace_attributes", []))
        events = ", ".join(metadata.get("available_event_attributes", []))
        self.attributes_label.setText(f"Trace: {trace or '-'}\nEvent: {events or '-'}")

    @staticmethod
    def _required_status(name: str, issue_count: int, missing_attribute: bool) -> str:
        if missing_attribute:
            return f"Tidak tersedia ({name})"
        if issue_count:
            return f"Bermasalah ({issue_count} nilai)"
        return "Valid"

    def _render_overview(self, overview: dict[str, Any]) -> None:
        self.total_cases_label.setText(str(overview.get("case_count", "-")))
        self.total_events_label.setText(str(overview.get("event_count", "-")))

        time_range = overview.get("time_range", {})
        self.time_range_label.setText(
            f"{time_range.get('start', '-')} sampai {time_range.get('end', '-')}"
        )
        mean_days = overview.get("mean_cycle_time_days")
        self.mean_cycle_label.setText(
            "-" if mean_days is None else f"{mean_days:.6f} hari"
        )

        frequencies = overview.get("activity_frequency", {})
        self.activity_table.setRowCount(len(frequencies))
        for row, (activity, count) in enumerate(frequencies.items()):
            self.activity_table.setItem(row, 0, QTableWidgetItem(str(activity)))
            self.activity_table.setItem(row, 1, QTableWidgetItem(str(count)))

        self._case_rows = [
            (
                record["case_id"], record["start_timestamp"], record["end_timestamp"],
                record["duration"], f"{record['duration_days']:.6f}",
            )
            for record in overview["case_durations"]
        ]
        self._filter_case_table(self.case_search.text())

    def _filter_case_table(self, text: str) -> None:
        query = text.casefold().strip()
        rows = self._case_rows
        if query:
            rows = [row for row in rows if query in str(row[0]).casefold()]
        self.case_table.set_rows(rows)

    def _append_messages(self, messages: list[str]) -> None:
        if not messages:
            return
        self.message_box.setPlainText("\n".join(str(message) for message in messages))
