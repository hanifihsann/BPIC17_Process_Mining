import os
import unittest
from datetime import datetime, timezone

import pandas as pd
from pm4py.objects.log.obj import Event, EventLog, Trace

from modules.case_explorer import (
    build_case_index,
    clear_case_index_cache,
    get_case_detail,
    get_case_trace,
    list_cases,
    search_cases,
)
from modules.exercise_1122 import analyze_1122


def _make_sample_log() -> EventLog:
    t0 = datetime(2026, 3, 1, 9, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 3, 1, 9, 15, tzinfo=timezone.utc)
    t2 = datetime(2026, 3, 1, 9, 30, tzinfo=timezone.utc)
    t3 = datetime(2026, 3, 1, 9, 45, tzinfo=timezone.utc)

    return EventLog(
        [
            Trace(
                [
                    Event(
                        {
                            "concept:name": "A_Create Application",
                            "time:timestamp": t0,
                            "lifecycle:transition": "complete",
                            "org:resource": "User_1",
                        }
                    ),
                    Event(
                        {
                            "concept:name": "O_Cancelled",
                            "time:timestamp": t1,
                            "lifecycle:transition": "complete",
                            "org:resource": "User_2",
                        }
                    ),
                    Event(
                        {
                            "concept:name": "W_Complete application",
                            "time:timestamp": t2,
                        }
                    ),
                    Event(
                        {
                            "concept:name": "O_Accepted",
                            "time:timestamp": t3,
                            "lifecycle:transition": "complete",
                            "org:resource": "User_3",
                        }
                    ),
                ],
                attributes={"concept:name": "App_1001"},
            ),
            Trace(
                [
                    Event(
                        {
                            "concept:name": "A_Submitted",
                            "time:timestamp": t0,
                        }
                    )
                ],
                attributes={"concept:name": "App_1002"},
            ),
        ]
    )


def _to_dataframe(log: EventLog) -> pd.DataFrame:
    rows = []
    for trace in log:
        cid = trace.attributes["concept:name"]
        for ev in trace:
            rows.append(
                {
                    "case:concept:name": cid,
                    "concept:name": ev.get("concept:name"),
                    "time:timestamp": ev.get("time:timestamp"),
                    "lifecycle:transition": ev.get("lifecycle:transition"),
                    "org:resource": ev.get("org:resource"),
                }
            )
    return pd.DataFrame(rows)


