"""Tests for Exercise 11.15/11.18 repeated-completion filtering and GUI wiring."""

import os
import time
import unittest
from datetime import datetime, timedelta, timezone

import pandas as pd
from pm4py.objects.log.obj import Event, EventLog, Trace

from modules.exercise_115_118 import analyze_115_118


TARGET = "W_Assess Potential Fraud"
START = datetime(2017, 1, 1, tzinfo=timezone.utc)


def _event(
    activity: str,
    index: int,
    lifecycle: str | None = "complete",
    resource: str | None = "User_1",
) -> Event:
    return Event(
        {
            "concept:name": activity,
            "time:timestamp": START + timedelta(minutes=index),
            "lifecycle:transition": lifecycle,
            "org:resource": resource,
        }
    )


def _trace(case_id: str, events: list[Event]) -> Trace:
    return Trace(events, attributes={"concept:name": case_id})


def _fixture_log() -> EventLog:
    return EventLog(
        [
            _trace(
                "SameResource",
                [
                    _event("A_Create Application", 0),
                    _event(TARGET, 1, "complete", "User_A"),
                    _event(TARGET, 2, "start", "User_A"),
                    _event(TARGET, 3, "complete", "User_A"),
                    _event(TARGET, 4, "complete", "User_A"),
                ],
            ),
            _trace(
                "DifferentResources",
                [
                    _event(TARGET, 5, "complete", "User_A"),
                    _event(TARGET, 6, "complete", "User_B"),
                ],
            ),
            _trace(
                "OnlyOneComplete",
                [
                    _event(TARGET, 7, "complete", "User_A"),
                    _event(TARGET, 8, "start", "User_A"),
                    _event(TARGET, 9, "schedule", "User_A"),
                ],
            ),
            _trace(
                "MissingResources",
                [
                    _event(TARGET, 10, "complete", None),
                    _event(TARGET, 11, "complete", None),
                ],
            ),
            _trace(
                "BlankResources",
                [
                    _event(TARGET, 12, "complete", ""),
                    _event(TARGET, 13, "complete", "   "),
                ],
            ),
            _trace(
                "TwoQualifyingResources",
                [
                    _event(TARGET, 14, "complete", "User_C"),
                    _event(TARGET, 15, "complete", "User_C"),
                    _event(TARGET, 16, "complete", "User_D"),
                    _event(TARGET, 17, "complete", "User_D"),
                ],
            ),
            _trace(
                "OtherActivity",
                [
                    _event("W_Call incomplete files", 18),
                    _event("W_Call incomplete files", 19),
                ],
            ),
            _trace(
                "RepeatedNonComplete",
                [
                    _event(TARGET, 20, "start", "User_E"),
                    _event(TARGET, 21, "schedule", "User_E"),
                ],
            ),
        ]
    )


def _to_dataframe(log: EventLog) -> pd.DataFrame:
    rows = []
    for trace in log:
        case_id = trace.attributes["concept:name"]
        for event in trace:
            rows.append(
                {
                    "case:concept:name": case_id,
                    "concept:name": event["concept:name"],
                    "time:timestamp": event["time:timestamp"],
                    "lifecycle:transition": event.get("lifecycle:transition"),
                    "org:resource": event.get("org:resource"),
                }
            )
    return pd.DataFrame(rows)


