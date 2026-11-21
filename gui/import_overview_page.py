"""PySide6 Import/Overview page for the BPIC17 application.

This module provides a QWidget that can be embedded by the main window. It
does not create a QApplication or a second main window. XES loading and
overview calculation run in a QThread so the host GUI remains responsive.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, QThread, Qt, Signal, Slot
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

from modules.data_loader import load_xes, validate_log
from modules.overview import calculate_overview


class ImportOverviewWorker(QObject):
    """Background worker for one complete import and overview operation."""

    progress = Signal(str)
    completed = Signal(object, object, object)
    validation_failed = Signal(object, object, object)
    failed = Signal(str)

    def __init__(self, file_path: str) -> None:
        super().__init__()
        self.file_path = file_path

    @Slot()
    def run(self) -> None:
        try:
            self.progress.emit("Membaca file XES dengan PM4Py...")
            log, metadata = load_xes(self.file_path)

            # load_xes already validates the same in-memory log. The fallback
            # keeps this worker robust if a compatible loader omits metadata.
            validation = metadata.get("validation")
            if validation is None:
                self.progress.emit("Memvalidasi atribut event log...")
                validation = validate_log(log)
                metadata["validation"] = validation

            overview = None
            if validation.get("valid", False):
                self.progress.emit("Menghitung overview dan durasi case...")
                overview = calculate_overview(log, metadata)
                self.completed.emit(log, metadata, overview)
            else:
                self.validation_failed.emit(log, metadata, validation)
        except Exception as error:
            self.failed.emit(str(error))


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

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.active_log: Any | None = None
        self.active_metadata: dict[str, Any] | None = None
        self.active_overview: dict[str, Any] | None = None
        self._thread: QThread | None = None
        self._worker: ImportOverviewWorker | None = None
        self._pending_file_path: str | None = None
        self._closing = False

        self._build_ui()

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
        self.case_table = QTableWidget(0, 5)
        self.case_table.setHorizontalHeaderLabels(
            ["Case ID", "Mulai", "Selesai", "Durasi", "Durasi (hari)"]
        )
        self._configure_table(self.case_table)
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

        if self._thread is not None and self._thread.isRunning():
            self._set_status("Proses sebelumnya masih berjalan.")
            return

        path = str(Path(file_path))
        self._pending_file_path = path
        self.select_button.setEnabled(False)
        self._set_status(f"Menyiapkan import: {path}")
        self.load_started.emit(path)

        thread = QThread(self)
        worker = ImportOverviewWorker(path)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self._set_status)
        worker.completed.connect(self._on_worker_completed)
        worker.validation_failed.connect(self._on_worker_validation_failed)
        worker.failed.connect(self._on_worker_failed)
        worker.completed.connect(thread.quit)
        worker.validation_failed.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(self._on_thread_finished)
        # Keep this connection after the page cleanup callback so references
        # are cleared before the QThread QObject is scheduled for deletion.
        thread.finished.connect(thread.deleteLater)

        self._thread = thread
        self._worker = worker
        thread.start()

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
        self._thread = None
        self._worker = None

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt API name
        """Stop accepting worker callbacks before the page is destroyed."""

        self._closing = True
        thread = self._thread
        if thread is not None and thread.isRunning():
            # PM4Py's read_xes call is not cancellable through this worker.
            # Waiting here prevents QThread from being destroyed while it is
            # still running when the host window closes.
            thread.requestInterruption()
            thread.quit()
            thread.wait()
        self._thread = None
        self._worker = None
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
        ):
            label.setText("-")
        self.activity_table.setRowCount(0)
        self.case_table.setRowCount(0)
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

        durations = overview.get("case_durations", [])
        self.case_table.setRowCount(len(durations))
        for row, record in enumerate(durations):
            values = (
                record.get("case_id"),
                record.get("start_timestamp"),
                record.get("end_timestamp"),
                record.get("duration"),
                record.get("duration_days"),
            )
            for column, value in enumerate(values):
                if column == 4 and isinstance(value, (int, float)):
                    text = f"{value:.6f}"
                else:
                    text = "" if value is None else str(value)
                self.case_table.setItem(row, column, QTableWidgetItem(text))

    def _filter_case_table(self, text: str) -> None:
        query = text.casefold().strip()
        for row in range(self.case_table.rowCount()):
            item = self.case_table.item(row, 0)
            case_id = item.text().casefold() if item else ""
            self.case_table.setRowHidden(row, query not in case_id)

    def _append_messages(self, messages: list[str]) -> None:
        if not messages:
            return
        self.message_box.setPlainText("\n".join(str(message) for message in messages))
