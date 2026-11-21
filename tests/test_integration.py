"""Desktop integration tests with tiny XES fixtures and an isolated test panel."""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from threading import Event
from unittest.mock import patch

from PySide6.QtCore import QEventLoop, QThread, QTimer, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFileDialog, QLabel, QVBoxLayout, QWidget

from gui.app_state import ActiveDataset
from gui.import_overview_page import load_xes
from gui.main_window import FEATURES, PAGES, MainWindow
from gui.widgets import DataTable, ResultArea, TaskControls


PAGE = "exercise_117"
ROOT = Path(__file__).resolve().parents[1]


class ShellTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setQuitOnLastWindowClosed(False)

    def setUp(self):
        self.window = MainWindow()
        self.window.show()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.release = Event()

    def tearDown(self):
        self.release.set()
        self.wait_for(lambda: not self.window.busy)
        self.window.close()
        self.window.deleteLater()
        QTest.qWait(1)

    def wait_for(self, predicate):
        if predicate():
            return
        loop = QEventLoop()
        poll = QTimer(loop)

        def check():
            if predicate():
                loop.quit()

        poll.timeout.connect(check)
        poll.start(10)
        QTimer.singleShot(10000, loop, loop.quit)
        loop.exec()
        poll.stop()
        self.assertTrue(predicate(), "Qt did not reach the expected state")

    def xes_file(self, name="synthetic", case_id="Test_1", *, timestamp=True):
        path = Path(self.temp_dir.name) / f"{name}.xes"
        date = '<date key="time:timestamp" value="2026-01-01T00:00:00.000+00:00"/>' if timestamp else ""
        path.write_text(
            '<log xes.version="1.0" xmlns="http://www.xes-standard.org/">'
            f'<trace><string key="concept:name" value="{case_id}"/>'
            '<event><string key="concept:name" value="Test event"/>'
            f'{date}</event></trace></log>',
            encoding="utf-8",
        )
        return path

    def import_dataset(self, path):
        with patch.object(QFileDialog, "getOpenFileName", return_value=(str(path), "XES")):
            self.window.import_page.select_button.click()
        self.wait_for(lambda: not self.window.busy)

    def install_test_panel(self, operation):
        page = QWidget()
        layout = QVBoxLayout(page)
        controls = TaskControls()
        table = DataTable(["Fixture result"])
        result = ResultArea(table)
        layout.addWidget(controls)
        layout.addWidget(result)
        self.window.install_page(PAGE, page, controls)
        controls.run_requested.connect(lambda: self.window.run_task(PAGE, "Uji worker", operation))

        def render_result(key):
            if key != PAGE:
                return
            if self.window.state.has_result(key):
                table.set_rows([(self.window.state.result(key),)])
                result.show_result()
            else:
                table.set_rows(())
                result.show_message("Belum ada hasil.")

        self.window.state.result_changed.connect(render_result)
        self.window.navigate(PAGE)
        return controls, table

    def test_navigation_placeholder_and_about(self):
        self.assertTrue(self.window.isVisible())
        for row, (key, title) in enumerate(PAGES.items()):
            with self.subTest(key=key):
                self.window.navigation.setCurrentRow(row)
                self.assertEqual(self.window.page_title.text(), title)
                page = self.window.stack.currentWidget()
                if key in FEATURES:
                    labels = [label.text() for label in page.findChildren(QLabel)]
                    self.assertIn("Menunggu integrasi", labels)
                if key in ("import", "overview"):
                    self.assertIs(self.window.import_scroll.widget(), self.window.import_page)
        self.window.navigate("import")
        self.window.menuBar().actions()[0].menu().actions()[0].trigger()
        self.assertEqual(self.window.page_title.text(), "About")
        labels = [label.text() for label in self.window.stack.currentWidget().findChildren(QLabel)]
        self.assertTrue({"Python", "PySide6", "PM4Py", "pandas"}.issubset(labels))

    def test_task_controls_without_dataset(self):
        controls, _ = self.install_test_panel(lambda _: self.fail("Task should not run"))
        self.assertFalse(controls.run_button.isEnabled())
        self.assertFalse(self.window.run_task(PAGE, "Uji", lambda _: None))
        self.assertIn("Impor dataset XES", self.window.feedback.message_label.toolTip())

    def test_import_publishes_same_log_and_overview(self):
        path = self.xes_file()
        self.import_dataset(path)
        dataset = self.window.state.dataset
        self.assertIs(dataset.log, self.window.import_page.active_log)
        self.assertIs(dataset.overview, self.window.import_page.active_overview)
        self.assertIsNone(self.window.import_page.findChild(QThread))
        self.assertTrue(self.window.import_page.select_button.isEnabled())
        self.assertEqual(self.window.dataset_bar.name_label.toolTip(), path.name)
        self.assertEqual(self.window.dataset_bar.counts_label.text(), "1 case  /  1 event")
        self.window.navigate("overview")
        self.assertEqual(self.window.import_page.case_table.item(0, 0).text(), "Test_1")

    def test_failed_replacement_keeps_previous_dataset_and_result(self):
        original = self.xes_file("original")
        self.import_dataset(original)
        dataset = self.window.state.dataset
        self.window.state.save_result(dataset, PAGE, "hasil lama")
        invalid = self.xes_file("invalid", timestamp=False)
        broken = Path(self.temp_dir.name) / "broken.xes"
        broken.write_text("<log>", encoding="utf-8")
        for path in (invalid, broken):
            with self.subTest(path=path.name), self.assertLogs("gui.main_window", level="WARNING"):
                self.import_dataset(path)
                self.assertIs(self.window.state.dataset, dataset)
                self.assertEqual(self.window.state.result(PAGE), "hasil lama")
                message = self.window.feedback.message_label.toolTip()
                self.assertIn(f"Impor {path.name} gagal", message)
                self.assertIn(f"Dataset aktif tetap {original.name}", message)

    def test_worker_progress_duplicate_click_reset_and_rerun(self):
        started = Event()
        seen = []

        def operation(dataset):
            seen.append((dataset.log, QThread.currentThread() == self.app.thread()))
            started.set()
            if not self.release.wait(8):
                raise TimeoutError("Test worker was not released")
            return "hasil fixture"

        controls, table = self.install_test_panel(operation)
        self.import_dataset(self.xes_file())
        QTest.mouseClick(controls.run_button, Qt.MouseButton.LeftButton)
        self.wait_for(started.is_set)
        self.assertTrue(self.window.busy)
        self.assertTrue(self.window.feedback.progress.isVisible())
        self.assertEqual(self.window.feedback.progress.maximum(), 0)
        self.assertFalse(self.window.import_page.select_button.isEnabled())
        controls.run_button.click()
        self.assertFalse(self.window.run_task(PAGE, "Duplikat", operation))
        navigation_ran = Event()

        def navigate():
            self.window.navigate("about")
            navigation_ran.set()

        QTimer.singleShot(0, navigate)
        self.wait_for(navigation_ran.is_set)
        self.assertEqual(self.window.page_title.text(), "About")
        self.assertTrue(self.window.busy)
        self.release.set()
        self.wait_for(lambda: not self.window.busy)
        self.window.navigate(PAGE)
        self.assertFalse(self.window.feedback.progress.isVisible())
        self.assertEqual(table.model().index(0, 0).data(), "hasil fixture")
        QTest.mouseClick(controls.reset_button, Qt.MouseButton.LeftButton)
        self.assertFalse(self.window.state.has_result(PAGE))
        self.assertEqual(table.model().rowCount(), 0)
        self.assertTrue(controls.rerun_button.isEnabled())
        QTest.mouseClick(controls.rerun_button, Qt.MouseButton.LeftButton)
        self.wait_for(lambda: not self.window.busy)
        self.assertEqual(self.window.state.result(PAGE), "hasil fixture")
        self.assertEqual(len(seen), 2)
        for log, on_gui_thread in seen:
            self.assertIs(log, self.window.state.dataset.log)
            self.assertFalse(on_gui_thread)

    def test_replacement_clears_result_and_rerun(self):
        controls, _ = self.install_test_panel(lambda dataset: dataset.metadata["file_name"])
        self.import_dataset(self.xes_file("first"))
        controls.run_button.click()
        self.wait_for(lambda: not self.window.busy)
        self.assertEqual(self.window.state.result(PAGE), "first.xes")
        self.import_dataset(self.xes_file("second", "Test_2"))
        self.assertEqual(self.window.state.dataset.metadata["file_name"], "second.xes")
        self.assertFalse(self.window.state.has_result(PAGE))
        self.assertTrue(controls.run_button.isEnabled())
        self.assertFalse(controls.rerun_button.isEnabled())

    def test_worker_failure_is_visible_and_allows_retry(self):
        def broken_operation(_):
            raise RuntimeError("Fixture error")

        self.import_dataset(self.xes_file())
        with self.assertLogs("gui.workers", level="ERROR") as logs:
            self.assertTrue(self.window.run_task("export", "Ekspor uji", broken_operation))
            self.wait_for(lambda: not self.window.busy)
        self.assertIn("Fixture error", logs.output[0])
        self.assertIn("Ekspor uji gagal. Fixture error", self.window.feedback.message_label.toolTip())
        self.assertFalse(self.window.state.has_result("export"))
        self.assertTrue(self.window.run_task("export", "Ekspor uji", lambda _: "fixture.csv"))
        self.wait_for(lambda: not self.window.busy)
        self.assertEqual(self.window.state.result("export"), "fixture.csv")

    def test_worker_output_is_discarded_after_dataset_changes(self):
        self.import_dataset(self.xes_file())
        dataset = self.window.state.dataset

        def delayed_result(_):
            self.release.wait(8)
            return "hasil usang"

        self.assertTrue(self.window.run_task(PAGE, "Uji hasil lama", delayed_result))
        replacement = ActiveDataset(dataset.log, dict(dataset.metadata), dataset.overview)
        self.window.state.activate(replacement)
        self.release.set()
        self.wait_for(lambda: not self.window.busy)
        self.assertFalse(self.window.state.has_result(PAGE))
        self.assertIn("diabaikan", self.window.feedback.message_label.toolTip())

    def test_close_waits_for_import_without_blocking_gui(self):
        path = self.xes_file()

        def delayed_load(file_path):
            self.release.wait(8)
            return load_xes(file_path)

        with patch("gui.import_overview_page.load_xes", side_effect=delayed_load):
            self.window.import_page.load_file(str(path))
            self.assertFalse(self.window.close())
            self.assertTrue(self.window.isVisible())
            QTimer.singleShot(0, self.release.set)
            self.wait_for(lambda: not self.window.isVisible())

    def test_close_waits_for_feature_worker(self):
        self.import_dataset(self.xes_file())
        self.assertTrue(self.window.run_task(PAGE, "Uji penutupan", lambda _: self.release.wait(8)))
        self.assertFalse(self.window.close())
        self.assertTrue(self.window.isVisible())
        QTimer.singleShot(0, self.release.set)
        self.wait_for(lambda: not self.window.isVisible())

    def test_main_entry_point(self):
        script = """
import runpy
from unittest.mock import patch
from PySide6.QtCore import QTimer
from gui.main_window import MainWindow

def opened(window):
    if not window.isVisible():
        raise SystemExit(3)
    print('WINDOW_SHOWN', flush=True)
    window.close()

def create_window():
    window = MainWindow()
    QTimer.singleShot(0, lambda: opened(window))
    return window

with patch('gui.main_window.MainWindow', side_effect=create_window):
    runpy.run_path('main.py', run_name='__main__')
"""
        result = subprocess.run(
            [sys.executable, "-c", script], cwd=ROOT, capture_output=True, text=True, timeout=20
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("WINDOW_SHOWN", result.stdout)


if __name__ == "__main__":
    unittest.main()
