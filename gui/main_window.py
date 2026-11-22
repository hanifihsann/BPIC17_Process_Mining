"""Desktop navigation and integration for the BPIC17 feature panels."""

import logging
import platform
from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

from PySide6.QtCore import QThread, QTimer, Qt, Signal, Slot
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from gui.app_state import ActiveDataset, AppState
from gui.import_overview_page import ImportOverviewPage
from gui.widgets import DatasetBar, FeedbackBar, TaskControls
from gui.workers import TaskThread


LOGGER = logging.getLogger(__name__)

FEATURES = {
    "exercise_117": ("Exercise 11.7", "Anggota 2"),
    "exercise_115_118": ("Exercise 11.15 & 11.18", "Anggota 3"),
    "exercise_1122": ("Exercise 11.22", "Anggota 4"),
    "case_explorer": ("Case Explorer", "Anggota 4"),
    "export": ("Export Results", "Anggota 2"),
}

PAGES = {
    "import": "Import Dataset",
    "overview": "Overview",
    **{key: title for key, (title, _) in FEATURES.items()},
    "about": "About",
}


@dataclass(frozen=True, slots=True)
class FeatureTask:
    page_key: str
    description: str
    operation: Callable[[ActiveDataset], Any]


@dataclass(frozen=True, slots=True)
class RunningTask:
    task: FeatureTask
    dataset: ActiveDataset
    thread: TaskThread


def _package_version(package: str) -> str:
    try:
        return version(package)
    except PackageNotFoundError:
        return "Belum terpasang"


def _surface() -> tuple[QFrame, QVBoxLayout]:
    frame = QFrame()
    frame.setObjectName("surface")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(20, 18, 20, 18)
    layout.setSpacing(10)
    return frame, layout


def _placeholder(owner: str) -> QWidget:
    page, layout = _surface()
    title = QLabel("Menunggu integrasi")
    title.setObjectName("sectionTitle")
    message = QLabel(f"Panel ini akan tersedia setelah modul {owner} siap diintegrasikan.")
    message.setObjectName("helpText")
    message.setWordWrap(True)
    layout.addWidget(title)
    layout.addWidget(message)
    layout.addStretch()
    return page


def _about() -> QWidget:
    page, layout = _surface()
    title = QLabel("BPIC17 Process Mining")
    title.setObjectName("sectionTitle")
    description = QLabel("Aplikasi desktop untuk proyek Tahap 1 mata kuliah Data Mining. "
                         "Aplikasi ini membaca event log pengajuan pinjaman BPI Challenge 2017.")
    description.setWordWrap(True)
    description.setObjectName("helpText")
    layout.addWidget(title)
    layout.addWidget(description)

    versions = QFormLayout()
    versions.addRow("Python", QLabel(platform.python_version()))
    for package in ("PySide6", "PM4Py", "pandas"):
        versions.addRow(package, QLabel(_package_version(package)))
    layout.addLayout(versions)
    layout.addStretch()
    return page