class Exercise115118Tests(unittest.TestCase):
    def test_complete_only_filter_and_case_level_counts(self):
        result = analyze_115_118(_fixture_log())

        self.assertEqual(result["total_cases"], 8)
        self.assertEqual(result["11.15"]["count"], 5)
        self.assertEqual(
            result["11.15"]["case_ids"],
            [
                "SameResource",
                "DifferentResources",
                "MissingResources",
                "BlankResources",
                "TwoQualifyingResources",
            ],
        )
        self.assertEqual(result["11.18"]["count"], 2)
        self.assertEqual(
            result["11.18"]["case_ids"],
            ["SameResource", "TwoQualifyingResources"],
        )

        same_resource = result["11.15"]["evidence"][0]
        self.assertEqual(same_resource["occurrence_count"], 3)
        self.assertEqual(same_resource["evidence_positions"], [1, 3, 4])
        self.assertTrue(
            all(event["lifecycle"] == "complete" for event in same_resource["evidence_events"])
        )

    def test_1118_reports_resource_groups_but_counts_each_case_once(self):
        result = analyze_115_118(_fixture_log())["11.18"]

        self.assertEqual(result["count"], 2)
        self.assertEqual(result["evidence_group_count"], 3)
        groups = [
            (row["case_id"], row["resource_id"], row["occurrence_count"])
            for row in result["evidence"]
        ]
        self.assertEqual(
            groups,
            [
                ("SameResource", "User_A", 3),
                ("TwoQualifyingResources", "User_C", 2),
                ("TwoQualifyingResources", "User_D", 2),
            ],
        )
        self.assertNotIn("MissingResources", result["case_ids"])
        self.assertNotIn("BlankResources", result["case_ids"])

    def test_event_log_and_dataframe_results_match(self):
        log = _fixture_log()
        log_result = analyze_115_118(log)
        dataframe_result = analyze_115_118(_to_dataframe(log))

        for key in ("total_cases", "11.15", "11.18"):
            self.assertEqual(log_result[key], dataframe_result[key])

    def test_lifecycle_or_resource_attribute_missing_is_handled_explicitly(self):
        rows = [
            {
                "case:concept:name": "NoLifecycle",
                "concept:name": TARGET,
                "time:timestamp": START,
                "org:resource": "User_1",
            },
            {
                "case:concept:name": "NoLifecycle",
                "concept:name": TARGET,
                "time:timestamp": START + timedelta(minutes=1),
                "org:resource": "User_1",
            },
        ]
        no_lifecycle = analyze_115_118(pd.DataFrame(rows))
        self.assertFalse(no_lifecycle["lifecycle_attribute_available"])
        self.assertEqual(no_lifecycle["11.15"]["count"], 0)
        self.assertEqual(no_lifecycle["11.18"]["count"], 0)

        df = _to_dataframe(_fixture_log()).drop(columns=["org:resource"])
        no_resource = analyze_115_118(df)
        self.assertTrue(no_resource["lifecycle_attribute_available"])
        self.assertFalse(no_resource["resource_attribute_available"])
        self.assertEqual(no_resource["11.15"]["count"], 5)
        self.assertEqual(no_resource["11.18"]["count"], 0)

    def test_dataframe_case_positions_keep_original_row_order(self):
        dataframe = pd.DataFrame(
            [
                {"case:concept:name": "A", "concept:name": TARGET, "time:timestamp": START,
                 "lifecycle:transition": "start", "org:resource": "User_1"},
                {"case:concept:name": "B", "concept:name": "Other", "time:timestamp": START,
                 "lifecycle:transition": "complete", "org:resource": "User_2"},
                {"case:concept:name": "A", "concept:name": TARGET, "time:timestamp": START,
                 "lifecycle:transition": "complete", "org:resource": "User_1"},
                {"case:concept:name": "A", "concept:name": TARGET, "time:timestamp": START,
                 "lifecycle:transition": "complete", "org:resource": "User_1"},
            ]
        )

        result = analyze_115_118(dataframe)
        self.assertEqual(result["11.15"]["evidence"][0]["evidence_positions"], [1, 2])
        self.assertEqual(result["11.18"]["evidence"][0]["evidence_positions"], [1, 2])

    def test_empty_inputs_validation_and_custom_activity(self):
        empty_log = analyze_115_118(EventLog([]))
        self.assertEqual(empty_log["total_cases"], 0)
        self.assertEqual(empty_log["11.15"]["count"], 0)
        self.assertEqual(empty_log["11.18"]["count"], 0)

        empty_df = pd.DataFrame(
            columns=["case:concept:name", "concept:name", "time:timestamp"]
        )
        self.assertEqual(analyze_115_118(empty_df)["total_cases"], 0)
        self.assertEqual(analyze_115_118(pd.DataFrame())["total_cases"], 0)

        with self.assertRaises(ValueError):
            analyze_115_118(None)
        with self.assertRaises(TypeError):
            analyze_115_118("not a log")
        with self.assertRaises(ValueError):
            analyze_115_118(pd.DataFrame({"wrong": [1]}))

        custom = analyze_115_118(
            _fixture_log(), activity="A_Create Application"
        )
        self.assertEqual(custom["activity"], "A_Create Application")
        self.assertEqual(custom["11.15"]["count"], 0)


