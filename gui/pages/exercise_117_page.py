"""Embeddable PySide6 page for Exercise 11.7 (A–E) analysis.

High-performance implementation:
- Uses a virtual QAbstractTableModel for the filtered case list so that large datasets
  (like BPIC17 with 40,000+ filtered occurrences) render and select instantaneously (0 ms)
  without freezing the UI or triggering "Not Responding".
- Operates on the active dataset without reloading XES.
- Integrates with Case Explorer via ``open_case_requested(case_id, evidence)``.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QObject, QThread, Qt, Signal, Slot
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QSplitter,
    QTableView,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from modules.export_csv import export_cases_to_csv, export_summary_to_csv
from modules.exercise_117 import (
    RULE_117_A,
    RULE_117_B,
    RULE_117_C,
    RULE_117_D,
    RULE_117_E,
    analyze_117,
)


class CaseResultsTableModel(QAbstractTableModel):
    """Virtual table model for fast rendering of tens of thousands of case rows."""

    def __init__(self, headers: Sequence[str], parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._headers = tuple(headers)
        self._cases: list[dict[str, Any]] = []

    def set_cases(self, cases: list[dict[str, Any]]) -> None:
        self.beginResetModel()
        self._cases = cases
        self.endResetModel()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._cases)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._headers)

    def headerData(
        self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole
    ) -> Any:
        if (
            role == Qt.ItemDataRole.DisplayRole
            and orientation == Qt.Orientation.Horizontal
            and 0 <= section < len(self._headers)
        ):
            return self._headers[section]
        return None

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid():
            return None

        row = index.row()
        col = index.column()
        if not (0 <= row < len(self._cases)):
            return None

        case = self._cases[row]

        if role == Qt.ItemDataRole.TextAlignmentRole:
            if col in (1, 2, 3, 4, 5, 6):
                return Qt.AlignmentFlag.AlignCenter
            return Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft

        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.ToolTipRole):
            if col == 0:
                return str(case.get("case_id", ""))
            elif col == 1:
                return str(case.get("subsoal", ""))
            elif col == 2:
                return str(case.get("activity", ""))
            elif col == 3:
                return str(case.get("occurrence_count", 1))
            elif col == 4:
                return "; ".join(str(p) for p in case.get("evidence_positions", []))
            elif col == 5:
                dur = case.get("duration_days")
                return f"{dur:.4f}" if isinstance(dur, (int, float)) else "-"
            elif col == 6:
                return str(case.get("trace_length", "-"))

        return None

    def get_case(self, row: int) -> dict[str, Any] | None:
        if 0 <= row < len(self._cases):
            return self._cases[row]
        return None


class ResultsTableView(QTableView):
    """QTableView wrapper with helper rowCount for compatibility."""

    def rowCount(self) -> int:
        model = self.model()
        return model.rowCount() if model is not None else 0


class Exercise117Worker(QObject):
    """Background worker executing ``analyze_117`` off the UI thread."""

    completed = Signal(object)
    failed = Signal(str)

    def __init__(self, log_or_df: Any) -> None:
        super().__init__()
        self._log_or_df = log_or_df

    @Slot()
    def run(self) -> None:
        try:
            result = analyze_117(self._log_or_df)
            self.completed.emit(result)
        except Exception as error:
            self.failed.emit(str(error))


class Exercise117Page(QWidget):
    """Embeddable Exercise 11.7 page widget."""

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
        state: Any = None,
        on_open_case: Callable[[Any, dict[str, Any]], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("exercise117Page")
        self._state_mgr = state
        self._host_window = None
        self._operations_available = True
        self._active_log: Any | None = None
        self._active_metadata: dict[str, Any] | None = None
        self._last_result: dict[str, Any] | None = None
        self._evidence_rows: list[dict[str, Any]] = []
        self._displayed_cases: list[dict[str, Any]] = []
        self._on_open_case = on_open_case
        self._state: str = "no_dataset"

        self._thread: QThread | None = None
        self._worker: Exercise117Worker | None = None
        self._closing = False

        self._build_ui()
        self._apply_state(
            "no_dataset",
            "Dataset belum dimuat. Muat file XES pada halaman Import/Overview.",
        )

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        # 1. Control & Description Box
        control_box = QGroupBox("Exercise 11.7 — Analisis Case, Cycle Time, & Status Penawaran")
        control_layout = QVBoxLayout(control_box)

        desc = QLabel(
            "Menghitung lima metrik Bab 11.7:\n"
            "• 11.7 A: Jumlah keseluruhan case (unique cases)\n"
            "• 11.7 B: Rata-rata cycle time seluruh case (event terakhir − pertama trace asli, dalam hari)\n"
            "• 11.7 C: Successful cases (mengandung O_Accepted) & rata-rata cycle time\n"
            "• 11.7 D: Unsuccessful cases (mengandung O_Refused) & rata-rata cycle time\n"
            "• 11.7 E: Canceled cases (event TERAKHIR trace adalah O_Cancelled) & rata-rata cycle time"
        )
        desc.setObjectName("helpText")
        desc.setWordWrap(True)
        control_layout.addWidget(desc)

        btn_row = QHBoxLayout()
        self.run_button = QPushButton("Jalankan Analisis 11.7")
        self.run_button.setObjectName("primaryAction")
        self.run_button.clicked.connect(self.run_analysis)
        self.reset_button = QPushButton("Reset Hasil")
        self.reset_button.clicked.connect(self.reset_results)
        self.open_explorer_button = QPushButton("Buka di Case Explorer")
        self.open_explorer_button.clicked.connect(self._open_selected_row)
        self.export_csv_button = QPushButton("Ekspor Ringkasan (CSV)...")
        self.export_csv_button.clicked.connect(self._quick_export_csv)

        btn_row.addWidget(self.run_button)
        btn_row.addWidget(self.reset_button)
        btn_row.addWidget(self.open_explorer_button)
        btn_row.addWidget(self.export_csv_button)
        btn_row.addStretch(1)
        control_layout.addLayout(btn_row)

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        control_layout.addWidget(self.status_label)
        root.addWidget(control_box)

        # 2. Splitter for Summary Table and Case Table
        splitter = QSplitter(Qt.Orientation.Vertical)

        # Summary Metrics Box
        summary_box = QGroupBox("Ringkasan Metrik Latihan 11.7 (A–E)")
        summary_layout = QVBoxLayout(summary_box)

        self.summary_table = QTableWidget(5, 7)
        self.summary_table.setHorizontalHeaderLabels([
            "Subsoal",
            "Pertanyaan",
            "Aturan / Filter",
            "Jumlah Case",
            "Total Case (Denom)",
            "Persentase",
            "Mean Cycle Time (Hari)",
        ])
        self.summary_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.summary_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.summary_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.summary_table.setAlternatingRowColors(True)
        self.summary_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.summary_table.horizontalHeader().setStretchLastSection(True)
        self.summary_table.verticalHeader().setVisible(False)
        for column, width in enumerate((70, 190, 200, 86, 108, 84, 145)):
            self.summary_table.setColumnWidth(column, width)
        self.summary_table.setMinimumHeight(
            5 * self.summary_table.verticalHeader().defaultSectionSize()
            + self.summary_table.horizontalHeader().sizeHint().height()
            + self.summary_table.horizontalScrollBar().sizeHint().height() + 4
        )
        summary_layout.addWidget(self.summary_table)
        splitter.addWidget(summary_box)

        # Matching Cases Table Box
        table_box = QGroupBox("Daftar Case Terpilih (Pilih baris untuk membuka Case Explorer)")
        table_layout = QVBoxLayout(table_box)

        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Kategori:"))
        self.category_combo = QComboBox()
        self.category_combo.addItems([
            "Semua Subsoal (C, D, E)",
            "11.7 C — Successful (O_Accepted)",
            "11.7 D — Unsuccessful (O_Refused)",
            "11.7 E — Canceled (Endpoint O_Cancelled)",
        ])
        self.category_combo.currentIndexChanged.connect(self._filter_table)
        filter_row.addWidget(self.category_combo)

        filter_row.addSpacing(14)
        filter_row.addWidget(QLabel("Cari Case ID:"))
        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("Ketik sebagian Case ID...")
        self.filter_input.textChanged.connect(self._filter_table)
        filter_row.addWidget(self.filter_input)

        self.table_count_label = QLabel("0 case")
        self.table_count_label.setObjectName("helpText")
        filter_row.addSpacing(14)
        filter_row.addWidget(self.table_count_label)
        filter_row.addStretch()
        table_layout.addLayout(filter_row)

        headers = [
            "Case ID",
            "Subsoal",
            "Aktivitas Target",
            "Kemunculan",
            "Posisi Evidence",
            "Durasi (Hari)",
            "Total Event",
        ]
        self._table_model = CaseResultsTableModel(headers, self)
        self.result_table = ResultsTableView(self)
        self.result_table.setModel(self._table_model)
        self.result_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.result_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.result_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.result_table.setAlternatingRowColors(True)
        self.result_table.verticalHeader().setVisible(False)
        self.result_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.result_table.horizontalHeader().setStretchLastSection(True)
        self.result_table.setColumnWidth(0, 155)

        self.result_table.selectionModel().selectionChanged.connect(self._on_selection_changed)
        self.result_table.doubleClicked.connect(lambda _: self._open_selected_row())

        table_layout.addWidget(self.result_table)
        splitter.addWidget(table_box)

        root.addWidget(splitter, 1)

    @property
    def current_state(self) -> str:
        return self._state

    @property
    def last_result(self) -> dict[str, Any] | None:
        return self._last_result

    def is_running(self) -> bool:
        return self._thread is not None or self._state == "loading"

    def bind_main_window(self, window: Any) -> None:
        """Use the shell worker and dataset state in the desktop application."""
        self._host_window = window
        self._state_mgr = window.state
        window.state.dataset_changed.connect(self._set_active_dataset)
        window.state.result_changed.connect(self._on_shell_result)
        window.operations_available.connect(self._set_operations_available)
        window.task_failed.connect(self._on_shell_failure)
        self._set_active_dataset(window.state.dataset)

    @Slot(object)
    def _set_active_dataset(self, dataset: Any) -> None:
        if dataset is None:
            self.set_dataset(None)
        else:
            self.set_dataset(dataset.log, dataset.metadata, dataset.overview)

    @Slot(str)
    def _on_shell_result(self, page_key: str) -> None:
        if page_key != "exercise_117":
            return
        if self._state_mgr.has_result(page_key):
            result = self._state_mgr.result(page_key)
            self._populate_results(result)
            self.analysis_completed.emit(result)
        else:
            self._clear_result_widgets()
            if self._active_log is not None:
                self._apply_state("ready", "Jalankan Analisis 11.7 dari dataset aktif.")

    @Slot(str, str)
    def _on_shell_failure(self, page_key: str, message: str) -> None:
        if page_key == "exercise_117":
            self._on_analysis_error(message)

    @Slot(bool)
    def _set_operations_available(self, available: bool) -> None:
        self._operations_available = available
        self._sync_controls()

    def set_dataset(
        self,
        log_or_df: Any,
        metadata: dict[str, Any] | None = None,
        overview: dict[str, Any] | None = None,
    ) -> None:
        """Attach active dataset and reset previous results."""
        if self._thread is not None and self._thread.isRunning():
            self._thread.quit()
            self._thread.wait(2000)
            self._thread = None
            self._worker = None

        self._active_log = log_or_df
        self._active_metadata = metadata
        self._clear_result_widgets()

        if log_or_df is None:
            self._apply_state(
                "no_dataset",
                "Dataset belum dimuat. Muat file XES pada halaman Import/Overview.",
            )
            return

        file_name = (metadata or {}).get("file_name", "dataset aktif")
        case_count = (metadata or {}).get("case_count")
        if case_count is None:
            case_count = len(log_or_df) if hasattr(log_or_df, "__len__") else "-"
        self._apply_state(
            "ready",
            f"Dataset siap ({file_name}, {case_count} cases). Klik 'Jalankan Analisis 11.7'.",
        )

    def set_result(self, result: dict[str, Any] | None) -> None:
        """Directly render a result dict computed externally."""
        if result is None:
            self.reset_results()
            return
        self._populate_results(result)

    @Slot()
    def run_analysis(self) -> None:
        """Launch analyze_117 in background thread."""
        if self._active_log is None or self._thread is not None:
            return

        if self._host_window is not None:
            if self._host_window.run_task(
                "exercise_117", "Analisis Exercise 11.7", lambda dataset: analyze_117(dataset.log)
            ):
                self._apply_state("loading", "Menghitung analisis Exercise 11.7 (A–E)...")
                self.analysis_started.emit()
            return

        self._apply_state("loading", "Menghitung analisis Exercise 11.7 (A–E)...")
        self.analysis_started.emit()

        thread = QThread(self)
        worker = Exercise117Worker(self._active_log)
        worker.moveToThread(thread)

        thread.started.connect(worker.run)
        worker.completed.connect(self._on_analysis_success)
        worker.failed.connect(self._on_analysis_error)
        worker.completed.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(thread.deleteLater)

        self._thread = thread
        self._worker = worker
        thread.start()

    @Slot(object)
    def _on_analysis_success(self, result: dict[str, Any]) -> None:
        self._thread = None
        self._worker = None
        self._populate_results(result)
        if self._state_mgr is not None and self._state_mgr.dataset is not None:
            self._state_mgr.save_result(self._state_mgr.dataset, "exercise_117", result)
        self.analysis_completed.emit(result)

    def _populate_results(self, result: dict[str, Any]) -> None:
        self._last_result = result
        total_cases = result.get("total_cases", 0)

        # Build summary table rows
        sub_a = result.get("11.7_a", {})
        sub_b = result.get("11.7_b", {})
        sub_c = result.get("11.7_c", {})
        sub_d = result.get("11.7_d", {})
        sub_e = result.get("11.7_e", {})

        mean_b = sub_b.get("mean_cycle_time_days", 0.0)
        mean_c = sub_c.get("mean_cycle_time_days", 0.0)
        mean_d = sub_d.get("mean_cycle_time_days", 0.0)
        mean_e = sub_e.get("mean_cycle_time_days", 0.0)

        summary_rows = [
            (
                "11.7 A",
                sub_a.get("question", "Jumlah keseluruhan case"),
                sub_a.get("rule", RULE_117_A),
                str(sub_a.get("count", total_cases)),
                str(total_cases),
                "100.0%" if total_cases else "0.0%",
                "-",
            ),
            (
                "11.7 B",
                sub_b.get("question", "Rata-rata cycle time seluruh case"),
                sub_b.get("rule", RULE_117_B),
                str(sub_b.get("valid_duration_cases", total_cases)),
                str(total_cases),
                f"{sub_b.get('valid_duration_cases', total_cases) / total_cases:.2%}"
                if total_cases else "0.00%",
                f"{mean_b:.4f}",
            ),
            (
                "11.7 C",
                sub_c.get("question", "Successful cases & cycle time"),
                sub_c.get("rule", RULE_117_C),
                str(sub_c.get("count", 0)),
                str(total_cases),
                f"{sub_c.get('percentage', 0.0):.2f}%",
                f"{mean_c:.4f}",
            ),
            (
                "11.7 D",
                sub_d.get("question", "Unsuccessful cases & cycle time"),
                sub_d.get("rule", RULE_117_D),
                str(sub_d.get("count", 0)),
                str(total_cases),
                f"{sub_d.get('percentage', 0.0):.2f}%",
                f"{mean_d:.4f}",
            ),
            (
                "11.7 E",
                sub_e.get("question", "Canceled cases & cycle time"),
                sub_e.get("rule", RULE_117_E),
                str(sub_e.get("count", 0)),
                str(total_cases),
                f"{sub_e.get('percentage', 0.0):.2f}%",
                f"{mean_e:.4f}",
            ),
        ]

        self.summary_table.setRowCount(len(summary_rows))
        for row_idx, row in enumerate(summary_rows):
            for col_idx, val in enumerate(row):
                item = QTableWidgetItem(val)
                item.setToolTip(val)
                if col_idx in (0, 3, 4, 5, 6):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.summary_table.setItem(row_idx, col_idx, item)

        # Collect evidence rows
        c_evidence = sub_c.get("evidence", [])
        d_evidence = sub_d.get("evidence", [])
        e_evidence = sub_e.get("evidence", [])
        self._evidence_rows = c_evidence + d_evidence + e_evidence

        self._filter_table()

        msg = (
            f"Analisis selesai: {total_cases} total case, "
            f"{sub_c.get('count', 0)} successful (C), "
            f"{sub_d.get('count', 0)} unsuccessful (D), "
            f"{sub_e.get('count', 0)} canceled (E)."
        )
        self._apply_state("loaded", msg)

    @Slot(str)
    def _on_analysis_error(self, message: str) -> None:
        self._thread = None
        self._worker = None
        self._apply_state("error", f"Analisis gagal: {message}")
        self.analysis_failed.emit(message)

    @Slot()
    def reset_results(self) -> None:
        """Clear results and return to ready state."""
        if self._host_window is not None:
            self._host_window.reset_result("exercise_117")
            return
        if self._thread is not None and self._thread.isRunning():
            self._thread.quit()
            self._thread.wait(2000)
            self._thread = None
            self._worker = None

        self._clear_result_widgets()

        if self._state_mgr is not None:
            self._state_mgr.clear_result("exercise_117")

        if self._active_log is not None:
            self._apply_state("ready", "Hasil direset. Klik 'Jalankan Analisis 11.7' untuk menghitung kembali.")
        else:
            self._apply_state("no_dataset", "Dataset belum dimuat.")

    def _clear_result_widgets(self) -> None:
        self._last_result = None
        self._evidence_rows = []
        self._displayed_cases = []
        self._table_model.set_cases([])
        self.summary_table.setRowCount(0)
        self.table_count_label.setText("0 case")

    def _filter_table(self) -> None:
        """Fast filter in Python memory, updating the virtual model in 0 ms."""
        if not self._last_result:
            self._displayed_cases = []
            self._table_model.set_cases([])
            self.table_count_label.setText("0 case")
            self._update_open_button_state()
            return

        cat_idx = self.category_combo.currentIndex()
        query = self.filter_input.text().strip().lower()

        sub_c = self._last_result.get("11.7_c", {}).get("evidence", [])
        sub_d = self._last_result.get("11.7_d", {}).get("evidence", [])
        sub_e = self._last_result.get("11.7_e", {}).get("evidence", [])

        if cat_idx == 1:
            candidates = sub_c
        elif cat_idx == 2:
            candidates = sub_d
        elif cat_idx == 3:
            candidates = sub_e
        else:
            candidates = self._evidence_rows

        if query:
            filtered = [c for c in candidates if query in str(c.get("case_id", "")).lower()]
        else:
            filtered = list(candidates)

        self._displayed_cases = filtered
        self._table_model.set_cases(filtered)
        self.table_count_label.setText(f"{len(filtered):,} case tampil")
        self._update_open_button_state()

    def _apply_state(self, state: str, message: str) -> None:
        self._state = state
        self.status_label.setText(message)
        self._sync_controls()
        self.state_changed.emit(state)

    def _sync_controls(self) -> None:
        has_dataset = self._active_log is not None
        running = self._state == "loading"
        ready = has_dataset and not running and self._operations_available

        self.run_button.setEnabled(ready)
        self.reset_button.setEnabled(ready and self._last_result is not None)
        self.export_csv_button.setEnabled(ready and self._last_result is not None)
        self.filter_input.setEnabled(not running and len(self._evidence_rows) > 0)
        self.category_combo.setEnabled(not running and len(self._evidence_rows) > 0)
        self._update_open_button_state()

    def _quick_export_csv(self) -> None:
        """Direct export of 11.7 summary to CSV."""
        if self._last_result is None:
            return
        if self._host_window is not None:
            self._host_window.navigate("export")
            return
        default_name = "bpic17_summary_exercise_117.csv"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Simpan Ringkasan Exercise 11.7 ke CSV",
            default_name,
            "CSV Files (*.csv);;All Files (*)",
        )
        if file_path:
            try:
                saved = export_summary_to_csv(self._last_result, file_path)
                self.status_label.setText(f"Berhasil mengekspor ringkasan ke: {saved}")
            except Exception as err:
                self.status_label.setText(f"Gagal ekspor CSV: {err}")

    def _update_open_button_state(self) -> None:
        sel_model = self.result_table.selectionModel()
        has_sel = (
            self._state != "loading"
            and sel_model is not None
            and len(sel_model.selectedRows()) > 0
        )
        self.open_explorer_button.setEnabled(has_sel)

    def _on_selection_changed(self, *_) -> None:
        self._update_open_button_state()
        sel_model = self.result_table.selectionModel()
        if sel_model is not None:
            indexes = sel_model.selectedRows()
            if indexes:
                row = indexes[0].row()
                case = self._table_model.get_case(row)
                if case is not None:
                    self.case_selected.emit(case.get("case_id"), case)

    def _open_selected_row(self) -> None:
        sel_model = self.result_table.selectionModel()
        if sel_model is None:
            return
        indexes = sel_model.selectedRows()
        if not indexes:
            return
        row = indexes[0].row()
        case = self._table_model.get_case(row)
        if case is not None:
            case_id = case.get("case_id")
            self.open_case_requested.emit(case_id, case)
            if self._on_open_case is not None:
                self._on_open_case(case_id, case)

    def closeEvent(self, event: Any) -> None:
        self._closing = True
        if self._thread is not None and self._thread.isRunning():
            self._thread.quit()
            self._thread.wait(2000)
            self._thread = None
            self._worker = None
        super().closeEvent(event)
