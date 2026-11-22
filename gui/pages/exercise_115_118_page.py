"""Desktop page for repeated-completion Exercises 11.15 and 11.18."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from gui.widgets import TaskControls
from modules.exercise_115_118 import analyze_115_118


class Exercise115118Page(QWidget):
    """Render results and evidence for Exercises 11.15 and 11.18.

    The page uses the shared ``MainWindow`` task worker and AppState. Evidence
    rows can be sent directly to Case Explorer for full-trace inspection.
    """

    analysis_started = Signal()
    analysis_completed = Signal(object)
    analysis_failed = Signal(str)
    open_case_requested = Signal(object, object)
    state_changed = Signal(str)
    _shell_failed_signal = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("exercise115118Page")
        self._host_window: Any | None = None
        self._active_log: Any | None = None
        self._active_metadata: dict[str, Any] | None = None
        self._last_result: dict[str, Any] | None = None
        self._state = "no_dataset"
        self._task_pending = False
        self._pending_message = ""
        self._evidence_rows: dict[str, list[dict[str, Any]]] = {
            "11.15": [],
            "11.18": [],
        }

        self._build_ui()
        self._apply_state(
            "no_dataset",
            "Dataset belum dimuat. Muat file XES pada halaman Import Dataset.",
        )

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)

        control_box = QGroupBox("Exercise 11.15 & 11.18 — Repeated Complete Activity")
        control_layout = QVBoxLayout(control_box)
        description = QLabel(
            "Kedua latihan menghitung W_Assess Potential Fraud hanya jika "
            "lifecycle:transition bernilai complete. Exercise 11.18 menambahkan "
            "syarat minimal dua occurrence oleh resource yang sama dan teridentifikasi."
        )
        description.setWordWrap(True)
        control_layout.addWidget(description)

        self.task_controls = TaskControls("Jalankan Analisis")
        control_layout.addWidget(self.task_controls)
        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        control_layout.addWidget(self.status_label)
        root.addWidget(control_box)

        self.tabs = QTabWidget()
        self._count_labels: dict[str, QLabel] = {}
        self._table_widgets: dict[str, QTableWidget] = {}
        self._open_buttons: dict[str, QPushButton] = {}
        self._summary_labels: dict[str, QLabel] = {}

        self._add_exercise_tab(
            "11.15",
            "Exercise 11.15",
            ("Case ID", "Complete count", "Posisi event bukti", "Rincian event complete"),
        )
        self._add_exercise_tab(
            "11.18",
            "Exercise 11.18",
            (
                "Case ID",
                "Resource ID",
                "Complete count",
                "Posisi event bukti",
                "Rincian event complete",
            ),
        )
        root.addWidget(self.tabs, 1)

    def _add_exercise_tab(
        self, key: str, title: str, headers: tuple[str, ...]
    ) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)

        summary_box = QGroupBox("Ringkasan")
        summary_layout = QFormLayout(summary_box)
        count_label = QLabel("-")
        summary_label = QLabel("Belum ada hasil.")
        summary_label.setWordWrap(True)
        summary_layout.addRow("Jumlah case yang memenuhi:", count_label)
        summary_layout.addRow("Keterangan:", summary_label)
        layout.addWidget(summary_box)

        table_box = QGroupBox("Case terpilih dan event bukti")
        table_layout = QVBoxLayout(table_box)
        table = QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setAlternatingRowColors(True)
        table.setSortingEnabled(False)
        table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        table.horizontalHeader().setStretchLastSection(True)
        table.verticalHeader().setVisible(False)
        table.itemSelectionChanged.connect(lambda exercise=key: self._sync_open_button(exercise))
        table.cellDoubleClicked.connect(
            lambda row, _column, exercise=key: self._open_case(exercise, row)
        )
        table_layout.addWidget(table)

        button_row = QHBoxLayout()
        open_button = QPushButton("Buka case terpilih di Case Explorer")
        open_button.setEnabled(False)
        open_button.clicked.connect(
            lambda _checked=False, exercise=key: self._open_selected_case(exercise)
        )
        button_row.addWidget(open_button)
        button_row.addStretch()
        table_layout.addLayout(button_row)
        layout.addWidget(table_box, 1)

        self._count_labels[key] = count_label
        self._summary_labels[key] = summary_label
        self._table_widgets[key] = table
        self._open_buttons[key] = open_button
        self.tabs.addTab(page, title)

    @property
    def current_state(self) -> str:
        return self._state

    @property
    def last_result(self) -> dict[str, Any] | None:
        return self._last_result

    def bind_main_window(self, window: Any) -> TaskControls:
        """Connect this page to the shared dataset, task runner, and results."""

        if self._host_window is window:
            return self.task_controls

        self._host_window = window
        self.task_controls.run_requested.connect(self._run_analysis)
        self.task_controls.rerun_requested.connect(self._rerun_requested)
        window.state.dataset_changed.connect(self.set_dataset)
        window.state.result_changed.connect(self._on_shell_result_changed)
        self._shell_failed_signal.connect(self._on_shell_failure)

        if window.state.dataset is not None:
            self.set_dataset(window.state.dataset)
        if window.state.has_result("exercise_115_118"):
            self._render_result(window.state.result("exercise_115_118"))
        return self.task_controls

    @Slot(object)
    def set_dataset(self, dataset: Any) -> None:
        """Attach the active dataset and clear results from the prior import."""

        if dataset is None:
            self._task_pending = False
            self._active_log = None
            self._active_metadata = None
            self._clear_result_widgets()
            self._apply_state("no_dataset", "Dataset belum dimuat.")
            return

        if hasattr(dataset, "log") and hasattr(dataset, "metadata"):
            self._active_log = dataset.log
            self._active_metadata = dataset.metadata
        else:
            # Kept permissive for direct use in small fixtures.
            self._active_log = dataset
            self._active_metadata = None

        self._task_pending = False
        self._clear_result_widgets()
        file_name = (self._active_metadata or {}).get("file_name", "dataset aktif")
        case_count = (self._active_metadata or {}).get("case_count")
        suffix = f", {case_count:,} case" if isinstance(case_count, int) else ""
        self._apply_state("ready", f"Dataset siap ({file_name}{suffix}).")

    @Slot()
    def _run_analysis(self) -> None:
        if self._host_window is None:
            self._apply_state("error", "Halaman belum terhubung ke MainWindow.")
            return
        if self._active_log is None:
            self._apply_state("no_dataset", "Impor dataset XES sebelum analisis.")
            return

        self._task_pending = True
        self._pending_message = "Menghitung Exercise 11.15 dan 11.18..."
        self._apply_state("loading", self._pending_message)
        self.analysis_started.emit()

        def operation(dataset: Any) -> dict[str, Any]:
            try:
                return analyze_115_118(dataset.log)
            except Exception as error:
                self._shell_failed_signal.emit(str(error))
                raise

        accepted = self._host_window.run_task(
            "exercise_115_118",
            "Analisis Exercise 11.15 & 11.18",
            operation,
        )
        if not accepted:
            self._task_pending = False
            if self._active_log is None:
                self._apply_state("no_dataset", "Impor dataset XES sebelum analisis.")
            elif self._last_result is not None:
                self._apply_state("loaded", "Menampilkan hasil analisis sebelumnya.")
            else:
                self._apply_state("ready", "Proses lain sedang berjalan; tunggu hingga selesai.")

    @Slot()
    def _rerun_requested(self) -> None:
        self._task_pending = True
        self._pending_message = "Mengulang analisis Exercise 11.15 dan 11.18..."
        self._apply_state("loading", self._pending_message)
        self.analysis_started.emit()

    @Slot(str)
    def _on_shell_failure(self, message: str) -> None:
        self._task_pending = False
        self._apply_state("error", f"Analisis gagal: {message}")
        self.analysis_failed.emit(message)

    @Slot(str)
    def _on_shell_result_changed(self, page_key: str) -> None:
        if page_key != "exercise_115_118" or self._host_window is None:
            return
        if self._host_window.state.has_result(page_key):
            self._task_pending = False
            result = self._host_window.state.result(page_key)
            self._render_result(result)
            self.analysis_completed.emit(result)
        else:
            self._clear_result_widgets()
            if self._task_pending:
                self._apply_state("loading", self._pending_message)
            elif self._active_log is None:
                self._apply_state("no_dataset", "Dataset belum dimuat.")
            else:
                self._apply_state("ready", "Hasil direset. Jalankan analisis atau gunakan Jalankan ulang.")

    def _apply_state(self, state: str, message: str) -> None:
        self._state = state
        self.status_label.setText(message)
        running = state == "loading"
        for key in self._open_buttons:
            self._open_buttons[key].setEnabled(
                not running and self._table_widgets[key].currentRow() >= 0
            )
        self.state_changed.emit(state)

    def _clear_result_widgets(self) -> None:
        self._last_result = None
        for key in ("11.15", "11.18"):
            self._evidence_rows[key] = []
            self._count_labels[key].setText("-")
            self._summary_labels[key].setText("Belum ada hasil.")
            self._table_widgets[key].setRowCount(0)
            self._open_buttons[key].setEnabled(False)

    def _render_result(self, result: dict[str, Any]) -> None:
        self._last_result = result
        total_cases = result.get("total_cases", 0)
        for key in ("11.15", "11.18"):
            section = result.get(key, {})
            evidence = list(section.get("evidence", []))
            self._evidence_rows[key] = evidence
            count = section.get("count", 0)
            self._count_labels[key].setText(f"{count:,}")
            if key == "11.18":
                group_count = section.get("evidence_group_count", len(evidence))
                note = (
                    f"{count:,} case dari {total_cases:,} case aktif; "
                    f"{group_count:,} pasangan case-resource memenuhi aturan."
                )
            else:
                note = f"{count:,} case dari {total_cases:,} case aktif memenuhi aturan."
            self._summary_labels[key].setText(note)
            self._populate_table(key, evidence)

        count_1115 = result.get("11.15", {}).get("count", 0)
        count_1118 = result.get("11.18", {}).get("count", 0)
        if count_1115 or count_1118:
            self._apply_state(
                "loaded",
                f"Analisis selesai: {count_1115:,} case memenuhi 11.15 dan "
                f"{count_1118:,} case memenuhi 11.18 dari {total_cases:,} case.",
            )
        else:
            self._apply_state(
                "empty",
                f"Analisis selesai: tidak ada case yang memenuhi aturan dari {total_cases:,} case.",
            )

    def _populate_table(self, key: str, evidence: list[dict[str, Any]]) -> None:
        table = self._table_widgets[key]
        table.setRowCount(len(evidence))
        for row, record in enumerate(evidence):
            events = record.get("evidence_events", [])
            positions = "; ".join(
                f"#{event.get('seq')} (idx {event.get('position')})" for event in events
            )
            details = " | ".join(self._format_event(event) for event in events)
            if key == "11.15":
                values = (
                    record.get("case_id"),
                    record.get("occurrence_count"),
                    positions,
                    details,
                )
            else:
                values = (
                    record.get("case_id"),
                    record.get("resource_id"),
                    record.get("occurrence_count"),
                    positions,
                    details,
                )
            for column, value in enumerate(values):
                text = "-" if value is None else str(value)
                item = QTableWidgetItem(text)
                if (key == "11.15" and column in (1, 2)) or (
                    key == "11.18" and column == 2
                ):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if column == 0:
                    item.setData(Qt.ItemDataRole.UserRole, record)
                table.setItem(row, column, item)
        self._sync_open_button(key)

    @staticmethod
    def _format_event(event: dict[str, Any]) -> str:
        parts = [f"#{event.get('seq')} {event.get('activity')}"]
        lifecycle = event.get("lifecycle")
        resource = event.get("resource")
        lifecycle_text = "(kosong)" if lifecycle is None else str(lifecycle)
        resource_text = (
            "(kosong)"
            if resource is None or isinstance(resource, str) and not resource.strip()
            else str(resource)
        )
        parts.append(f"lifecycle={lifecycle_text}")
        parts.append(f"resource={resource_text}")
        timestamp = event.get("timestamp")
        if timestamp is not None:
            parts.append(f"timestamp={timestamp}")
        return " [" + "; ".join(parts[1:]) + "] " + parts[0]

    def _sync_open_button(self, key: str) -> None:
        table = self._table_widgets[key]
        self._open_buttons[key].setEnabled(
            self._state != "loading"
            and 0 <= table.currentRow() < len(self._evidence_rows[key])
        )

    def _open_selected_case(self, key: str) -> None:
        row = self._table_widgets[key].currentRow()
        self._open_case(key, row)

    def _open_case(self, key: str, row: int) -> None:
        evidence = self._evidence_rows[key]
        if not 0 <= row < len(evidence):
            return
        record = evidence[row]
        self.open_case_requested.emit(record["case_id"], record)

