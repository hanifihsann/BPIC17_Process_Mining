"""Export the results of the active dataset through the shared shell worker."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from PySide6.QtCore import Slot
from PySide6.QtWidgets import QComboBox, QFileDialog, QGroupBox, QLabel, QPushButton, QVBoxLayout, QWidget

from gui.app_state import AppState
from modules.export_csv import case_export_rows, export_cases_to_csv, export_completed_summary_to_csv


ANALYSES = {
    "exercise_117": "11.7 A–E",
    "exercise_115_118": "11.15 dan 11.18",
    "exercise_1122": "11.22",
}

CASE_SELECTIONS = (
    ("11.7 C, D, dan E · Semua kategori", "exercise_117", ("11.7 C", "11.7 D", "11.7 E")),
    ("11.7 C · Successful", "exercise_117", ("11.7 C",)),
    ("11.7 D · Unsuccessful", "exercise_117", ("11.7 D",)),
    ("11.7 E · Canceled", "exercise_117", ("11.7 E",)),
    ("11.15 · Penyelesaian berulang", "exercise_115_118", ("11.15",)),
    ("11.18 · Resource yang sama", "exercise_115_118", ("11.18",)),
    ("11.22 · O_Cancelled sebelum O_Accepted", "exercise_1122", ("11.22",)),
)


class ExportPage(QWidget):
    """Save a combined summary or evidence from one exercise."""

    def __init__(
        self,
        state: AppState,
        parent: QWidget | None = None,
        *,
        host_window: Any = None,
    ) -> None:
        super().__init__(parent)
        self._state = state
        self._host_window = host_window
        self._available = True
        self._exporting = False
        self._build_ui()
        state.result_changed.connect(self._results_changed)
        state.dataset_changed.connect(self._dataset_changed)
        if host_window is not None:
            host_window.operations_available.connect(self._set_available)
            host_window.task_failed.connect(self._export_failed)
        self._update_status()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        summary = QGroupBox("Ringkasan jawaban")
        summary_layout = QVBoxLayout(summary)
        description = QLabel("Simpan semua latihan yang sudah dihitung pada dataset aktif.")
        description.setWordWrap(True)
        summary_layout.addWidget(description)
        self.btn_export_summary = QPushButton("Ekspor Ringkasan ke CSV…")
        self.btn_export_summary.setObjectName("primaryAction")
        self.btn_export_summary.clicked.connect(self._export_summary)
        summary_layout.addWidget(self.btn_export_summary)
        layout.addWidget(summary)

        cases = QGroupBox("Daftar case dan bukti event")
        cases_layout = QVBoxLayout(cases)
        self.category_combo = QComboBox()
        self.category_combo.setAccessibleName("Latihan atau kategori case")
        self.category_combo.addItems([label for label, _, _ in CASE_SELECTIONS])
        self.category_combo.currentIndexChanged.connect(self._sync_buttons)
        cases_layout.addWidget(self.category_combo)
        self.btn_export_cases = QPushButton("Ekspor Daftar Case ke CSV…")
        self.btn_export_cases.clicked.connect(self._export_cases)
        cases_layout.addWidget(self.btn_export_cases)
        layout.addWidget(cases)

        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        self.status_label.setObjectName("helpText")
        layout.addWidget(self.status_label)
        layout.addStretch()

    @Slot(object)
    def _dataset_changed(self, _dataset: Any) -> None:
        self._exporting = False
        self._update_status()

    @Slot(bool)
    def _set_available(self, available: bool) -> None:
        self._available = available
        self._sync_buttons()

    @Slot(str)
    def _results_changed(self, key: str) -> None:
        if key in ANALYSES:
            self._update_status()
        elif key == "export" and self._state.has_result(key):
            self._exporting = False
            self.status_label.setText(f"CSV tersimpan di {self._state.result(key)}")

    @Slot(str, str)
    def _export_failed(self, key: str, message: str) -> None:
        if key == "export":
            self._exporting = False
            self.status_label.setText(f"Ekspor gagal. {message}")

    @Slot()
    @Slot(int)
    def _sync_buttons(self, _index: int = 0) -> None:
        _, key, _ = CASE_SELECTIONS[self.category_combo.currentIndex()]
        ready = self._available and not self._exporting
        self.btn_export_summary.setEnabled(ready and any(self._state.has_result(key) for key in ANALYSES))
        self.btn_export_cases.setEnabled(ready and self._state.has_result(key))
        self.category_combo.setEnabled(ready)

    def _update_status(self) -> None:
        available = [label for key, label in ANALYSES.items() if self._state.has_result(key)]
        message = ("Latihan siap diekspor: " + ", ".join(available) if available else
                   "Jalankan analisis pada dataset aktif untuk menyiapkan hasil ekspor.")
        self.status_label.setText(message)
        self._sync_buttons()

    def _save(self, default_name: str, operation: Callable[[str], Path]) -> None:
        dataset = self._state.dataset
        filename, _ = QFileDialog.getSaveFileName(self, "Simpan CSV", default_name, "CSV (*.csv)")
        if not filename or dataset is not self._state.dataset:
            return
        if not Path(filename).suffix:
            filename += ".csv"
        if self._host_window is not None:
            if self._host_window.run_task("export", "Ekspor CSV", lambda _: operation(filename)):
                self._exporting = True
                self.status_label.setText("Sedang menyimpan CSV…")
            return
        try:
            saved_path = operation(filename)
            self.status_label.setText(f"CSV tersimpan di {saved_path}")
        except OSError as error:
            self._export_failed("export", str(error))

    @Slot()
    def _export_summary(self) -> None:
        results = tuple(self._state.result(key) for key in ANALYSES if self._state.has_result(key))
        if results:
            self._save("bpic17_ringkasan.csv", lambda path: export_completed_summary_to_csv(results, path))

    @Slot()
    def _export_cases(self) -> None:
        _, key, codes = CASE_SELECTIONS[self.category_combo.currentIndex()]
        result = self._state.result(key)
        if result is not None:
            filename = "bpic17_case_" + "_".join(code.replace(" ", "_") for code in codes) + ".csv"
            self._save(filename, lambda path: export_cases_to_csv(case_export_rows(result, codes), path))