class Exercise115118GuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])
        cls.app.setQuitOnLastWindowClosed(False)

    def _wait_until(self, predicate, timeout_ms: int = 7000) -> bool:
        elapsed = 0
        while elapsed < timeout_ms:
            self.app.processEvents()
            if predicate():
                return True
            time.sleep(0.01)
            elapsed += 10
        self.app.processEvents()
        return bool(predicate())

    def test_mainwindow_runs_both_exercises_and_opens_evidence(self):
        from main import setup_feature_pages
        from gui.app_state import ActiveDataset
        from gui.main_window import MainWindow

        window = MainWindow()
        setup_feature_pages(window)
        page = window._page_widgets["exercise_115_118"]
        case_explorer = window._page_widgets["case_explorer"]
        self.addCleanup(window.close)

        log = _fixture_log()
        dataset = ActiveDataset(
            log=log,
            metadata={"file_name": "synthetic.xes", "case_count": len(log), "event_count": sum(map(len, log))},
            overview={},
        )
        window.state.activate(dataset)
        self.assertTrue(self._wait_until(lambda: not case_explorer.is_indexing()))

        window.navigate("exercise_115_118")
        page.task_controls.run_button.click()
        self.assertTrue(
            self._wait_until(
                lambda: not window.busy and window.state.has_result("exercise_115_118")
            )
        )

        self.assertEqual(page.current_state, "loaded")
        self.assertEqual(page._count_labels["11.15"].text(), "5")
        self.assertEqual(page._count_labels["11.18"].text(), "2")
        self.assertEqual(page._table_widgets["11.15"].rowCount(), 5)
        self.assertEqual(page._table_widgets["11.18"].rowCount(), 3)

        # Open a same-resource evidence group and verify trace highlights.
        page._table_widgets["11.18"].cellDoubleClicked.emit(0, 0)
        self.assertEqual(window.stack.currentWidget(), case_explorer)
        self.assertEqual(case_explorer.current_case_id, "SameResource")
        self.assertEqual(case_explorer.event_table.item(1, 5).text(),
                         "Evidence (11.18 W_Assess Potential Fraud complete / User_A)")
        self.assertEqual(case_explorer.event_table.item(3, 5).text(),
                         "Evidence (11.18 W_Assess Potential Fraud complete / User_A)")

        window.navigate("exercise_115_118")
        page._table_widgets["11.15"].cellDoubleClicked.emit(0, 0)
        self.assertEqual(window.stack.currentWidget(), case_explorer)
        self.assertEqual(case_explorer.current_case_id, "SameResource")
        self.assertEqual(case_explorer.event_table.item(4, 5).text(),
                         "Evidence (11.15 W_Assess Potential Fraud complete)")

        window.navigate("exercise_115_118")
        page.task_controls.rerun_button.click()
        self.assertEqual(page.current_state, "loading")
        self.assertTrue(
            self._wait_until(
                lambda: not window.busy and window.state.has_result("exercise_115_118")
            )
        )
        self.assertEqual(page.current_state, "loaded")

        page.task_controls.reset_button.click()
        self.app.processEvents()
        self.assertFalse(window.state.has_result("exercise_115_118"))
        self.assertEqual(page._table_widgets["11.15"].rowCount(), 0)
        self.assertTrue(page.task_controls.rerun_button.isEnabled())


if __name__ == "__main__":
    unittest.main()
