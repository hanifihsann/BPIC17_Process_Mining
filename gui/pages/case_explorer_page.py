"""Embeddable PySide6 Case Explorer page for inspecting full case traces.

Designed to be mounted inside Member 5's ``MainWindow`` via ``install_page``.
Reuses the active in-memory dataset from Member 1 without reloading XES files,
and integrates with Exercise 11.22 (and Exercises 11.7, 11.15, 11.18) via
``open_case(case_id, evidence=None)``.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QModelIndex, Qt, Signal, Slot
from PySide6.QtGui import QBrush, QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from gui.widgets import DataTable
from gui.workers import TaskThread
from modules.case_explorer import (
    CaseIndex,
    build_case_index,
    get_case_detail,
    search_cases,
)


class CaseExplorerPage(QWidget):
    """Embeddable Case Explorer widget.

    Integration methods and signals
    -------------------------------
    ``bind_main_window(window)``
        Subscribes to ``window.state.dataset_changed`` for automatic updates.
    ``set_dataset(log_or_df, metadata=None, overview=None)``
        Attaches an active dataset (or ``ActiveDataset``) and indexes cases in a worker thread.
    ``open_case(case_id, evidence=None)``
        Selects and renders ``case_id`` with optional evidence position markers.
    ``case_opened(case_id, event_count)``
        Emitted after a case trace is rendered.
    """

    case_opened = Signal(object, int)
    state_changed = Signal(str)
    indexing_failed = Signal(str)

    _EVIDENCE_BG = QColor("#FFF3CD")
    _EVIDENCE_FG = QColor("#533F03")

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._active_log: Any | None = None
        self._active_metadata: dict[str, Any] | None = None
        self._case_index: CaseIndex | None = None
        self._visible_cases: list[dict[str, Any]] = []
        self._current_case_id: Any | None = None
        self._current_evidence: Any = None
        self._pending_open: tuple[Any, Any] | None = None
        self._pending_dataset: tuple[Any, dict[str, Any] | None] | None = None
        self._host_window: Any | None = None
        self._state: str = "no_dataset"

        self._thread: TaskThread | None = None
        self._closing = False

        self._build_ui()
        app = QApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self._wait_for_thread)
        self._apply_state(
            "no_dataset",
            "Dataset belum dimuat. Muat file XES pada halaman Import Dataset.",
        )

    def _build_ui(self) -> None:
        self.setObjectName("caseExplorerPage")
        root = QVBoxLayout(self)

        # Search & control bar
        search_box = QGroupBox("Case Explorer — Pencarian && Inspeksi Trace Asli")
        search_layout = QVBoxLayout(search_box)

        controls_row = QHBoxLayout()
        controls_row.addWidget(QLabel("Cari Case ID:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Masukkan Case ID atau sebagian ID...")
        self.search_input.returnPressed.connect(self.apply_search)
        controls_row.addWidget(self.search_input, 1)

        self.search_button = QPushButton("Cari")
        self.search_button.setObjectName("primaryAction")
        self.search_button.clicked.connect(self.apply_search)
        self.reset_button = QPushButton("Reset")
        self.reset_button.clicked.connect(self.reset_view)

        controls_row.addWidget(self.search_button)
        controls_row.addWidget(self.reset_button)
        search_layout.addLayout(controls_row)

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        search_layout.addWidget(self.status_label)
        root.addWidget(search_box)

        # Split view: Case list (left) & full event trace (right)
        splitter = QSplitter(Qt.Horizontal)

        case_list_box = QGroupBox("Daftar Case")
        case_list_layout = QVBoxLayout(case_list_box)
        self.case_count_label = QLabel("Total case: 0")
        case_list_layout.addWidget(self.case_count_label)

        self.case_table = DataTable(["Case ID", "Event", "Mulai", "Selesai"])
        for column, width in enumerate((155, 54, 184)):
            self.case_table.setColumnWidth(column, width)
        self.case_table.clicked.connect(self._on_case_clicked)
        self.case_table.activated.connect(self._on_case_clicked)
        case_list_layout.addWidget(self.case_table)
        splitter.addWidget(case_list_box)

        trace_box = QGroupBox("Detail Event Trace (Seluruh Event Asli)")
        trace_layout = QVBoxLayout(trace_box)
        self.case_header_label = QLabel("Belum ada case dipilih.")
        self.case_header_label.setWordWrap(True)
        trace_layout.addWidget(self.case_header_label)

        self.event_table = QTableWidget(0, 6)
        self.event_table.setHorizontalHeaderLabels(
            ["No.", "Timestamp", "Activity", "Lifecycle", "Resource", "Evidence"]
        )
        self._configure_table(self.event_table)
        trace_layout.addWidget(self.event_table)
        splitter.addWidget(trace_box)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        root.addWidget(splitter, 1)

    @staticmethod
    def _configure_table(table: QTableWidget) -> None:
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setSelectionMode(QAbstractItemView.SingleSelection)
        table.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        table.setAlternatingRowColors(True)
        table.setSortingEnabled(False)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        table.horizontalHeader().setStretchLastSection(True)
        table.verticalHeader().setVisible(False)

    def bind_main_window(self, window: Any) -> None:
        """Subscribe Case Explorer to Member 5's shared ``AppState``."""

        if self._host_window is window:
            return
        self._host_window = window
        window.state.dataset_changed.connect(self.set_dataset)
        if window.state.dataset is not None:
            self.set_dataset(window.state.dataset)

    @property
    def current_state(self) -> str:
        """Return the current UI state name."""

        return self._state

    @property
    def current_case_id(self) -> Any | None:
        """Return the currently displayed Case ID."""

        return self._current_case_id

    def is_indexing(self) -> bool:
        """Return True while background case indexing is running."""

        return self._thread is not None

    def _apply_state(self, state: str, message: str) -> None:
        self._state = state
        self.status_label.setText(message)

        has_index = self._active_log is not None and self._case_index is not None
        loading = state == "loading"

        self.search_input.setEnabled(has_index and not loading)
        self.search_button.setEnabled(has_index and not loading)
        self.reset_button.setEnabled(self._active_log is not None and not loading)
        self.state_changed.emit(state)

    @Slot(object)
    @Slot(object, object)
    @Slot(object, object, object)
    def set_dataset(
        self,
        log_or_df: Any,
        metadata: dict[str, Any] | None = None,
        overview: dict[str, Any] | None = None,
    ) -> None:
        """Attach the active in-memory dataset (or ``ActiveDataset``) and build its index."""

        del overview
        if hasattr(log_or_df, "log") and hasattr(log_or_df, "metadata"):
            metadata = log_or_df.metadata
            log_or_df = log_or_df.log

        self._active_log = log_or_df
        self._active_metadata = metadata if isinstance(metadata, dict) else None
        self._case_index = None
        self._visible_cases = []
        self._current_case_id = None
        self._current_evidence = None
        self._pending_open = None

        self.search_input.clear()
        self.case_table.set_rows(())
        self.event_table.setRowCount(0)
        self.case_count_label.setText("Total case: 0")
        self.case_header_label.setText("Belum ada case dipilih.")

        if self.is_indexing():
            self._pending_dataset = (log_or_df, self._active_metadata)
            self._apply_state("loading", "Menunggu indeks dataset baru...")
            return

        if log_or_df is None:
            self._apply_state("no_dataset", "Dataset belum dimuat.")
            return

        self._apply_state("loading", "Membangun indeks case untuk Case Explorer...")

        thread = TaskThread(lambda: build_case_index(log_or_df), "Indeks Case Explorer", self)
        thread.finished.connect(self._on_thread_finished, Qt.ConnectionType.QueuedConnection)
        self._thread = thread
        thread.start()

    @Slot(object)
    def _on_index_completed(self, index: CaseIndex) -> None:
        if self._closing:
            return

        self._case_index = index
        self._visible_cases = list(index.case_summaries)
        self._populate_case_table(self._visible_cases)

        total = len(index.case_ids)
        if total == 0:
            self._apply_state("empty", "Dataset aktif kosong (0 case).")
        else:
            self._apply_state(
                "ready",
                f"Indeks siap: {total} case tersedia. Pilih atau cari Case ID.",
            )

        if self._pending_open is not None:
            case_id, evidence = self._pending_open
            self._pending_open = None
            self.open_case(case_id, evidence)

    @Slot(str)
    def _on_index_failed(self, message: str) -> None:
        if self._closing:
            return

        self._case_index = None
        self._pending_open = None
        self._apply_state("error", f"Gagal memvalidasi/mengindeks dataset: {message}")
        self.indexing_failed.emit(message)

    @Slot()
    def _on_thread_finished(self) -> None:
        thread = self._thread
        self._thread = None
        if thread is None:
            return
        thread.deleteLater()
        if self._closing:
            return
        if self._pending_dataset is not None:
            log_or_df, metadata = self._pending_dataset
            pending_open = self._pending_open
            self._pending_dataset = None
            self.set_dataset(log_or_df, metadata)
            self._pending_open = pending_open
        elif thread.error is not None:
            self._on_index_failed(thread.error)
        else:
            self._on_index_completed(thread.result)

    @Slot()
    def clear_dataset(self) -> None:
        """Detach the active dataset and clear the case view."""
        self.set_dataset(None)

    @Slot()
    def reset_view(self) -> None:
        """Reset search query, selected case, and evidence highlights without reloading XES."""

        if self.is_indexing():
            return
        self.search_input.clear()
        self._current_case_id = None
        self._current_evidence = None
        self.event_table.setRowCount(0)
        self.case_header_label.setText("Belum ada case dipilih.")

        if self._active_log is None or self._case_index is None:
            self._apply_state("no_dataset", "Dataset belum dimuat.")
            return

        self._visible_cases = list(self._case_index.case_summaries)
        self._populate_case_table(self._visible_cases)
        if not self._visible_cases:
            self._apply_state("empty", "Dataset aktif kosong (0 case).")
        else:
            self._apply_state(
                "ready",
                f"Tampilan direset. {len(self._visible_cases)} case tersedia.",
            )

    @Slot()
    def apply_search(self) -> None:
        """Filter the case list by search text and open an exact match if present."""

        if self._active_log is None or self._case_index is None:
            self._apply_state("no_dataset", "Dataset belum dimuat.")
            return

        query = self.search_input.text().strip()
        matches = search_cases(self._active_log, query, index=self._case_index)
        self._visible_cases = matches
        self._populate_case_table(matches)

        if not matches:
            self._current_case_id = None
            self._current_evidence = None
            self.event_table.setRowCount(0)
            self.case_header_label.setText(f"Case '{query}' tidak ditemukan.")
            self._apply_state("empty", f"Tidak ditemukan case untuk kata kunci '{query}'.")
            return

        exact = self._case_index.resolve_case_id(query)
        if exact is not None:
            self.open_case(exact, evidence=None)
        elif len(matches) == 1:
            self.open_case(matches[0]["case_id"], evidence=None)
        else:
            self._current_case_id = None
            self._current_evidence = None
            self.event_table.setRowCount(0)
            self.case_header_label.setText("Pilih case dari hasil pencarian.")
            self._apply_state(
                "ready",
                f"Ditemukan {len(matches)} case yang cocok dengan '{query}'. Pilih baris untuk melihat detail.",
            )

    @Slot(object)
    @Slot(object, object)
    def open_case(self, case_id: Any, evidence: Any = None) -> None:
        """Display the complete trace for ``case_id`` with optional evidence highlights."""

        if self._active_log is None:
            self._apply_state("no_dataset", "Dataset belum dimuat.")
            return

        if self._case_index is None:
            if self.is_indexing():
                self._pending_open = (case_id, evidence)
                self._apply_state(
                    "loading",
                    f"Menunggu indeks selesai untuk membuka case '{case_id}'...",
                )
                return
            self._apply_state("error", "Indeks case belum tersedia.")
            return

        try:
            detail = get_case_detail(
                self._active_log,
                case_id,
                evidence=evidence,
                index=self._case_index,
            )
        except Exception as error:
            self._apply_state("error", f"Gagal memuat trace case '{case_id}': {error}")
            return

        if not detail["found"]:
            self._current_case_id = None
            self._current_evidence = None
            self.event_table.setRowCount(0)
            self.case_header_label.setText(f"Case '{case_id}' tidak ditemukan.")
            self._apply_state("empty", f"Case '{case_id}' tidak ditemukan pada dataset aktif.")
            return

        self._current_case_id = detail["case_id"]
        self._current_evidence = evidence
        self._select_case_in_list(detail["case_id"])
        self._render_trace(detail)

        evidence_count = len(detail["evidence_positions"])
        header_parts = [
            f"Case ID: {detail['case_id']}",
            f"Jumlah event: {detail['event_count']}",
        ]
        if evidence_count > 0:
            seqs = ", ".join(f"#{p + 1}" for p in detail["evidence_positions"])
            header_parts.append(f"Evidence disorot pada urutan: {seqs}")
        self.case_header_label.setText(" | ".join(header_parts))

        self._apply_state(
            "loaded",
            f"Menampilkan {detail['event_count']} event asli untuk case '{detail['case_id']}'.",
        )
        self.case_opened.emit(detail["case_id"], detail["event_count"])

    def _populate_case_table(self, summaries: list[dict[str, Any]]) -> None:
        self.case_count_label.setText(f"Total case tampil: {len(summaries)}")
        columns = ("case_id", "event_count", "start_timestamp", "end_timestamp")
        self.case_table.set_rows([
            tuple(summary.get(column) for column in columns) for summary in summaries
        ])

    def _select_case_in_list(self, case_id: Any) -> None:
        for row, summary in enumerate(self._visible_cases):
            if summary["case_id"] == case_id:
                self.case_table.selectRow(row)
                self.case_table.scrollTo(
                    self.case_table.model().index(row, 0),
                    QAbstractItemView.ScrollHint.PositionAtCenter,
                )
                return

    def _render_trace(self, detail: dict[str, Any]) -> None:
        events = detail["events"]
        self.event_table.setRowCount(len(events))

        bold_font = QFont()
        bold_font.setBold(True)
        bg_brush = QBrush(self._EVIDENCE_BG)
        fg_brush = QBrush(self._EVIDENCE_FG)
        first_evidence_row: int | None = None

        for row_idx, event in enumerate(events):
            lifecycle = event.get("lifecycle")
            resource = event.get("resource")
            is_evidence = bool(event.get("is_evidence", False))
            evidence_role = event.get("evidence_role")
            if is_evidence and first_evidence_row is None:
                first_evidence_row = row_idx

            evidence_text = f"Evidence ({evidence_role})" if is_evidence else "-"
            values = (
                event.get("seq"),
                event.get("timestamp"),
                event.get("activity"),
                "-" if lifecycle is None else lifecycle,
                "-" if resource is None else resource,
                evidence_text,
            )

            for col_idx, val in enumerate(values):
                text = "-" if val is None else str(val)
                item = QTableWidgetItem(text)
                item.setToolTip(text)
                if is_evidence:
                    item.setBackground(bg_brush)
                    item.setForeground(fg_brush)
                    item.setFont(bold_font)
                self.event_table.setItem(row_idx, col_idx, item)

        if first_evidence_row is not None:
            first_item = self.event_table.item(first_evidence_row, 0)
            if first_item is not None:
                self.event_table.scrollToItem(
                    first_item, QAbstractItemView.ScrollHint.PositionAtCenter
                )

    @Slot(QModelIndex)
    def _on_case_clicked(self, index: QModelIndex) -> None:
        row = index.row()
        if 0 <= row < len(self._visible_cases):
            case_id = self._visible_cases[row]["case_id"]
            evidence = (
                self._current_evidence if case_id == self._current_case_id else None
            )
            self.open_case(case_id, evidence=evidence)

    @Slot()
    def _wait_for_thread(self) -> None:
        self._closing = True
        thread = self._thread
        if thread is not None:
            thread.wait()

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt API name
        """Wait cleanly for any active indexing thread before closing."""

        self._wait_for_thread()
        super().closeEvent(event)
