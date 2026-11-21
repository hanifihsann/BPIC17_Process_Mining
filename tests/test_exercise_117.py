"""Comprehensive unit tests for Exercise 11.7 (A–E), CSV Export, and GUI integration.

Tests cover:
- Empty datasets (EventLog and DataFrame) without ZeroDivisionError
- 11.7 A total case counting
- 11.7 B mean cycle time calculation in days
- 11.7 C contains O_Accepted (multiple occurrences counted once)
- 11.7 D contains O_Refused (multiple occurrences counted once)
- Overlap between 11.7 C and 11.7 D (not mutually exclusive)
- 11.7 E endpoint condition (O_Cancelled only at trace end vs in middle)
- Equivalence between PM4Py EventLog and DataFrame
- Validation and error handling
- CSV export functions
- Offscreen GUI smoke and integration tests with Case Explorer
"""

import os
import tempfile
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
from pm4py.objects.log.obj import Event, EventLog, Trace

from modules.exercise_117 import analyze_117
from modules.export_csv import export_cases_to_csv, export_summary_to_csv


def make_event(activity: str, ts: datetime, lifecycle: str | None = None, resource: str | None = None) -> Event:
    data = {
        "concept:name": activity,
        "time:timestamp": ts,
    }
    if lifecycle is not None:
        data["lifecycle:transition"] = lifecycle
    if resource is not None:
        data["org:resource"] = resource
    return Event(data)


def build_synthetic_fixture_log() -> EventLog:
    """Create a multi-case synthetic EventLog covering all edge cases.

    Case_1: A -> O_Accepted (duration: 2 days) -> Successful
    Case_2: A -> O_Accepted -> B -> O_Accepted (duration: 4 days) -> Successful (multiple accepted, counted once)
    Case_3: A -> O_Refused (duration: 1 day) -> Unsuccessful
    Case_4: A -> O_Accepted -> O_Refused (duration: 3 days) -> Both Successful & Unsuccessful (Overlap)
    Case_5: A -> O_Cancelled -> B (duration: 5 days) -> O_Cancelled in middle, NOT 11.7 E
    Case_6: A -> B -> O_Cancelled (duration: 6 days) -> O_Cancelled is last event, PASSES 11.7 E
    Case_7: A -> B (duration: 2 days) -> Neither accepted, refused, nor cancelled
    """
    t0 = datetime(2026, 1, 1, 10, 0, 0, tzinfo=timezone.utc)

    c1 = Trace(
        [
            make_event("A", t0),
            make_event("O_Accepted", t0 + timedelta(days=2)),
        ],
        attributes={"concept:name": "Case_1"},
    )

    c2 = Trace(
        [
            make_event("A", t0),
            make_event("O_Accepted", t0 + timedelta(days=1)),
            make_event("B", t0 + timedelta(days=2)),
            make_event("O_Accepted", t0 + timedelta(days=4)),
        ],
        attributes={"concept:name": "Case_2"},
    )

    c3 = Trace(
        [
            make_event("A", t0),
            make_event("O_Refused", t0 + timedelta(days=1)),
        ],
        attributes={"concept:name": "Case_3"},
    )

    c4 = Trace(
        [
            make_event("A", t0),
            make_event("O_Accepted", t0 + timedelta(days=1)),
            make_event("O_Refused", t0 + timedelta(days=3)),
        ],
        attributes={"concept:name": "Case_4"},
    )

    c5 = Trace(
        [
            make_event("A", t0),
            make_event("O_Cancelled", t0 + timedelta(days=2)),
            make_event("B", t0 + timedelta(days=5)),
        ],
        attributes={"concept:name": "Case_5"},
    )

    c6 = Trace(
        [
            make_event("A", t0),
            make_event("B", t0 + timedelta(days=3)),
            make_event("O_Cancelled", t0 + timedelta(days=6)),
        ],
        attributes={"concept:name": "Case_6"},
    )

    c7 = Trace(
        [
            make_event("A", t0),
            make_event("B", t0 + timedelta(days=2)),
        ],
        attributes={"concept:name": "Case_7"},
    )

    return EventLog([c1, c2, c3, c4, c5, c6, c7])