class CaseExplorerTests(unittest.TestCase):
    def setUp(self) -> None:
        clear_case_index_cache()

    def test_valid_and_not_found_case_search_and_lookup(self):
        log = _make_sample_log()

        valid_trace = get_case_trace(log, "App_1001")
        self.assertEqual(len(valid_trace), 4)

        missing_trace = get_case_trace(log, "App_9999")
        self.assertEqual(missing_trace, [])

        detail_missing = get_case_detail(log, "App_9999")
        self.assertFalse(detail_missing["found"])
        self.assertEqual(detail_missing["events"], [])

        matches = search_cases(log, "1002")
        self.assertEqual([m["case_id"] for m in matches], ["App_1002"])

        all_cases = list_cases(log)
        self.assertEqual([c["case_id"] for c in all_cases], ["App_1001", "App_1002"])

    def test_trace_detail_contains_all_events_and_honest_optional_attributes(self):
        log = _make_sample_log()
        result_1122 = analyze_1122(log)
        evidence_record = result_1122["evidence"][0]

        trace = get_case_trace(log, "App_1001", evidence=evidence_record)
        self.assertEqual(len(trace), 4)
        self.assertEqual([e["seq"] for e in trace], [1, 2, 3, 4])
        self.assertEqual(
            [e["activity"] for e in trace],
            [
                "A_Create Application",
                "O_Cancelled",
                "W_Complete application",
                "O_Accepted",
            ],
        )

        # Optional attributes present on event 0, missing on event 2 -> must stay None
        self.assertEqual(trace[0]["lifecycle"], "complete")
        self.assertEqual(trace[0]["resource"], "User_1")
        self.assertIsNone(trace[2]["lifecycle"])
        self.assertIsNone(trace[2]["resource"])

        # Evidence highlighting marks only positions 1 and 3, while keeping all 4 events
        self.assertEqual([e["is_evidence"] for e in trace], [False, True, False, True])
        self.assertEqual(trace[1]["evidence_role"], "O_Cancelled")
        self.assertEqual(trace[3]["evidence_role"], "O_Accepted")

    def test_generic_evidence_markers_usable_for_other_exercises(self):
        log = _make_sample_log()
        trace = get_case_trace(log, "App_1001", highlight_positions=[0, 2])
        self.assertEqual([e["is_evidence"] for e in trace], [True, False, True, False])

        trace_dict = get_case_trace(
            log,
            "App_1001",
            evidence={0: "11.7_Start", 3: "11.7_End"},
        )
        self.assertEqual(trace_dict[0]["evidence_role"], "11.7_Start")
        self.assertEqual(trace_dict[3]["evidence_role"], "11.7_End")

    def test_event_log_and_dataframe_return_equivalent_traces(self):
        log = _make_sample_log()
        df = _to_dataframe(log)
        evidence_log = analyze_1122(log)["evidence"][0]
        evidence_df = analyze_1122(df)["evidence"][0]

        trace_log = get_case_trace(log, "App_1001", evidence=evidence_log)
        trace_df = get_case_trace(df, "App_1001", evidence=evidence_df)

        self.assertEqual(trace_log, trace_df)

    def test_case_index_reused_without_full_rescan_and_handles_mutation(self):
        log = _make_sample_log()
        idx1 = build_case_index(log)
        self.assertEqual(len(idx1.case_ids), 2)

        t0 = datetime(2026, 3, 1, 11, 0, tzinfo=timezone.utc)
        log.append(
            Trace(
                [Event({"concept:name": "A_Create Application", "time:timestamp": t0})],
                attributes={"concept:name": "App_1003"},
            )
        )
        # Cached lookup detects length change and updates automatically
        trace_new = get_case_trace(log, "App_1003")
        self.assertEqual(len(trace_new), 1)
        self.assertEqual(trace_new[0]["activity"], "A_Create Application")

    def test_missing_required_attributes_raises_value_error(self):
        bad_log = EventLog(
            [Trace([Event({"concept:name": "A"})], attributes={"concept:name": "C1"})]
        )
        with self.assertRaises(ValueError):
            get_case_trace(bad_log, "C1")

        bad_df = pd.DataFrame({"case:concept:name": ["C1"], "concept:name": ["A"]})
        with self.assertRaises(ValueError):
            get_case_trace(bad_df, "C1")


class GuiWidgetsOffscreenSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def _wait_until(self, predicate, timeout_ms: int = 5000) -> bool:
        import time

        elapsed = 0
        step = 10
        while elapsed < timeout_ms:
            self.app.processEvents()
            if predicate():
                return True
            time.sleep(step / 1000.0)
            elapsed += step
        self.app.processEvents()
        return bool(predicate())

    def test_exercise_1122_and_case_explorer_integration_flow(self):
        from PySide6.QtTest import QSignalSpy
        from gui.pages.case_explorer_page import CaseExplorerPage
        from gui.pages.exercise_1122_page import Exercise1122Page

        log = _make_sample_log()
        ex_page = Exercise1122Page()
        ce_page = CaseExplorerPage()
        self.addCleanup(ex_page.close)
        self.addCleanup(ce_page.close)
        ex_page.open_case_requested.connect(ce_page.open_case)

        self.assertEqual(ex_page.current_state, "no_dataset")
        self.assertEqual(ce_page.current_state, "no_dataset")

        ex_page.set_dataset(log, {"file_name": "synthetic.xes", "case_count": 2})
        ce_page.set_dataset(log, {"file_name": "synthetic.xes", "case_count": 2})

        self.assertTrue(self._wait_until(lambda: not ce_page.is_indexing()))
        self.assertEqual(ex_page.current_state, "ready")
        self.assertEqual(ce_page.current_state, "ready")

        spy_done = QSignalSpy(ex_page.analysis_completed)
        ex_page.run_analysis()
        self.assertTrue(
            self._wait_until(lambda: not ex_page.is_running() and spy_done.count() > 0)
        )

        self.assertEqual(ex_page.current_state, "loaded")
        self.assertEqual(ex_page.count_label.text(), "1")
        self.assertEqual(ex_page.denominator_label.text(), "2")
        self.assertEqual(ex_page.percentage_label.text(), "50.00%")
        self.assertEqual(ex_page.result_table.rowCount(), 1)

        # Double-click row 0 -> opens App_1001 in Case Explorer with evidence highlights
        ex_page.result_table.selectRow(0)
        ex_page._on_row_double_clicked(0, 0)
        self.app.processEvents()

        self.assertEqual(ce_page.current_case_id, "App_1001")
        self.assertEqual(ce_page.current_state, "loaded")
        self.assertEqual(ce_page.event_table.rowCount(), 4)
        self.assertEqual(ce_page.event_table.item(2, 3).text(), "-")
        self.assertIn("O_Cancelled", ce_page.event_table.item(1, 5).text())
        self.assertIn("O_Accepted", ce_page.event_table.item(3, 5).text())

        # Reset and re-run without reloading XES
        ex_page.reset_results()
        self.assertEqual(ex_page.current_state, "ready")
        self.assertEqual(ex_page.result_table.rowCount(), 0)

        ex_page.run_analysis()
        self.assertTrue(
            self._wait_until(
                lambda: not ex_page.is_running() and ex_page.current_state == "loaded"
            )
        )
        self.assertEqual(ex_page.result_table.rowCount(), 1)

        ce_page.reset_view()
        self.assertEqual(ce_page.current_state, "ready")
        self.assertEqual(ce_page.event_table.rowCount(), 0)

        # Search not found -> empty state
        ce_page.search_input.setText("NO_SUCH_CASE")
        ce_page.apply_search()
        self.assertEqual(ce_page.current_state, "empty")

        # Dataset switching without reloading XES from disk
        ce_page.reset_view()
        new_log = EventLog(
            [
                Trace(
                    [
                        Event(
                            {
                                "concept:name": "O_Accepted",
                                "time:timestamp": datetime(2026, 4, 1, 10, 0, tzinfo=timezone.utc),
                            }
                        )
                    ],
                    attributes={"concept:name": "NewCase_1"},
                )
            ]
        )
        ex_page.set_dataset(new_log, {"file_name": "new.xes", "case_count": 1})
        ce_page.set_dataset(new_log, {"file_name": "new.xes", "case_count": 1})
        self.assertTrue(self._wait_until(lambda: not ce_page.is_indexing()))
        self.assertEqual(ex_page.current_state, "ready")
        self.assertEqual(ce_page.case_table.rowCount(), 1)

        ex_page.run_analysis()
        self.assertTrue(
            self._wait_until(
                lambda: not ex_page.is_running() and ex_page.current_state == "empty"
            )
        )
        self.assertEqual(ex_page.current_state, "empty")
        self.assertEqual(ex_page.count_label.text(), "0")
        self.assertEqual(ex_page.denominator_label.text(), "1")
        self.assertEqual(ex_page.percentage_label.text(), "0.00%")

        # Error handling for invalid dataset
        bad_df = pd.DataFrame({"wrong_col": [1]})
        ex_page.set_dataset(bad_df)
        ex_page.run_analysis()
        self.assertTrue(
            self._wait_until(
                lambda: not ex_page.is_running() and ex_page.current_state == "error"
            )
        )
        self.assertEqual(ex_page.current_state, "error")