class MainWindow(QMainWindow):
    """Host one import panel and coordinate tasks across feature pages."""

    operations_available = Signal(bool)
    task_failed = Signal(str, str)

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("BPIC17 Process Mining")
        self.resize(1100, 760)
        self.setMinimumSize(780, 540)
        self.state = AppState(self)
        self.import_page = ImportOverviewPage()
        self._page_widgets: dict[str, QWidget] = {}
        self._task_controls: dict[str, TaskControls] = {}
        self._last_tasks: dict[str, FeatureTask] = {}
        self._pending_import: str | None = None
        self._task: RunningTask | None = None
        self._close_requested = False

        self._build_ui()
        self.import_page.load_started.connect(self._import_started)
        self.import_page.status_changed.connect(self._import_status)
        self.import_page.dataset_loaded.connect(self._dataset_loaded)
        self.import_page.dataset_validation_failed.connect(self._validation_failed)
        self.import_page.load_failed.connect(self._load_failed)
        self.state.dataset_changed.connect(self._active_dataset_changed)
        self.feedback.display("Siap. Pilih file XES untuk mulai.")
        self.navigate("import")

    @property
    def busy(self) -> bool:
        return self._pending_import is not None or self._task is not None

    def _build_ui(self) -> None:
        root = QWidget()
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.setCentralWidget(root)

        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(222)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(16, 22, 16, 16)
        sidebar_layout.setSpacing(4)
        brand = QLabel("BPIC17")
        brand.setObjectName("brand")
        subtitle = QLabel("Process Mining")
        subtitle.setObjectName("brandSubtitle")
        sidebar_layout.addWidget(brand)
        sidebar_layout.addWidget(subtitle)
        sidebar_layout.addSpacing(14)
        self.navigation = QListWidget()
        self.navigation.setObjectName("navigation")
        self.navigation.setAccessibleName("Navigasi halaman")
        self.navigation.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.navigation.addItems(list(PAGES.values()))
        self.navigation.currentRowChanged.connect(self._show_page)
        sidebar_layout.addWidget(self.navigation, 1)
        layout.addWidget(sidebar)

        workspace = QWidget()
        workspace.setObjectName("workspace")
        workspace_layout = QVBoxLayout(workspace)
        workspace_layout.setContentsMargins(24, 18, 24, 16)
        workspace_layout.setSpacing(12)
        self.page_title = QLabel()
        self.page_title.setObjectName("pageTitle")
        self.dataset_bar = DatasetBar()
        self.stack = QStackedWidget()
        workspace_layout.addWidget(self.page_title)
        workspace_layout.addWidget(self.dataset_bar)
        workspace_layout.addWidget(self.stack, 1)
        layout.addWidget(workspace, 1)

        self.import_scroll = QScrollArea()
        self.import_scroll.setObjectName("importScroll")
        self.import_scroll.setWidgetResizable(True)
        self.import_page.file_label.setWordWrap(True)
        self.import_page.file_label.setTextFormat(Qt.TextFormat.PlainText)
        self.import_page.time_range_label.setWordWrap(True)
        self.import_scroll.setWidget(self.import_page)
        self.stack.addWidget(self.import_scroll)
        for key, (_, owner) in FEATURES.items():
            self._add_page(key, _placeholder(owner))
        self._add_page("about", _about())

        self.feedback = FeedbackBar()
        self.setStatusBar(self.feedback)
        help_menu = self.menuBar().addMenu("&Bantuan")
        help_menu.addAction("About", lambda: self.navigate("about"))

    def _add_page(self, page_key: str, page: QWidget) -> None:
        self._page_widgets[page_key] = page
        self.stack.addWidget(page)

    def navigate(self, page_key: str) -> None:
        """Open a page by its stable integration key."""
        row = tuple(PAGES).index(page_key)
        if self.navigation.currentRow() == row:
            self._show_page(row)
        else:
            self.navigation.setCurrentRow(row)

    @Slot(int)
    def _show_page(self, row: int) -> None:
        if row < 0:
            return
        page_key = tuple(PAGES)[row]
        self.page_title.setText(PAGES[page_key])
        if page_key in ("import", "overview"):
            self.stack.setCurrentWidget(self.import_scroll)
            if page_key == "overview":
                # The existing combined panel places the label in its Overview section.
                overview_section = self.import_page.total_cases_label.parentWidget()
                top = overview_section.mapTo(self.import_page, overview_section.rect().topLeft())
                self.import_scroll.verticalScrollBar().setValue(top.y() - 8)
            else:
                self.import_scroll.verticalScrollBar().setValue(0)
            return
        self.stack.setCurrentWidget(self._page_widgets[page_key])

    def install_page(
        self, page_key: str, page: QWidget, controls: TaskControls | None = None
    ) -> None:
        """Replace a feature placeholder with a PIC-owned widget while idle."""
        if page_key not in FEATURES:
            raise ValueError(f"Halaman fitur tidak dikenal: {page_key}")
        if self.busy or self._close_requested:
            raise RuntimeError("Tunggu proses selesai sebelum memasang halaman.")
        previous = self._page_widgets[page_key]
        was_visible = self.stack.currentWidget() is previous
        self._task_controls.pop(page_key, None)
        self._last_tasks.pop(page_key, None)
        self.state.clear_result(page_key)
        self.stack.removeWidget(previous)
        previous.deleteLater()
        self._add_page(page_key, page)
        if controls is not None:
            self._task_controls[page_key] = controls
            controls.reset_requested.connect(partial(self.reset_result, page_key))
            controls.rerun_requested.connect(partial(self.rerun_task, page_key))
        if was_visible:
            self.stack.setCurrentWidget(page)
        self._sync_controls()

    def run_task(
        self, page_key: str, description: str, operation: Callable[[ActiveDataset], Any]
    ) -> bool:
        """Run one registered feature operation using the current dataset."""
        return self._start_task(FeatureTask(page_key, description, operation))

    def rerun_task(self, page_key: str) -> bool:
        """Repeat the last requested operation for this dataset and page."""
        task = self._last_tasks.get(page_key)
        return self._start_task(task) if task is not None else False

    def reset_result(self, page_key: str) -> None:
        """Clear the page's result and retain its operation for re-run."""
        if self.busy or self._close_requested or not self.state.has_result(page_key):
            return
        self.state.clear_result(page_key)
        self._sync_controls()
        self.feedback.display(f"Hasil {PAGES[page_key]} direset.")

    def _start_task(self, task: FeatureTask) -> bool:
        if self.busy or self._close_requested:
            return False
        if task.page_key not in FEATURES:
            raise ValueError(f"Halaman fitur tidak dikenal: {task.page_key}")
        dataset = self.state.dataset
        if dataset is None:
            self.feedback.display("Impor dataset XES sebelum menjalankan proses.", "error")
            return False

        thread = TaskThread(partial(task.operation, dataset), task.description, self)
        thread.finished.connect(self._task_finished, Qt.ConnectionType.QueuedConnection)
        self._last_tasks[task.page_key] = task
        self._task = RunningTask(task, dataset, thread)
        self.state.clear_result(task.page_key)
        self.feedback.display(f"{task.description} sedang berjalan…", "busy")
        self._sync_controls()
        thread.start()
        return True

    @Slot()
    def _task_finished(self) -> None:
        if self._task is None:
            return
        task = self._task.task
        dataset = self._task.dataset
        thread = self._task.thread
        if dataset is not self.state.dataset:
            self.feedback.display("Dataset aktif berubah. Hasil proses sebelumnya diabaikan.")
        elif thread.error is not None:
            self.feedback.display(f"{task.description} gagal. {thread.error}", "error")
            self.task_failed.emit(task.page_key, thread.error)
        else:
            self.state.save_result(dataset, task.page_key, thread.result)
            self.feedback.display(f"{task.description} selesai.", "success")
        self._task = None
        thread.deleteLater()
        self._operation_finished()

    @Slot(str)
    def _import_started(self, path: str) -> None:
        self._pending_import = path
        self.feedback.display(f"Mengimpor {Path(path).name}…", "busy")
        self._sync_controls()

    @Slot(str)
    def _import_status(self, message: str) -> None:
        if self._pending_import is not None and not self._close_requested:
            self.feedback.display(message, "busy")

    @Slot(object, object, object)
    def _dataset_loaded(self, log: Any, metadata: dict[str, Any], overview: dict[str, Any]) -> None:
        if not self._close_requested:
            self.state.activate(ActiveDataset(log, metadata, overview))
        self._finish_import(f"{metadata['file_name']} siap digunakan.", "success")

    @Slot(object)
    def _active_dataset_changed(self, dataset: ActiveDataset) -> None:
        self._last_tasks.clear()
        self.dataset_bar.set_dataset(dataset)
        self._sync_controls()

    @Slot(object, object, object)
    def _validation_failed(
        self, _log: Any, _metadata: dict[str, Any], validation: dict[str, Any]
    ) -> None:
        errors = validation.get("errors") or ["Atribut atau nilai wajib tidak valid."]
        self._load_failed(" ".join(errors))

    @Slot(str)
    def _load_failed(self, message: str) -> None:
        filename = Path(self._pending_import).name if self._pending_import else "XES"
        dataset = self.state.dataset
        context = "Belum ada dataset aktif."
        if dataset is not None:
            context = f"Dataset aktif tetap {dataset.metadata['file_name']}."
        LOGGER.warning("Impor %s gagal: %s", filename, message)
        self._finish_import(f"Impor {filename} gagal. {context} {message}", "error")

    def _finish_import(self, message: str, tone: str) -> None:
        # The panel reports its outcome before cleaning up its child QThread.
        # Keep the import button disabled until the panel can accept a new import.
        self.import_page.select_button.setEnabled(False)
        thread = self.import_page.findChild(QThread)
        if thread is None:
            self._report_import_finished(message, tone)
        else:
            thread.destroyed.connect(lambda: self._report_import_finished(message, tone))

    def _report_import_finished(self, message: str, tone: str) -> None:
        self._pending_import = None
        self.feedback.display(message, tone)
        self._operation_finished()

    def _sync_controls(self) -> None:
        ready = not self.busy and not self._close_requested
        self.import_page.select_button.setEnabled(ready)
        for key, controls in self._task_controls.items():
            controls.set_availability(
                run=ready and self.state.dataset is not None,
                reset=ready and self.state.has_result(key),
                rerun=ready and key in self._last_tasks,
            )
        self.operations_available.emit(ready)

    def _operation_finished(self) -> None:
        self._sync_controls()
        if self._close_requested and not self.busy:
            QTimer.singleShot(0, self.close)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 - Qt API name
        if self.busy:
            self._close_requested = True
            self.feedback.display("Menunggu proses selesai sebelum menutup aplikasi…", "busy")
            self._sync_controls()
            event.ignore()
            return
        self.import_page.close()
        super().closeEvent(event)