def log_to_dataframe(log: EventLog) -> pd.DataFrame:
    rows = []
    for trace in log:
        case_id = trace.attributes["concept:name"]
        for event in trace:
            rows.append({
                "case:concept:name": case_id,
                "concept:name": event["concept:name"],
                "time:timestamp": event["time:timestamp"],
                "lifecycle:transition": event.get("lifecycle:transition"),
                "org:resource": event.get("org:resource"),
            })
    return pd.DataFrame(rows)


class Exercise117Tests(unittest.TestCase):
    def test_empty_event_log(self):
        empty_log = EventLog([])
        res = analyze_117(empty_log)
        self.assertEqual(res["total_cases"], 0)
        self.assertEqual(res["11.7_a"]["count"], 0)
        self.assertEqual(res["11.7_b"]["mean_cycle_time_days"], 0.0)
        self.assertEqual(res["11.7_c"]["count"], 0)
        self.assertEqual(res["11.7_d"]["count"], 0)
        self.assertEqual(res["11.7_e"]["count"], 0)

    def test_empty_dataframe(self):
        empty_df = pd.DataFrame(columns=["case:concept:name", "concept:name", "time:timestamp"])
        res = analyze_117(empty_df)
        self.assertEqual(res["total_cases"], 0)
        self.assertEqual(res["11.7_a"]["count"], 0)
        self.assertEqual(res["11.7_b"]["mean_cycle_time_days"], 0.0)

    def test_117_a_total_cases(self):
        log = build_synthetic_fixture_log()
        res = analyze_117(log)
        self.assertEqual(res["total_cases"], 7)
        self.assertEqual(res["11.7_a"]["count"], 7)

    def test_117_b_cycle_time_calculation(self):
        log = build_synthetic_fixture_log()
        res = analyze_117(log)
        # Durations: c1: 2, c2: 4, c3: 1, c4: 3, c5: 5, c6: 6, c7: 2 -> sum = 23, count = 7
        expected_mean = 23.0 / 7.0
        self.assertAlmostEqual(res["11.7_b"]["mean_cycle_time_days"], expected_mean, places=4)
        self.assertEqual(res["11.7_b"]["valid_duration_cases"], 7)

    def test_117_c_successful_cases_and_duplicate_accepted(self):
        log = build_synthetic_fixture_log()
        res = analyze_117(log)
        sub_c = res["11.7_c"]
        # Cases with O_Accepted: Case_1, Case_2 (has 2 O_Accepted), Case_4
        self.assertEqual(sub_c["count"], 3)
        self.assertEqual(set(sub_c["case_ids"]), {"Case_1", "Case_2", "Case_4"})
        self.assertEqual(len(sub_c["evidence"]), 3)
        # Check evidence for Case_2 records 2 positions
        c2_ev = next(e for e in sub_c["evidence"] if e["case_id"] == "Case_2")
        self.assertEqual(c2_ev["occurrence_count"], 2)
        self.assertEqual(c2_ev["evidence_positions"], [1, 3])
        # Mean cycle time of c1 (2d), c2 (4d), c4 (3d) -> sum = 9, mean = 3.0 days
        self.assertAlmostEqual(sub_c["mean_cycle_time_days"], 3.0, places=4)

    def test_117_d_unsuccessful_cases(self):
        log = build_synthetic_fixture_log()
        res = analyze_117(log)
        sub_d = res["11.7_d"]
        # Cases with O_Refused: Case_3 (1d), Case_4 (3d)
        self.assertEqual(sub_d["count"], 2)
        self.assertEqual(set(sub_d["case_ids"]), {"Case_3", "Case_4"})
        # Mean cycle time of c3 (1d) and c4 (3d) -> (1 + 3) / 2 = 2.0 days
        self.assertAlmostEqual(sub_d["mean_cycle_time_days"], 2.0, places=4)

    def test_overlap_c_and_d_not_mutually_exclusive(self):
        """Case_4 contains both O_Accepted and O_Refused and must qualify for BOTH 11.7 C and 11.7 D."""
        log = build_synthetic_fixture_log()
        res = analyze_117(log)
        self.assertIn("Case_4", res["11.7_c"]["case_ids"])
        self.assertIn("Case_4", res["11.7_d"]["case_ids"])

    def test_117_e_endpoint_rule(self):
        """11.7 E requires O_Cancelled to be the last event in trace."""
        log = build_synthetic_fixture_log()
        res = analyze_117(log)
        sub_e = res["11.7_e"]
        # Case_5 has O_Cancelled at index 1 followed by B at index 2 -> MUST NOT PASS
        self.assertNotIn("Case_5", sub_e["case_ids"])
        # Case_6 has O_Cancelled as last event (index 2) -> MUST PASS
        self.assertIn("Case_6", sub_e["case_ids"])
        self.assertEqual(sub_e["count"], 1)
        # Cycle time of Case_6 is 6.0 days
        self.assertAlmostEqual(sub_e["mean_cycle_time_days"], 6.0, places=4)

    def test_eventlog_and_dataframe_equivalence(self):
        log = build_synthetic_fixture_log()
        df = log_to_dataframe(log)

        res_log = analyze_117(log)
        res_df = analyze_117(df)

        self.assertEqual(res_log["total_cases"], res_df["total_cases"])
        self.assertEqual(res_log["11.7_a"]["count"], res_df["11.7_a"]["count"])
        self.assertAlmostEqual(
            res_log["11.7_b"]["mean_cycle_time_days"],
            res_df["11.7_b"]["mean_cycle_time_days"],
            places=4,
        )
        self.assertEqual(res_log["11.7_c"]["count"], res_df["11.7_c"]["count"])
        self.assertEqual(res_log["11.7_c"]["case_ids"], res_df["11.7_c"]["case_ids"])
        self.assertEqual(res_log["11.7_d"]["count"], res_df["11.7_d"]["count"])
        self.assertEqual(res_log["11.7_e"]["count"], res_df["11.7_e"]["count"])
        self.assertEqual(res_log["11.7_e"]["case_ids"], res_df["11.7_e"]["case_ids"])

    def test_validation_errors(self):
        with self.assertRaises(ValueError):
            analyze_117(None)

        with self.assertRaises(TypeError):
            analyze_117("invalid_string_input")

        bad_df = pd.DataFrame({"some_col": [1, 2]})
        with self.assertRaises(ValueError):
            analyze_117(bad_df)


