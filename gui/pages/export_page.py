"""PySide6 page widget for Export Results (CSV export for Exercise 11.7 & overall analyses).

Follows BPIC17 desktop architecture:
- Designed to be installed into MainWindow via ``MainWindow.install_page("export", panel)``.
- Exports summary metrics and case lists into CSV format.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from gui.app_state import AppState
from modules.export_csv import export_cases_to_csv, export_summary_to_csv


class ExportPage(QWidget):
    """Widget panel for Export Results to CSV."""

    def __init__(
        self,
        state: AppState,
        parent: QWidget | None = None,
        *,
        ex117_page: Any = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("exportPage")
        self._state = state
        self._ex117_page = ex117_page
        self._build_ui()
        self._state.result_changed.connect(self._on_results_updated)
        self._state.dataset_changed.connect(lambda _: self._update_export_status())
        if self._ex117_page is not None and hasattr(self._ex117_page, "analysis_completed"):
            self._ex117_page.analysis_completed.connect(lambda _: self._update_export_status())
        self._update_export_status()

    def showEvent(self, event: Any) -> None:
        super().showEvent(event)
        self._update_export_status()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        # Header card
        header_frame = QFrame()
        header_frame.setObjectName("surface")
        header_layout = QVBoxLayout(header_frame)
        header_layout.setContentsMargins(16, 14, 16, 14)
        header_layout.setSpacing(6)

        title = QLabel("Ekspor Hasil Analisis (CSV)")
        title.setObjectName("sectionTitle")
        desc = QLabel(
            "Simpan ringkasan jawaban metrik dan daftar case hasil pemfilteran "
            "ke dalam file format CSV (UTF-8) untuk pelaporan dan verifikasi."
        )
        desc.setObjectName("helpText")
        desc.setWordWrap(True)

        header_layout.addWidget(title)
        header_layout.addWidget(desc)
        layout.addWidget(header_frame)

        # Main Export Actions
        body_frame = QFrame()
        body_frame.setObjectName("surface")
        body_layout = QVBoxLayout(body_frame)
        body_layout.setContentsMargins(18, 16, 18, 16)
        body_layout.setSpacing(16)

        # 1. Summary Export Section
        summary_group = QGroupBox("1. Ekspor Ringkasan Jawaban Metrik (Exercise 11.7 A–E)")
        summary_layout = QVBoxLayout(summary_group)
        summary_desc = QLabel(
            "Mengekspor tabel ringkasan: Subsoal, Pertanyaan, Aturan/Filter, Jumlah Case, "
            "Total Denominator, Persentase, dan Mean Cycle Time (Hari)."
        )
        summary_desc.setObjectName("helpText")
        summary_desc.setWordWrap(True)

        summary_btn_row = QHBoxLayout()
        self.btn_export_summary = QPushButton("Ekspor Ringkasan ke CSV...")
        self.btn_export_summary.setObjectName("primaryAction")
        self.btn_export_summary.clicked.connect(self._export_summary)
        summary_btn_row.addWidget(self.btn_export_summary)
        summary_btn_row.addStretch()

        summary_layout.addWidget(summary_desc)
        summary_layout.addLayout(summary_btn_row)
        body_layout.addWidget(summary_group)

        # 2. Filtered Cases Export Section
        cases_group = QGroupBox("2. Ekspor Daftar Case Terpilih & Bukti Event")
        cases_layout = QVBoxLayout(cases_group)
        cases_desc = QLabel(
            "Mengekspor daftar detail case terpilih: Case ID, Kategori, Aktivitas Target, "
            "Posisi Evidence, Durasi Case (Hari), dan Rentang Timestamp."
        )
        cases_desc.setObjectName("helpText")
        cases_desc.setWordWrap(True)

        cases_filter_row = QHBoxLayout()
        filter_label = QLabel("Kategori Kasus:")
        self.category_combo = QComboBox()
        self.category_combo.addItems([
            "Semua Kasus Terfilter (11.7 C, D, E)",
            "11.7 C — Successful (O_Accepted)",
            "11.7 D — Unsuccessful (O_Refused)",
            "11.7 E — Canceled (Endpoint O_Cancelled)",
        ])
        cases_filter_row.addWidget(filter_label)
        cases_filter_row.addWidget(self.category_combo)
        cases_filter_row.addSpacing(16)

        self.btn_export_cases = QPushButton("Ekspor Daftar Case ke CSV...")
        self.btn_export_cases.clicked.connect(self._export_cases)
        cases_filter_row.addWidget(self.btn_export_cases)
        cases_filter_row.addStretch()

        cases_layout.addWidget(cases_desc)
        cases_layout.addLayout(cases_filter_row)
        body_layout.addWidget(cases_group)

        # Status / Feedback area
        self.status_label = QLabel("Menunggu analisis dijalankan...")
        self.status_label.setObjectName("helpText")
        self.status_label.setWordWrap(True)
        body_layout.addWidget(self.status_label)

        body_layout.addStretch()
        layout.addWidget(body_frame, 1)

    def _on_results_updated(self, page_key: str) -> None:
        self._update_export_status()

    def _get_117_result(self) -> dict[str, Any] | None:
        if self._state.has_result("exercise_117"):
            return self._state.result("exercise_117")
        if self._ex117_page is not None and getattr(self._ex117_page, "last_result", None) is not None:
            return self._ex117_page.last_result
        return None

    def _update_export_status(self) -> None:
        res_117 = self._get_117_result()
        has_117 = res_117 is not None
        self.btn_export_summary.setEnabled(has_117)
        self.btn_export_cases.setEnabled(has_117)

        if has_117 and res_117:
            total = res_117.get("total_cases", 0)
            c_cnt = res_117.get("11.7_c", {}).get("count", 0)
            d_cnt = res_117.get("11.7_d", {}).get("count", 0)
            e_cnt = res_117.get("11.7_e", {}).get("count", 0)
            self.status_label.setText(
                f"Hasil Exercise 11.7 siap diekspor: {total:,} total case, "
                f"{c_cnt:,} successful (C), {d_cnt:,} unsuccessful (D), {e_cnt:,} canceled (E)."
            )
        else:
            self.status_label.setText(
                "Hasil analisis Exercise 11.7 belum tersedia. "
                "Silakan buka menu Exercise 11.7 dan klik 'Jalankan Analisis 11.7' terlebih dahulu."
            )

    def _export_summary(self) -> None:
        result = self._get_117_result()
        if not result:
            return

        default_name = "bpic17_summary_exercise_117.csv"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Simpan Ringkasan Jawaban ke CSV",
            default_name,
            "CSV Files (*.csv);;All Files (*)",
        )

        if not file_path:
            return

        try:
            saved_path = export_summary_to_csv(result, file_path)
            self.status_label.setText(f"Berhasil mengekspor ringkasan ke: {saved_path}")
        except Exception as err:
            self.status_label.setText(f"Gagal mengekspor ringkasan: {err}")

    def _export_cases(self) -> None:
        result = self._get_117_result()
        if not result:
            return

        idx = self.category_combo.currentIndex()

        c_evidence = result.get("11.7_c", {}).get("evidence", [])
        d_evidence = result.get("11.7_d", {}).get("evidence", [])
        e_evidence = result.get("11.7_e", {}).get("evidence", [])

        if idx == 1:
            cases_to_export = c_evidence
            cat_name = "11.7 C (Successful)"
            default_name = "bpic17_cases_117c_successful.csv"
        elif idx == 2:
            cases_to_export = d_evidence
            cat_name = "11.7 D (Unsuccessful)"
            default_name = "bpic17_cases_117d_unsuccessful.csv"
        elif idx == 3:
            cases_to_export = e_evidence
            cat_name = "11.7 E (Canceled)"
            default_name = "bpic17_cases_117e_canceled.csv"
        else:
            cases_to_export = c_evidence + d_evidence + e_evidence
            cat_name = "Exercise 11.7 (C, D, E)"
            default_name = "bpic17_cases_117_all_filtered.csv"

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            f"Simpan Daftar Case {cat_name} ke CSV",
            default_name,
            "CSV Files (*.csv);;All Files (*)",
        )

        if not file_path:
            return

        try:
            saved_path = export_cases_to_csv(cases_to_export, file_path, category_title=cat_name)
            self.status_label.setText(f"Berhasil mengekspor {len(cases_to_export)} baris case ke: {saved_path}")
        except Exception as err:
            self.status_label.setText(f"Gagal mengekspor daftar case: {err}")