class MainWindowAnggota4IntegrationTests(unittest.TestCase):
    """End-to-end tests of Anggota 4 pages mounted into Anggota 5's MainWindow."""

    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])
        cls.app.setQuitOnLastWindowClosed(False)

    def _wait_until(self, predicate, timeout_ms: int = 10000) -> bool:
        import time

        elapsed = 0
        step = 10
        while elapsed < timeout_ms:
            self.app.processEvents()
            if predicate():
                return True
            time.sleep(step / 1000.0)
            elapsed += step
        self.app.processEvents()
        return bool(predicate())

    def test_mainwindow_navigation_1122_case_explorer_search_reset_rerun(self):
        import tempfile
        from pathlib import Path
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        from gui.main_window import MainWindow
        from gui.pages import install_anggota4_pages

        window = MainWindow()
        ex_page, ce_page = install_anggota4_pages(window)
        self.addCleanup(lambda: (ex_page.close(), ce_page.close(), window.close()))

        self.assertEqual(ex_page.current_state, "no_dataset")
        self.assertEqual(ce_page.current_state, "no_dataset")
        self.assertFalse(ex_page.task_controls.run_button.isEnabled())

        # Create a real temporary XES file and load it via Anggota 1's ImportOverviewPage
        with tempfile.TemporaryDirectory() as tmpdir:
            xes_path = Path(tmpdir) / "bpic17_synthetic.xes"
            xes_path.write_text(
                '<log xes.version="1.0" xmlns="http://www.xes-standard.org/">'
                '<trace><string key="concept:name" value="App_Pass"/>'
                '<event><string key="concept:name" value="A_Create Application"/>'
                '<date key="time:timestamp" value="2026-01-01T09:00:00.000+00:00"/>'
                '<string key="lifecycle:transition" value="complete"/>'
                '<string key="org:resource" value="User_1"/></event>'
                '<event><string key="concept:name" value="O_Cancelled"/>'
                '<date key="time:timestamp" value="2026-01-01T09:10:00.000+00:00"/>'
                '<string key="lifecycle:transition" value="complete"/>'
                '<string key="org:resource" value="User_2"/></event>'
                '<event><string key="concept:name" value="W_Validate"/>'
                '<date key="time:timestamp" value="2026-01-01T09:20:00.000+00:00"/></event>'
                '<event><string key="concept:name" value="O_Accepted"/>'
                '<date key="time:timestamp" value="2026-01-01T09:30:00.000+00:00"/>'
                '<string key="lifecycle:transition" value="complete"/></event>'
                '</trace>'
                '<trace><string key="concept:name" value="App_Fail_Order"/>'
                '<event><string key="concept:name" value="O_Accepted"/>'
                '<date key="time:timestamp" value="2026-01-01T10:00:00.000+00:00"/></event>'
                '<event><string key="concept:name" value="O_Cancelled"/>'
                '<date key="time:timestamp" value="2026-01-01T10:05:00.000+00:00"/></event>'
                '</trace>'
                '<trace><string key="concept:name" value="App_Other"/>'
                '<event><string key="concept:name" value="A_Submitted"/>'
                '<date key="time:timestamp" value="2026-01-01T11:00:00.000+00:00"/></event>'
                '</trace>'
                '</log>',
                encoding="utf-8",
            )
            window.import_page.load_file(str(xes_path))
            self.assertTrue(
                self._wait_until(
                    lambda: window.state.dataset is not None and not window.busy and not ce_page.is_indexing()
                )
            )

        self.assertIs(window.state.dataset.log, window.import_page.active_log)
        self.assertEqual(ex_page.current_state, "ready")
        self.assertEqual(ce_page.current_state, "ready")
        self.assertTrue(ex_page.task_controls.run_button.isEnabled())

        # Navigate to Exercise 11.22 and run via Anggota 5's TaskControls + TaskThread
        window.navigate("exercise_1122")
        self.assertIs(window.stack.currentWidget(), ex_page)
        QTest.mouseClick(ex_page.task_controls.run_button, Qt.MouseButton.LeftButton)
        self.assertTrue(
            self._wait_until(lambda: not window.busy and window.state.has_result("exercise_1122"))
        )

        self.assertEqual(ex_page.current_state, "loaded")
        self.assertEqual(ex_page.count_label.text(), "1")
        self.assertEqual(ex_page.denominator_label.text(), "3")
        self.assertEqual(ex_page.percentage_label.text(), "33.33%")
        self.assertEqual(ex_page.result_table.rowCount(), 1)
        self.assertEqual(ex_page.result_table.item(0, 0).text(), "App_Pass")

        # Double-click result row -> navigates to Case Explorer and highlights evidence
        ex_page.result_table.selectRow(0)
        ex_page._on_row_double_clicked(0, 0)
        self.app.processEvents()

        self.assertIs(window.stack.currentWidget(), ce_page)
        self.assertEqual(window.page_title.text(), "Case Explorer")
        self.assertEqual(ce_page.current_case_id, "App_Pass")
        self.assertEqual(ce_page.event_table.rowCount(), 4)
        self.assertIn("O_Cancelled", ce_page.event_table.item(1, 5).text())
        self.assertIn("O_Accepted", ce_page.event_table.item(3, 5).text())
        self.assertEqual(ce_page.event_table.item(2, 3).text(), "-")
        self.assertEqual(ce_page.event_table.item(2, 4).text(), "-")

        # Search Case ID in Case Explorer + Reset
        ce_page.search_input.setText("App_Fail_Order")
        ce_page.apply_search()
        self.assertEqual(ce_page.current_case_id, "App_Fail_Order")
        self.assertEqual(ce_page.event_table.rowCount(), 2)

        ce_page.search_input.setText("TIDAK_ADA")
        ce_page.apply_search()
        self.assertEqual(ce_page.current_state, "empty")

        ce_page.reset_view()
        self.assertEqual(ce_page.current_state, "ready")
        self.assertEqual(ce_page.case_table.rowCount(), 3)

        # Navigate back to Exercise 11.22 -> Reset & Re-run via MainWindow TaskControls
        window.navigate("exercise_1122")
        QTest.mouseClick(ex_page.task_controls.reset_button, Qt.MouseButton.LeftButton)
        self.app.processEvents()
        self.assertFalse(window.state.has_result("exercise_1122"))
        self.assertEqual(ex_page.result_table.rowCount(), 0)
        self.assertTrue(ex_page.task_controls.rerun_button.isEnabled())

        QTest.mouseClick(ex_page.task_controls.rerun_button, Qt.MouseButton.LeftButton)
        self.assertTrue(
            self._wait_until(lambda: not window.busy and window.state.has_result("exercise_1122"))
        )
        self.assertEqual(ex_page.count_label.text(), "1")
        self.assertEqual(ex_page.denominator_label.text(), "3")
        self.assertEqual(ex_page.result_table.rowCount(), 1)

        # Error handling inside MainWindow TaskThread updates page state to error
        from gui.app_state import ActiveDataset

        bad_df = pd.DataFrame({"wrong_col": [1]})
        window.state.activate(ActiveDataset(bad_df, {"file_name": "bad.xes", "case_count": 1, "event_count": 1}, {}))
        with self.assertLogs("gui.workers", level="ERROR"):
            QTest.mouseClick(ex_page.task_controls.run_button, Qt.MouseButton.LeftButton)
            self.assertTrue(
                self._wait_until(lambda: not window.busy and ex_page.current_state == "error")
            )
        self.assertEqual(ex_page.current_state, "error")
        self.assertIn("Analisis gagal", ex_page.status_label.text())


if __name__ == "__main__":
    unittest.main()