class CsvExportTests(unittest.TestCase):
    def test_export_summary_and_cases_csv(self):
        log = build_synthetic_fixture_log()
        res = analyze_117(log)

        with tempfile.TemporaryDirectory() as tmp_dir:
            summary_path = Path(tmp_dir) / "summary_117.csv"
            cases_path = Path(tmp_dir) / "cases_117.csv"

            out_summary = export_summary_to_csv(res, summary_path)
            self.assertTrue(out_summary.exists())
            summary_content = out_summary.read_text(encoding="utf-8-sig")
            self.assertIn("11.7 A", summary_content)
            self.assertIn("11.7 B", summary_content)
            self.assertIn("11.7 C", summary_content)
            self.assertIn("11.7 D", summary_content)
            self.assertIn("11.7 E", summary_content)

            all_evidence = res["11.7_c"]["evidence"] + res["11.7_d"]["evidence"] + res["11.7_e"]["evidence"]
            out_cases = export_cases_to_csv(all_evidence, cases_path)
            self.assertTrue(out_cases.exists())
            cases_content = out_cases.read_text(encoding="utf-8-sig")
            self.assertIn("Case_1", cases_content)
            self.assertIn("Case_2", cases_content)
            self.assertIn("Case_3", cases_content)
            self.assertIn("Case_4", cases_content)
            self.assertIn("Case_6", cases_content)


class Exercise117GuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def _wait_until(self, predicate, timeout_ms: int = 5000) -> bool:
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

    def test_exercise_117_page_and_case_explorer_flow(self):
        from PySide6.QtTest import QSignalSpy
        from gui.pages.case_explorer_page import CaseExplorerPage
        from gui.pages.exercise_117_page import Exercise117Page

        log = build_synthetic_fixture_log()
        ex_page = Exercise117Page()
        ce_page = CaseExplorerPage()
        self.addCleanup(ex_page.close)
        self.addCleanup(ce_page.close)

        ex_page.open_case_requested.connect(ce_page.open_case)

        self.assertEqual(ex_page.current_state, "no_dataset")
        ex_page.set_dataset(log, {"file_name": "synthetic.xes", "case_count": 7})
        ce_page.set_dataset(log, {"file_name": "synthetic.xes", "case_count": 7})

        self.assertTrue(self._wait_until(lambda: not ce_page.is_indexing()))
        self.assertEqual(ex_page.current_state, "ready")

        spy_done = QSignalSpy(ex_page.analysis_completed)
        ex_page.run_analysis()
        self.assertTrue(
            self._wait_until(lambda: not ex_page.is_running() and spy_done.count() > 0)
        )

        self.assertEqual(ex_page.current_state, "loaded")
        self.assertEqual(ex_page.summary_table.rowCount(), 5)
        # Total cases in 11.7 A cell
        self.assertEqual(ex_page.summary_table.item(0, 3).text(), "7")
        # Successful cases in 11.7 C cell
        self.assertEqual(ex_page.summary_table.item(2, 3).text(), "3")
        # Unsuccessful cases in 11.7 D cell
        self.assertEqual(ex_page.summary_table.item(3, 3).text(), "2")
        # Canceled cases in 11.7 E cell
        self.assertEqual(ex_page.summary_table.item(4, 3).text(), "1")

        # Result table should have 3 + 2 + 1 = 6 evidence rows across all subsoals
        self.assertEqual(ex_page.result_table.rowCount(), 6)

        # Filter by 11.7 C category
        ex_page.category_combo.setCurrentIndex(1)
        self.assertEqual(ex_page.result_table.rowCount(), 3)

        # Select row 0 (Case_1 or Case_2) and trigger open case to Case Explorer
        ex_page.result_table.selectRow(0)
        ex_page._open_selected_row()
        self.app.processEvents()

        self.assertIsNotNone(ce_page.current_case_id)
        self.assertEqual(ce_page.current_state, "loaded")

        # Test reset
        ex_page.reset_results()
        self.assertEqual(ex_page.current_state, "ready")
        self.assertEqual(ex_page.result_table.rowCount(), 0)

    def test_export_page_integration(self):
        from gui.app_state import ActiveDataset, AppState
        from gui.pages.export_page import ExportPage

        state = AppState()
        export_page = ExportPage(state)
        self.addCleanup(export_page.close)

        self.assertFalse(export_page.btn_export_summary.isEnabled())
        self.assertFalse(export_page.btn_export_cases.isEnabled())

        log = build_synthetic_fixture_log()
        dummy_dataset = ActiveDataset(log=log, metadata={"file_name": "test.xes"}, overview={})
        state.activate(dummy_dataset)

        res_117 = analyze_117(log)
        state.save_result(dummy_dataset, "exercise_117", res_117)
        self.app.processEvents()

        self.assertTrue(export_page.btn_export_summary.isEnabled())
        self.assertTrue(export_page.btn_export_cases.isEnabled())
        self.assertIn("siap diekspor", export_page.status_label.text())


if __name__ == "__main__":
    unittest.main()
